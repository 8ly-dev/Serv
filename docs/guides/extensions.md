# Extensions

Extensions are the foundation of Serv's modular architecture. They provide a clean way to organize your application into reusable, configurable components. This guide covers everything you need to know about creating and using extensions in Serv.

## What are Extensions?

In Serv, extensions are:

1. **Event-driven components** that contain Listener classes responding to application lifecycle events
2. **Configuration containers** that define routes, middleware, and settings declaratively
3. **Modular packages** that can be easily shared and reused
4. **CLI-managed entities** that are created and maintained using Serv's command-line tools

## Extension Architecture

### Core Principles

Serv extensions follow these key principles:

- **Declarative Configuration**: Routes and middleware are defined in `extension.yaml` files
- **Event-Only Code**: Listener classes only handle events, not route definitions
- **CLI-First Development**: Use CLI commands to create and manage extensions
- **Automatic Wiring**: Serv automatically connects configuration to functionality

### Extension Structure

A typical extension has this structure:

```
extensions/
└── my_extension/
    ├── __init__.py
    ├── extension.yaml          # Extension configuration and metadata
    ├── my_extension.py         # Main listener class (event handlers only)
    ├── route_*.py           # Route handler files
    ├── middleware_*.py      # Middleware files
    └── templates/           # Optional: Jinja2 templates
        └── *.html
```

## Creating Extensions

### Using the CLI

The recommended way to create extensions is using the Serv CLI:

```bash
# Create a new extension
serv create extension --name "User Management"

# This creates:
# - extensions/user_management/ directory
# - extension.yaml with basic configuration
# - user_management.py with extension class
```

### Generated Extension Structure

After running the command above, you'll have:

**extensions/user_management/extension.yaml:**
```yaml
name: User Management
description: A cool Serv extension.
version: 0.1.0
author: Your Name

# Routes will be added here when you create them
routers: []

# Middleware will be added here when you create them
middleware: []

# Entry points for additional listener classes
entry_points: []
```

**extensions/user_management/user_management.py:**
```python
from serv.extensions import Listener
from bevy import dependency

class UserManagement(Listener):
    async def on_app_startup(self):
        """Called when the application starts up"""
        print("User Management extension starting up")
    
    async def on_app_shutdown(self):
        """Called when the application shuts down"""
        print("User Management extension shutting down")
```

## Adding Routes to Extensions

### Using the CLI

Add routes to your extension using the CLI:

```bash
# Add a route to the extension
serv create route --name "user_list" --path "/users" --extension "user_management"

# Add another route with a parameter
serv create route --name "user_detail" --path "/users/{id}" --extension "user_management"

# Add an API route to a specific router
serv create route --name "api_users" --path "/users" --router "api_router" --extension "user_management"
```

### Updated Extension Configuration

After adding routes, your `extension.yaml` will be updated:

```yaml
name: User Management
description: A cool Serv extension.
version: 0.1.0
author: Your Name

routers:
  - name: main_router
    routes:
      - path: /users
        handler: route_user_list:UserList
      - path: /users/{id}
        handler: route_user_detail:UserDetail
  
  - name: api_router
    mount: /api/v1
    routes:
      - path: /users
        handler: route_api_users:ApiUsers
```

### Generated Route Handlers

The CLI creates route handler files:

**extensions/user_management/route_user_list.py:**
```python
from serv.responses import ResponseBuilder
from bevy import dependency

async def UserList(response: ResponseBuilder = dependency(), **path_params):
    """Handle requests to /users"""
    response.content_type("text/html")
    response.body("<h1>User List</h1>")
```

**extensions/user_management/route_user_detail.py:**
```python
from serv.responses import ResponseBuilder
from bevy import dependency

async def UserDetail(user_id: str, response: ResponseBuilder = dependency()):
    """Handle requests to /users/{id}"""
    response.content_type("text/html")
    response.body(f"<h1>User {user_id}</h1>")
```

## Extension Events

Listener classes are used exclusively for handling application events. Here are the key events:

### Lifecycle Events

```python
from serv.extensions import Listener
from bevy import dependency

class MyListener(Listener):
    async def on_app_startup(self):
        """Called when the application starts"""
        print("Application is starting up")
        # Initialize databases, external connections, etc.
        self.database = await connect_to_database()
    
    async def on_app_shutdown(self):
        """Called when the application shuts down"""
        print("Application is shutting down")
        # Clean up resources, close connections, etc.
        if hasattr(self, 'database'):
            await self.database.close()
```

