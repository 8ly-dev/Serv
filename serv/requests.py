import json
from typing import Type, get_origin, get_args, List, Union, Any
from urllib.parse import parse_qs


class Request:
    def __init__(self, scope, receive):
        if scope["type"] != "http":
            raise RuntimeError("Request only supports HTTP scope")

        self.scope = scope
        self._receive = receive
        self._body_consumed = False
        self._buffer = bytearray()

    @property
    def method(self) -> str:
        return self.scope.get("method", "")

    @property
    def scheme(self) -> str:
        return self.scope.get("scheme", "")

    @property
    def path(self) -> str:
        return self.scope.get("path", "")

    @property
    def query_string(self) -> str:
        return self.scope.get("query_string", b"").decode("utf-8")

    @property
    def query_params(self) -> dict:
        return {k: v if len(v) > 1 else v[0] for k, v in parse_qs(self.query_string).items()}

    @property
    def headers(self) -> dict:
        return {
            name.decode("latin-1").lower(): value.decode("latin-1")
            for name, value in self.scope.get("headers", [])
        }

    @property
    def cookies(self) -> dict:
        cookie_header = self.headers.get("cookie")
        if not cookie_header:
            return {}
        cookies = {}
        for cookie_pair in cookie_header.split(";"):
            cookie_pair = cookie_pair.strip()
            if "=" in cookie_pair:
                name, value = cookie_pair.split("=", 1)
                cookies[name.strip()] = value.strip()
            elif cookie_pair: # handles cookies with no value
                cookies[cookie_pair.strip()] = ""
        return cookies

    @property
    def client(self):
        return self.scope.get("client")

    @property
    def server(self):
        return self.scope.get("server")

    @property
    def http_version(self) -> str:
        return self.scope.get("http_version", "")

    async def body(self, max_size: int = 10*1024*1024) -> bytes:
        """
        Returns the request body as bytes up to max_size (default 10MB).
        Aggregates chunks from the read() stream.
        """
        body_bytes = bytearray()
        async for chunk in self.read(max_size=max_size):
            body_bytes.extend(chunk)
        return bytes(body_bytes)

    async def read(self, max_size: int = -1):
        """
        Async generator yielding chunks of the request body as bytes.

        Stops when no more chunks are available. If max_size is set, it only yields that many bytes 
        across all yielded chunks.

        This method raises a RuntimeError if the body has been fully consumed.
        """
        if self._body_consumed and not self._buffer:
            raise RuntimeError("Request body already consumed")

        total_read = 0
        while not self._body_consumed or self._buffer:
            if not self._body_consumed and (not self._buffer or total_read + len(self._buffer) < max_size if max_size > 0 else True):
                message = await self._receive()
                if message["type"] != "http.request":
                    break

                self._buffer.extend(message.get("body", b""))
                self._body_consumed = not message.get("more_body", False)

            if max_size <= 0 or total_read + len(self._buffer) <= max_size :
                yield self._buffer
                total_read += len(self._buffer)
                self._buffer.clear()
            else: # max_size > 0 and total_read + len(self._buffer) > max_size
                can_yield = max_size - total_read
                yield self._buffer[:can_yield]
                self._buffer = self._buffer[can_yield:]
                total_read = max_size # or total_read += can_yield
                break


    async def text(self, encoding: str = "utf-8", max_size: int = -1) -> str:
        data = await self.body(max_size=max_size)
        return data.decode(encoding)

    async def json(self, max_size: int = -1, encoding: str = "utf-8"):
        text_data = await self.text(encoding=encoding, max_size=max_size)
        return json.loads(text_data) if text_data else None

    def _coerce_value(self, value_str: str, target_type: type) -> Any:
        origin_type = get_origin(target_type)
        type_args = get_args(target_type)

        if origin_type is Union: # Handles Optional[T] as Union[T, NoneType]
            # If empty string and None is an option, return None directly.
            if value_str == "" and type(None) in type_args:
                return None

            # Attempt coercion for each type in the Union, return on first success
            # Prioritize non-NoneType if NoneType is present
            non_none_types = [t for t in type_args if t is not type(None)]
            # other_types = [t for t in type_args if t is type(None)] # Should just be [NoneType] if present

            for t in non_none_types:
                try:
                    return self._coerce_value(value_str, t)
                except (ValueError, TypeError):
                    continue
            # If all non-NoneType coercions fail, and NoneType is an option
            # (and value_str was not empty, handled above), this is an error.
            if type(None) in type_args: # value_str is not empty here
                 pass # Let it fall through to the final raise if it was not coercible to non-None types

            raise ValueError(f"Cannot coerce {value_str!r} to any type in Union {target_type}")

        if target_type is Any: # If type is Any, return the string value directly
            return value_str

        if target_type is str:
            return value_str

        
        if target_type is bool:
            val_lower = value_str.lower()
            if val_lower in ("true", "on", "1", "yes"):
                return True
            if val_lower in ("false", "off", "0", "no"):
                return False
            raise ValueError(f"Cannot coerce {value_str!r} to bool.")
        
        try:
            return target_type(value_str)
        except Exception as e:
            raise ValueError(f"Unsupported coercion for type {target_type} from value {value_str!r}: {e}")

    async def form(
        self, 
        model: type = dict,
        max_size: int = 10*1024*1024, 
        encoding: str = "utf-8", 
        *, 
        data: dict[str, Any] | None = None
    ) -> Any:
        content_type_header = self.headers.get("content-type", "")
        if not content_type_header.startswith("application/x-www-form-urlencoded"):
            raise RuntimeError(
                f"Cannot parse form data for Content-Type '{content_type_header}'. "
                f"Expected 'application/x-www-form-urlencoded'."
            )

        if data:
            raw_form_values = data
        
        else:
            form_data_bytes = await self.body(max_size=max_size)
            if not form_data_bytes:
                if model is dict:
                    return {}
                # Try to return an empty model instance. If it requires arguments,
                # this will raise a TypeError, which should propagate.
                return model()
                # except TypeError: # model might require arguments
                #      return {} # Fallback for models that can't be empty-instantiated easily and no data

            form_data_str = form_data_bytes.decode(encoding)
            # parse_qs returns dict[str, list[str]]
            raw_form_values = parse_qs(form_data_str, keep_blank_values=True)

        print(f"\n\n\n\n{raw_form_values}\n\n\n\n")

        if model is dict:
            return raw_form_values

        coerced_data = {}
        annotations = getattr(model, '__annotations__', {})

        for field_name, field_type in annotations.items():
            values_from_form = raw_form_values.get(field_name)

            if values_from_form is None: # Field not present in form
                continue

            origin_type = get_origin(field_type)
            type_args = get_args(field_type)
            # Robust check for list types
            is_list_expected = (
                field_type is list or 
                field_type is List or 
                origin_type is list or 
                origin_type is List
            )

            if is_list_expected:
                if not type_args: # e.g. list or List without inner type
                    # Treat as list of strings by default if no inner type specified
                    coerced_data[field_name] = [str(item) for item in values_from_form]
                else:
                    target_inner_type = type_args[0]
                    coerced_items = []
                    for item_str in values_from_form:
                        try:
                            coerced_items.append(self._coerce_value(item_str, target_inner_type))
                        except ValueError as e:
                            # Handle coercion errors for list items, e.g., log or raise
                            # For now, let's be strict and raise, or one could collect errors.
                            raise ValueError(f"Error coercing item '{item_str}' for field '{field_name}': {e}")
                    coerced_data[field_name] = coerced_items
            else: # Single value expected
                # Rule 1: Use the first value if multiple submitted for a non-list field
                value_to_coerce_str = values_from_form[0]
                try:
                    coerced_data[field_name] = self._coerce_value(value_to_coerce_str, field_type)
                except ValueError as e:
                     # Handle coercion errors for single items
                    raise ValueError(f"Error coercing value '{value_to_coerce_str}' for field '{field_name}': {e}")
        
        try:
            return model(**coerced_data)
        except Exception as e:
            # This could happen if model validation fails (e.g. missing required fields not in form)
            # or if there's a mismatch not caught by type hints alone.
            raise TypeError(f"Failed to instantiate model {model.__name__} with coerced data. Error: {e}. Data: {coerced_data}")

    def __repr__(self):
        return (
            f"<Request {self.method} {self.scheme}://"
            f"{self.headers.get('host', '')}{self.path}>"
        )
