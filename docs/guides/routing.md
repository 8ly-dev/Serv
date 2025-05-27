# Routing

Serv provides a powerful declarative routing system that emphasizes configuration over code. Routes are defined in YAML configuration files and automatically wired to handler functions, making your application structure clear and maintainable.

## Overview

In Serv, routing follows these principles:

1. **Declarative Configuration**: Routes are defined in `extension.yaml` files
2. **CLI-First Development**: Use CLI commands to create routes and handlers
3. **Automatic Wiring**: Serv automatically connects routes to handler functions
4. **Extension-Based Organization**: Routes are organized within extensions for modularity

## Getting Started

### Creating Your First Route

The easiest way to create a route is using the Serv CLI:

```bash
# Create a new extension for your routes
serv create extension --name "Blog API"

# Create a route within the extension
serv create route --name "blog_posts" --path "/api/posts"
```

This creates:
1. A extension directory structure
2. A route handler file
3. Updates the extension's `extension.yaml` with the route configuration

### Understanding the Generated Files

After running the commands above, you'll have:

```
extensions/
└── blog_api/
    ├── __init__.py
    ├── extension.yaml
    └── route_blog_posts.py
```

**extension.yaml:**
```yaml
name: Blog API
description: A cool Serv extension.
version: 0.1.0
author: Your Name

routers:
  - name: main_router
    routes:
      - path: /api/posts
        handler: route_blog_posts:BlogPosts
```

**route_blog_posts.py:**
```python
from typing import Annotated, Any
from serv.routes import GetRequest, Jinja2Response, Route
from serv.responses import ResponseBuilder
from bevy import dependency

class BlogPosts(Route):
    async def handle_get(self, request: GetRequest) -> None:
        """Handle GET requests to /api/posts"""
        # Your route logic here
        pass
```

## Declarative Route Configuration

### Basic Route Definition

Routes are defined in the `routers` section of your extension's `extension.yaml`:

```yaml
routers:
  - name: api_router
    routes:
      - path: /posts
        handler: handlers:PostList
      - path: /posts/{id}
        handler: handlers:PostDetail
      - path: /users/{user_id}/posts
        handler: handlers:UserPosts
```

### Route with HTTP Methods

Specify which HTTP methods a route should handle:

```yaml
routers:
  - name: api_router
    routes:
      - path: /posts
        handler: handlers:PostList
        methods: ["GET", "POST"]
      - path: /posts/{id}
        handler: handlers:PostDetail
        methods: ["GET", "PUT", "DELETE"]
```

### Mounted Routers

Mount routers at specific paths for better organization:

```yaml
routers:
  - name: api_router
    mount: /api/v1
    routes:
      - path: /posts
        handler: api:PostList
      - path: /users
        handler: api:UserList
  
  - name: admin_router
    mount: /admin
    routes:
      - path: /dashboard
        handler: admin:Dashboard
      - path: /users
        handler: admin:UserManagement
```

This creates routes at:
- `/api/v1/posts`
- `/api/v1/users`
- `/admin/dashboard`
- `/admin/users`

## Creating Route Handlers

### Using the CLI

Create route handlers using the CLI for consistency:

```bash
# Create a route with custom path and router
serv create route --name "user_profile" \
  --path "/users/{id}/profile" \
  --router "api_router"

# Create a route for a specific extension
serv create route --name "admin_dashboard" \
  --path "/dashboard" \
  --router "admin_router" \
  --extension "admin_extension"
```

### Handler Function Structure

Route handlers are simple async functions that handle HTTP requests:

```python
from serv.responses import ResponseBuilder
from bevy import dependency

async def PostList(response: ResponseBuilder = dependency(), **path_params):
    """Handle requests to /posts"""
    response.content_type("application/json")
    response.body('{"posts": []}')

async def PostDetail(post_id: str, response: ResponseBuilder = dependency()):
    """Handle requests to /posts/{id}"""
    response.content_type("application/json")
    response.body(f'{{"post_id": "{post_id}"}}')

async def UserPosts(user_id: str, response: ResponseBuilder = dependency()):
    """Handle requests to /users/{user_id}/posts"""
    response.content_type("application/json")
    response.body(f'{{"user_id": "{user_id}", "posts": []}}')
```

