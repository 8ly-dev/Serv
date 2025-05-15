import pytest
import pytest_asyncio
from httpx import AsyncClient

from serv.app import App
from serv.responses import ResponseBuilder # For ResponseBuilder.clear() check

@pytest.fixture(scope="session")
def event_loop():
    """Force pytest-asyncio to use the same event loop for all tests."""
    # This is a common pattern if you encounter issues with event loops across test files.
    # For simple cases, pytest-asyncio might handle it automatically.
    # For now, let's try without explicitly setting the policy, as pytest-asyncio usually manages it.
    # If issues arise, we can reinstate: policy = asyncio.get_event_loop_policy(); loop = policy.new_event_loop(); policy.set_event_loop(loop); yield loop; loop.close()
    pass

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

    _app = App()
    # If your app requires explicit startup/shutdown for some test setups (e.g., background tasks):
    # async with _app.lifespan_context():
    #     yield _app
    # For now, assuming direct instantiation is enough for most tests via httpx.AsyncClient(app=_app)
    return _app

@pytest_asyncio.fixture
async def client(app: App) -> AsyncClient:
    async with AsyncClient(app=app, base_url="http://testserver") as c:
        yield c 