### Request Events

```python
class RequestLoggingListener(Listener):
    async def on_app_request_begin(self, request = dependency()):
        """Called at the beginning of each request"""
        print(f"Request started: {request.method} {request.path}")
    
    async def on_app_request_before_router(self, request = dependency()):
        """Called before routing happens"""
        # Log requests, add headers, etc.
        print(f"Processing {request.method} {request.path}")
    
    async def on_app_request_after_router(self, request = dependency(), error=None):
        """Called after routing (whether successful or not)"""
        if error:
            print(f"Request failed: {error}")
        else:
            print(f"Request completed successfully")
    
    async def on_app_request_end(self, request = dependency(), error=None):
        """Called at the end of each request"""
        print(f"Request finished: {request.method} {request.path}")
```

### Custom Events

You can emit and handle custom events:

```python
class UserListener(Listener):
    async def on_user_created(self, user_id: int, email: str):
        """Handle custom user_created event"""
        print(f"User {user_id} created with email {email}")
        # Send welcome email, create user directory, etc.
    
    async def on_user_deleted(self, user_id: int):
        """Handle custom user_deleted event"""
        print(f"User {user_id} deleted")
        # Clean up user data, send notifications, etc.

# Emit custom events from your route handlers
async def CreateUser(request: PostRequest, app = dependency()):
    # Create user logic here
    user_id = create_user_in_database()
    
    # Emit custom event
    await app.emit("user_created", user_id=user_id, email=user_email)
```

## Adding Middleware to Extensions

### Using the CLI

Add middleware to your extension:

```bash
serv create middleware --name "auth_check" --extension "user_management"
```

This updates your `extension.yaml`:

```yaml
name: User Management
# ... other configuration ...

middleware:
  - entry: middleware_auth_check:auth_check_middleware
    config:
      timeout: 30
```

And creates **extensions/user_management/middleware_auth_check.py:**

```python
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency

async def auth_check_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Authentication middleware"""
    
    # Check authentication before request
    auth_header = request.headers.get("authorization")
    if not auth_header and request.path.startswith("/admin"):
        response.set_status(401)
        response.body("Authentication required")
        return
    
    yield  # Continue to next middleware/handler
    
    # Code here runs after the request is handled
    print("Auth check completed")
```

## Extension Configuration

### Basic Configuration

Define extension settings in `extension.yaml`:

```yaml
name: User Management
description: Handles user authentication and management
version: 1.0.0
author: Your Name

# Extension settings with defaults
settings:
  database_url: "sqlite:///users.db"
  session_timeout: 3600
  enable_registration: true
  admin_email: "admin@example.com"

routers:
  - name: main_router
    routes:
      - path: /login
        handler: route_login:LoginPage
      - path: /register
        handler: route_register:RegisterPage

middleware:
  - entry: middleware_auth:auth_middleware
    config:
      timeout: 30
```

### Accessing Configuration in Extension Code

```python
class UserManagementListener(Listener):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Access extension configuration
        config = self.__extension_spec__.config
        self.database_url = config.get("database_url", "sqlite:///users.db")
        self.session_timeout = config.get("session_timeout", 3600)
        self.enable_registration = config.get("enable_registration", True)
    
    async def on_app_startup(self):
        """Initialize extension with configuration"""
        print(f"Connecting to database: {self.database_url}")
        self.db = await connect_database(self.database_url)
        
        if self.enable_registration:
            print("User registration is enabled")
```

### Application-Level Configuration Override

Users can override extension settings in their `serv.config.yaml`:

```yaml
site_info:
  name: "My Application"
  description: "A Serv application"

extensions:
  - extension: user_management
    settings:
      database_url: "postgresql://localhost/myapp"
      session_timeout: 7200
      enable_registration: false
      admin_email: "admin@mycompany.com"
```

## Advanced Extension Patterns

### Extension with Database Integration

