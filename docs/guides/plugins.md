# Plugins

Plugins are the heart of Serv's extensibility. They allow you to modularize your application, share functionality, and build reusable components. This guide covers everything you need to know about creating and using plugins in Serv.

## What are Plugins?

Plugins in Serv are Python classes that extend the `Plugin` base class and respond to application events. They can:

- Add routes to your application
- Register middleware
- Handle application lifecycle events
- Provide reusable functionality
- Be configured via YAML files

## Basic Plugin Structure

### Simple Plugin

Here's the simplest possible plugin:

```python
from serv.plugins import Plugin

class MyPlugin(Plugin):
    async def on_app_startup(self):
        print("My plugin is starting up!")
    
    async def on_app_shutdown(self):
        print("My plugin is shutting down!")
```

### Plugin with Routes

Most plugins will add routes to your application:

```python
from serv.plugins import Plugin
from serv.plugins.routing import Router
from serv.responses import ResponseBuilder
from bevy import dependency

class HelloPlugin(Plugin):
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_route("/hello", self.hello_handler)
        router.add_route("/hello/{name}", self.hello_name_handler)
    
    async def hello_handler(self, response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body("Hello from my plugin!")
    
    async def hello_name_handler(self, name: str, response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body(f"Hello, {name}!")
```

## Plugin Events

Plugins respond to various application events. Here are the most common ones:

### Lifecycle Events

```python
class LifecyclePlugin(Plugin):
    async def on_app_startup(self):
        """Called when the application starts"""
        print("Application is starting up")
        # Initialize databases, connections, etc.
    
    async def on_app_shutdown(self):
        """Called when the application shuts down"""
        print("Application is shutting down")
        # Clean up resources, close connections, etc.
```

### Request Events

```python
class RequestPlugin(Plugin):
    async def on_app_request_begin(self, router: Router = dependency()):
        """Called at the beginning of each request"""
        # Add routes, modify router, etc.
        router.add_route("/my-route", self.my_handler)
    
    async def on_app_request_before_router(self, request: Request = dependency()):
        """Called before routing happens"""
        # Log requests, modify headers, etc.
        print(f"Processing {request.method} {request.path}")
    
    async def on_app_request_after_router(self, request: Request = dependency(), error=None):
        """Called after routing (whether successful or not)"""
        if error:
            print(f"Request failed: {error}")
        else:
            print(f"Request completed successfully")
    
    async def on_app_request_end(self, request: Request = dependency(), error=None):
        """Called at the end of each request"""
        # Final cleanup, logging, etc.
        print(f"Request finished: {request.method} {request.path}")
```

## Plugin Configuration

### Plugin YAML File

Create a `plugin.yaml` file to define your plugin's metadata and configuration:

```yaml
name: My Awesome Plugin
description: A plugin that does awesome things
version: 1.0.0
author: Your Name
entry: my_plugin.main:MyPlugin

# Default settings
settings:
  debug: false
  api_key: ""
  max_items: 100

# Additional entry points
entry_points:
  - entry: my_plugin.admin:AdminPlugin
    config:
      admin_only: true

# Middleware provided by this plugin
middleware:
  - entry: my_plugin.middleware:LoggingMiddleware
    config:
      log_level: "INFO"
```

### Accessing Configuration

Access plugin configuration in your plugin code:

```python
class ConfigurablePlugin(Plugin):
    def __init__(self):
        # Access plugin configuration
        self.config = self.get_config()
        self.debug = self.config.get('debug', False)
        self.api_key = self.config.get('api_key', '')
    
    async def on_app_startup(self):
        if self.debug:
            print(f"Plugin starting with API key: {self.api_key}")
```

### Application Configuration Override

Users can override plugin settings in their `serv.config.yaml`:

```yaml
plugins:
  - plugin: my_plugin
    settings:
      debug: true
      api_key: "secret-key-123"
      max_items: 50
```

## Advanced Plugin Patterns

### Plugin with Database

```python
import sqlite3
from contextlib import asynccontextmanager

class DatabasePlugin(Plugin):
    def __init__(self):
        self.db_path = self.get_config().get('db_path', 'app.db')
        self.connection = None
    
    async def on_app_startup(self):
        """Initialize database connection"""
        self.connection = sqlite3.connect(self.db_path)
        self._create_tables()
    
    async def on_app_shutdown(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
    
    def _create_tables(self):
        """Create necessary database tables"""
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL
            )
        """)
        self.connection.commit()
    
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_route("/users", self.list_users)
        router.add_route("/users/{user_id}", self.get_user)
    
    async def list_users(self, response: ResponseBuilder = dependency()):
        cursor = self.connection.execute("SELECT * FROM users")
        users = cursor.fetchall()
        response.content_type("application/json")
        response.body(json.dumps(users))
    
    async def get_user(self, user_id: str, response: ResponseBuilder = dependency()):
        cursor = self.connection.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if user:
            response.content_type("application/json")
            response.body(json.dumps(user))
        else:
            response.set_status(404)
            response.body("User not found")
```

