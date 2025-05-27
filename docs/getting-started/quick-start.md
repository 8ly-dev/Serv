# Quick Start

Get up and running with Serv in just a few minutes! This guide will walk you through creating your first Serv application using the CLI-first approach.

## Prerequisites

Make sure you have Serv installed. If not, check out the [Installation](installation.md) guide.

## Your First Serv App

Let's create a simple "Hello World" application using Serv's CLI tools:

### 1. Initialize a New Project

Create a new Serv project:

```bash
serv app init my-first-app
cd my-first-app
```

This creates a basic project structure:

```
my-first-app/
├── serv.config.yaml    # Application configuration
├── plugins/            # Plugin directory
└── templates/          # Template directory (optional)
```

### 2. Create Your First Plugin

Create a plugin to handle your routes:

```bash
serv create plugin --name "Hello World"
```

This creates:

```
plugins/
└── hello_world/
    ├── __init__.py
    ├── plugin.yaml
    └── hello_world.py
```

### 3. Add Routes to Your Plugin

Add some routes using the CLI:

```bash
# Create a home page route
serv create route --name "home" --path "/" --plugin "hello_world"

# Create a greeting route with a parameter
serv create route --name "greet" --path "/greet/{name}" --plugin "hello_world"

# Create an API route
serv create route --name "api_hello" --path "/api/hello" --plugin "hello_world"
```

### 4. Implement Your Route Handlers

Edit the generated route files to add your logic:

**plugins/hello_world/route_home.py:**
```python
from serv.responses import ResponseBuilder
from bevy import dependency

async def Home(response: ResponseBuilder = dependency(), **path_params):
    """Handle requests to /"""
    response.content_type("text/html")
    response.body("""
    <h1>Hello, World from Serv!</h1>
    <p>Welcome to your first Serv application!</p>
    <ul>
        <li><a href="/greet/YourName">Personalized Greeting</a></li>
        <li><a href="/api/hello">JSON API</a></li>
    </ul>
    """)
```

**plugins/hello_world/route_greet.py:**
```python
from serv.responses import ResponseBuilder
from bevy import dependency

async def Greet(name: str, response: ResponseBuilder = dependency()):
    """Handle requests to /greet/{name}"""
    response.content_type("text/html")
    response.body(f"""
    <h1>Hello, {name}!</h1>
    <p>Welcome to Serv!</p>
    <p><a href="/">← Back to Home</a></p>
    """)
```

**plugins/hello_world/route_api_hello.py:**
```python
from typing import Annotated
from serv.routes import JsonResponse

async def ApiHello() -> Annotated[dict, JsonResponse]:
    """Handle requests to /api/hello"""
    return {
        "message": "Hello from Serv API!",
        "framework": "Serv",
        "version": "0.1.0",
        "status": "success"
    }
```

### 5. Enable Your Plugin

Enable the plugin in your application:

```bash
serv plugin enable hello_world
```

### 6. Run Your Application

Start the development server:

```bash
serv dev
```

Or use the standard launch command:

```bash
serv launch
```

### 7. Test Your Application

Open your browser and visit:

- `http://localhost:8000/` - See the hello world page
- `http://localhost:8000/greet/YourName` - See a personalized greeting
- `http://localhost:8000/api/hello` - See the JSON API response

## Understanding the Generated Structure

Let's explore what the CLI created for you:

### Plugin Configuration

**plugins/hello_world/plugin.yaml:**
```yaml
name: Hello World
description: A cool Serv plugin.
version: 0.1.0
author: Your Name

routers:
  - name: main_router
    routes:
      - path: /
        handler: route_home:Home
      - path: /greet/{name}
        handler: route_greet:Greet
      - path: /api/hello
        handler: route_api_hello:ApiHello
```

This declarative configuration:
- Defines your plugin metadata
- Maps URL paths to handler functions
- Automatically wires everything together

### Plugin Class (Event Handling Only)

**plugins/hello_world/hello_world.py:**
```python
from serv.plugins import Plugin
from bevy import dependency

class HelloWorld(Plugin):
    async def on_app_startup(self):
        """Called when the application starts up"""
        print("Hello World plugin starting up")
    
    async def on_app_shutdown(self):
        """Called when the application shuts down"""
        print("Hello World plugin shutting down")
```

The plugin class only handles events - routes are defined declaratively in `plugin.yaml`.

### Application Configuration

**serv.config.yaml:**
```yaml
site_info:
  name: "My First App"
  description: "A Serv application"

plugins:
  - plugin: hello_world
```

## Adding More Features

### Create an API Plugin

Let's add a dedicated API plugin:

```bash
# Create an API plugin
serv create plugin --name "API"

# Add API routes
serv create route --name "users" --path "/users" --router "api_router" --plugin "api"
serv create route --name "user_detail" --path "/users/{id}" --router "api_router" --plugin "api"
```

Update the API plugin configuration to mount at `/api/v1`:

**plugins/api/plugin.yaml:**
```yaml
name: API
description: REST API endpoints
version: 1.0.0
author: Your Name

routers:
  - name: api_router
    mount: /api/v1
    routes:
      - path: /users
        handler: route_users:Users
        methods: ["GET", "POST"]
      - path: /users/{id}
        handler: route_user_detail:UserDetail
        methods: ["GET", "PUT", "DELETE"]
```

### Implement API Handlers

