# Routing

Serv provides a flexible and powerful routing system that supports both functional and class-based approaches. This guide covers everything you need to know about routing in Serv.

## Basic Routing

### Function-Based Routes

The simplest way to define routes is using functions:

```python
from serv.responses import ResponseBuilder
from serv.plugins import Plugin
from serv.plugins.routing import Router
from bevy import dependency

async def hello_world(response: ResponseBuilder = dependency()):
    response.content_type("text/plain")
    response.body("Hello, World!")

async def greet_user(name: str, response: ResponseBuilder = dependency()):
    response.content_type("text/html")
    response.body(f"<h1>Hello, {name}!</h1>")

class MyPlugin(Plugin):
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_route("/", hello_world)
        router.add_route("/greet/{name}", greet_user)
```

### HTTP Methods

By default, routes respond to GET requests. You can specify different methods:

```python
async def create_user(response: ResponseBuilder = dependency()):
    response.body("User created!")

async def update_user(user_id: str, response: ResponseBuilder = dependency()):
    response.body(f"User {user_id} updated!")

async def delete_user(user_id: str, response: ResponseBuilder = dependency()):
    response.body(f"User {user_id} deleted!")

# In your plugin
router.add_route("/users", create_user, methods=["POST"])
router.add_route("/users/{user_id}", update_user, methods=["PUT"])
router.add_route("/users/{user_id}", delete_user, methods=["DELETE"])
```

### Multiple Methods on One Route

You can handle multiple HTTP methods with a single handler:

```python
from serv.requests import Request

async def user_handler(user_id: str, request: Request, response: ResponseBuilder = dependency()):
    if request.method == "GET":
        response.body(f"Getting user {user_id}")
    elif request.method == "PUT":
        response.body(f"Updating user {user_id}")
    elif request.method == "DELETE":
        response.body(f"Deleting user {user_id}")

router.add_route("/users/{user_id}", user_handler, methods=["GET", "PUT", "DELETE"])
```

## Path Parameters

### Basic Parameters

Path parameters are defined using curly braces and automatically passed to your handler:

```python
async def get_post(post_id: str, response: ResponseBuilder = dependency()):
    response.body(f"Post ID: {post_id}")

router.add_route("/posts/{post_id}", get_post)
```

### Multiple Parameters

You can have multiple path parameters:

```python
async def get_comment(post_id: str, comment_id: str, response: ResponseBuilder = dependency()):
    response.body(f"Post {post_id}, Comment {comment_id}")

router.add_route("/posts/{post_id}/comments/{comment_id}", get_comment)
```

### Type Conversion

Path parameters are always strings, but you can convert them in your handler:

```python
async def get_post_by_id(post_id: str, response: ResponseBuilder = dependency()):
    try:
        post_id_int = int(post_id)
        # Use the integer ID
        response.body(f"Post ID as integer: {post_id_int}")
    except ValueError:
        response.set_status(400)
        response.body("Invalid post ID")

router.add_route("/posts/{post_id}", get_post_by_id)
```

## Class-Based Routes

For more complex routing scenarios, you can use class-based routes:

```python
from serv.routes import Route
from serv.requests import Request, GetRequest, PostRequest

class UserRoute(Route):
    async def get_user(self, request: GetRequest, response: ResponseBuilder = dependency()):
        """Handle GET requests"""
        response.body("Getting user information")
    
    async def create_user(self, request: PostRequest, response: ResponseBuilder = dependency()):
        """Handle POST requests"""
        response.body("Creating new user")
    
    async def handle_any_method(self, request: Request, response: ResponseBuilder = dependency()):
        """Handle any HTTP method"""
        response.body(f"Handling {request.method} request")

# Register the route class
router.add_route("/users", UserRoute)
```

### Method Detection

Serv automatically detects which methods to handle based on the parameter types:

- `GetRequest` → GET requests
- `PostRequest` → POST requests  
- `PutRequest` → PUT requests
- `DeleteRequest` → DELETE requests
- `Request` → Any HTTP method

## Form Handling

Serv provides automatic form handling with class-based routes:

```python
from serv.routes import Form
from dataclasses import dataclass

@dataclass
class UserForm(Form):
    name: str
    email: str
    age: int = 0  # Optional field with default

class UserRoute(Route):
    async def create_user(self, form: UserForm, response: ResponseBuilder = dependency()):
        """Automatically handles POST requests with form data"""
        response.body(f"Created user: {form.name} ({form.email})")

router.add_route("/users", UserRoute)
```

### Custom Form Methods

You can specify which HTTP method a form should handle:

```python
@dataclass
class UpdateUserForm(Form):
    name: str
    email: str
    
    __form_method__ = "PUT"  # Handle PUT requests instead of POST

class UserRoute(Route):
    async def update_user(self, form: UpdateUserForm, response: ResponseBuilder = dependency()):
        response.body(f"Updated user: {form.name}")
```

## Advanced Routing

### Route Priorities

Routes are matched in the order they're added. More specific routes should be added before more general ones:

```python
# Add specific routes first
router.add_route("/users/admin", admin_handler)
router.add_route("/users/profile", profile_handler)

# Add parameterized routes last
router.add_route("/users/{user_id}", user_handler)
```

### Sub-Routers

You can create sub-routers for organizing complex applications:

```python
# Create separate routers for different sections
api_router = Router()
admin_router = Router()

# Add routes to sub-routers
api_router.add_route("/users", api_users_handler)
api_router.add_route("/posts", api_posts_handler)

admin_router.add_route("/dashboard", admin_dashboard)
admin_router.add_route("/users", admin_users)

# Add sub-routers to main router
class MyPlugin(Plugin):
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_router(api_router, prefix="/api")
        router.add_router(admin_router, prefix="/admin")
```