```python
import asyncpg
from serv.extensions import Listener

class DatabaseListener(Listener):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        config = self.__extension_spec__.config
        self.database_url = config.get("database_url")
        self.pool = None
    
    async def on_app_startup(self):
        """Initialize database connection pool"""
        self.pool = await asyncpg.create_pool(self.database_url)
        print(f"Database pool created: {self.database_url}")
        
        # Make pool available to route handlers
        from serv.app import get_current_app
        app = get_current_app()
        app._container.instances[asyncpg.Pool] = self.pool
    
    async def on_app_shutdown(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            print("Database pool closed")
```

### Extension with External Service Integration

```python
import httpx
from serv.extensions import Listener

class EmailListener(Listener):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        config = self.__extension_spec__.config
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url", "https://api.emailservice.com")
        self.client = None
    
    async def on_app_startup(self):
        """Initialize HTTP client for email service"""
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        print("Email service client initialized")
    
    async def on_app_shutdown(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
    
    async def on_user_created(self, user_id: int, email: str):
        """Send welcome email when user is created"""
        if self.client:
            await self.client.post("/send", json={
                "to": email,
                "template": "welcome",
                "data": {"user_id": user_id}
            })
```

### Extension with Scheduled Tasks

```python
import asyncio
from serv.extensions import Listener

class SchedulerListener(Listener):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks = []
    
    async def on_app_startup(self):
        """Start background tasks"""
        # Start a cleanup task that runs every hour
        task = asyncio.create_task(self._cleanup_task())
        self.tasks.append(task)
        print("Scheduler extension started background tasks")
    
    async def on_app_shutdown(self):
        """Cancel background tasks"""
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        print("Scheduler extension stopped background tasks")
    
    async def _cleanup_task(self):
        """Background task that runs periodically"""
        while True:
            try:
                print("Running cleanup task...")
                # Perform cleanup operations
                await self._perform_cleanup()
                await asyncio.sleep(3600)  # Wait 1 hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Cleanup task error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def _perform_cleanup(self):
        """Actual cleanup logic"""
        # Clean up temporary files, expired sessions, etc.
        pass
```

## Extension Management

### Enabling and Disabling Extensions

Use the CLI to manage extensions:

```bash
# Enable a extension
serv extension enable user_management

# Disable a extension
serv extension disable user_management

# List all extensions
serv extension list

# List available extensions
serv extension list --available

# Validate extension configuration
serv extension validate user_management

# Validate all extensions
serv extension validate --all
```

### Extension Dependencies

Define dependencies between extensions in `extension.yaml`:

```yaml
name: Blog
description: Blog functionality
version: 1.0.0
dependencies:
  - user_management  # Requires user management for authentication
  - email_service    # Requires email service for notifications

routers:
  - name: blog_router
    routes:
      - path: /blog
        handler: route_blog_home:BlogHome
      - path: /blog/new
        handler: route_create_post:CreatePost  # Uses user auth
```

### Extension Entry Points

Define multiple entry points for complex extensions:

```yaml
name: Admin Panel
description: Administrative interface
version: 1.0.0

# Main extension class
entry: admin_panel:AdminPanelExtension

# Additional entry points
entry_points:
  - entry: admin_auth:AdminAuthExtension
    config:
      require_2fa: true
  - entry: admin_logging:AdminLoggingExtension
    config:
      log_level: "DEBUG"

routers:
  - name: admin_router
    mount: /admin
    routes:
      - path: /dashboard
        handler: route_dashboard:AdminDashboard
```

## Testing Extensions

### Unit Testing Extension Events

```python
import pytest
from unittest.mock import Mock, AsyncMock
from extensions.user_management.user_management import UserManagementExtension

@pytest.mark.asyncio
async def test_extension_startup():
    """Test extension startup event"""
    extension = UserManagementExtension()
    
    # Mock the database connection
    extension.connect_database = AsyncMock()
    
    await extension.on_app_startup()
    
    extension.connect_database.assert_called_once()

@pytest.mark.asyncio
async def test_user_created_event():
    """Test custom user created event"""
    extension = UserManagementExtension()
    extension.send_welcome_email = AsyncMock()
    
    await extension.on_user_created(user_id=123, email="test@example.com")
    
    extension.send_welcome_email.assert_called_once_with("test@example.com")
```

### Integration Testing

```python
import pytest
from httpx import AsyncClient
from serv.app import App

@pytest.mark.asyncio
async def test_extension_routes():
    """Test that extension routes work correctly"""
    app = App(config="test_config.yaml")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test user list route
        response = await client.get("/users")
        assert response.status_code == 200
        assert "User List" in response.text
        
        # Test user detail route
        response = await client.get("/users/123")
        assert response.status_code == 200
        assert "User 123" in response.text
```

