# Serv Usage Guide

This document provides a guide to understanding and using the Serv web framework, covering core concepts such as dependency injection, routing, plugins, middleware, and the command-line interface (CLI).

## Table of Contents

1.  [Core Concepts](#core-concepts)
    *   [Dependency Injection (DI)](#dependency-injection-di)
    *   [Routing](#routing)
    *   [Extensions](#plugins)
    *   [Middleware](#middleware)
2.  [Command-Line Interface (CLI)](#command-line-interface-cli)
3.  [Testing](#testing)
4.  [Getting Started (Example from `demos/basic_app`)](#getting-started-example-from-demosbasic_app)

## Core Concepts

### Dependency Injection (DI)

Serv leverages the `bevy` library for dependency injection. This allows for clean, decoupled, and testable code. Dependencies are typically injected into handler functions or class methods by type-hinting parameters with `bevy.dependency()` or specific types that Serv knows how to provide.

**Example (from `demos/basic_app/main.py`):**

```python
from serv.responses import ResponseBuilder
from bevy import dependency

async def homepage(response: ResponseBuilder = dependency()):
    response.content_type("text/plain")
    response.body("Hello from Serv! This is the basic demo.")
```

In this example, `ResponseBuilder` is automatically injected into the `homepage` handler. Serv pre-registers common types like `Request`, `ResponseBuilder`, and the `Container` itself. Extensions and middleware can also have dependencies injected.

### Routing

Routing in Serv maps URL paths (and HTTP methods) to handler functions or methods within `Route` classes.

**1. Simple Functional Handlers:**

You can define simple `async` functions as handlers and add them to a router, typically within a plugin.

*   **Definition (`demos/basic_app/main.py`):**
    ```python
    async def homepage(response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body("Hello from Serv! This is the basic demo.")
    ```

* **Registration (within a Extension in `demos/basic_app/main.py`):**
  ```python
  from serv.plugins.routing import Router
  from serv.plugins import Extension
  from bevy import dependency

  class BasicAppExtension(Extension):
      async def on_app_request_begin(self, router: Router = dependency()):
          router.add_route("/", homepage) # GET by default
          router.add_route("/about", about_page, methods=["GET"]) # Explicit method
  ```
    The `router.add_route()` method is used. If `methods` is not specified, it typically defaults to `GET`.

**2. Class-Based Routes (`serv.routes.Route`):**

For more complex scenarios or to group related endpoints, you can create classes that inherit from `serv.routes.Route`.

* **Definition (`demos/complex_route_demo/demo.py`):**
  ```python
  from typing import Annotated, Any
  from serv.plugins.routes import Route, GetRequest, Form, Jinja2Response, HtmlResponse
  from dataclasses import dataclass

  class HomeRoute(Route):
      async def show_home_page(
          self, request: GetRequest # Method determined by GetRequest
      ) -> Annotated[
          tuple[str, dict[str, Any]], # (template_name, context)
          Jinja2Response # Response type
      ]:
          return "home.html", {"request": request}

  @dataclass
  class UserForm(Form): # Define a form data structure
      name: str
      email: str
      # __form_method__ defaults to "POST" if not specified

  class SubmitRoute(Route):
      async def receive_form_submission(
          self, form: UserForm # Handles POST requests with matching form data
      ) -> Annotated[str, HtmlResponse]:
          return f"<h1>Submission Received!</h1><p>Thanks, {form.name}!</p>"
  ```
    - Serv inspects methods in `Route` subclasses.
    - If a method's first argument (after `self`) is type-hinted with a specific request type (e.g., `GetRequest`, `PostRequest` from `serv.requests`), that method becomes the handler for the corresponding HTTP method.
    - If a method's first argument is type-hinted with a `Form` subclass (from `serv.routes`), it becomes a handler for form submissions matching that form's structure and `__form_method__` (default POST).
    - `Annotated` return types (e.g., `Annotated[str, HtmlResponse]`) instruct Serv on how to process the return value into an HTTP response. `Jinja2Response` renders a Jinja2 template.

* **Registration (within a Extension in `demos/complex_route_demo/plugins.py`):**
  ```python
  from serv.plugins.routing import Router
  from serv.plugins import Extension
  from bevy import dependency
  from .demo import HomeRoute, SubmitRoute # Assuming demo.py is in the same directory

  class DemoRoutesExtension(Extension):
      async def on_app_request_begin(self, router: Router = dependency()):
          router.add_route("/", HomeRoute) # Registers all handlers in HomeRoute for "/"
          router.add_route("/submit", SubmitRoute)
  ```
    When `router.add_route()` receives a `Route` class, it registers all implicitly discovered handlers (method-based and form-based) from that class.

**3. Path Parameters:**

The router supports basic path parameters using curly braces:

*   **Matching Logic (`serv/routing.py -> Router._match_path`):**
    ```python
    # Simplified example of how it works
    # pattern_parts = "/users/{id}".strip("/").split("/") -> ["users", "{id}"]
    # request_parts = "/users/123".strip("/").split("/") -> ["users", "123"]
    # params["id"] = "123"
    ```
    Captured parameters are passed as keyword arguments to your handler function or method.

**4. Multiple Routers & Sub-Routers:**

Serv supports multiple router instances. Middleware can be used to select which router handles a request.

*   **Example (`demos/cookie_form_app/main.py`):**
    ```python
    form_router = Router()
    welcome_router = Router()

    # ... routes added to form_router and welcome_router ...

    async def cookie_based_router_middleware(router: Router = dependency(), username: Annotated[str, Cookie("username", default="")] = dependency()) -> AsyncIterator[None]:
        if username:
            router.add_router(welcome_router) # Add welcome_router as a sub-router to the main request router
        else:
            router.add_router(form_router)
        yield
    
    app.add_middleware(cookie_based_router_middleware)
    ```
    The `app.add_middleware()` registers the `cookie_based_router_middleware`. Inside the middleware, `router.add_router()` dynamically adds one of the pre-configured routers (`welcome_router` or `form_router`) as a sub-router to the main router instance created for the request. The main router then delegates to this sub-router. Sub-routers are checked in LIFO order.

### Extensions

Extensions are the primary way to organize and extend Serv applications. They can define routes, event listeners, and their own configurations.

*   **Structure (`serv/plugins.py`):**
    Extensions are classes that inherit from `serv.plugins.Extension`.

*   **Event Handling:**
    Extensions respond to application events by defining methods with names like `on_{event_name}` (e.g., `on_app_request_begin`, `on_lifespan_startup`). The `App`'s `emit` method triggers these.
    ```python
    # Example from demos/basic_app/main.py
    class BasicAppExtension(Extension):
        async def on_app_request_begin(self, router: Router = dependency()):
            router.add_route("/", homepage)
            router.add_route("/about", about_page)
    ```
    The `on_app_request_begin` event is commonly used to add routes.

*   **Extension Configuration (`plugin.yaml`):**
    Extensions can have their own `plugin.yaml` file in their directory. This file can define metadata (name, version, entry point) and plugin-specific configuration.
    The `Extension.config()` method can be used to access this configuration, though specific mechanisms for DI of this config into handlers might vary or be evolving. The CLI (`serv create plugin --name "Extension Name"`) scaffolds this file.

*   **Loading Extensions:**
    Extensions are typically added to the `App` instance or configured via `serv.config.yaml`.
    ```python
    # Direct addition (demos/basic_app/main.py)
    app = App()
    app.add_plugin(BasicAppExtension())
    ```
    Or via `serv.config.yaml` (handled by the CLI or `setup_app_from_config`):
    ```yaml
    # serv.config.yaml
    plugins:
      - entry: my_project.my_plugins:MyExtension
        config:
          some_setting: value
    ```

### Middleware

Middleware components process requests before they reach route handlers and process responses before they are sent to the client. They are useful for tasks like authentication, logging, request modification, or dynamic routing.

*   **Structure:**
    Middleware are `async` generator functions that take dependencies (like `Router`, `Request`, or custom services) via `bevy`. They `yield` control to the next item in the processing chain (another middleware or the router/handler).

* **Example (`demos/cookie_form_app/main.py`):**
  ```python
  from typing import Annotated, AsyncIterator
  from serv.plugins.routing import Router
  from serv.injectors import Cookie # For injecting cookie values
  from bevy import dependency

  async def cookie_based_router_middleware(
      router: Router = dependency(), 
      username: Annotated[str, Cookie("username", default="")] = dependency()
  ) -> AsyncIterator[None]:
      if username:
          print(f"Username cookie found: '{username}'. Setting welcome_router.")
          router.add_router(welcome_router) # Dynamically add a router
      else:
          print("No username cookie. Setting form_router.")
          router.add_router(form_router)
      
      yield # Pass control to the selected router (or next middleware)
      
      # Code here would run after the request is handled (response phase)
      print("Cookie middleware finishing up.")

  app.add_middleware(cookie_based_router_middleware)
  ```
    - The middleware receives the main `Router` instance for the request.
    - It uses an injected cookie value (`username`) to decide which specialized router (`welcome_router` or `form_router`) to add to the main router using `router.add_router()`.
    - `yield` passes control. Code after `yield` executes during the response phase, allowing modification or observation of the response.

*   **Execution Order (`serv/app.py -> App._run_middleware_stack`):**
    Middleware are executed in the order they are added for the request phase. During the response phase (after `yield`), they are executed in reverse order.

## Command-Line Interface (CLI)

Serv includes a CLI for managing projects, plugins, and running the application. It is accessed via the `serv` command.

Key commands (discovered from `serv/cli.py` and `serv/bundled_plugins/welcome/templates/welcome.html`):

*   **`serv app init`**:
    Initializes a new Serv project by creating a `serv.config.yaml` file. This file is used to configure the application, including site information, plugins, and middleware.
    ```bash
    serv app init
    ```
    Use `--force` to overwrite an existing configuration file.

*   **`serv app details`**:
    Displays the loaded application configuration from `serv.config.yaml`, showing how Serv interprets the file, including resolved plugin paths.
    ```bash
    serv app details
    ```

*   **`serv launch`**:
    Starts the Uvicorn development server to run your Serv application.
    ```bash
    serv launch [app_module] [--host HOST] [--port PORT] [--reload] [--workers N] [--config PATH] [--factory]
    ```
    - `app_module`: The application instance or factory to run (e.g., `my_app.main:app`). Defaults to `serv.app:App`.
    - `--host`: Host to bind to (default: `127.0.0.1` or `SERV_HOST` env var).
    - `--port`: Port to bind to (default: `8000` or `SERV_PORT` env var).
    - `--reload`: Enable auto-reload on code changes (or `SERV_RELOAD` env var).
    - `--workers`: Number of worker processes (default: 1).
    - `--config`: Path to `serv.config.yaml` (default: `serv.config.yaml` in CWD or `SERV_CONFIG_PATH` env var).
    - `--factory`: Treat `app_module` as an application factory.

*   **`serv create plugin`**:
    Scaffolds a new plugin structure, creating a directory (usually under `./plugins/`), a `plugin.yaml` definition file, and a `main.py` template for your plugin class.
    ```bash
    serv create plugin --name "My Extension Name"
    ```
    You'll be prompted for plugin details (author, description, version, etc.).

*   **`serv plugin enable <plugin_identifier>`**:
    Enables a plugin by adding its entry to the `serv.config.yaml` file.
    `<plugin_identifier>` can be a simple name (if the plugin is in `./plugins/` and has a `plugin.yaml`) or a full module path (e.g., `my_package.plugins:MyExtension`).
    ```bash
    serv plugin enable my_cool_plugin
    serv plugin enable some.other.module:AnotherExtension
    ```

*   **`serv plugin disable <plugin_identifier>`**:
    Disables a plugin by removing its entry from `serv.config.yaml`.
    ```bash
    serv plugin disable my_cool_plugin
    ```

*   **`serv --version`**: Displays Serv CLI version.
*   **`serv --debug`**: Enables debug logging for the CLI.

## Testing

Serv provides comprehensive testing utilities to make testing your applications easy and efficient. The primary testing approach uses the `create_test_app_client` function, which creates a test client that mirrors the CLI's functionality without needing to run a server.

### Test Client Factory (`create_test_app_client`)

The `create_test_app_client` function creates an httpx AsyncClient that wraps your Serv application, supporting all the same configuration options as the `serv launch` command.

**Basic Usage:**

```python
import pytest
from pathlib import Path
from serv import create_test_app_client

@pytest.mark.asyncio
async def test_basic_functionality():
    async with create_test_app_client(Path("serv.config.yaml")) as client:
        response = await client.get("/")
        assert response.status_code == 200
```

**Supported Parameters:**

The function accepts the same parameters as the CLI launch command:

- `config_path` - Path to config file (required)
- `dev=True` - Enable development mode (equivalent to `--dev`)
- `extension_dirs="./custom"` - Custom extension directory (equivalent to `--extension-dirs`)
- `app_module_str="myapp:create_app"` - Custom app factory (equivalent to `--app`)
- `dry_run=True` - Validate app creation only (equivalent to `--dry-run`)
- `host`, `port`, `reload`, `workers` - Server settings (used only in dry run output)
- `base_url` - Custom base URL for test requests
- `use_lifespan=True` - Enable/disable lifespan event handling
- `timeout=5.0` - Request timeout in seconds

**Development Mode Testing:**

```python
@pytest.mark.asyncio
async def test_development_features():
    async with create_test_app_client(
        Path("serv.config.yaml"), 
        dev=True  # Enable enhanced error reporting and debug features
    ) as client:
        response = await client.get("/debug-endpoint")
        assert response.status_code == 200
```

**Custom Extension Directory:**

```python
@pytest.mark.asyncio
async def test_with_custom_extensions():
    async with create_test_app_client(
        Path("test.config.yaml"),
        extension_dirs="./test_extensions"  # Use test-specific extensions
    ) as client:
        response = await client.get("/test-specific-endpoint")
        assert response.status_code == 200
```

**Testing Different HTTP Methods:**

```python
@pytest.mark.asyncio
async def test_api_endpoints():
    async with create_test_app_client(Path("api.config.yaml")) as client:
        # Test POST request with JSON data
        response = await client.post("/api/users", json={
            "name": "Test User",
            "email": "test@example.com"
        })
        assert response.status_code == 201
        user_data = response.json()
        
        # Test GET request with path parameters
        user_id = user_data["id"]
        response = await client.get(f"/api/users/{user_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Test User"
        
        # Test PUT request for updates
        response = await client.put(f"/api/users/{user_id}", json={
            "name": "Updated User"
        })
        assert response.status_code == 200
        
        # Test DELETE request
        response = await client.delete(f"/api/users/{user_id}")
        assert response.status_code == 204
```

**Form Testing:**

```python
@pytest.mark.asyncio
async def test_form_submission():
    async with create_test_app_client(Path("form.config.yaml")) as client:
        # Test form submission with form data
        response = await client.post("/contact", data={
            "name": "John Doe",
            "email": "john@example.com",
            "message": "Hello from test!"
        })
        assert response.status_code == 200
        assert "Thanks John!" in response.text
```

**File Upload Testing:**

```python
@pytest.mark.asyncio
async def test_file_upload():
    async with create_test_app_client(Path("upload.config.yaml")) as client:
        # Test file upload
        files = {"file": ("test.txt", b"Test file content", "text/plain")}
        response = await client.post("/upload", files=files)
        assert response.status_code == 200
        assert "File uploaded successfully" in response.json()["message"]
```

**Error Handling Testing:**

```python
@pytest.mark.asyncio
async def test_error_handling():
    async with create_test_app_client(Path("serv.config.yaml")) as client:
        # Test 404 handling
        response = await client.get("/nonexistent")
        assert response.status_code == 404
        
        # Test validation errors
        response = await client.post("/api/users", json={})  # Missing required fields
        assert response.status_code == 422
```

**Dry Run Mode:**

Use dry run mode to validate app configuration without making requests:

```python
@pytest.mark.asyncio
async def test_app_configuration():
    # This validates that the app can be created with the given config
    async with create_test_app_client(Path("serv.config.yaml"), dry_run=True) as client:
        assert client is None  # No client returned in dry run mode
    # If we reach here, the app was created successfully
```

**Testing with Custom App Classes:**

```python
@pytest.mark.asyncio
async def test_custom_app():
    async with create_test_app_client(
        Path("custom.config.yaml"),
        app_module_str="myproject.app:CustomApp"
    ) as client:
        response = await client.get("/custom-feature")
        assert response.status_code == 200
```

**Configuration File Not Found:**

```python
@pytest.mark.asyncio
async def test_missing_config():
    with pytest.raises(FileNotFoundError):
        async with create_test_app_client(Path("nonexistent.yaml")) as client:
            pass
```

### Best Practices for Testing

1. **Use separate test configurations**: Create test-specific `serv.config.yaml` files that use test databases and minimal extensions.

2. **Test in isolation**: Each test should use its own client instance and not depend on other tests.

3. **Test both success and failure cases**: Include tests for error conditions, validation failures, and edge cases.

4. **Use meaningful assertions**: Check both status codes and response content to ensure correctness.

5. **Organize tests by functionality**: Group related tests into classes or modules based on the features they test.

Example test organization:

```python
class TestUserAPI:
    @pytest.mark.asyncio
    async def test_create_user(self):
        async with create_test_app_client(Path("test.config.yaml")) as client:
            # Test user creation
            pass
    
    @pytest.mark.asyncio
    async def test_get_user(self):
        async with create_test_app_client(Path("test.config.yaml")) as client:
            # Test user retrieval
            pass

class TestAuthenticationAPI:
    @pytest.mark.asyncio
    async def test_login(self):
        async with create_test_app_client(Path("test.config.yaml")) as client:
            # Test login functionality
            pass
```

## Getting Started (Example from `demos/basic_app`)

This example demonstrates a minimal Serv application using a plugin for routing.

**`demos/basic_app/main.py`:**

```python
from serv.app import App
from serv.plugins import Extension
from serv.responses import ResponseBuilder
from bevy import dependency
from serv.plugins.routing import Router


# 1. Define Handlers
async def homepage(response: ResponseBuilder = dependency()):
    response.content_type("text/plain")
    response.body("Hello from Serv! This is the basic demo.")


async def about_page(response: ResponseBuilder = dependency()):
    response.content_type("text/html")
    response.body("<h1>About Us</h1><p>This is a simple demo of the Serv framework.</p>")


# 2. Create a Extension to Register Routes
class BasicAppExtension(Extension):
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_route("/", homepage)
        router.add_route("/about", about_page)


# 3. Create App Instance and Add Extension
app = App()
app.add_plugin(BasicAppExtension())

# 4. Run with Uvicorn (if script is run directly)
if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("Uvicorn is not installed. Please install it with: pip install uvicorn")
    else:
        print("Starting Serv basic demo on http://127.0.0.1:8000")
        print("Press Ctrl+C to stop.")
        uvicorn.run(app, host="127.0.0.1", port=8000)
```

**To Run This Demo:**

1.  Ensure Serv and Uvicorn are installed.
2.  Navigate to the `demos/basic_app/` directory.
3.  Run `python main.py`.
4.  Access `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/about` in your browser.

Alternatively, you could configure this app via `serv.config.yaml` and run it using `serv launch`. 