**plugins/api/route_users.py:**
```python
from typing import Annotated
from serv.routes import GetRequest, PostRequest, JsonResponse
from serv.responses import ResponseBuilder
from bevy import dependency

async def Users(request: GetRequest) -> Annotated[dict, JsonResponse]:
    """Handle GET /api/v1/users"""
    return {
        "users": [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"}
        ]
    }

# For POST requests, create a separate handler or use method detection
async def CreateUser(request: PostRequest, response: ResponseBuilder = dependency()):
    """Handle POST /api/v1/users"""
    form_data = await request.form()
    
    # In a real app, you'd save to a database
    new_user = {
        "id": 3,
        "name": form_data.get("name"),
        "email": form_data.get("email")
    }
    
    response.content_type("application/json")
    response.set_status(201)
    response.body(f'{{"user": {new_user}, "message": "User created"}}')
```

### Add Middleware

Add authentication middleware to your API:

```bash
serv create middleware --name "auth_check" --plugin "api"
```

**plugins/api/middleware_auth_check.py:**
```python
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency

async def auth_check_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Simple API key authentication"""
    
    # Only check auth for API routes
    if not request.path.startswith("/api/"):
        yield
        return
    
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != "demo-api-key":
        response.set_status(401)
        response.content_type("application/json")
        response.body('{"error": "Invalid or missing API key"}')
        return
    
    yield  # Continue processing
```

Update the API plugin configuration:

**plugins/api/plugin.yaml:**
```yaml
name: API
description: REST API endpoints
version: 1.0.0
author: Your Name

middleware:
  - entry: middleware_auth_check:auth_check_middleware

routers:
  - name: api_router
    mount: /api/v1
    routes:
      - path: /users
        handler: route_users:Users
        methods: ["GET"]
      - path: /users/{id}
        handler: route_user_detail:UserDetail
        methods: ["GET"]
```

### Enable the API Plugin

```bash
serv plugin enable api
```

Now test the API with authentication:

```bash
# This will fail (401 Unauthorized)
curl http://localhost:8000/api/v1/users

# This will succeed
curl -H "X-API-Key: demo-api-key" http://localhost:8000/api/v1/users
```

## CLI Commands Reference

Here are the essential CLI commands you'll use:

### Project Management
```bash
serv app init <name>           # Initialize new project
serv app details               # Show project information
serv app check                 # Validate project health
```

### Plugin Management
```bash
serv create plugin --name "Name"              # Create new plugin
serv plugin enable <plugin>                   # Enable plugin
serv plugin disable <plugin>                  # Disable plugin
serv plugin list                               # List enabled plugins
serv plugin list --available                  # List all available plugins
serv plugin validate <plugin>                 # Validate plugin
```

### Component Creation
```bash
serv create route --name "name" --path "/path" --plugin "plugin"
serv create middleware --name "name" --plugin "plugin"
serv create listener --name "name" --plugin "plugin"
```

### Development
```bash
serv dev                       # Start development server
serv launch                    # Start production server
serv test                      # Run tests
serv shell                     # Interactive shell
```

### Configuration
```bash
serv config show               # Show current configuration
serv config validate           # Validate configuration
serv config get <key>          # Get configuration value
serv config set <key> <value>  # Set configuration value
```

## Best Practices

### 1. Use the CLI for Everything

Always use CLI commands to create components:

```bash
# Good
serv create plugin --name "Blog"
serv create route --name "blog_home" --path "/blog" --plugin "blog"

# Avoid manual file creation
```

### 2. Organize by Feature

Create plugins for each major feature:

```bash
serv create plugin --name "User Management"
serv create plugin --name "Blog"
serv create plugin --name "API"
serv create plugin --name "Admin"
```

### 3. Use Declarative Configuration

Define routes in `plugin.yaml`, not in code:

```yaml
# Good: Declarative routing
routers:
  - name: blog_router
    routes:
      - path: /blog
        handler: route_blog_home:BlogHome

# Avoid: Programmatic routing in plugin classes
```

### 4. Keep Plugin Classes Event-Only

Use plugin classes only for event handling:

```python
# Good: Events only
class MyPlugin(Plugin):
    async def on_app_startup(self):
        # Initialize resources
        pass
    
    async def on_user_created(self, user_id: int):
        # Handle custom events
        pass

# Avoid: Route registration in plugin classes
```

## Next Steps

Congratulations! You've created your first Serv application using the CLI-first approach. Here's what to explore next:

### Learn Core Concepts

- **[Routing](../guides/routing.md)** - Master declarative routing patterns
- **[Plugins](../guides/plugins.md)** - Build powerful, reusable plugins
- **[Middleware](../guides/middleware.md)** - Add cross-cutting concerns
- **[Dependency Injection](../guides/dependency-injection.md)** - Master the DI system

### Build a Complete Application

- **[Configuration](configuration.md)** - Advanced configuration techniques
- **[Testing](../guides/testing.md)** - Test your applications effectively

### Explore Advanced Features

- **[Forms and Validation](../guides/forms.md)** - Handle complex form processing
- **[Database Integration](../guides/database.md)** - Connect to databases
- **[Authentication](../guides/authentication.md)** - Implement user authentication

## Troubleshooting

### Common Issues

**Plugin not found:**
```bash
# Make sure the plugin is enabled
serv plugin enable my_plugin

# Check plugin status
serv plugin list
```

**Route not working:**
```bash
# Validate your plugin configuration
serv plugin validate my_plugin

# Check application health
serv app check
```

**Configuration errors:**
```bash
# Validate configuration
serv config validate

# Check current configuration
serv config show
```

### Getting Help

```bash
# Get help for any command
serv --help
serv create --help
serv plugin --help

# Check application status
serv app details
serv app check
```

You're now ready to build amazing applications with Serv! 🚀 