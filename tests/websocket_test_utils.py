"""Test utilities for WebSocket testing that mimic real ASGI behavior."""

import asyncio
from typing import Any


class WebSocketTestClient:
    """A test WebSocket client that properly simulates ASGI WebSocket behavior.

    This client handles the full WebSocket lifecycle including the initial
    websocket.connect message, proper message queuing, and disconnect handling.
    """

    def __init__(self, scope: dict[str, Any] = None):
        """Initialize the test WebSocket client.

        Args:
            scope: ASGI scope dict. If None, creates a default WebSocket scope.
        """
        self.scope = scope or {
            "type": "websocket",
            "path": "/ws",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }

        self._message_queue: list[dict[str, Any]] = []
        self._sent_messages: list[dict[str, Any]] = []
        self._connected = False
        self._closed = False

        # Queue the initial connect message that real ASGI provides
        self._message_queue.append({"type": "websocket.connect"})

    @property
    def sent_messages(self) -> list[dict[str, Any]]:
        """Get messages sent by the WebSocket."""
        return self._sent_messages.copy()

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected and not self._closed

    def add_incoming_message(self, message: dict[str, Any]) -> None:
        """Add a message to the incoming queue.

        Args:
            message: ASGI WebSocket message dict
        """
        if not self._closed:
            self._message_queue.append(message)

    def add_text_message(self, text: str) -> None:
        """Add a text message to the incoming queue.

        Args:
            text: Text message to receive
        """
        self.add_incoming_message({"type": "websocket.receive", "text": text})

    def add_bytes_message(self, data: bytes) -> None:
        """Add a binary message to the incoming queue.

        Args:
            data: Binary data to receive
        """
        self.add_incoming_message({"type": "websocket.receive", "bytes": data})

    def disconnect(self, code: int = 1000, reason: str = "") -> None:
        """Disconnect the WebSocket.

        Args:
            code: WebSocket close code
            reason: Disconnect reason
        """
        if not self._closed:
            self.add_incoming_message(
                {"type": "websocket.disconnect", "code": code, "reason": reason}
            )
            self._closed = True

    async def receive(self) -> dict[str, Any]:
        """ASGI receive callable that mimics real WebSocket behavior."""
        while not self._message_queue and not self._closed:
            await asyncio.sleep(0.001)  # Prevent busy waiting

        if self._message_queue:
            return self._message_queue.pop(0)

        # If no messages and closed, return disconnect
        return {"type": "websocket.disconnect", "code": 1000}

    async def send(self, message: dict[str, Any]) -> None:
        """ASGI send callable that captures sent messages."""
        self._sent_messages.append(message)

        # Handle connection state changes
        if message["type"] == "websocket.accept":
            self._connected = True
        elif message["type"] == "websocket.close":
            self._closed = True
            self._connected = False

    def get_last_sent_message(self) -> dict[str, Any] | None:
        """Get the last message sent by the WebSocket."""
        return self._sent_messages[-1] if self._sent_messages else None

    def get_sent_messages_of_type(self, message_type: str) -> list[dict[str, Any]]:
        """Get all sent messages of a specific type.

        Args:
            message_type: ASGI message type to filter by

        Returns:
            List of messages matching the type
        """
        return [msg for msg in self._sent_messages if msg.get("type") == message_type]

    def clear_sent_messages(self) -> None:
        """Clear the sent messages list."""
        self._sent_messages.clear()


def create_websocket_scope(
    path: str = "/ws", query_string: str = "", headers: list[tuple] = None
) -> dict[str, Any]:
    """Create a WebSocket ASGI scope for testing.

    Args:
        path: WebSocket path
        query_string: Query string
        headers: List of (name, value) header tuples

    Returns:
        ASGI WebSocket scope dict
    """
    return {
        "type": "websocket",
        "path": path,
        "query_string": query_string.encode("utf-8"),
        "headers": headers
        or [
            (b"host", b"testserver"),
            (b"connection", b"upgrade"),
            (b"upgrade", b"websocket"),
        ],
        "client": ("127.0.0.1", 12345),
    }