### Testing Extension Configuration

```python
def test_extension_configuration():
    """Test extension configuration loading"""
    from extensions.user_management.user_management import UserManagementExtension
    
    # Mock extension spec with configuration
    mock_spec = Mock()
    mock_spec.config = {
        "database_url": "postgresql://test",
        "session_timeout": 1800
    }
    
    extension = UserManagementExtension(extension_spec=mock_spec)
    
    assert extension.database_url == "postgresql://test"
    assert extension.session_timeout == 1800
```

## Best Practices

### 1. Use CLI for All Extension Operations

```bash
# Good: Use CLI commands
serv create extension --name "My Feature"
serv create route --name "feature_api" --extension "my_feature"
serv extension enable my_feature

# Avoid: Manual file creation and configuration
```

### 2. Keep Extension Classes Event-Only

```python
# Good: Extension class only handles events
class MyExtension(Extension):
    async def on_app_startup(self):
        # Initialize resources
        pass
    
    async def on_user_created(self, user_id: int):
        # Handle custom event
        pass

# Avoid: Adding routes in extension class
class BadExtension(Extension):
    async def on_app_request_begin(self, router = dependency()):
        # Don't do this - use declarative routing instead
        router.add_route("/bad", self.bad_handler)
```

### 3. Use Declarative Configuration

```yaml
# Good: Define routes in extension.yaml
routers:
  - name: api_router
    mount: /api/v1
    routes:
      - path: /users
        handler: route_users:UserList
        methods: ["GET", "POST"]

# Avoid: Programmatic route registration
```

### 4. Organize by Feature

```
extensions/
├── user_management/     # User-related functionality
├── blog/               # Blog functionality  
├── api/                # API endpoints
├── admin/              # Admin interface
└── email/              # Email service integration
```

### 5. Handle Errors Gracefully

```python
class RobustExtension(Extension):
    async def on_app_startup(self):
        try:
            self.service = await initialize_external_service()
        except Exception as e:
            print(f"Failed to initialize service: {e}")
            self.service = None
    
    async def on_user_created(self, user_id: int, email: str):
        if not self.service:
            print("Service not available, skipping user notification")
            return
        
        try:
            await self.service.send_notification(email)
        except Exception as e:
            print(f"Failed to send notification: {e}")
```

### 6. Document Your Extensions

```yaml
# extension.yaml
name: User Management
description: |
  Comprehensive user management system with authentication,
  authorization, and user profile management.
  
  Features:
  - User registration and login
  - Password reset functionality
  - Role-based access control
  - User profile management
  
  Configuration:
  - database_url: Database connection string
  - session_timeout: Session timeout in seconds
  - enable_registration: Allow new user registration

version: 1.0.0
author: Your Name
```

## Development Workflow

### 1. Plan Your Extension

Define what your extension will do:
- What routes will it provide?
- What events will it handle?
- What configuration options will it need?
- What dependencies does it have?

### 2. Create the Extension

```bash
serv create extension --name "My Feature"
```

### 3. Add Routes

```bash
serv create route --name "feature_home" --path "/feature" --extension "my_feature"
serv create route --name "feature_api" --path "/api/feature" --router "api_router" --extension "my_feature"
```

### 4. Add Middleware (if needed)

```bash
serv create middleware --name "feature_auth" --extension "my_feature"
```

### 5. Implement Event Handlers

Edit the extension class to handle events:

```python
class MyFeatureExtension(Extension):
    async def on_app_startup(self):
        # Initialize extension
        pass
    
    async def on_feature_event(self, data):
        # Handle custom events
        pass
```

### 6. Configure and Test

```bash
# Enable the extension
serv extension enable my_feature

# Validate configuration
serv extension validate my_feature

# Test the application
serv --dev launch
```

## Next Steps

- **[Routing](routing.md)** - Learn about declarative routing configuration
- **[Middleware](middleware.md)** - Add cross-cutting concerns to your application
- **[Dependency Injection](dependency-injection.md)** - Master dependency injection patterns
- **[Configuration](../getting-started/configuration.md)** - Advanced configuration techniques 