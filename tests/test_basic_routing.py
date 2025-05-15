import pytest
from httpx import AsyncClient

from serv.app import App
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.routing import get_current_router # To add routes in tests
from tests.helpers import RouteAddingPlugin, EventWatcherPlugin

@pytest.mark.asyncio
async def test_hello_world(app: App, client: AsyncClient):
    async def hello_handler(response: ResponseBuilder):
        response.content_type("text/plain")
        response.body("Hello, World!")

    plugin = RouteAddingPlugin("/hello", hello_handler, methods=["GET"])
    app.add_plugin(plugin)

    response = await client.get("/hello")
    assert response.status_code == 200
    assert response.text == "Hello, World!"
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert plugin.was_called

@pytest.mark.asyncio
async def test_not_found(client: AsyncClient):
    response = await client.get("/nonexistent")
    assert response.status_code == 404
    assert "Not Found" in response.text
    assert response.headers["content-type"] == "text/plain; charset=utf-8"

@pytest.mark.asyncio
async def test_method_not_allowed(app: App, client: AsyncClient):
    async def post_only_handler(response: ResponseBuilder):
        response.body("Processed POST")

    plugin = RouteAddingPlugin("/restricted", post_only_handler, methods=["POST"])
    app.add_plugin(plugin)

    response_get = await client.get("/restricted")
    assert response_get.status_code == 405
    assert "Method Not Allowed" in response_get.text
    assert "POST" in response_get.headers.get("allow", "")

    response_post = await client.post("/restricted")
    assert response_post.status_code == 200
    assert response_post.text == "Processed POST"
    assert plugin.was_called

@pytest.mark.asyncio
async def test_path_parameters(app: App, client: AsyncClient):
    async def user_handler(response: ResponseBuilder, user_id: str, item_id: str | None = None):
        if item_id:
            response.body(f"User: {user_id}, Item: {item_id}")
        else:
            response.body(f"User: {user_id}")

    plugin_user = RouteAddingPlugin("/users/{user_id}", user_handler, methods=["GET"])
    plugin_user_item = RouteAddingPlugin("/users/{user_id}/items/{item_id}", user_handler, methods=["GET"])
    app.add_plugin(plugin_user)
    app.add_plugin(plugin_user_item)

    response1 = await client.get("/users/123")
    assert response1.status_code == 200
    assert response1.text == "User: 123"
    assert plugin_user.was_called
    assert plugin_user.received_kwargs == {"user_id": "123"} 

    response2 = await client.get("/users/abc/items/xyz")
    assert response2.status_code == 200
    assert response2.text == "User: abc, Item: xyz"
    assert plugin_user_item.was_called
    assert plugin_user_item.received_kwargs == {"user_id": "abc", "item_id": "xyz"}

@pytest.mark.asyncio
async def test_request_events_emitted(app: App, client: AsyncClient):
    event_watcher = EventWatcherPlugin()
    app.add_plugin(event_watcher)

    async def dummy_handler(response: ResponseBuilder):
        response.body("dummy")

    route_plugin = RouteAddingPlugin("/events", dummy_handler, methods=["GET"])
    app.add_plugin(route_plugin)

    await client.get("/events")

    seen_event_names = [name for name, _ in event_watcher.events_seen]
    assert "app.request.begin" in seen_event_names
    assert "app.request.before_router" in seen_event_names
    assert "app.request.after_router" in seen_event_names
    assert "app.request.end" in seen_event_names

    # Check that error is None for successful request in after_router and end events
    for name, kwargs_evt in event_watcher.events_seen:
        if name == "app.request.after_router" or name == "app.request.end":
            assert "error" in kwargs_evt
            assert kwargs_evt["error"] is None 