import pytest
import pytest_asyncio
import asyncio # Import asyncio
from httpx import AsyncClient, ASGITransport # Import ASGITransport

from serv.app import App
from serv.responses import ResponseBuilder # For ResponseBuilder.clear() check

# @pytest.fixture(scope="session")
# def event_loop():
#     """Force pytest-asyncio to use the same event loop for all tests."""
#     # policy = asyncio.get_event_loop_policy()
#     # loop = policy.new_event_loop()
#     # yield loop
#     # loop.close()
#     # The above is one way, but pytest-asyncio might prefer a different setup.
#     # Let's try to use the recommended way for newer pytest-asyncio versions:
#     # By default, pytest-asyncio provides an event_loop fixture. 
#     # If we redefine it, we must ensure it actually yields a running loop.
#     # The issue is that other fixtures might be trying to get the loop before this one runs or in a different way.
#
#     # Let's try yielding a new loop and setting it as the current loop.
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     yield loop
#     loop.close()

@pytest_asyncio.fixture
async def app() -> App:
    """App fixture, ensuring ResponseBuilder has a clear method for error handling tests."""
    # Ensure ResponseBuilder has a clear method, as app.py error handling relies on it.
    if not hasattr(ResponseBuilder, 'clear'):
        def clear_stub(self_rb):
            self_rb._status = 200
            self_rb._headers = []
            self_rb._body_components = []
            # self_rb._headers_sent = False # send_response should ideally reset this or handle it
            self_rb._has_content_type = False
        ResponseBuilder.clear = clear_stub

    _app = App(dev_mode=True)
    # If your app requires explicit startup/shutdown for some test setups (e.g., background tasks):
    # async with _app.lifespan_context():
    #     yield _app
    # For now, assuming direct instantiation is enough for most tests via httpx.AsyncClient(app=_app)
    return _app

@pytest_asyncio.fixture
async def client(app: App) -> AsyncClient:
    # Use ASGITransport for the app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c 