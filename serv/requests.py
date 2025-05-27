import io
import json
from dataclasses import dataclass
from types import UnionType
from typing import Any, Union, get_args, get_origin
from urllib.parse import parse_qs

from python_multipart.multipart import parse_options_header

from serv.multipart_parser import MultipartParser


@dataclass
class FileUpload:
    filename: str | None
    content_type: str | None
    headers: dict[str, str]
    file: io.IOBase

    async def read(self) -> bytes:
        return self.file.read()

    async def seek(self, offset: int) -> int:
        return self.file.seek(offset)

    async def close(self) -> None:
        return self.file.close()


class Request:
    """HTTP request object providing access to request data and parsing utilities.

    The Request class encapsulates all information about an incoming HTTP request,
    including headers, body, query parameters, cookies, and provides methods for
    parsing different content types like JSON, form data, and file uploads.

    This class is automatically injected into route handlers through the dependency
    injection system, so you typically don't need to instantiate it directly.

    Examples:
        Basic request handling:

        ```python
        from serv.routes import Route, GetRequest, PostRequest
        from serv.responses import JsonResponse
        from typing import Annotated

        class ApiRoute(Route):
            async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
                # Access query parameters
                user_id = request.query_params.get("user_id")
                page = int(request.query_params.get("page", "1"))

                # Access headers
                auth_token = request.headers.get("authorization")

                return {"user_id": user_id, "page": page}

            async def handle_post(self, request: PostRequest) -> Annotated[dict, JsonResponse]:
                # Parse JSON body
                data = await request.json()

                # Access cookies
                session_id = request.cookies.get("session_id")

                return {"received": data, "session": session_id}
        ```

        Form data handling:

        ```python
        from serv.routes import Form

        class UserForm(Form):
            name: str
            email: str
            age: int

        class UserRoute(Route):
            async def handle_post(self, request: PostRequest):
                # Parse form data into a model
                form_data = await request.form(UserForm)

                # Access typed form fields
                print(f"Name: {form_data.name}, Age: {form_data.age}")

                return {"status": "success"}
        ```

        File upload handling:

        ```python
        class UploadRoute(Route):
            async def handle_post(self, request: PostRequest):
                # Parse multipart form data
                form_data = await request.form()

                # Access uploaded files
                if "avatar" in form_data:
                    file_upload = form_data["avatar"]
                    filename = file_upload.filename
                    content = await file_upload.read()

                    # Save file or process content
                    with open(f"uploads/{filename}", "wb") as f:
                        f.write(content)

                return {"status": "uploaded"}
        ```

        Raw body access:

        ```python
        class WebhookRoute(Route):
            async def handle_post(self, request: PostRequest):
                # Get raw body bytes
                raw_body = await request.body()

                # Or stream large bodies
                chunks = []
                async for chunk in request.read(max_size=1024*1024):  # 1MB chunks
                    chunks.append(chunk)

                return {"received_bytes": len(raw_body)}
        ```

    Attributes:
        method: HTTP method (GET, POST, etc.)
        path: Request path without query string
        query_string: Raw query string
        query_params: Parsed query parameters as dict
        headers: Request headers as dict (lowercase keys)
        cookies: Parsed cookies as dict
        scheme: URL scheme (http, https)
        client: Client address information
        server: Server address information
        http_version: HTTP version string
    """

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
        return {
            k: v if len(v) > 1 else v[0] for k, v in parse_qs(self.query_string).items()
        }

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
            elif cookie_pair:  # handles cookies with no value
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

    async def body(self, max_size: int = 10 * 1024 * 1024) -> bytes:
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
            if not self._body_consumed and (
                not self._buffer or total_read + len(self._buffer) < max_size
                if max_size > 0
                else True
            ):
                message = await self._receive()
                if message["type"] != "http.request":
                    break

                self._buffer.extend(message.get("body", b""))
                self._body_consumed = not message.get("more_body", False)

            if max_size <= 0 or total_read + len(self._buffer) <= max_size:
                yield self._buffer
                total_read += len(self._buffer)
                self._buffer.clear()
            else:  # max_size > 0 and total_read + len(self._buffer) > max_size
                can_yield = max_size - total_read
                yield self._buffer[:can_yield]
                self._buffer = self._buffer[can_yield:]
                total_read = max_size  # or total_read += can_yield
                break

    async def text(self, encoding: str = "utf-8", max_size: int = -1) -> str:
        data = await self.body(max_size=max_size)
        return data.decode(encoding)

    async def json(self, max_size: int = -1, encoding: str = "utf-8"):
        text_data = await self.text(encoding=encoding, max_size=max_size)
        return json.loads(text_data) if text_data else None

    def _coerce_value(self, value: Any, target_type: type) -> Any:
        origin_type = get_origin(target_type)
        type_args = get_args(target_type)

        if (
            origin_type is Union or origin_type is UnionType
        ):  # Handles Optional[T] as Union[T, NoneType]
            # If empty string and None is an option, return None directly.
            if value == "" and type(None) in type_args:
                return None

            # Attempt coercion for each type in the Union, return on first success
            # Prioritize non-NoneType if NoneType is present
            non_none_types = [t for t in type_args if t is not type(None)]
            # other_types = [t for t in type_args if t is type(None)] # Should just be [NoneType] if present

            for t in non_none_types:
                try:
                    return self._coerce_value(value, t)
                except (ValueError, TypeError):
                    continue
            # If all non-NoneType coercions fail, and NoneType is an option
            # (and value_str was not empty, handled above), this is an error.
            if type(None) in type_args:  # value_str is not empty here
                pass  # Let it fall through to the final raise if it was not coercible to non-None types

            raise ValueError(
                f"Cannot coerce {value!r} to any type in Union {target_type}"
            )

        if target_type is Any:  # If type is Any, return the string value directly
            return value

        if target_type is str:
            return str(value)

        if target_type is bool:
            val_lower = value.lower()
            if val_lower in ("true", "on", "1", "yes"):
                return True
            if val_lower in ("false", "off", "0", "no"):
                return False
            raise ValueError(f"Cannot coerce {value!r} to bool.")

        if target_type is FileUpload:
            return FileUpload(
                filename=value["filename"],
                content_type=value["content_type"],
                headers=value["headers"],
                file=value["file"],
            )

        try:
            return target_type(value)
        except Exception as e:
            raise ValueError(
                f"Unsupported coercion for type {target_type} from value {value!r}: {e}"
            ) from e

    async def _parse_form_data(
        self, max_size: int = 10 * 1024 * 1024, encoding: str = "utf-8"
    ) -> dict[str, Any]:
        form_data_bytes = await self.body(max_size=max_size)
        form_data_str = form_data_bytes.decode(encoding)
        return parse_qs(form_data_str, keep_blank_values=True)

    async def _parse_multipart_body(self, encoding: str, boundary: bytes) -> dict:
        parser = MultipartParser(boundary=boundary, charset=encoding)
        return await parser.parse(self._receive)

    async def form(
        self,
        model: type = dict,
        max_size: int = 10
        * 1024
        * 1024,  # max_size for urlencoded, multipart handled by stream
        encoding: str = "utf-8",
        *,
        data: dict[str, Any] | None = None,
    ) -> Any:
        content_type_header = self.headers.get("content-type", "")
        raw_form_values: dict[str, Any] | None = None  # Initialize

        if data:
            raw_form_values = data
        elif content_type_header.startswith("application/x-www-form-urlencoded"):
            raw_form_values = await self._parse_form_data(
                max_size=max_size, encoding=encoding
            )
        elif content_type_header.startswith("multipart/form-data"):
            _content_type_val_bytes, params = parse_options_header(
                content_type_header.encode("latin-1")
            )
            boundary = params.get(b"boundary")
            if not boundary:
                raise ValueError("Multipart form missing boundary.")
            raw_form_values = await self._parse_multipart_body(
                encoding=encoding, boundary=boundary
            )
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
                raise TypeError(
                    f"Failed to instantiate model {model.__name__} from empty form. Error: {e}"
                ) from e

        return self._build_model(model, raw_form_values)

    def _build_model(self, model: type, raw_form_values: dict[str, Any]) -> Any:
        coerced_data = {}
        annotations = getattr(model, "__annotations__", {})

        for field_name, field_type in annotations.items():
            values_from_form = raw_form_values.get(field_name)

            if values_from_form is None:  # Field not present in form
                continue

            origin_type = get_origin(field_type)
            type_args = get_args(field_type)
            # Robust check for list types
            is_list_expected = (
                field_type is list
                or field_type is list
                or origin_type is list
                or origin_type is list
            )

            if is_list_expected:
                if not type_args:  # e.g. list or List without inner type
                    # Treat as list of strings by default if no inner type specified
                    coerced_data[field_name] = [str(item) for item in values_from_form]
                else:
                    target_inner_type = type_args[0]
                    coerced_items = []
                    for item_str in values_from_form:
                        try:
                            coerced_items.append(
                                self._coerce_value(item_str, target_inner_type)
                            )
                        except ValueError as e:
                            # Handle coercion errors for list items, e.g., log or raise
                            # For now, let's be strict and raise, or one could collect errors.
                            raise ValueError(
                                f"Error coercing item '{item_str}' for field '{field_name}': {e}"
                            ) from e
                    coerced_data[field_name] = coerced_items
            else:  # Single value expected
                # Rule 1: Use the first value if multiple submitted for a non-list field
                value_to_coerce_str = values_from_form[0]
                try:
                    coerced_data[field_name] = self._coerce_value(
                        value_to_coerce_str, field_type
                    )
                except ValueError as e:
                    # Handle coercion errors for single items
                    raise ValueError(
                        f"Error coercing value '{value_to_coerce_str}' for field '{field_name}': {e}"
                    ) from e

        try:
            return model(**coerced_data)
        except Exception as e:
            # This could happen if model validation fails (e.g. missing required fields not in form)
            # or if there's a mismatch not caught by type hints alone.
            raise TypeError(
                f"Failed to instantiate model {model.__name__} with coerced data. Error: {e}. Data: {coerced_data}"
            ) from e

    def __repr__(self):
        return (
            f"<Request {self.method} {self.scheme}://"
            f"{self.headers.get('host', '')}{self.path}>"
        )