### Path Parameters

Path parameters are automatically extracted and passed to your handler:

```python
# Route: /users/{user_id}/posts/{post_id}
async def UserPost(
    user_id: str, 
    post_id: str, 
    response: ResponseBuilder = dependency()
):
    response.body(f"User {user_id}, Post {post_id}")
```

## HTTP Methods and Request Types

### Method-Specific Handlers

Use request type annotations to handle specific HTTP methods:

```python
from serv.routes import GetRequest, PostRequest, PutRequest, DeleteRequest

async def PostList(request: GetRequest, response: ResponseBuilder = dependency()):
    """Handle GET /posts"""
    response.body("List of posts")

async def CreatePost(request: PostRequest, response: ResponseBuilder = dependency()):
    """Handle POST /posts"""
    response.body("Post created")

async def UpdatePost(
    post_id: str,
    request: PutRequest, 
    response: ResponseBuilder = dependency()
):
    """Handle PUT /posts/{post_id}"""
    response.body(f"Post {post_id} updated")

async def DeletePost(
    post_id: str,
    request: DeleteRequest, 
    response: ResponseBuilder = dependency()
):
    """Handle DELETE /posts/{post_id}"""
    response.body(f"Post {post_id} deleted")
```

### Configuration for Multiple Methods

Configure multiple handlers for the same path:

```yaml
routers:
  - name: api_router
    routes:
      - path: /posts
        handler: handlers:PostList
        methods: ["GET"]
      - path: /posts
        handler: handlers:CreatePost
        methods: ["POST"]
      - path: /posts/{id}
        handler: handlers:PostDetail
        methods: ["GET"]
      - path: /posts/{id}
        handler: handlers:UpdatePost
        methods: ["PUT"]
      - path: /posts/{id}
        handler: handlers:DeletePost
        methods: ["DELETE"]
```

## Response Types

### JSON Responses

Return structured data easily:

```python
from typing import Annotated
from serv.routes import JsonResponse

async def ApiPosts() -> Annotated[dict, JsonResponse]:
    return {
        "posts": [
            {"id": 1, "title": "First Post"},
            {"id": 2, "title": "Second Post"}
        ]
    }
```

### HTML Templates

Render HTML templates with Jinja2:

```python
from typing import Annotated, Any
from serv.routes import Jinja2Response

async def BlogHome() -> Annotated[tuple[str, dict[str, Any]], Jinja2Response]:
    return "blog/home.html", {
        "title": "My Blog",
        "posts": get_recent_posts()
    }
```

### Plain Text and Custom Responses

```python
async def HealthCheck(response: ResponseBuilder = dependency()):
    response.content_type("text/plain")
    response.body("OK")

async def ApiStatus(response: ResponseBuilder = dependency()):
    response.content_type("application/json")
    response.set_status(200)
    response.body('{"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}')
```

## Advanced Routing Patterns

### Nested Resource Routes

Create RESTful nested resources:

```yaml
routers:
  - name: api_router
    mount: /api/v1
    routes:
      # Users
      - path: /users
        handler: api:UserList
        methods: ["GET", "POST"]
      - path: /users/{user_id}
        handler: api:UserDetail
        methods: ["GET", "PUT", "DELETE"]
      
      # User Posts (nested resource)
      - path: /users/{user_id}/posts
        handler: api:UserPostList
        methods: ["GET", "POST"]
      - path: /users/{user_id}/posts/{post_id}
        handler: api:UserPostDetail
        methods: ["GET", "PUT", "DELETE"]
      
      # Post Comments (deeply nested)
      - path: /posts/{post_id}/comments
        handler: api:PostCommentList
        methods: ["GET", "POST"]
      - path: /posts/{post_id}/comments/{comment_id}
        handler: api:PostCommentDetail
        methods: ["GET", "PUT", "DELETE"]
```

