"""HTTP response classes and response building utilities."""

import inspect
import json
from typing import Any, AsyncGenerator, Protocol, runtime_checkable

from bevy import Inject, injectable
from serv.protocols import AppContextProtocol


@runtime_checkable
class AsyncIterable(Protocol):
    async def __aiter__(self): ...


@runtime_checkable
class Iterable(Protocol):
    def __iter__(self): ...


class ResponseBuilder:
    """Builder for constructing HTTP responses in Serv applications.

    The ResponseBuilder provides a fluent interface for building HTTP responses,
    including setting status codes, headers, cookies, and response bodies. It
    supports streaming responses, various content types, and automatic encoding.

    The ResponseBuilder is automatically injected into route handlers and middleware
    through the dependency injection system, so you typically don't need to
    instantiate it directly.

    Features:
    - Fluent API for chaining method calls
    - Automatic content-type detection and encoding
    - Cookie management (set, delete)
    - Header manipulation
    - Streaming response support
    - Redirect helpers
    - Multiple body content types (str, bytes, iterables, async iterables)

    Examples:
        Basic response:

        ```python
        from serv.http.responses import ResponseBuilder
        from bevy import injectable, Inject

        @injectable
        async def my_handler(response: Inject[ResponseBuilder]):
            response.set_status(200)
            response.content_type("text/plain")
            response.body("Hello, World!")
        ```

        JSON response:

        ```python
        import json

        @injectable
        async def api_handler(response: Inject[ResponseBuilder]):
            data = {"message": "Hello", "status": "success"}
            response.set_status(200)
            response.content_type("application/json")
            response.body(json.dumps(data))
        ```

        HTML response with headers:

        ```python
        @injectable
        async def html_handler(response: Inject[ResponseBuilder]):
            html = "<h1>Welcome</h1><p>This is a test page.</p>"
            response.set_status(200)
            response.content_type("text/html")
            response.add_header("X-Custom-Header", "MyValue")
            response.body(html)
        ```

        Redirect response:

        ```python
        @injectable
        async def redirect_handler(response: Inject[ResponseBuilder]):
            response.redirect("/new-location", status_code=301)
        ```

        Cookie management:

        ```python
        @injectable
        async def cookie_handler(response: Inject[ResponseBuilder]):
            response.set_cookie("session_id", "abc123", max_age=3600, httponly=True)
            response.set_cookie("theme", "dark", path="/", secure=True)
            response.body("Cookies set!")
        ```

        Streaming response:

        ```python
        @injectable
        async def stream_handler(response: Inject[ResponseBuilder]):
            response.content_type("text/plain")

            # Add multiple body components
            response.body("Starting stream...\n")
            response.body("Processing data...\n")

            # Add async iterable
            async def data_generator():
                for i in range(5):
                    yield f"Item {i}\n"
                    await asyncio.sleep(0.1)

            response.body(data_generator())
            response.body("Stream complete!")
        ```

        Chained method calls:

        ```python
        @injectable
        async def chained_handler(response: Inject[ResponseBuilder]):
            (response
                .set_status(201)
                .content_type("application/json")
                .add_header("Location", "/api/users/123")
                .set_cookie("last_action", "create_user")
                .body('{"id": 123, "name": "John Doe"}'))
        ```

    Note:
        The ResponseBuilder automatically handles encoding, content-length calculation,
        and proper ASGI message formatting. Once `send_response()` is called (which
        happens automatically at the end of request processing), no further
        modifications can be made to the response.
    """

    def __init__(self, send_callable):
        self._send = send_callable

        self._status = 200
        self._headers = []  # List of (name_bytes, value_bytes)
        self._body_components = []
        self._headers_sent = False
        self._default_encoding = "utf-8"
        self._has_content_type = False

    def set_status(self, status_code: int):
        """Set the HTTP status code for the response.

        Args:
            status_code: HTTP status code (e.g., 200, 404, 500).

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If headers have already been sent.

        Examples:
            ```python
            response.set_status(200)  # OK
            response.set_status(404)  # Not Found
            response.set_status(500)  # Internal Server Error
            ```
        """
        if self._headers_sent:
            raise RuntimeError("Cannot set status after headers have been sent.")
        self._status = status_code
        return self

    def add_header(self, name: str, value: str):
        if self._headers_sent:
            raise RuntimeError("Cannot add headers after they have been sent.")
        # Ensure we don't re-add default content-type if _has_content_type was from a previous add
        # This check needs to be robust if clear() is called.
        if name.lower() == "content-type":
            self._has_content_type = True
        self._headers.append((name.lower().encode("latin-1"), value.encode("latin-1")))
        return self

    def content_type(self, ctype: str, charset: str | None = None):
        """Set the Content-Type header for the response.

        Args:
            ctype: MIME type (e.g., "text/html", "application/json").
            charset: Character encoding. Defaults to "utf-8" if not specified.

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If headers have already been sent.

        Examples:
            ```python
            response.content_type("text/html")
            response.content_type("application/json")
            response.content_type("text/plain", charset="iso-8859-1")
            response.content_type("image/png")  # No charset for binary content
            ```
        """
        if self._headers_sent:
            raise RuntimeError("Cannot set content_type after headers have been sent.")
        if charset is None:
            charset = self._default_encoding
        # Remove existing Content-Type headers before adding the new one to avoid duplicates
        self._headers = [h for h in self._headers if h[0] != b"content-type"]
        self.add_header("Content-Type", f"{ctype}; charset={charset}")
        self._has_content_type = True  # Explicitly set true by this method
        return self

    def set_cookie(
        self,
        key: str,
        value: str = "",
        max_age: int | None = None,
        expires: int | None = None,  # Timestamp
        path: str = "/",
        domain: str | None = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: str = "lax",  # "lax", "strict", or "none"
    ):
        if self._headers_sent:
            raise RuntimeError("Cannot set cookie after headers have been sent.")

        cookie_parts = [f"{key}={value}"]
        if domain is not None:
            cookie_parts.append(f"Domain={domain}")
        if path is not None:
            cookie_parts.append(f"Path={path}")
        if max_age is not None:
            cookie_parts.append(f"Max-Age={max_age}")
        if expires is not None:
            # This expects a pre-formatted string or a timestamp.
            # For robust formatting from timestamp, datetime.strftime would be needed.
            # Example: datetime.datetime.utcfromtimestamp(expires).strftime('%a, %d %b %Y %H:%M:%S GMT')
            cookie_parts.append(f"Expires={expires}")
        if secure:
            cookie_parts.append("Secure")
        if httponly:
            cookie_parts.append("HttpOnly")
        if samesite and samesite.lower() in ["lax", "strict", "none"]:
            cookie_parts.append(f"SameSite={samesite.capitalize()}")

        self.add_header("Set-Cookie", "; ".join(cookie_parts))
        return self

    def delete_cookie(
        self,
        key: str,
        path: str = "/",
        domain: str | None = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: str = "lax",
    ):
        """Instructs the client to delete a cookie by setting its Max-Age to 0 and an expiry date in the past."""
        # Setting Max-Age=0 is the primary method. Expires is a fallback.
        # Use a known past date string for Expires for robustness.
        past_expiry_date = "Thu, 01 Jan 1970 00:00:00 GMT"
        self.set_cookie(
            key,
            value="",
            max_age=0,
            path=path,
            domain=domain,
            expires=past_expiry_date,
            secure=secure,
            httponly=httponly,
            samesite=samesite,
        )
        return self

    def redirect(self, url: str, status_code: int = 302):
        if self._headers_sent:
            raise RuntimeError("Cannot redirect after headers have been sent.")
        self.set_status(status_code)
        self.add_header("Location", url)
        # According to RFC 7231, a 301/302 response to POST should be followed by GET.
        # For 303, the method *must* be GET. For others, it's a bit more ambiguous historically.
        # Browsers typically convert POST to GET for 301/302 as well.
        # We don't need to send a body for redirects, but can ensure content type is minimal.
        if not self._has_content_type:
            self.content_type("text/plain")  # Minimal body if any is expected by client
        self.body(f"Redirecting to {url}")  # Minimal body
        return self

    def body(self, component):
        self._body_components.append(component)
        return self

    def clear(self):
        """Clears the response body and headers. This is useful for error handlers. It cannot change
        anything that has already been sent, it only affects future sends and is intended to be used
        before send_response() has been called."""
        self._body_components = []
        self._headers = []
        self._status = 200
        return self

    async def _send_headers_if_not_sent(self):
        if not self._headers_sent:
            if not self._has_content_type:
                self.add_header(
                    "Content-Type", f"text/plain; charset={self._default_encoding}"
                )

            await self._send(
                {
                    "type": "http.response.start",
                    "status": self._status,
                    "headers": self._headers,
                }
            )
            self._headers_sent = True

    async def _send_body_chunk(self, chunk: bytes):
        if not chunk:
            return

        await self._send(
            {
                "type": "http.response.body",
                "body": chunk,
                "more_body": True,
            }
        )

    async def send_response(self):
        await (
            self._send_headers_if_not_sent()
        )  # Ensures headers are sent even for empty body
        for component in self._body_components:
            await self._stream_component(component)

        # Final empty body chunk
        await self._send(
            {
                "type": "http.response.body",
                "body": b"",
                "more_body": False,
            }
        )
        # Ensure _headers_sent is true, even if body was empty and _send_headers_if_not_sent was the one setting it.
        self._headers_sent = True

    async def _stream_component(self, component):
        match component:
            case bytes() as bytes_value:
                await self._send_body_chunk(bytes_value)
            case bytearray() as bytearray_value:
                await self._send_body_chunk(bytes(bytearray_value))
            case str() as str_value:
                await self._send_body_chunk(str_value.encode(self._default_encoding))
            case AsyncIterable() as async_iterable:
                async for item in async_iterable:
                    await self._stream_component(item)
            case Iterable() as iterable:
                for item in iterable:
                    await self._stream_component(item)
            case awaitable if inspect.isawaitable(component):
                await self._stream_component(await awaitable)
            case function if callable(component):
                await self._stream_component(function())
            case None:
                pass
            case _:
                raise TypeError(
                    f"Body component or function return value must resolve to str, bytes, bytearray, None, "
                    f"or an iterable/async iterable yielding these types. Got: {type(component)}"
                )


