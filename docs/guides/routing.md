# Routing

Serv provides a powerful and intuitive routing system built around Route classes that use decorator-based method dispatch. Routes automatically detect and invoke the appropriate handler method based on HTTP method decorators and request parameters, making your application structure clear and maintainable.

## Overview

In Serv, routing follows these principles:

1. **Route Classes**: Create classes that inherit from `Route` with decorated handler methods
2. **Decorator-Based Dispatch**: Handlers are selected based on @handle decorators and request data
3. **Parameter Injection**: Automatic extraction of parameters from requests based on type annotations
4. **Multiple Handlers**: Support multiple handlers per HTTP method with different parameter requirements
5. **Extension-Based Organization**: Routes are organized within extensions for modularity

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
from typing import Annotated
from serv.routes import Route, GetRequest, PostRequest, handle
from serv.responses import JsonResponse, TextResponse
from serv.injectors import Query, Header

class BlogPosts(Route):
    @handle.GET
    async def get_all_posts(self) -> Annotated[list[dict], JsonResponse]:
        """Handle GET requests to /api/posts"""
        posts = await self.fetch_all_posts()
        return posts
    
    @handle.GET
    async def get_posts_by_author(
        self, 
        author: Annotated[str, Query("author")]
    ) -> Annotated[list[dict], JsonResponse]:
        """Handle GET requests with author filter"""
        posts = await self.fetch_posts_by_author(author)
        return posts
    
    @handle.POST
    async def create_post(
        self, 
        request: PostRequest,
        auth_token: Annotated[str, Header("Authorization")]
    ) -> Annotated[str, TextResponse]:
        """Handle POST requests to create new posts"""
        if not self.validate_auth(auth_token):
            raise HTTPUnauthorizedException("Invalid token")
        
        data = await request.json()
        post = await self.save_post(data)
        return "Post created successfully"
    
    async def fetch_all_posts(self):
        """Get all blog posts"""
        return [{"id": 1, "title": "Sample Post", "content": "Sample content"}]
    
    async def fetch_posts_by_author(self, author: str):
        """Get posts by specific author"""
        return [{"id": 1, "title": "Sample Post", "author": author}]
    
    async def save_post(self, data: dict):
        """Create a new blog post"""
        return {"id": 2, "title": data.get("title"), "content": data.get("content")}
    
    def validate_auth(self, token: str) -> bool:
        """Validate authentication token"""
        return token == "valid-token"
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

## Route Classes and Decorator-Based Routing

### Route Class Structure

Route classes inherit from `Route` and define handler methods decorated with HTTP method decorators:

```python
from typing import Annotated
from serv.routes import Route, GetRequest, PostRequest, PutRequest, DeleteRequest, handle
from serv.responses import JsonResponse, TextResponse
from serv.injectors import Query, Header, Cookie
from serv.exceptions import HTTPNotFoundException, HTTPUnauthorizedException

class UserRoute(Route):
    @handle.GET
    async def get_user_by_id(self, user_id: Annotated[str, Query("id")]) -> Annotated[dict, JsonResponse]:
        """Get user by ID"""
        user = await self.get_user(user_id)
        if not user:
            raise HTTPNotFoundException(f"User {user_id} not found")
        return user
    
    @handle.GET
    async def get_user_profile(
        self, 
        user_id: Annotated[str, Query("id")],
        include_private: Annotated[str, Query("private", default="false")]
    ) -> Annotated[dict, JsonResponse]:
        """Get user profile with optional private data"""
        user = await self.get_user_profile_data(user_id, include_private == "true")
        return user
    
    @handle.POST
    async def create_new_user(
        self, 
        request: PostRequest,
        auth_token: Annotated[str, Header("Authorization")]
    ) -> Annotated[str, TextResponse]:
        """Create new user"""
        if not self.validate_auth(auth_token):
            raise HTTPUnauthorizedException("Authentication required")
        
        data = await request.json()
        user = await self.create_user(data)
        return "User created successfully"
    
    @handle.PUT
    async def update_user_data(
        self, 
        request: PutRequest,
        user_id: Annotated[str, Query("id")],
        session_id: Annotated[str, Cookie("session_id")]
    ) -> Annotated[dict, JsonResponse]:
        """Update user"""
        if not self.validate_session(session_id):
            raise HTTPUnauthorizedException("Invalid session")
        
        data = await request.json()
        user = await self.update_user(user_id, data)
        return user
    
    @handle.DELETE
    async def delete_user_account(
        self, 
        user_id: Annotated[str, Query("id")],
        auth_token: Annotated[str, Header("Authorization")]
    ) -> Annotated[str, TextResponse]:
        """Delete user"""
        if not self.validate_admin_auth(auth_token):
            raise HTTPUnauthorizedException("Admin access required")
        
        await self.delete_user(user_id)
        return "User deleted successfully"
```

### Decorator-Based Method Selection