### Plugin with Services

Create reusable services that can be injected into other parts of your application:

```python
from bevy import dependency

class EmailService:
    def __init__(self, smtp_host: str, smtp_port: int):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
    
    async def send_email(self, to: str, subject: str, body: str):
        # Implementation for sending emails
        print(f"Sending email to {to}: {subject}")

class EmailPlugin(Plugin):
    async def on_app_startup(self, container: Container = dependency()):
        """Register the email service"""
        config = self.get_config()
        email_service = EmailService(
            smtp_host=config.get('smtp_host', 'localhost'),
            smtp_port=config.get('smtp_port', 587)
        )
        container.instances[EmailService] = email_service
    
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_route("/send-email", self.send_email_handler)
    
    async def send_email_handler(
        self, 
        email_service: EmailService = dependency(),
        response: ResponseBuilder = dependency()
    ):
        await email_service.send_email(
            to="user@example.com",
            subject="Hello",
            body="Hello from Serv!"
        )
        response.body("Email sent!")
```

### Plugin with Middleware

Plugins can register middleware:

```python
from typing import AsyncIterator

class SecurityPlugin(Plugin):
    async def on_app_startup(self, app: App = dependency()):
        """Register security middleware"""
        app.add_middleware(self.security_middleware)
    
    async def security_middleware(
        self,
        request: Request = dependency(),
        response: ResponseBuilder = dependency()
    ) -> AsyncIterator[None]:
        """Add security headers to all responses"""
        # Before request processing
        if not self._is_secure_request(request):
            response.set_status(403)
            response.body("Forbidden")
            return
        
        yield  # Process the request
        
        # After request processing
        response.add_header("X-Content-Type-Options", "nosniff")
        response.add_header("X-Frame-Options", "DENY")
        response.add_header("X-XSS-Protection", "1; mode=block")
    
    def _is_secure_request(self, request: Request) -> bool:
        # Implement your security logic
        return True
```

## Plugin Organization

### Directory Structure

Organize your plugins in a clear directory structure:

```
plugins/
├── auth/
│   ├── __init__.py
│   ├── main.py          # Main plugin class
│   ├── models.py        # Data models
│   ├── handlers.py      # Route handlers
│   ├── middleware.py    # Middleware
│   └── plugin.yaml      # Plugin configuration
├── blog/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   └── plugin.yaml
└── api/
    ├── __init__.py
    ├── main.py
    ├── v1/
    │   ├── __init__.py
    │   └── handlers.py
    └── plugin.yaml
```

### Multi-File Plugins

For larger plugins, split functionality across multiple files:

```python
# plugins/blog/main.py
from .handlers import BlogHandlers
from .models import BlogStorage

class BlogPlugin(Plugin):
    def __init__(self):
        self.storage = BlogStorage()
        self.handlers = BlogHandlers(self.storage)
    
    async def on_app_request_begin(self, router: Router = dependency()):
        self.handlers.register_routes(router)

# plugins/blog/handlers.py
class BlogHandlers:
    def __init__(self, storage):
        self.storage = storage
    
    def register_routes(self, router):
        router.add_route("/blog", self.list_posts)
        router.add_route("/blog/{post_id}", self.get_post)
    
    async def list_posts(self, response: ResponseBuilder = dependency()):
        # Implementation
        pass
    
    async def get_post(self, post_id: str, response: ResponseBuilder = dependency()):
        # Implementation
        pass
```

## Plugin Loading

### Automatic Loading

Serv can automatically load plugins from directories:

```python
from serv import App

# Load plugins from the ./plugins directory
app = App(plugin_dir="./plugins")
```

### Manual Loading

You can also load plugins manually:

```python
from serv import App
from my_plugins import MyPlugin

app = App()
app.add_plugin(MyPlugin())
```

### Configuration-Based Loading

Load plugins via configuration:

```yaml
# serv.config.yaml
plugins:
  - plugin: auth
    settings:
      secret_key: "your-secret-key"
  - plugin: blog
    settings:
      posts_per_page: 10
  - entry: external_package.plugin:ExternalPlugin
    config:
      api_url: "https://api.example.com"
```

## Plugin Dependencies

### Plugin Ordering

Sometimes plugins need to load in a specific order:

