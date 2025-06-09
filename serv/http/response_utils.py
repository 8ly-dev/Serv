"""Response utilities for creating and managing HTTP responses."""

import json
from collections.abc import AsyncGenerator
from typing import Any


class BaseResponse:
    """Base response class with common functionality."""

    __match_args__ = ("status_code", "headers")

    def __init__(
        self,
        status_code: int,
        body: str | bytes | None = None,
        headers: dict[str, str] | None = None,
        content_type: str | None = None,
    ):
        self.status_code = status_code
        self.body = body or b""
        self.headers = headers or {}
        self.created_by = None

        if content_type:
            self.headers["Content-Type"] = content_type

    async def render(self) -> AsyncGenerator[bytes]:
        """Render the response body as bytes."""
        if isinstance(self.body, str):
            yield self.body.encode("utf-8")
        else:
            yield self.body

    def set_created_by(self, handler: Any) -> None:
        """Set which handler created this response."""
        self.created_by = handler

    def __repr__(self):
        body_preview = str(self.body)[:20]
        if len(str(self.body)) > 20:
            body_preview += "..."

        return (
            f"<{self.__class__.__name__} "
            f"status={self.status_code} "
            f"headers={self.headers} "
            f"body={body_preview!r}"
            f">"
        )


class Response(BaseResponse):
    """Standard HTTP response."""

    def __init__(
        self,
        status_code: int,
        body: str | bytes | None = None,
        headers: dict[str, str] | None = None,
    ):
        # Convert body to bytes for compatibility
        if isinstance(body, str):
            body = body.encode("utf-8")
        super().__init__(status_code, body, headers)


def create_typed_response(content_type: str):
    """Factory function to create response classes with specific content types."""

    class TypedResponse(BaseResponse):
        def __init__(self, content: Any, status_code: int = 200):
            if content_type == "application/json":
                body = json.dumps(content)
            else:
                body = str(content)

            super().__init__(status_code, body, content_type=content_type)

    return TypedResponse


# Create specific response types using the factory
JsonResponse = create_typed_response("application/json")
TextResponse = create_typed_response("text/plain")
HtmlResponse = create_typed_response("text/html")


class FileResponse(BaseResponse):
    """Response for file downloads."""

    def __init__(
        self,
        file: bytes,
        filename: str,
        status_code: int = 200,
        content_type: str = "application/octet-stream",
    ):
        super().__init__(status_code, file, content_type=content_type)
        self.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