# Response classes for type annotations and structured responses


class Response:
    def __init__(
        self,
        status_code: int,
        body: str | bytes | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.body = body or b""
        self.headers = headers or {}

        # A reference to the handler that returned this response. This is only set after creation but
        # before the response is rendered.
        self.created_by = None

    async def render(self) -> AsyncGenerator[bytes]:
        yield self.body

    def set_created_by(self, handler: Any) -> None:
        self.created_by = handler

    def __repr__(self):
        body_preview = self.body[:20].decode("utf-8", errors="replace")
        if len(self.body) > 20:
            body_preview += "..."

        return (
            f"<{self.__class__.__name__} "
            f"status={self.status_code} "
            f"headers={self.headers} "
            f"body={body_preview!r}"
            f">"
        )


class JsonResponse(Response):
    def __init__(self, data: Any, status_code: int = 200):
        super().__init__(status_code)
        self.body = json.dumps(data).encode("utf-8")
        self.headers["Content-Type"] = "application/json"


class TextResponse(Response):
    def __init__(self, text: str, status_code: int = 200):
        super().__init__(status_code)
        self.body = text.encode("utf-8")
        self.headers["Content-Type"] = "text/plain"


class HtmlResponse(Response):
    def __init__(self, html: str, status_code: int = 200):
        super().__init__(status_code)
        self.body = html.encode("utf-8")
        self.headers["Content-Type"] = "text/html"


class FileResponse(Response):
    def __init__(
        self,
        file: bytes,
        filename: str,
        status_code: int = 200,
        content_type: str = "application/octet-stream",
    ):
        super().__init__(status_code)
        self.body = file
        self.headers["Content-Type"] = content_type
        self.headers["Content-Disposition"] = f"attachment; filename={filename}"


class StreamingResponse(Response):
    def __init__(
        self,
        content: AsyncGenerator[str | bytes],
        status_code: int = 200,
        media_type: str = "text/plain",
        headers: dict[str, str] | None = None,
    ):
        super().__init__(status_code, headers=headers)
        self.content = content
        self.headers["Content-Type"] = media_type

        self._running_renderer = None

    @injectable
    async def render(
        self, app_context: Inject[AppContextProtocol]
    ) -> AsyncGenerator[bytes]:
        self._running_renderer = self._render()
        app_context.on_shutdown(self._shutdown)
        return self._running_renderer

    async def _shutdown(self):
        if self._running_renderer:
            await self._running_renderer.athrow(StopAsyncIteration())

    async def _render(self):
        try:
            async for chunk in self.content:
                if isinstance(chunk, str):
                    yield chunk.encode("utf-8")
                elif isinstance(chunk, bytes):
                    yield chunk
                else:
                    yield str(chunk).encode("utf-8")
        except Exception as e:
            e.add_note(f" - Rendering {self}")
            raise
        finally:
            self._running_renderer = None

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}"
            f" status={self.status_code}"
            f" headers={self.headers}"
            f" content={self.content!r}"
            f">"
        )


