# End-to-End Testing in Serv

This directory contains tools and examples for end-to-end testing of Serv applications.

## Overview

End-to-end testing is crucial for validating that your Serv application works correctly from the user's perspective. The testing tools in this package allow you to:

1. Create test instances of your application
2. Make HTTP requests to these instances
3. Validate the responses without running a full server

The tests use HTTPX's `AsyncClient` with an `ASGITransport` to communicate with your app directly, without needing to bind to a port or start a server process.

## Available Tools

### `create_test_client`

The primary function for creating a test client:

```python
from tests.e2e.helpers import create_test_client

async with create_test_client(
    app_factory=my_app_factory,
    plugins=[MyExtension()],
    base_url="http://testserver",
    use_lifespan=False
) as client:
    response = await client.get("/my-endpoint")
    assert response.status_code == 200
```

### `TestAppBuilder`

A builder class for creating test applications with a fluent interface:

```python
from tests.e2e.helpers import TestAppBuilder

builder = TestAppBuilder().with_plugin(MyExtension()).with_dev_mode(True)
app = builder.build()

# Or create a client directly:
async with builder.build_client() as client:
    response = await client.get("/endpoint")
    assert response.status_code == 200
```

### Pytest Fixtures

Several pytest fixtures are available in `conftest.py`:

1. `app`: Returns a basic App instance
2. `test_client`: Returns an AsyncClient configured with the app
3. `app_factory`: Returns a factory function for creating app instances
4. `app_builder`: Returns a new TestAppBuilder instance

## Example Patterns

### Basic Usage

```python
@pytest.mark.asyncio
async def test_basic_route():
    async with create_test_client(plugins=[MyExtension()]) as client:
        response = await client.get("/hello")
        assert response.status_code == 200
        assert response.text == "Hello, World!"
```

### Using a Custom App Factory

```python
@pytest.mark.asyncio
async def test_with_custom_app(app_factory):
    def create_my_app():
        app = app_factory()
        app.add_plugin(MyExtension())
        return app
    
    async with create_test_client(app_factory=create_my_app) as client:
        response = await client.get("/endpoint")
        assert response.status_code == 200
```

### Using the TestAppBuilder

```python
@pytest.mark.asyncio
async def test_with_builder(app_builder):
    builder = (
        app_builder
        .with_plugin(RouteExtension("/api/users", my_handler))
        .with_config({"debug": True})
    )
    
    async with builder.build_client() as client:
        response = await client.get("/api/users")
        assert response.status_code == 200
        assert "users" in response.json()
```

### Using the Provided Fixtures

```python
@pytest.mark.asyncio
async def test_with_fixtures(app, test_client):
    # Add a plugin to the app
    app.add_plugin(MyExtension())
    
    # Use the test_client that's already configured with the app
    response = await test_client.get("/my-endpoint")
    assert response.status_code == 200
```

## Tips for Effective Testing

1. **Create Reusable Test Extensions**: Define test-specific plugins that help set up common test scenarios.

2. **Isolate Tests**: Each test should create its own application instance to prevent state leakage between tests.

3. **Use Custom App Factories**: For complex setups, create functions that return fully configured application instances.

4. **Test Edge Cases**: Test error handling, unusual inputs, and boundary conditions.

## Example Files

This directory includes several example files:

- `test_minimal.py`: Simple examples of basic e2e tests
- `test_example.py`: More comprehensive examples of different testing patterns
- `helpers.py`: Core utilities for e2e testing
- `conftest.py`: Pytest fixtures for e2e testing 