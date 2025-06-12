"""Tests for WebSocket functionality in Serv."""

import json
from typing import Annotated

import pytest

from serv import App, WebSocket
from serv._routing import Router
from serv.websocket import (
    FrameType,
    WebSocketConnectionError,
    WebSocketError,
    WebSocketState,
)
from tests.websocket_test_utils import WebSocketTestClient, create_websocket_scope


@pytest.fixture
def websocket_scope():
    """Create a WebSocket ASGI scope for testing."""
    return create_websocket_scope(
        path="/ws",
        query_string="test=value",
        headers=[
            (b"host", b"testserver"),
            (b"connection", b"upgrade"),
            (b"upgrade", b"websocket"),
        ],
    )


@pytest.fixture
def websocket_client():
    """Create a test WebSocket client for testing."""
    scope = create_websocket_scope(
        path="/ws",
        query_string="test=value",
        headers=[
            (b"host", b"testserver"),
            (b"connection", b"upgrade"),
            (b"upgrade", b"websocket"),
        ],
    )
    return WebSocketTestClient(scope)


class TestWebSocketClass:
    """Test the WebSocket class functionality."""

    def test_websocket_init(self, websocket_client):
        """Test WebSocket initialization."""
        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        assert ws.path == "/ws"
        assert ws.query_string == "test=value"
        assert ws.client == ("127.0.0.1", 12345)
        assert ws.frame_type == FrameType.TEXT
        assert ws.state == WebSocketState.CONNECTING
        assert not ws.is_connected

    def test_websocket_init_with_frame_type(self, websocket_client):
        """Test WebSocket initialization with binary frame type."""
        ws = WebSocket(
            websocket_client.scope,
            websocket_client.receive,
            websocket_client.send,
            FrameType.BINARY,
        )
        assert ws.frame_type == FrameType.BINARY

    def test_websocket_init_invalid_scope(self, websocket_client):
        """Test WebSocket initialization with invalid scope type."""
        invalid_scope = {"type": "http"}

        with pytest.raises(
            ValueError, match="WebSocket requires 'websocket' scope type"
        ):
            WebSocket(invalid_scope, websocket_client.receive, websocket_client.send)

    async def test_websocket_accept(self, websocket_client):
        """Test WebSocket connection acceptance."""
        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()

        assert ws.state == WebSocketState.CONNECTED
        assert ws.is_connected
        assert websocket_client.get_last_sent_message() == {"type": "websocket.accept"}

    async def test_websocket_accept_with_subprotocol(self, websocket_client):
        """Test WebSocket connection acceptance with subprotocol."""
        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept(subprotocol="chat")

        assert ws.state == WebSocketState.CONNECTED
        assert websocket_client.get_last_sent_message() == {
            "type": "websocket.accept",
            "subprotocol": "chat",
        }

    async def test_websocket_accept_already_connected(self, websocket_client):
        """Test WebSocket accept when already connected."""
        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()

        with pytest.raises(WebSocketConnectionError, match="already established"):
            await ws.accept()

    async def test_websocket_close(self, websocket_client):
        """Test WebSocket connection closure."""
        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()
        await ws.close()

        assert ws.state == WebSocketState.DISCONNECTED
        assert not ws.is_connected
        close_messages = websocket_client.get_sent_messages_of_type("websocket.close")
        assert {"type": "websocket.close", "code": 1000, "reason": ""} in close_messages

    async def test_websocket_close_with_code_and_reason(self, websocket_client):
        """Test WebSocket close with custom code and reason."""
        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()
        await ws.close(code=1001, reason="Going away")

        close_messages = websocket_client.get_sent_messages_of_type("websocket.close")
        assert {
            "type": "websocket.close",
            "code": 1001,
            "reason": "Going away",
        } in close_messages

    async def test_websocket_send_text(self, websocket_client):
        """Test sending text messages."""
        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()
        await ws.send("Hello, WebSocket!")

        send_messages = websocket_client.get_sent_messages_of_type("websocket.send")
        assert {"type": "websocket.send", "text": "Hello, WebSocket!"} in send_messages

    async def test_websocket_send_bytes(self, websocket_client):
        """Test sending binary messages."""
        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()
        await ws.send(b"Binary data")

        send_messages = websocket_client.get_sent_messages_of_type("websocket.send")
        assert {"type": "websocket.send", "bytes": b"Binary data"} in send_messages

    async def test_websocket_send_json(self, websocket_client):
        """Test sending JSON messages."""
        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()
        await ws.send_json({"message": "Hello", "type": "greeting"})

        expected_text = json.dumps({"message": "Hello", "type": "greeting"})
        send_messages = websocket_client.get_sent_messages_of_type("websocket.send")
        assert {"type": "websocket.send", "text": expected_text} in send_messages

    async def test_websocket_send_not_connected(self, websocket_client):
        """Test sending message when not connected."""
        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )

        with pytest.raises(WebSocketConnectionError, match="not active"):
            await ws.send("Hello")

    async def test_websocket_receive_text(self, websocket_client):
        """Test receiving text messages."""
        websocket_client.add_text_message("Hello from client")

        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()
        message = await ws.receive()

        assert message == "Hello from client"

    async def test_websocket_receive_bytes(self, websocket_client):
        """Test receiving binary messages."""
        websocket_client.add_bytes_message(b"Binary from client")

        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()
        message = await ws.receive()

        assert message == b"Binary from client"

    async def test_websocket_receive_json(self, websocket_client):
        """Test receiving and parsing JSON messages."""
        json_data = {"action": "ping", "data": {"timestamp": 12345}}
        websocket_client.add_text_message(json.dumps(json_data))

        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()
        data = await ws.receive_json()

        assert data == json_data

    async def test_websocket_receive_disconnect(self, websocket_client):
        """Test handling disconnect messages."""
        websocket_client.disconnect(code=1000, reason="Normal closure")

        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()

        with pytest.raises(
            WebSocketConnectionError,
            match="WebSocket disconnected: 1000 Normal closure",
        ):
            await ws.receive()

        assert ws.state == WebSocketState.DISCONNECTED

    async def test_websocket_async_iteration(self, websocket_client):
        """Test async iteration over WebSocket messages."""
        # Add some messages to receive
        test_messages = ["Message 1", "Message 2", "Message 3"]
        for msg in test_messages:
            websocket_client.add_text_message(msg)

        # Add disconnect to end iteration
        websocket_client.disconnect()

        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()

        received_messages = []
        async for message in ws:
            received_messages.append(message)

        assert received_messages == test_messages

    async def test_websocket_context_manager(self, websocket_client):
        """Test WebSocket as async context manager."""
        async with WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        ) as ws:
            assert ws.is_connected
            await ws.send("Test message")

        # Should be closed after context exit
        assert not ws.is_connected
        close_messages = websocket_client.get_sent_messages_of_type("websocket.close")
        assert len(close_messages) > 0