```python
class DatabasePlugin(Plugin):
    priority = 100  # Load early
    
    async def on_app_startup(self):
        # Set up database
        pass

class UserPlugin(Plugin):
    priority = 50  # Load after database
    depends_on = ['database']
    
    async def on_app_startup(self):
        # Use database set up by DatabasePlugin
        pass
```

### Service Dependencies

Use dependency injection to share services between plugins:

```python
class DatabasePlugin(Plugin):
    async def on_app_startup(self, container: Container = dependency()):
        db = Database()
        container.instances[Database] = db

class UserPlugin(Plugin):
    async def on_app_request_begin(
        self, 
        router: Router = dependency(),
        db: Database = dependency()
    ):
        # Use the database service
        router.add_route("/users", lambda: self.list_users(db))
```

## Testing Plugins

### Unit Testing

Test plugin functionality in isolation:

```python
import pytest
from unittest.mock import Mock
from my_plugin import MyPlugin

@pytest.mark.asyncio
async def test_plugin_startup():
    plugin = MyPlugin()
    
    # Mock dependencies
    container = Mock()
    
    await plugin.on_app_startup(container=container)
    
    # Assert expected behavior
    assert container.instances[SomeService] is not None
```

### Integration Testing

Test plugins within a full application:

```python
import pytest
import httpx
from serv import App
from my_plugin import MyPlugin

@pytest.fixture
def app():
    app = App()
    app.add_plugin(MyPlugin())
    return app

@pytest.mark.asyncio
async def test_plugin_routes(app):
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/my-route")
        assert response.status_code == 200
```

## Best Practices

### 1. Single Responsibility

Each plugin should have a single, well-defined purpose:

```python
# Good: Focused on authentication
class AuthPlugin(Plugin):
    pass

# Good: Focused on blog functionality  
class BlogPlugin(Plugin):
    pass

# Bad: Too many responsibilities
class EverythingPlugin(Plugin):
    pass
```

### 2. Configuration

Make your plugins configurable:

```python
class MyPlugin(Plugin):
    def __init__(self):
        config = self.get_config()
        self.enabled = config.get('enabled', True)
        self.debug = config.get('debug', False)
    
    async def on_app_request_begin(self, router: Router = dependency()):
        if not self.enabled:
            return
        
        # Add routes only if enabled
        router.add_route("/my-route", self.handler)
```

### 3. Error Handling

Handle errors gracefully in your plugins:

```python
class RobustPlugin(Plugin):
    async def on_app_startup(self):
        try:
            # Initialize external service
            self.service = ExternalService()
        except Exception as e:
            logger.error(f"Failed to initialize service: {e}")
            # Provide fallback or disable functionality
            self.service = None
    
    async def my_handler(self, response: ResponseBuilder = dependency()):
        if not self.service:
            response.set_status(503)
            response.body("Service unavailable")
            return
        
        # Use the service
        result = await self.service.do_something()
        response.body(result)
```

### 4. Documentation

Document your plugins well:

```python
class WellDocumentedPlugin(Plugin):
    """
    A plugin that provides user authentication functionality.
    
    Configuration:
        secret_key (str): Secret key for JWT tokens
        token_expiry (int): Token expiry time in seconds (default: 3600)
        
    Events:
        - Responds to app.startup to initialize JWT handler
        - Responds to app.request.begin to add auth routes
        
    Routes:
        - POST /auth/login: User login
        - POST /auth/logout: User logout
        - GET /auth/profile: Get user profile
    """
    
    async def on_app_startup(self):
        """Initialize JWT handler with configured secret key."""
        pass
```

### 5. Versioning

Version your plugins for compatibility:

```yaml
# plugin.yaml
name: My Plugin
version: 2.1.0
serv_version: ">=0.1.0,<0.2.0"
```

## Publishing Plugins

### Package Structure

Structure your plugin as a Python package:

```
my-serv-plugin/
├── setup.py
├── README.md
├── my_serv_plugin/
│   ├── __init__.py
│   ├── plugin.py
│   └── handlers.py
└── tests/
    └── test_plugin.py
```

### Setup.py

```python
from setuptools import setup, find_packages

setup(
    name="my-serv-plugin",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "getserving>=0.1.0",
    ],
    entry_points={
        "serv.plugins": [
            "my_plugin = my_serv_plugin.plugin:MyPlugin",
        ],
    },
)
```

## Next Steps

- **[Middleware](middleware.md)** - Learn about middleware development
- **[Dependency Injection](dependency-injection.md)** - Master the DI system
- **[Events](events.md)** - Understand the event system
- **[Testing](testing.md)** - Test your plugins effectively 