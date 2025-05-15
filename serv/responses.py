import inspect
from typing import Protocol, runtime_checkable


@runtime_checkable
class AsyncIterable(Protocol):
    async def __aiter__(self):
        ...


@runtime_checkable
class Iterable(Protocol):
    def __iter__(self):
        ...


class ResponseBuilder:
    def __init__(self, send_callable):
        self._send = send_callable
        self._status = 200
        self._headers = []  # List of (name_bytes, value_bytes)
        self._body_components = []
        self._headers_sent = False
        self._default_encoding = "utf-8"
        self._has_content_type = False

    def set_status(self, status_code: int):
        if self._headers_sent:
            raise RuntimeError("Cannot set status after headers have been sent.")
        self._status = status_code
        return self

    def add_header(self, name: str, value: str):
        if self._headers_sent:
            raise RuntimeError("Cannot add headers after they have been sent.")
        self._headers.append((name.lower().encode("latin-1"), value.encode("latin-1")))
        self._has_content_type = self._has_content_type or name.lower() == "content-type"
        return self

    def content_type(self, ctype: str, charset: str | None = None):
        if charset is None:
            charset = self._default_encoding
        self.add_header("Content-Type", f"{ctype}; charset={charset}")
        return self

    def body(self, component):
        # It's generally fine to add body components before headers are finalized,
        # as send_response() is the terminal operation that sends headers.
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
                self.add_header("Content-Type", f"text/plain; charset={self._default_encoding}")
            
            await self._send({
                "type": "http.response.start",
                "status": self._status,
                "headers": self._headers,
            })
            self._headers_sent = True

    async def _send_body_chunk(self, chunk: bytes):
        if not chunk: # Avoid sending empty \'\'\'body\'\'\' messages if a component resolves to empty
            return
        
        await self._send({
            "type": "http.response.body",
            "body": chunk,
            "more_body": True,
        })

    async def send_response(self):
        await self._send_headers_if_not_sent() # Ensures headers are sent even for empty body
        for component in self._body_components:
            await self._stream_component(component)
        
        await self._send({
            "type": "http.response.body",
            "body": b"",
            "more_body": False,
        })

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