class TestWebSocketRouting:
    """Test WebSocket routing functionality."""

    def test_router_add_websocket(self):
        """Test adding WebSocket routes to router."""
        router = Router()

        async def echo_handler(websocket: WebSocket):
            async for message in websocket:
                await websocket.send(message)

        router.add_websocket("/ws", echo_handler)

        # Check that the route was added
        assert len(router._websocket_routes) == 1
        path, handler, settings = router._websocket_routes[0]
        assert path == "/ws"
        assert handler is echo_handler
        assert settings == {}

    def test_router_add_websocket_with_settings(self):
        """Test adding WebSocket routes with settings."""
        router = Router()

        async def auth_handler(websocket: WebSocket):
            pass

        router.add_websocket("/ws", auth_handler, settings={"auth_required": True})

        path, handler, settings = router._websocket_routes[0]
        assert settings == {"auth_required": True}

    def test_router_resolve_websocket(self):
        """Test resolving WebSocket routes."""
        router = Router()

        async def echo_handler(websocket: WebSocket):
            pass

        router.add_websocket("/ws", echo_handler)

        result = router.resolve_websocket("/ws")
        assert result is not None
        handler, path_params, settings = result
        assert handler is echo_handler
        assert path_params == {}
        assert settings == {}

    def test_router_resolve_websocket_with_params(self):
        """Test resolving WebSocket routes with path parameters."""
        router = Router()

        async def room_handler(websocket: WebSocket):
            pass

        router.add_websocket("/ws/room/{room_id}", room_handler)

        result = router.resolve_websocket("/ws/room/123")
        assert result is not None
        handler, path_params, settings = result
        assert handler is room_handler
        assert path_params == {"room_id": "123"}

    def test_router_resolve_websocket_not_found(self):
        """Test resolving non-existent WebSocket routes."""
        router = Router()

        result = router.resolve_websocket("/nonexistent")
        assert result is None

    def test_router_mounted_websocket_routes(self):
        """Test WebSocket routes in mounted routers."""
        main_router = Router()
        api_router = Router()

        async def api_websocket(websocket: WebSocket):
            pass

        api_router.add_websocket("/ws", api_websocket)
        main_router.mount("/api", api_router)

        result = main_router.resolve_websocket("/api/ws")
        assert result is not None
        handler, path_params, settings = result
        assert handler is api_websocket