Serv automatically selects the most appropriate handler based on:

1. **HTTP Method Match**: Methods decorated with `@handle.GET`, `@handle.POST`, etc.
2. **Parameter Availability**: Handlers requiring parameters that are available in the request
3. **Specificity Score**: More specific handlers (more parameters) are preferred

**Example with multiple GET handlers:**

```python
class ProductRoute(Route):
    async def handle_get(self) -> Annotated[list[dict], JsonResponse]:
        """Fallback: Get all products"""
        return await self.get_all_products()
    
    async def handle_get_by_category(
        self, 
        category: Annotated[str, Query("category")]
    ) -> Annotated[list[dict], JsonResponse]:
        """Get products by category"""
        return await self.get_products_by_category(category)
    
    async def handle_get_by_user(
        self, 
        user_id: Annotated[str, Query("user_id")]
    ) -> Annotated[list[dict], JsonResponse]:
        """Get products for specific user"""
        return await self.get_user_products(user_id)
    
    async def handle_get_filtered(
        self,
        category: Annotated[str, Query("category")],
        user_id: Annotated[str, Query("user_id")]
    ) -> Annotated[list[dict], JsonResponse]:
        """Get products filtered by both category and user"""
        return await self.get_filtered_products(category, user_id)
```

**Request routing examples:**
- `GET /products` → `handle_get` (no parameters)
- `GET /products?category=electronics` → `handle_get_by_category` (has category)
- `GET /products?user_id=123` → `handle_get_by_user` (has user_id)
- `GET /products?category=electronics&user_id=123` → `handle_get_filtered` (most specific)

## Parameter Injection

### Query Parameters

Inject query parameters using the `Query` annotation:

```python
from serv.injectors import Query

class SearchRoute(Route):
    async def handle_get(
        self,
        query: Annotated[str, Query("q")],
        page: Annotated[int, Query("page", default=1)],
        limit: Annotated[int, Query("limit", default=10)]
    ) -> Annotated[dict, JsonResponse]:
        """Search with pagination"""
        results = await self.search(query, page, limit)
        return {"results": results, "page": page, "limit": limit}
```

### Headers

Inject HTTP headers using the `Header` annotation:

```python
from serv.injectors import Header

class AuthenticatedRoute(Route):
    async def handle_get(
        self,
        auth_token: Annotated[str, Header("Authorization")],
        api_key: Annotated[str, Header("X-API-Key", default=None)]
    ) -> Annotated[dict, JsonResponse]:
        """Authenticated endpoint"""
        if not auth_token.startswith("Bearer "):
            raise HTTPUnauthorizedException("Invalid authorization header")
        
        user = await self.validate_token(auth_token)
        return {"user": user}
```

### Cookies

Inject cookies using the `Cookie` annotation:

```python
from serv.injectors import Cookie

class SessionRoute(Route):
    async def handle_get(
        self,
        session_id: Annotated[str, Cookie("session_id")],
        theme: Annotated[str, Cookie("theme", default="light")]
    ) -> Annotated[dict, JsonResponse]:
        """Session-based endpoint"""
        session = await self.get_session(session_id)
        if not session:
            raise HTTPUnauthorizedException("Invalid session")
        
        return {"session": session, "theme": theme}
```

### Path Parameters

Path parameters from URL patterns are accessible via `request.path_params`:

```python
class UserDetailRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Get user by path parameter"""
        user_id = request.path_params["user_id"]
        user = await self.get_user(user_id)
        return user
```

## Form Handling

### Form Classes

Define form classes using dataclasses for structured form handling:

```python
from dataclasses import dataclass
from serv.routes import Form, Route, PostRequest
from serv.responses import HtmlResponse, TextResponse
from typing import Annotated

@dataclass
class ContactForm(Form):
    name: str
    email: str
    message: str

@dataclass
class UserRegistrationForm(Form):
    username: str
    email: str
    password: str
    age: int = 18  # Optional with default

class ContactRoute(Route):
    async def handle_get(self) -> Annotated[str, HtmlResponse]:
        """Show contact form"""
        return '''
        <form method="post">
            <input name="name" placeholder="Name" required>
            <input name="email" type="email" placeholder="Email" required>
            <textarea name="message" placeholder="Message" required></textarea>
            <button type="submit">Send</button>
        </form>
        '''
    
    async def handle_contact_form(self, form: ContactForm) -> Annotated[str, HtmlResponse]:
        """Handle contact form submission"""
        # Process the form data
        await self.send_email(form.email, form.name, form.message)
        return f"<h1>Thank you {form.name}! Your message has been sent.</h1>"
    
    async def handle_registration_form(self, form: UserRegistrationForm) -> Annotated[str, TextResponse]:
        """Handle user registration"""
        # Validate and create user
        user = await self.create_user(form.username, form.email, form.password, form.age)
        return f"User {form.username} registered successfully"
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
serv --dev launch

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