class ServerSentEventsResponse(StreamingResponse):
    def __init__(
        self,
        content: AsyncGenerator[str | bytes],
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ):
        sse_headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        if headers:
            sse_headers.update(headers)

        super().__init__(content, status_code, "text/event-stream", sse_headers)


class RedirectResponse(Response):
    def __init__(self, url: str, status_code: int = 302):
        super().__init__(status_code)
        self.headers["Location"] = url
        self.body = f"Redirecting to {url}"


class Jinja2Response(Response):
    def __init__(self, template: str, context: dict[str, Any], status_code: int = 200):
        super().__init__(status_code)
        self.template = template
        self.context = context
        self.headers["Content-Type"] = "text/html"

    def render(self) -> AsyncGenerator[str, object]:
        from jinja2 import Environment, FileSystemLoader
        from pathlib import Path

        template_locations = self._get_template_locations(self.created_by)

        env = Environment(
            loader=FileSystemLoader(template_locations), enable_async=True
        )
        template = env.get_template(self.template)
        return template.generate_async(**self.context)

    @staticmethod
    def _get_template_locations(extension: "pl.ExtensionSpec"):
        from pathlib import Path

        if not extension:
            raise RuntimeError("Jinja2Response cannot be used outside of a extension.")

        return [
            Path.cwd() / "templates" / extension.name,
            extension.path / "templates",
        ]

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}"
            f" status={self.status_code}"
            f" headers={self.headers}"
            f" template={self.template!r}"
            f" context={self.context!r}"
            f">"
        )


__all__ = [
    # Protocols
    "AsyncIterable",
    "Iterable",
    # Builder
    "ResponseBuilder",
    # Response classes
    "Response",
    "JsonResponse",
    "TextResponse",
    "HtmlResponse",
    "FileResponse",
    "StreamingResponse",
    "ServerSentEventsResponse",
    "RedirectResponse",
    "Jinja2Response",
]