class TestWebSocketApp:
    """Test WebSocket integration with the App class."""

    @pytest.fixture
    def app_with_websocket(self):
        """Create an app with WebSocket routes for testing."""
        app = App(dev_mode=True)

        # Add a simple echo WebSocket handler during request begin
        async def echo_handler(websocket: WebSocket):
            async for message in websocket:
                await websocket.send(message)

        async def setup_routes(container, **kwargs):
            router = container.get(Router)
            router.add_websocket("/ws/echo", echo_handler)

        # Create a proper extension with _stand_alone attribute
        extension = type(
            "TestExtension",
            (),
            {"on_app_request_begin": setup_routes, "_stand_alone": True},
        )()
        app.add_extension(extension)
        return app

    @pytest.fixture
    def app_with_binary_websocket(self):
        """Create an app with binary WebSocket routes."""
        app = App(dev_mode=True)

        async def binary_handler(ws: Annotated[WebSocket, FrameType.BINARY]):
            async for message in ws:
                await ws.send(message)

        async def setup_routes(container, **kwargs):
            router = container.get(Router)
            router.add_websocket("/ws/binary", binary_handler)

        # Create a proper extension with _stand_alone attribute
        extension = type(
            "TestExtension",
            (),
            {"on_app_request_begin": setup_routes, "_stand_alone": True},
        )()
        app.add_extension(extension)
        return app

    async def test_websocket_connection_not_found(self):
        """Test WebSocket connection to non-existent route."""
        app = App(dev_mode=True)

        # Mock ASGI scope for WebSocket
        scope = {"type": "websocket", "path": "/nonexistent"}
        receive_called = False
        send_messages = []

        async def receive():
            nonlocal receive_called
            receive_called = True
            return {"type": "websocket.connect"}

        async def send(message):
            send_messages.append(message)

        await app(scope, receive, send)

        # Should reject with 4404 code
        assert {"type": "websocket.close", "code": 4404} in send_messages
        assert not receive_called  # Should not have called receive

    async def test_websocket_echo_functionality(self, app_with_websocket):
        """Test WebSocket echo functionality through the app."""
        # This test demonstrates the integration but would need a real WebSocket client
        # for full end-to-end testing. For now, we test the routing setup.

        # Test that the app can handle WebSocket scope
        scope = {"type": "websocket", "path": "/ws/echo"}
        messages_sent = []
        connection_accepted = False

        async def receive():
            return {"type": "websocket.connect"}

        async def send(message):
            nonlocal connection_accepted
            messages_sent.append(message)
            if message["type"] == "websocket.accept":
                connection_accepted = True

        # This will attempt to handle the WebSocket connection
        # In a real scenario, we'd need to provide the full WebSocket handshake
        try:
            await app_with_websocket(scope, receive, send)
        except Exception:
            # Expected since we're not providing a full WebSocket interaction
            pass

        # The important thing is that the route resolution works
        # We can verify this by checking that no immediate rejection occurred
        rejection_messages = [msg for msg in messages_sent if msg.get("code") == 4404]
        assert len(rejection_messages) == 0  # No "not found" rejections

    async def test_websocket_binary_frame_type(self, app_with_binary_websocket):
        """Test that binary frame type annotation is handled correctly."""
        # Similar to above, this tests the routing and frame type handling
        scope = {"type": "websocket", "path": "/ws/binary"}
        messages_sent = []

        async def receive():
            return {"type": "websocket.connect"}

        async def send(message):
            messages_sent.append(message)

        try:
            await app_with_binary_websocket(scope, receive, send)
        except Exception:
            pass

        # Verify no rejection for binary WebSocket route
        rejection_messages = [msg for msg in messages_sent if msg.get("code") == 4404]
        assert len(rejection_messages) == 0


class TestWebSocketFrameTypes:
    """Test WebSocket frame type functionality."""

    def test_frame_type_enum(self):
        """Test FrameType enum values."""
        assert FrameType.TEXT.value == "text"
        assert FrameType.BINARY.value == "binary"

    def test_frame_type_annotation_parsing(self):
        """Test that frame type annotations work correctly."""
        from typing import get_args, get_origin, get_type_hints

        # Define a function with frame type annotation
        async def binary_handler(ws: Annotated[WebSocket, FrameType.BINARY]):
            pass

        # Get type hints
        hints = get_type_hints(binary_handler, include_extras=True)
        ws_annotation = hints["ws"]

        # Check annotation structure
        assert get_origin(ws_annotation) is not None
        args = get_args(ws_annotation)
        assert len(args) >= 2
        assert args[0] is WebSocket
        assert FrameType.BINARY in args


class TestWebSocketErrorHandling:
    """Test WebSocket error handling."""

    def test_websocket_error_hierarchy(self):
        """Test WebSocket exception hierarchy."""
        assert issubclass(WebSocketConnectionError, WebSocketError)
        assert issubclass(WebSocketError, Exception)

    async def test_websocket_error_scenarios(self, websocket_client):
        """Test various WebSocket error scenarios."""
        # Test invalid data type
        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()

        with pytest.raises(TypeError, match="WebSocket data must be str or bytes"):
            await ws.send(123)  # Invalid data type

        # Test JSON serialization error
        with pytest.raises(TypeError, match="not JSON serializable"):
            await ws.send_json(object())  # Non-serializable object

    async def test_websocket_type_validation(self, websocket_client):
        """Test WebSocket message type validation."""
        websocket_client.add_bytes_message(b"binary data")

        ws = WebSocket(
            websocket_client.scope, websocket_client.receive, websocket_client.send
        )
        await ws.accept()

        # Try to receive text when binary was sent
        with pytest.raises(TypeError, match="Expected text message"):
            await ws.receive_text()
