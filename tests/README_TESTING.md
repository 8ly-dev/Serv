# End-to-End Testing in Serv

This document explains how to use the end-to-end testing tools provided in the `tests/e2e_test_helpers.py` module.

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
async with create_test_client(
    app_factory=my_app_factory,
    plugins=[MyExtension()],
    base_url="http://testserver",
    use_lifespan=True
) as client:
    response = await client.get("/my-endpoint")
    assert response.status_code == 200
```

### `TestAppBuilder`

A builder class for creating test applications with a fluent interface:

```python
builder = TestAppBuilder().with_plugin(MyExtension()).with_dev_mode(True)
app = builder.build()

# Or create a client directly:
async with builder.build_client() as client:
    response = await client.get("/endpoint")
    assert response.status_code == 200
```

### Pytest Fixtures

Two pytest fixtures are available in `conftest.py`:

1. `app_test_client`: Returns the `create_test_client` function
2. `app_builder`: Returns a new `TestAppBuilder` instance

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
async def test_with_custom_app():
    def create_my_app():
        app = App(dev_mode=True)
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

### Testing Multiple App Configurations

```python
@pytest.mark.asyncio
async def test_different_configs():
    # First configuration
    async with create_test_client(plugins=[ConfigExtension(debug=True)]) as debug_client:
        debug_response = await debug_client.get("/status")
        assert "debug_info" in debug_response.json()
    
    # Second configuration
    async with create_test_client(plugins=[ConfigExtension(debug=False)]) as prod_client:
        prod_response = await prod_client.get("/status")
        assert "debug_info" not in prod_response.json()
```

## Tips for Effective Testing

1. **Create Reusable Test Extensions**: Define test-specific plugins that help set up common test scenarios.

2. **Test Lifespan Events**: Use `use_lifespan=True` to test that your application correctly handles startup and shutdown events.

3. **Isolate Tests**: Each test should create its own application instance to prevent state leakage between tests.

4. **Use Custom App Factories**: For complex setups, create functions that return fully configured application instances.

5. **Test Edge Cases**: Test error handling, unusual inputs, and boundary conditions.

## Creating Test Extensions

For testing, you can create simple plugins that implement specific functionality:

```python
class TestRouteExtension(Extension):
    def __init__(self, path, response_text):
        self.path = path
        self.response_text = response_text
        self._stand_alone = True
        
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_route(self.path, self._handler, methods=["GET"])
        
    async def _handler(self, response: ResponseBuilder = dependency()):
        response.body(self.response_text)
```

## Example Tests

See `tests/test_e2e_example.py` for comprehensive examples of using these testing tools. 