### Multiple Routers in One Extension

Organize complex applications with multiple routers:

```yaml
routers:
  # Public API
  - name: public_api
    mount: /api/v1
    routes:
      - path: /posts
        handler: public_api:PostList
      - path: /posts/{id}
        handler: public_api:PostDetail
  
  # Admin API
  - name: admin_api
    mount: /admin/api
    routes:
      - path: /posts
        handler: admin_api:AdminPostList
      - path: /users
        handler: admin_api:AdminUserList
  
  # Web Interface
  - name: web_interface
    routes:
      - path: /
        handler: web:HomePage
      - path: /blog
        handler: web:BlogPage
      - path: /blog/{slug}
        handler: web:BlogPost
```

## Form Handling

### Creating Form Routes

Use the CLI to create form-handling routes:

```bash
serv create route --name "contact_form" --path "/contact"
```

### Form Data Processing

Handle form submissions in your route handlers:

```python
from serv.routes import PostRequest

async def ContactForm(request: PostRequest, response: ResponseBuilder = dependency()):
    """Handle contact form submission"""
    form_data = await request.form()
    
    name = form_data.get("name")
    email = form_data.get("email")
    message = form_data.get("message")
    
    # Process the form data
    send_contact_email(name, email, message)
    
    response.content_type("text/html")
    response.body("<h1>Thank you for your message!</h1>")
```

### File Upload Handling

Handle file uploads in your routes:

```python
async def FileUpload(request: PostRequest, response: ResponseBuilder = dependency()):
    """Handle file upload"""
    form_data = await request.form()
    
    uploaded_file = form_data.get("file")
    if uploaded_file:
        # Save the file
        with open(f"uploads/{uploaded_file.filename}", "wb") as f:
            f.write(await uploaded_file.read())
        
        response.body("File uploaded successfully")
    else:
        response.set_status(400)
        response.body("No file provided")
```

## Extension Organization

### Feature-Based Extensions

Organize routes by feature or domain:

```bash
# User management
serv create extension --name "User Management"
serv create route --name "user_list" --path "/users" --extension "user_management"
serv create route --name "user_detail" --path "/users/{id}" --extension "user_management"

# Blog functionality
serv create extension --name "Blog"
serv create route --name "blog_home" --path "/blog" --extension "blog"
serv create route --name "blog_post" --path "/blog/{slug}" --extension "blog"

# API endpoints
serv create extension --name "API"
serv create route --name "api_posts" --path "/api/posts" --extension "api"
serv create route --name "api_users" --path "/api/users" --extension "api"
```

### Extension Dependencies

Extensions can depend on other extensions for shared functionality:

```yaml
# In blog extension's extension.yaml
name: Blog
description: Blog functionality
version: 1.0.0
dependencies:
  - user_management  # Depends on user management for authentication

routers:
  - name: blog_router
    routes:
      - path: /blog
        handler: blog:BlogHome
      - path: /blog/new
        handler: blog:CreatePost  # May use user auth from user_management
```

## Error Handling

### Route-Level Error Handling

Handle errors within your route handlers:

```python
from serv.exceptions import HTTPNotFoundException

async def PostDetail(post_id: str, response: ResponseBuilder = dependency()):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPNotFoundException(f"Post {post_id} not found")
    
    response.content_type("application/json")
    response.body(post.to_json())
```

### Custom Error Pages

Create custom error handlers:

```python
async def NotFoundHandler(response: ResponseBuilder = dependency()):
    response.set_status(404)
    response.content_type("text/html")
    response.body("<h1>Page Not Found</h1>")

# Register in your extension's event handler
class MyListener(Listener):
    async def on_app_startup(self, app = dependency()):
        app.add_error_handler(HTTPNotFoundException, NotFoundHandler)
```

## Testing Routes

### Testing Route Handlers

Test your route handlers in isolation:

