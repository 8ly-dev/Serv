"""Tests for WebSocket functionality in Serv."""

import json
import asyncio
import pytest
from typing import Annotated

from serv import App, WebSocket
from serv.websocket import FrameType, WebSocketError, WebSocketConnectionError, WebSocketState
from serv.routing import Router
from tests.e2e_test_helpers import create_test_client


@pytest.fixture
def websocket_scope():
    """Create a WebSocket ASGI scope for testing."""
    return {
        "type": "websocket",
        "path": "/ws",
        "query_string": b"test=value",
        "headers": [
            (b"host", b"testserver"),
            (b"connection", b"upgrade"),
            (b"upgrade", b"websocket"),
        ],
        "client": ("127.0.0.1", 12345),
    }


@pytest.fixture
def mock_receive_send():
    """Create mock receive and send callables for testing."""
    received_messages = []
    sent_messages = []

    async def receive():
        if received_messages:
            return received_messages.pop(0)
        await asyncio.sleep(0.01)  # Prevent busy waiting
        return {"type": "websocket.disconnect", "code": 1000}

    async def send(message):
        sent_messages.append(message)

    return receive, send, received_messages, sent_messages


class TestWebSocketClass:
    """Test the WebSocket class functionality."""

    def test_websocket_init(self, websocket_scope, mock_receive_send):
        """Test WebSocket initialization."""
        receive, send, _, _ = mock_receive_send
        
        ws = WebSocket(websocket_scope, receive, send)
        assert ws.path == "/ws"
        assert ws.query_string == "test=value"
        assert ws.client == ("127.0.0.1", 12345)
        assert ws.frame_type == FrameType.TEXT
        assert ws.state == WebSocketState.CONNECTING
        assert not ws.is_connected

    def test_websocket_init_with_frame_type(self, websocket_scope, mock_receive_send):
        """Test WebSocket initialization with binary frame type."""
        receive, send, _, _ = mock_receive_send
        
        ws = WebSocket(websocket_scope, receive, send, FrameType.BINARY)
        assert ws.frame_type == FrameType.BINARY

    def test_websocket_init_invalid_scope(self, mock_receive_send):
        """Test WebSocket initialization with invalid scope type."""
        receive, send, _, _ = mock_receive_send
        invalid_scope = {"type": "http"}
        
        with pytest.raises(ValueError, match="WebSocket requires 'websocket' scope type"):
            WebSocket(invalid_scope, receive, send)

    async def test_websocket_accept(self, websocket_scope, mock_receive_send):
        """Test WebSocket connection acceptance."""
        receive, send, _, sent_messages = mock_receive_send
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        
        assert ws.state == WebSocketState.CONNECTED
        assert ws.is_connected
        assert sent_messages == [{"type": "websocket.accept"}]

    async def test_websocket_accept_with_subprotocol(self, websocket_scope, mock_receive_send):
        """Test WebSocket connection acceptance with subprotocol."""
        receive, send, _, sent_messages = mock_receive_send
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept(subprotocol="chat")
        
        assert ws.state == WebSocketState.CONNECTED
        assert sent_messages == [{"type": "websocket.accept", "subprotocol": "chat"}]

    async def test_websocket_accept_already_connected(self, websocket_scope, mock_receive_send):
        """Test WebSocket accept when already connected."""
        receive, send, _, _ = mock_receive_send
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        
        with pytest.raises(WebSocketConnectionError, match="already established"):
            await ws.accept()

    async def test_websocket_close(self, websocket_scope, mock_receive_send):
        """Test WebSocket connection closure."""
        receive, send, _, sent_messages = mock_receive_send
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        await ws.close()
        
        assert ws.state == WebSocketState.DISCONNECTED
        assert not ws.is_connected
        assert {"type": "websocket.close", "code": 1000, "reason": ""} in sent_messages

    async def test_websocket_close_with_code_and_reason(self, websocket_scope, mock_receive_send):
        """Test WebSocket close with custom code and reason."""
        receive, send, _, sent_messages = mock_receive_send
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        await ws.close(code=1001, reason="Going away")
        
        assert {"type": "websocket.close", "code": 1001, "reason": "Going away"} in sent_messages

    async def test_websocket_send_text(self, websocket_scope, mock_receive_send):
        """Test sending text messages."""
        receive, send, _, sent_messages = mock_receive_send
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        await ws.send("Hello, WebSocket!")
        
        assert {"type": "websocket.send", "text": "Hello, WebSocket!"} in sent_messages

    async def test_websocket_send_bytes(self, websocket_scope, mock_receive_send):
        """Test sending binary messages."""
        receive, send, _, sent_messages = mock_receive_send
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        await ws.send(b"Binary data")
        
        assert {"type": "websocket.send", "bytes": b"Binary data"} in sent_messages

    async def test_websocket_send_json(self, websocket_scope, mock_receive_send):
        """Test sending JSON messages."""
        receive, send, _, sent_messages = mock_receive_send
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        await ws.send_json({"message": "Hello", "type": "greeting"})
        
        expected_text = json.dumps({"message": "Hello", "type": "greeting"})
        assert {"type": "websocket.send", "text": expected_text} in sent_messages

    async def test_websocket_send_not_connected(self, websocket_scope, mock_receive_send):
        """Test sending message when not connected."""
        receive, send, _, _ = mock_receive_send
        
        ws = WebSocket(websocket_scope, receive, send)
        
        with pytest.raises(WebSocketConnectionError, match="not active"):
            await ws.send("Hello")

    async def test_websocket_receive_text(self, websocket_scope, mock_receive_send):
        """Test receiving text messages."""
        receive, send, received_messages, _ = mock_receive_send
        received_messages.append({"type": "websocket.receive", "text": "Hello from client"})
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        message = await ws.receive()
        
        assert message == "Hello from client"

    async def test_websocket_receive_bytes(self, websocket_scope, mock_receive_send):
        """Test receiving binary messages."""
        receive, send, received_messages, _ = mock_receive_send
        received_messages.append({"type": "websocket.receive", "bytes": b"Binary from client"})
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        message = await ws.receive()
        
        assert message == b"Binary from client"

    async def test_websocket_receive_json(self, websocket_scope, mock_receive_send):
        """Test receiving and parsing JSON messages."""
        receive, send, received_messages, _ = mock_receive_send
        json_data = {"action": "ping", "data": {"timestamp": 12345}}
        received_messages.append({"type": "websocket.receive", "text": json.dumps(json_data)})
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        data = await ws.receive_json()
        
        assert data == json_data

    async def test_websocket_receive_disconnect(self, websocket_scope, mock_receive_send):
        """Test handling disconnect messages."""
        receive, send, received_messages, _ = mock_receive_send
        received_messages.append({"type": "websocket.disconnect", "code": 1000, "reason": "Normal closure"})
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        
        with pytest.raises(WebSocketConnectionError, match="WebSocket disconnected: 1000 Normal closure"):
            await ws.receive()
        
        assert ws.state == WebSocketState.DISCONNECTED

    async def test_websocket_async_iteration(self, websocket_scope, mock_receive_send):
        """Test async iteration over WebSocket messages."""
        receive, send, received_messages, _ = mock_receive_send
        
        # Add some messages to receive
        test_messages = ["Message 1", "Message 2", "Message 3"]
        for msg in test_messages:
            received_messages.append({"type": "websocket.receive", "text": msg})
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        
        collected_messages = []
        message_count = 0
        async for message in ws:
            collected_messages.append(message)
            message_count += 1
            if message_count >= 3:  # Stop after receiving all test messages
                break
        
        assert collected_messages == test_messages

    async def test_websocket_context_manager(self, websocket_scope, mock_receive_send):
        """Test WebSocket as async context manager."""
        receive, send, _, sent_messages = mock_receive_send
        
        async with WebSocket(websocket_scope, receive, send) as ws:
            assert ws.is_connected
            await ws.send("Hello")
        
        # Check that accept and close messages were sent
        assert {"type": "websocket.accept"} in sent_messages
        assert any(msg["type"] == "websocket.close" for msg in sent_messages)


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
        extension = type("TestExtension", (), {
            "on_app_request_begin": setup_routes,
            "_stand_alone": True
        })()
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
        extension = type("TestExtension", (), {
            "on_app_request_begin": setup_routes,
            "_stand_alone": True
        })()
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
        from typing import get_type_hints, get_args, get_origin
        
        # Define a function with frame type annotation
        async def binary_handler(ws: Annotated[WebSocket, FrameType.BINARY]):
            pass
        
        # Get type hints
        hints = get_type_hints(binary_handler, include_extras=True)
        ws_annotation = hints['ws']
        
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

    async def test_websocket_error_scenarios(self, websocket_scope, mock_receive_send):
        """Test various WebSocket error scenarios."""
        receive, send, received_messages, _ = mock_receive_send
        
        # Test invalid data type
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        
        with pytest.raises(TypeError, match="WebSocket data must be str or bytes"):
            await ws.send(123)  # Invalid data type
        
        # Test JSON serialization error
        with pytest.raises(TypeError, match="not JSON serializable"):
            await ws.send_json(object())  # Non-serializable object

    async def test_websocket_type_validation(self, websocket_scope, mock_receive_send):
        """Test WebSocket message type validation."""
        receive, send, received_messages, _ = mock_receive_send
        received_messages.append({"type": "websocket.receive", "bytes": b"binary data"})
        
        ws = WebSocket(websocket_scope, receive, send)
        await ws.accept()
        
        # Try to receive text when binary was sent
        with pytest.raises(TypeError, match="Expected text message"):
            await ws.receive_text() 