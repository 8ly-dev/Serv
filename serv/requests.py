import json
from typing import get_origin, get_args, List, Union, Any, Dict
from urllib.parse import parse_qs
import io
from dataclasses import dataclass
from collections import defaultdict

from multipart.multipart import parse_options_header
from python_multipart import FormParser


@dataclass
class FileUpload:
    filename: str | None
    content_type: str | None
    file: io.IOBase


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

    async def _parse_form_data(self, max_size: int = 10*1024*1024, encoding: str = "utf-8") -> dict[str, Any]:
        form_data_bytes = await self.body(max_size=max_size)
        form_data_str = form_data_bytes.decode(encoding)
        return parse_qs(form_data_str, keep_blank_values=True)

    async def _parse_multipart_body(self, encoding: str, boundary: bytes) -> dict:
        print(f"DEBUG _parse_multipart_body: encoding='{encoding}', boundary='{boundary}'") # Debug
        content_type_header = self.headers.get("content-type", "")
        print(f"DEBUG _parse_multipart_body: content_type_header='{content_type_header}'") # Debug
        _, params = parse_options_header(content_type_header.encode('latin-1'))
        form_charset = params.get(b"charset", encoding.encode()).decode()
        print(f"DEBUG _parse_multipart_body: effective form_charset='{form_charset}'") # Debug

        collected_fields: Dict[str, List[str]] = defaultdict(list)
        collected_files: Dict[str, List[FileUpload]] = defaultdict(list)

        async def body_stream_producer() -> io.BytesIO:
            # Let's use self.read() to robustly consume the body
            # as it handles the _buffer and _body_consumed state correctly.
            final_full_body = bytearray()
            
            # If self.read() has already been partially used, it will resume.
            # If body is already fully consumed by a prior different mechanism, 
            # self.read() will raise RuntimeError, which is fine as it means an API misuse.
            # For a fresh request to .form(), self.read() will consume the body from _receive.
            async for chunk in self.read(): # Use the existing self.read() method
                final_full_body.extend(chunk)
            
            # After self.read() completes, self._body_consumed is True, 
            # and self._buffer should be empty (or contain only residue if max_size was hit, not relevant here).
            # We are storing the full body back into self._buffer so that subsequent calls to 
            # request.body() or request.text() can still access it, even though FormParser consumes it from BytesIO.
            # This behavior makes request.form() idempotent in terms of body availability for other methods.
            self._buffer = final_full_body 
            # self.read() already sets self._body_consumed = True upon full consumption.
            return io.BytesIO(final_full_body)

        body_stream_for_parser = await body_stream_producer()
        # Let's see the raw body before parsing
        raw_body_bytes_to_parse = body_stream_for_parser.getvalue() # Getvalue before read consumes it
        print(f"DEBUG _parse_multipart_body: raw_body_bytes_to_parse (first 500 bytes): {raw_body_bytes_to_parse[:500]}")
        body_stream_for_parser.seek(0) # Reset stream position for parser.write

        def on_field_sync(field):
            # field is python_multipart.multipart.Field (from BaseStreamingParser)
            # It has .field_name (bytes) and .value (bytes)
            field_name_str = field.field_name.decode(form_charset)
            field_value_str = field.value.decode(form_charset)
            print(f"DEBUG _parse_multipart_body: on_field_sync: name='{field_name_str}', value='{field_value_str}'")
            collected_fields[field_name_str].append(field_value_str)

        def on_file_sync(file_part):
            print(f"DEBUG on_file_sync: type(file_part) = {type(file_part)}")
            # print(f"DEBUG on_file_sync: dir(file_part) = {dir(file_part)}") # Already seen this

            field_name_str = file_part.field_name.decode(form_charset)
            
            actual_filename = None
            if hasattr(file_part, 'file_name') and file_part.file_name:
                actual_filename = file_part.file_name.decode(form_charset)
            elif hasattr(file_part, '_file_name') and file_part._file_name:
                actual_filename = file_part._file_name.decode(form_charset)

            print(f"DEBUG _parse_multipart_body: on_file_sync: name='{field_name_str}', filename='{actual_filename}'")

            actual_content_type_str = None # Cannot reliably get this

            current_file_stream = None
            raw_file_object = None

            if hasattr(file_part, 'file_object'):
                raw_file_object = file_part.file_object
            elif hasattr(file_part, '_fileobj'):
                raw_file_object = file_part._fileobj
            
            if raw_file_object:
                try:
                    print(f"DEBUG on_file_sync: raw_file_object type = {type(raw_file_object)}")
                    if hasattr(file_part, 'size'):
                        print(f"DEBUG on_file_sync: file_part.size = {file_part.size}")
                    
                    raw_file_object.seek(0)
                    file_content_sample = raw_file_object.read() # Read all
                    print(f"DEBUG on_file_sync: file_object yielded {len(file_content_sample)} bytes. Sample: {file_content_sample[:60]}")
                    raw_file_object.seek(0) # Reset for actual use by FileUpload
                    current_file_stream = raw_file_object
                except Exception as e:
                    print(f"ERROR: Could not seek/read file_object in on_file_sync: {e}")
                    current_file_stream = io.BytesIO(b"Error reading stream in on_file_sync")
            else:
                print(f"ERROR: file_part does not have file_object or _fileobj.")

            upload = FileUpload(
                filename=actual_filename,
                content_type=actual_content_type_str, 
                file=current_file_stream
            )
            collected_files[field_name_str].append(upload)
        
        # Get the main content_type (e.g. "multipart/form-data") without parameters
        # parse_options_header already gave us `_ct` but it's bytes.
        main_content_type = content_type_header.split(';')[0].strip()

        parser = FormParser(
            content_type=main_content_type, 
            on_field=on_field_sync,
            on_file=on_file_sync,
            boundary=boundary
        )

        parser.write(body_stream_for_parser.read()) 
        parser.finalize()
        
        raw_form_values: dict[str, Any] = {}
        for key, val_list in collected_fields.items():
            raw_form_values[key] = val_list
        for key, file_list in collected_files.items():
            raw_form_values[key] = file_list
            
        return raw_form_values

    async def form(
        self, 
        model: type = dict,
        max_size: int = 10*1024*1024,  # max_size for urlencoded, multipart handled by stream
        encoding: str = "utf-8", 
        *, 
        data: dict[str, Any] | None = None
    ) -> Any:
        content_type_header = self.headers.get("content-type", "")
        raw_form_values: dict[str, Any] | None = None # Initialize

        if data:
            raw_form_values = data
        elif content_type_header.startswith("application/x-www-form-urlencoded"):
            raw_form_values = await self._parse_form_data(max_size=max_size, encoding=encoding)
        elif content_type_header.startswith("multipart/form-data"):
            _content_type_val_bytes, params = parse_options_header(content_type_header.encode('latin-1'))
            boundary = params.get(b'boundary')
            if not boundary:
                raise ValueError("Multipart form missing boundary.")
            raw_form_values = await self._parse_multipart_body(encoding=encoding, boundary=boundary)
        else:
            raise RuntimeError(
                f"Cannot parse form data for Content-Type '{content_type_header}'. "
                f"Expected 'application/x-www-form-urlencoded' or 'multipart/form-data'."
            )

        if model is dict:
            return raw_form_values if raw_form_values is not None else {}
        
        if not raw_form_values: 
            try:
                return model() 
            except TypeError as e:
                raise TypeError(f"Failed to instantiate model {model.__name__} from empty form. Error: {e}")

        return self._build_model(model, raw_form_values)
    
    def _build_model(self, model: type, raw_form_values: dict[str, Any]) -> Any:
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
