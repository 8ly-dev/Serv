"""Serv - A modern Python web framework built for simplicity and extensibility.

Serv is an ASGI-based web framework that emphasizes:
- Extension-based architecture for extensible functionality
- Dependency injection for clean, testable code
- Type-safe request/response handling
- Automatic route discovery and URL generation
- Built-in form handling and validation
- Middleware support for cross-cutting concerns
- Template rendering with Jinja2
- Event-driven extension system
- WebSocket support for real-time communication

Quick Start:
    ```python
    from serv import App
    from serv.routes import Route, GetRequest
    from serv.responses import TextResponse
    from typing import Annotated

    # Create the application
    app = App()

    # Define a route
    class HelloRoute(Route):
        async def handle_get(self, request: GetRequest) -> Annotated[str, TextResponse]:
            name = request.query_params.get("name", "World")
            return f"Hello, {name}!"

    # Run with: uvicorn main:app --reload
    ```

WebSocket Support:
    ```python
    from serv import App, WebSocket
    from serv.websocket import FrameType
    from typing import Annotated

    app = App()

    # Simple echo WebSocket handler
    async def websocket_handler(websocket: WebSocket):
        async for message in websocket:
            await websocket.send(message)

    # Binary WebSocket handler
    async def binary_handler(ws: Annotated[WebSocket, FrameType.BINARY]):
        async for message in ws:
            # message is bytes
            await ws.send(message)
    ```

Key Components:
    - App: Main application class and ASGI entry point
    - Route: Base class for HTTP route handlers
    - WebSocket: WebSocket connection handler for real-time communication
    - Extension: Base class for extending application functionality
    - Router: URL routing and path matching
    - ResponseBuilder: Fluent response construction
    - Request types: Type-safe request handling (GetRequest, PostRequest, etc.)
    - Response types: Structured response objects (JsonResponse, HtmlResponse, etc.)
    - Forms: Automatic form parsing and validation
    - Exceptions: HTTP-aware exception handling

For detailed documentation and examples, visit: https://serv.dev/docs
"""

from serv.app import App
from serv.routes import handle
from serv.websocket import WebSocket

__all__ = ["App", "handle", "WebSocket"]
