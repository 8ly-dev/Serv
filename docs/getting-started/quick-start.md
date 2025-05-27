# Quick Start

Get up and running with Serv in just a few minutes! This guide will walk you through creating your first Serv application.

## Prerequisites

Make sure you have Serv installed. If not, check out the [Installation](installation.md) guide.

## Your First Serv App

Let's create a simple "Hello World" application:

### 1. Create the Application File

Create a new file called `app.py`:

```python
from serv import App
from serv.responses import ResponseBuilder
from serv.plugins import Plugin
from serv.plugins.routing import Router
from bevy import dependency

async def hello_world(response: ResponseBuilder = dependency()):
    response.content_type("text/plain")
    response.body("Hello, World from Serv!")

async def greet_user(name: str, response: ResponseBuilder = dependency()):
    response.content_type("text/html")
    response.body(f"<h1>Hello, {name}!</h1><p>Welcome to Serv!</p>")

class HelloPlugin(Plugin):
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_route("/", hello_world)
        router.add_route("/greet/{name}", greet_user)

# Create the app and add our plugin
app = App()
app.add_plugin(HelloPlugin())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 2. Run the Application

Run your application:

```bash
python app.py
```

Or using uvicorn directly:

```bash
uvicorn app:app --reload
```

### 3. Test Your Application

Open your browser and visit:

- `http://localhost:8000/` - See the hello world message
- `http://localhost:8000/greet/YourName` - See a personalized greeting

## Understanding the Code

Let's break down what's happening in this simple application:

### The Plugin System

```python
class HelloPlugin(Plugin):
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_route("/", hello_world)
        router.add_route("/greet/{name}", greet_user)
```

- **Plugins** are the building blocks of Serv applications
- The `on_app_request_begin` event is called for every request
- We use dependency injection to get the `Router` instance
- Routes are added using `router.add_route()`

### Dependency Injection

```python
async def hello_world(response: ResponseBuilder = dependency()):
    response.content_type("text/plain")
    response.body("Hello, World from Serv!")
```

- Serv uses the `bevy` library for dependency injection
- `ResponseBuilder` is automatically injected into your handler functions
- No need to manually pass objects around!

### Path Parameters

```python
async def greet_user(name: str, response: ResponseBuilder = dependency()):
    # The 'name' parameter is extracted from the URL path
```

- Path parameters are defined using `{parameter_name}` in the route
- They're automatically passed to your handler function

## Adding JSON Responses

Let's add an API endpoint that returns JSON:

```python
import json

async def api_hello(response: ResponseBuilder = dependency()):
    response.content_type("application/json")
    data = {
        "message": "Hello from Serv API!",
        "framework": "Serv",
        "version": "0.1.0"
    }
    response.body(json.dumps(data))

# Add this route in your plugin:
router.add_route("/api/hello", api_hello)
```

## Using the CLI

Serv comes with a powerful CLI for scaffolding and managing projects:

### Create a New Project

```bash
serv project create my-awesome-app
cd my-awesome-app
```

### Create a Plugin

```bash
serv plugin create my-plugin
```

### Run the Development Server

```bash
serv launch --dev
```

## Configuration with YAML

For more complex applications, you can use YAML configuration. Create a `serv.config.yaml` file:

```yaml
plugins:
  - plugin: my_plugin
    settings:
      debug: true
      api_key: "your-api-key"
```

Then load it in your app:

```python
app = App(config="./serv.config.yaml")
```

## Next Steps

Congratulations! You've created your first Serv application. Here's what to explore next:

### Learn More About Core Concepts

- **[Routing](../guides/routing.md)** - Advanced routing patterns and techniques
- **[Dependency Injection](../guides/dependency-injection.md)** - Master the DI system
- **[Plugins](../guides/plugins.md)** - Build powerful, reusable plugins

### Build a Complete Application

- **[Your First App](first-app.md)** - Step-by-step tutorial for a complete web application
- **[Configuration](configuration.md)** - Learn about advanced configuration options

### Explore Examples

- **[Basic App](../examples/basic-app.md)** - More detailed basic application examples
- **[Plugin Development](../examples/plugin-development.md)** - Learn to build custom plugins
- **[Advanced Routing](../examples/advanced-routing.md)** - Complex routing scenarios

## Common Patterns

### Error Handling

```python
from serv.exceptions import HTTPNotFoundException

async def not_found_handler(response: ResponseBuilder = dependency()):
    response.set_status(404)
    response.content_type("text/html")
    response.body("<h1>Page Not Found</h1>")

# Add custom error handlers
app.add_error_handler(HTTPNotFoundException, not_found_handler)
```

### Middleware

```python
from typing import AsyncIterator

async def logging_middleware() -> AsyncIterator[None]:
    print("Request started")
    yield
    print("Request finished")

app.add_middleware(logging_middleware)
```

### Multiple HTTP Methods

```python
async def handle_post(response: ResponseBuilder = dependency()):
    response.body("POST request received")

# Add route with specific HTTP method
router.add_route("/submit", handle_post, methods=["POST"])
```

Ready to dive deeper? Continue with [Your First App](first-app.md) for a comprehensive tutorial! 