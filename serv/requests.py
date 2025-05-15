import json
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
        body = bytearray()
        async for chunk in self.read(max_size=max_size):
            body.extend(chunk)
        return bytes(body)

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
            if not self._body_consumed and (not self._buffer or total_read + len(self._buffer) < max_size):
                message = await self._receive()
                if message["type"] != "http.request":
                    break

                self._buffer.extend(message.get("body", b""))
                self._body_consumed = not message.get("more_body", False)

            if total_read + len(self._buffer) <= max_size or max_size <= 0:
                yield self._buffer
                total_read += len(self._buffer)
                self._buffer.clear()

            else:
                yield self._buffer[:max_size - total_read]
                self._buffer = self._buffer[max_size - total_read:]
                total_read = max_size
                break


    async def text(self, encoding: str = "utf-8", max_size: int = -1) -> str:
        data = await self.body(max_size=max_size)
        return data.decode(encoding)

    async def json(self, max_size: int = -1):
        text = await self.text(max_size=max_size)
        return json.loads(text) if text else None

    async def form(self, max_size: int = 10*1024*1024, encoding: str = "utf-8") -> dict:
        """
        Parses form data from the request body (application/x-www-form-urlencoded).

        Args:
            max_size: Maximum size of the request body to read (default 10MB).
            encoding: The encoding to use for decoding the request body.

        Returns:
            A dictionary of form fields. Values are single strings if only one value
            is present for a key, otherwise a list of strings.

        Raises:
            RuntimeError: If the Content-Type is not application/x-www-form-urlencoded.
        """
        content_type_header = self.headers.get("content-type", "")
        if not content_type_header.startswith("application/x-www-form-urlencoded"):
            # You might want to handle multipart/form-data differently or raise a more specific error.
            # For now, strict check.
            raise RuntimeError(
                f"Cannot parse form data for Content-Type '{content_type_header}'. "
                f"Expected 'application/x-www-form-urlencoded'."
            )

        form_data_bytes = await self.body(max_size=max_size)
        if not form_data_bytes:
            return {}
            
        form_data_str = form_data_bytes.decode(encoding)
        parsed_form = parse_qs(form_data_str, keep_blank_values=True)
        return parsed_form

    def __repr__(self):
        return (
            f"<Request {self.method} {self.scheme}://"
            f"{self.headers.get('host', '')}{self.path}>"
        )