### Conditional Routing with Middleware

You can use middleware to conditionally add routes:

```python
from typing import AsyncIterator

async def conditional_routing_middleware(
    router: Router = dependency(),
    request: Request = dependency()
) -> AsyncIterator[None]:
    # Add different routes based on conditions
    if request.headers.get("X-API-Version") == "v2":
        router.add_route("/api/users", users_v2_handler)
    else:
        router.add_route("/api/users", users_v1_handler)
    
    yield

app.add_middleware(conditional_routing_middleware)
```

## Route Settings

You can pass additional settings to routes that can be accessed in handlers:

```python
from serv.routing import RouteSettings

async def protected_handler(
    settings: RouteSettings = dependency(),
    response: ResponseBuilder = dependency()
):
    if settings.require_auth:
        # Check authentication
        pass
    response.body("Protected content")

# Add route with settings
router.add_route(
    "/protected", 
    protected_handler,
    settings={"require_auth": True, "roles": ["admin"]}
)
```

## Error Handling

### Route-Level Error Handling

Handle errors within your route handlers:

```python
from serv.exceptions import HTTPNotFoundException

async def get_user(user_id: str, response: ResponseBuilder = dependency()):
    user = find_user(user_id)
    if not user:
        raise HTTPNotFoundException(f"User {user_id} not found")
    
    response.body(f"User: {user.name}")
```

### Custom Error Handlers

Register custom error handlers for specific exceptions:

```python
async def not_found_handler(
    error: HTTPNotFoundException,
    response: ResponseBuilder = dependency()
):
    response.set_status(404)
    response.content_type("application/json")
    response.body('{"error": "Resource not found"}')

app.add_error_handler(HTTPNotFoundException, not_found_handler)
```

## Response Types

### Different Response Types

Serv supports various response types through annotations:

```python
from typing import Annotated
from serv.responses import JsonResponse, HtmlResponse, RedirectResponse

class ApiRoute(Route):
    async def get_data(self) -> Annotated[dict, JsonResponse]:
        return {"message": "Hello, API!"}
    
    async def get_page(self) -> Annotated[str, HtmlResponse]:
        return "<h1>Hello, HTML!</h1>"
    
    async def redirect_user(self) -> Annotated[str, RedirectResponse]:
        return "/dashboard"
```

### Template Responses

Use Jinja2 templates for HTML responses:

```python
from serv.responses import Jinja2Response

class PageRoute(Route):
    async def home_page(self) -> Annotated[tuple[str, dict], Jinja2Response]:
        return "home.html", {
            "title": "Welcome",
            "user": {"name": "John"}
        }
```

## Best Practices

### 1. Organize Routes by Feature

Group related routes into plugins:

```python
class UserPlugin(Plugin):
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_route("/users", UserListRoute)
        router.add_route("/users/{user_id}", UserDetailRoute)

class PostPlugin(Plugin):
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_route("/posts", PostListRoute)
        router.add_route("/posts/{post_id}", PostDetailRoute)
```

### 2. Use Type Hints

Always use type hints for better IDE support and documentation:

```python
async def get_user(
    user_id: str,
    response: ResponseBuilder = dependency()
) -> None:
    # Implementation
```

### 3. Validate Input

Always validate and sanitize input parameters:

```python
import re

async def get_user(user_id: str, response: ResponseBuilder = dependency()):
    # Validate user_id format
    if not re.match(r'^\d+$', user_id):
        response.set_status(400)
        response.body("Invalid user ID format")
        return
    
    # Continue with valid input
```

### 4. Use Descriptive Route Names

Make your routes self-documenting:

```python
# Good
router.add_route("/api/v1/users/{user_id}/posts", get_user_posts)

# Better with clear handler name
async def get_posts_by_user_id(user_id: str, response: ResponseBuilder = dependency()):
    pass
```

### 5. Handle Edge Cases

Always consider edge cases in your routes:

```python
async def get_user(user_id: str, response: ResponseBuilder = dependency()):
    # Handle empty or invalid IDs
    if not user_id or not user_id.strip():
        response.set_status(400)
        response.body("User ID is required")
        return
    
    try:
        user_id_int = int(user_id)
        if user_id_int <= 0:
            response.set_status(400)
            response.body("User ID must be positive")
            return
    except ValueError:
        response.set_status(400)
        response.body("User ID must be a number")
        return
    
    # Continue with valid input
```

## Testing Routes

### Unit Testing

Test your route handlers in isolation:

```python
import pytest
from serv.responses import ResponseBuilder
from unittest.mock import Mock

@pytest.mark.asyncio
async def test_hello_world():
    response = Mock(spec=ResponseBuilder)
    
    await hello_world(response)
    
    response.content_type.assert_called_with("text/plain")
    response.body.assert_called_with("Hello, World!")
```

### Integration Testing

Test complete request/response cycles:

```python
import httpx
import pytest

@pytest.mark.asyncio
async def test_user_endpoint():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/users/123")
        assert response.status_code == 200
        assert "User 123" in response.text
```

## Next Steps

- **[Dependency Injection](dependency-injection.md)** - Learn how to inject services into your routes
- **[Request Handling](requests.md)** - Master request processing
- **[Response Building](responses.md)** - Create rich responses
- **[Forms and File Uploads](forms.md)** - Handle form data and file uploads 