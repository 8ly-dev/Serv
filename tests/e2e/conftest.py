"""
Pytest fixtures for end-to-end testing of Serv applications.
"""

import pytest
import pytest_asyncio

from serv.app import App
from serv.responses import ResponseBuilder
from tests.e2e.helpers import AppBuilder, create_test_client


@pytest_asyncio.fixture
async def app() -> App:
    """
    Creates a basic Serv App instance for testing.

    This fixture ensures ResponseBuilder has a clear method for error handling.
    """
    # Ensure ResponseBuilder has a clear method, as app.py error handling relies on it.
    if not hasattr(ResponseBuilder, "clear"):

        def clear_stub(self_rb):
            self_rb._status = 200
            self_rb._headers = []
            self_rb._body_components = []
            self_rb._has_content_type = False

        ResponseBuilder.clear = clear_stub

    return App(dev_mode=True)


@pytest_asyncio.fixture
async def test_client(app: App):
    """
    Creates an AsyncClient instance for the provided app.

    This is a basic client with no lifespan events or plugins.
    For more complex setups, use the create_test_client function directly.
    """
    async with create_test_client(app_factory=lambda: app) as client:
        yield client


@pytest.fixture
def app_factory() -> App:
    """
    Returns a factory function for creating App instances.

    This is useful when you need to create multiple app instances
    with different configurations in the same test.
    """

    def _create_app(**kwargs):
        return App(dev_mode=True, **kwargs)

    return _create_app


@pytest.fixture
def app_builder() -> AppBuilder:
    """
    Returns a AppBuilder instance.

    This allows tests to create customized app instances with a fluent interface.

    Usage:
        ```
        @pytest.mark.asyncio
        async def test_with_builder(app_builder):
            builder = app_builder.with_plugin(MyExtension())

            # Use as a factory for app instance
            app = builder.build()

            # Or directly as a test client
            async with builder.build_client() as client:
                response = await client.get("/my-endpoint")
                assert response.status_code == 200
        ```
    """
    return AppBuilder()