```python
import pytest
from unittest.mock import Mock
from serv.responses import ResponseBuilder

@pytest.mark.asyncio
async def test_post_list():
    response = Mock(spec=ResponseBuilder)
    
    await PostList(response)
    
    response.content_type.assert_called_with("application/json")
    assert '"posts"' in response.body.call_args[0][0]
```

### Integration Testing

Test complete request/response cycles:

```python
import pytest
from httpx import AsyncClient
from serv.app import App

@pytest.mark.asyncio
async def test_blog_api():
    app = App(config="test_config.yaml")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/posts")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
```

## Best Practices

### 1. Use the CLI for Consistency

Always use the CLI to create routes for consistent structure:

```bash
# Good: Use CLI
serv create route --name "user_profile" --path "/users/{id}"

# Avoid: Manual file creation (error-prone)
```

### 2. Organize by Feature

Group related routes in feature-specific extensions:

```
extensions/
├── user_management/
│   ├── extension.yaml
│   ├── route_user_list.py
│   └── route_user_detail.py
├── blog/
│   ├── extension.yaml
│   ├── route_blog_home.py
│   └── route_blog_post.py
└── api/
    ├── extension.yaml
    ├── route_api_posts.py
    └── route_api_users.py
```

### 3. Use Descriptive Handler Names

Make your handlers self-documenting:

```python
# Good
async def UserProfilePage(user_id: str, response: ResponseBuilder = dependency()):
    pass

async def CreateBlogPost(request: PostRequest, response: ResponseBuilder = dependency()):
    pass

# Avoid generic names
async def Handler(response: ResponseBuilder = dependency()):
    pass
```

### 4. Validate Input

Always validate path parameters and form data:

```python
import re

async def UserDetail(user_id: str, response: ResponseBuilder = dependency()):
    # Validate user_id format
    if not re.match(r'^\d+$', user_id):
        response.set_status(400)
        response.body("Invalid user ID format")
        return
    
    # Continue with valid input
    user = get_user(int(user_id))
    response.body(user.to_json())
```

### 5. Use Type Annotations

Always use type hints for better IDE support:

```python
from typing import Annotated
from serv.routes import GetRequest, JsonResponse

async def ApiPosts(request: GetRequest) -> Annotated[dict, JsonResponse]:
    return {"posts": get_all_posts()}
```

## Development Workflow

### 1. Plan Your Routes

Start by planning your application's URL structure:

```
/                    # Home page
/blog                # Blog listing
/blog/{slug}         # Individual blog post
/api/posts           # API: List posts
/api/posts/{id}      # API: Post detail
/admin/dashboard     # Admin dashboard
/admin/posts         # Admin: Manage posts
```

### 2. Create Extensions

Create extensions for each major feature:

```bash
serv create extension --name "Blog"
serv create extension --name "API"
serv create extension --name "Admin"
```

### 3. Add Routes

Add routes to each extension:

```bash
# Blog routes
serv create route --name "blog_home" --path "/blog" --extension "blog"
serv create route --name "blog_post" --path "/blog/{slug}" --extension "blog"

# API routes
serv create route --name "api_posts" --path "/posts" --router "api_router" --extension "api"
serv create route --name "api_post_detail" --path "/posts/{id}" --router "api_router" --extension "api"

# Admin routes
serv create route --name "admin_dashboard" --path "/dashboard" --router "admin_router" --extension "admin"
```

### 4. Enable Extensions

Enable your extensions in the application:

```bash
serv extension enable blog
serv extension enable api
serv extension enable admin
```

### 5. Test and Iterate

Test your routes and iterate:

```bash
# Start development server
serv dev

# Run tests
serv test

# Validate configuration
serv extension validate --all
```

## Next Steps

- **[Extensions](extensions.md)** - Learn about extension architecture and event handling
- **[Dependency Injection](dependency-injection.md)** - Master dependency injection patterns
- **[Middleware](middleware.md)** - Add cross-cutting concerns to your routes
- **[Forms and Validation](forms.md)** - Handle complex form processing 