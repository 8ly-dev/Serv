# Serv Framework - Complete Quick Start Guide

Welcome to Serv! This comprehensive guide will get you up and running with Serv's powerful ASGI web framework, covering CLI commands, routing, database integration with Ommi, and the extension system.

## Table of Contents

1. [Installation & Setup](#installation--setup)
2. [CLI Commands](#cli-commands)
3. [Creating Your First Route](#creating-your-first-route)
4. [Database Integration with Ommi](#database-integration-with-ommi)
5. [Building Extensions](#building-extensions)
6. [Advanced Examples](#advanced-examples)
7. [Testing & Development](#testing--development)

## Installation & Setup

### 1. Install Serv

```bash
# Install with uv (recommended)
uv add getserving

# Or with pip
pip install getserving
```

### 2. Create Your First Project

```bash
# Create project directory
mkdir my-serv-app
cd my-serv-app

# Initialize configuration
serv init
```

This creates `serv.config.yaml`:

```yaml
site_info:
  name: My Serv Site
  description: A new website powered by Serv

extensions: []
middleware: []
```

## CLI Commands

Serv provides a powerful CLI for scaffolding and managing your application.

### Core Commands

```bash
# Initialize a new project
serv init

# Create a new extension
serv create extension --name blog

# Create routes within an extension
serv create route --name home --extension blog --path /

# Create listeners for handling events
serv create listener --name startup --extension blog

# Create middleware
serv create middleware --name logging --extension blog

# Launch the development server
serv launch --dev

# Launch with auto-reload disabled
serv launch --dev --no-reload

# Run tests
serv test

# Interactive shell with app context
serv shell
```

### Extension Management

```bash
# List available extensions
serv extension list --available

# Enable an extension
serv extension enable blog

# Disable an extension
serv extension disable blog

# Validate extension configuration
serv extension validate blog
```

### Configuration Management

```bash
# Show current configuration
serv config show

# Validate configuration
serv config validate

# Get specific config values
serv config get site_info.name

# Set config values
serv config set site_info.name "My Blog" --type string
```

## Creating Your First Route

### Basic Route Example

Let's create a simple route that handles GET and POST requests:

```bash
# Create an extension for our routes
serv create extension --name myapp
serv extension enable myapp

# Create a home route
serv create route --name home --extension myapp --path /
```

This generates `extensions/myapp/route_home.py`:

```python
from typing import Annotated
from serv.routes import Route, GetRequest, PostRequest, JsonResponse, HtmlResponse, handle

class HomeRoute(Route):
    """Home page route handler."""
    
    @handle.GET
    async def get_home(self, request: GetRequest) -> Annotated[str, HtmlResponse]:
        return """
        <html>
            <body>
                <h1>Welcome to Serv!</h1>
                <form method="post">
                    <input name="message" placeholder="Enter a message">
                    <button type="submit">Submit</button>
                </form>
            </body>
        </html>
        """
    
    @handle.POST
    async def post_home(self, request: PostRequest) -> Annotated[dict, JsonResponse]:
        form_data = await request.form()
        message = form_data.get("message", [""])[0]
        return {"message": f"You said: {message}"}
```

### Advanced Route with Dependency Injection

```python
from typing import Annotated
from bevy import Inject
from serv.routes import Route, GetRequest, JsonResponse, handle
from serv.injectors import Query, Header, Cookie

class UserRoute(Route):
    """User management route with dependency injection."""
    
    @handle.GET
    async def get_user(
        self,
        request: GetRequest,
        user_id: Annotated[str, Query("id")],
        auth_token: Annotated[str | None, Header("Authorization")] = None,
        session: Annotated[str | None, Cookie("session_id")] = None
    ) -> Annotated[dict, JsonResponse]:
        # Validate authentication
        if not auth_token:
            return {"error": "Authentication required"}, 401
            
        return {
            "user_id": user_id,
            "authenticated": True,
            "session": session
        }
```

### Form Handling with Type Safety

```python
from serv.routes import Route, Form, GetRequest, HtmlResponse, handle
from typing import Annotated

class ContactForm(Form):
    name: str
    email: str
    message: str

class ContactRoute(Route):
    """Contact form with automatic form validation."""
    
    @handle.GET
    async def show_form(self, request: GetRequest) -> Annotated[str, HtmlResponse]:
        return """
        <form method="post">
            <input name="name" placeholder="Name" required>
            <input name="email" type="email" placeholder="Email" required>
            <textarea name="message" placeholder="Message" required></textarea>
            <button type="submit">Send</button>
        </form>
        """
    
    async def handle_contact_form(self, form: ContactForm) -> Annotated[str, HtmlResponse]:
        # Form is automatically validated and parsed
        await self.send_email(form.email, form.name, form.message)
        return f"<h1>Thank you {form.name}! Message sent.</h1>"
```

## Database Integration with Ommi

Serv includes built-in integration with Ommi, a powerful Python ORM.

### Database Configuration

Add database configuration to `serv.config.yaml`:

```yaml
site_info:
  name: My Blog App
  description: A blogging application with Serv and Ommi

# Database configuration
databases:
  blog:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "sqlite:///blog.db"
    
  # PostgreSQL example
  main:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "postgresql://user:pass@localhost:5432/mydb"

extensions:
  - extension: blog
```

### Define Models

Create `extensions/blog/models.py`:

```python
from dataclasses import dataclass
from typing import Annotated
from ommi import ommi_model, Key

@ommi_model
@dataclass
class User:
    name: str
    email: str
    age: int
    id: Annotated[int, Key] = None

@ommi_model
@dataclass
class Post:
    title: str
    content: str
    author_id: int
    created_at: str
    id: Annotated[int, Key] = None
```

### Database-Powered Routes

```python
from typing import Annotated
from bevy import Inject, Options
from ommi import Ommi
from serv.routes import Route, GetRequest, PostRequest, JsonResponse, handle
from .models import User, Post

class BlogRoute(Route):
    """Blog route with database integration."""
    
    @handle.GET
    async def list_posts(
        self, 
        request: GetRequest,
        db: Inject[Ommi, Options(qualifier="blog")]
    ) -> Annotated[list, JsonResponse]:
        posts = []
        query_result = await db.find(Post).all().or_raise()
        async for post in query_result:
            posts.append({
                "id": post.id,
                "title": post.title,
                "content": post.content[:100] + "..." if len(post.content) > 100 else post.content
            })
        return posts
    
    @handle.POST
    async def create_post(
        self,
        request: PostRequest,
        db: Inject[Ommi, Options(qualifier="blog")]
    ) -> Annotated[dict, JsonResponse]:
        form_data = await request.form()
        title = form_data.get("title", [""])[0]
        content = form_data.get("content", [""])[0]
        
        if not title or not content:
            return {"error": "Title and content are required"}, 400
            
        post = Post(
            title=title,
            content=content,
            author_id=1,  # Hardcoded for demo
            created_at=datetime.now().isoformat()
        )
        
        await db.add(post).or_raise()
        return {"message": "Post created successfully", "id": post.id}
```

### Advanced Database Operations

```python
from ommi.query_ast import when

class UserRoute(Route):
    """Advanced user management with complex queries."""
    
    @handle.GET
    async def search_users(
        self,
        request: GetRequest,
        db: Inject[Ommi, Options(qualifier="blog")]
    ) -> Annotated[list, JsonResponse]:
        # Complex query with multiple conditions
        adult_users = await db.find(
            when(User.age >= 18).And(User.email.contains("@gmail.com"))
        ).all().or_raise()
        
        users = []
        async for user in adult_users:
            users.append({
                "id": user.id,
                "name": user.name,
                "email": user.email
            })
        return users
    
    @handle.GET
    async def get_user_posts(
        self,
        request: GetRequest,
        user_id: Annotated[str, Query("user_id")],
        db: Inject[Ommi, Options(qualifier="blog")]
    ) -> Annotated[dict, JsonResponse]:
        # Join-like operation
        user = await db.find(User.id == int(user_id)).one().or_use(None)
        if not user:
            return {"error": "User not found"}, 404
            
        posts = []
        user_posts = await db.find(Post.author_id == user.id).all().or_raise()
        async for post in user_posts:
            posts.append({
                "id": post.id,
                "title": post.title,
                "created_at": post.created_at
            })
            
        return {
            "user": {"id": user.id, "name": user.name},
            "posts": posts
        }
```

## Building Extensions

Extensions are the primary way to add functionality to Serv applications.

### Extension Structure

```
extensions/
  blog/
    __init__.py
    extension.yaml        # Extension metadata
    blog.py              # Main extension (listener)
    models.py            # Database models
    routes.py            # Route handlers
    templates/           # Jinja2 templates
      post.html
      home.html
```

### Extension Configuration

`extensions/blog/extension.yaml`:

```yaml
name: Blog
version: 1.0.0
description: A complete blogging system
author: Your Name

# Listeners handle application events
listeners:
  - blog:BlogExtension

# Routers define URL routing
routers:
  - name: blog_router
    routes:
      - path: /
        handler: routes:HomeRoute
      - path: /posts
        handler: routes:PostListRoute
      - path: /posts/{post_id}
        handler: routes:PostDetailRoute
      - path: /create
        handler: routes:CreatePostRoute

# Middleware for request processing
middleware:
  - entry: middleware_auth:auth_middleware
```

### Main Extension (Listener)

`extensions/blog/blog.py`:

```python
from bevy import Inject
from serv.extensions import Listener
from serv.routing import Router
from serv.protocols import AppContextProtocol
from serv.extensions.router_extension import on

class BlogExtension(Listener):
    """Main blog extension listener."""
    
    @on("app.startup")
    async def setup_database(self, app_context: Inject[AppContextProtocol]):
        """Initialize database on startup."""
        print("🗄️  Setting up blog database...")
        # Database setup is handled automatically by Ommi
        print("✅ Blog database ready!")
    
    @on("app.request.begin")
    async def log_requests(self, request, app_context: Inject[AppContextProtocol]):
        """Log incoming requests."""
        print(f"📝 {request.method} {request.path}")
    
    @on("app.shutdown")
    async def cleanup(self, app_context: Inject[AppContextProtocol]):
        """Cleanup on shutdown."""
        print("🧹 Blog extension cleanup complete")
```

### Custom Middleware

`extensions/blog/middleware_auth.py`:

```python
async def auth_middleware(request, call_next):
    """Simple authentication middleware."""
    
    # Skip auth for public paths
    public_paths = ["/", "/login", "/register"]
    if request.path in public_paths:
        return await call_next(request)
    
    # Check for auth token
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    
    # Add user info to request state
    token = auth_header[7:]  # Remove "Bearer "
    request.state.user_id = decode_token(token)  # Your token validation logic
    
    return await call_next(request)
```

## Advanced Examples

### WebSocket Integration

```python
from serv.websocket import WebSocketRoute

class ChatRoute(WebSocketRoute):
    """Real-time chat with WebSockets."""
    
    async def on_connect(self, websocket):
        await websocket.accept()
        print(f"Client connected: {websocket.client}")
    
    async def on_message(self, websocket, data):
        message = data.get("message", "")
        username = data.get("username", "Anonymous")
        
        # Broadcast to all connected clients
        await self.broadcast({
            "type": "message",
            "username": username,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_disconnect(self, websocket):
        print(f"Client disconnected: {websocket.client}")
```

### Server-Sent Events (SSE)

```python
from serv.routes import ServerSentEventsResponse
import asyncio

class EventsRoute(Route):
    """Server-sent events for real-time updates."""
    
    @handle.GET
    async def events_stream(self, request: GetRequest) -> ServerSentEventsResponse:
        async def generate_events():
            counter = 0
            while True:
                yield f"data: Event {counter}\n\n"
                counter += 1
                await asyncio.sleep(1)
        
        return ServerSentEventsResponse(generate_events())
```

### File Upload Handling

```python
from serv.routes import FileResponse
import aiofiles

class FileUploadRoute(Route):
    """Handle file uploads and downloads."""
    
    @handle.POST
    async def upload_file(self, request: PostRequest) -> Annotated[dict, JsonResponse]:
        form = await request.form()
        uploaded_file = form.get("file")
        
        if not uploaded_file:
            return {"error": "No file uploaded"}, 400
        
        # Save file
        file_path = f"uploads/{uploaded_file.filename}"
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(uploaded_file.file.read())
        
        return {"message": "File uploaded successfully", "filename": uploaded_file.filename}
    
    @handle.GET
    async def download_file(
        self, 
        request: GetRequest,
        filename: Annotated[str, Query("filename")]
    ) -> FileResponse:
        file_path = f"uploads/{filename}"
        
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
        
        return FileResponse(
            file=content,
            filename=filename,
            content_type="application/octet-stream"
        )
```

### Template System & Hierarchy

Serv includes a sophisticated template system built on Jinja2 with support for template inheritance and extension-specific template organization.

#### Template Location Hierarchy

Serv automatically searches for templates in these locations (in order):

1. `./templates/{extension_name}/` - Project-level override templates
2. `./extensions/{extension_name}/templates/` - Extension's own templates

This allows you to override any extension template at the project level without modifying the extension itself.

#### Template Structure Example

```
my-serv-app/
├── templates/                    # Project-level template overrides
│   └── blog/                    # Override templates for blog extension
│       └── home.html            # Custom home template
├── extensions/
│   └── blog/
│       └── templates/           # Extension's default templates
│           ├── base.html        # Base template with shared layout
│           ├── home.html        # Home page template
│           ├── post_detail.html # Individual post view
│           └── post_form.html   # Create/edit post form
```

#### Base Template Pattern

Create `extensions/blog/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}{{ site_name }}{% endblock %}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --secondary: #f1f5f9;
            --text: #1e293b;
            --border: #e2e8f0;
            --surface: #ffffff;
        }
        
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            margin: 0;
            padding: 2rem;
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: var(--surface);
            border-radius: 1rem;
            box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1);
            overflow: hidden;
        }
        
        .header {
            background: var(--primary);
            color: white;
            padding: 2rem;
            text-align: center;
        }
        
        .content {
            padding: 2rem;
        }
        
        .nav {
            background: var(--secondary);
            padding: 1rem 2rem;
            border-bottom: 1px solid var(--border);
        }
        
        .btn {
            display: inline-block;
            padding: 0.75rem 1.5rem;
            background: var(--primary);
            color: white;
            text-decoration: none;
            border-radius: 0.5rem;
            font-weight: 500;
            transition: background 0.2s;
        }
        
        .btn:hover {
            background: var(--primary-dark);
        }
        
        {% block extra_css %}{% endblock %}
    </style>
    {% block extra_head %}{% endblock %}
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>{% block header_title %}{{ site_name }}{% endblock %}</h1>
            <p>{% block header_subtitle %}{{ site_description }}{% endblock %}</p>
        </header>
        
        {% block navigation %}
        <nav class="nav">
            <a href="/" class="btn">🏠 Home</a>
            <a href="/posts" class="btn">📝 Posts</a>
            <a href="/create" class="btn">✍️ Create</a>
        </nav>
        {% endblock %}
        
        <main class="content">
            {% block content %}{% endblock %}
        </main>
        
        {% block footer %}
        <footer style="padding: 1rem 2rem; text-align: center; color: var(--text-light);">
            <p>Powered by Serv Framework</p>
        </footer>
        {% endblock %}
    </div>
    
    <script>
        {% block extra_js %}{% endblock %}
    </script>
</body>
</html>
```

#### Child Templates with Inheritance

Create `extensions/blog/templates/home.html`:

```html
{% extends "base.html" %}

{% block title %}Home | {{ site_name }}{% endblock %}

{% block header_title %}✨ {{ site_name }}{% endblock %}
{% block header_subtitle %}{{ site_description }}{% endblock %}

{% block content %}
<div class="posts">
    {% if posts %}
        {% for post in posts %}
        <article class="post" style="border-bottom: 1px solid var(--border); padding: 2rem 0;">
            <h3>
                <a href="/posts/{{ post.id }}" style="color: var(--text); text-decoration: none;">
                    {{ post.title }}
                </a>
            </h3>
            <div class="post-content" style="color: var(--text-light); margin: 1rem 0;">
                {{ post.content[:200] }}{% if post.content|length > 200 %}...{% endif %}
            </div>
            <div class="post-meta" style="font-size: 0.9rem; color: var(--text-light);">
                <span>📅 {{ post.created_at }}</span>
            </div>
        </article>
        {% endfor %}
    {% else %}
        <div class="no-posts" style="text-align: center; padding: 3rem;">
            <h3>🌟 Welcome to your Blog!</h3>
            <p>No posts yet. Start sharing your thoughts!</p>
            <a href="/create" class="btn" style="margin-top: 1rem;">✍️ Write your first post</a>
        </div>
    {% endif %}
</div>
{% endblock %}

{% block extra_css %}
<style>
    .post:last-child {
        border-bottom: none !important;
    }
    
    .post h3 a:hover {
        color: var(--primary);
    }
</style>
{% endblock %}
```

#### Form Templates

Create `extensions/blog/templates/post_form.html`:

```html
{% extends "base.html" %}

{% block title %}{% if post %}Edit{% else %}Create{% endif %} Post | {{ site_name }}{% endblock %}

{% block content %}
<div class="form-container">
    <h2>{% if post %}Edit Post{% else %}Create New Post{% endif %}</h2>
    
    {% if error %}
        <div class="error" style="background: #fef2f2; color: #dc2626; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
            {{ error }}
        </div>
    {% endif %}
    
    <form method="post" style="background: white; padding: 2rem; border-radius: 0.5rem;">
        <div class="form-group" style="margin-bottom: 1.5rem;">
            <label for="title" style="display: block; font-weight: 600; margin-bottom: 0.5rem;">Title</label>
            <input type="text" 
                   id="title" 
                   name="title" 
                   value="{{ post.title if post else '' }}"
                   required
                   style="width: 100%; padding: 0.75rem; border: 2px solid var(--border); border-radius: 0.5rem;">
        </div>
        
        <div class="form-group" style="margin-bottom: 1.5rem;">
            <label for="content" style="display: block; font-weight: 600; margin-bottom: 0.5rem;">Content</label>
            <textarea id="content" 
                     name="content" 
                     rows="10" 
                     required
                     placeholder="Write your post content here... (Markdown supported)"
                     style="width: 100%; padding: 0.75rem; border: 2px solid var(--border); border-radius: 0.5rem; resize: vertical; font-family: inherit;">{{ post.content if post else '' }}</textarea>
        </div>
        
        <div class="form-actions">
            <button type="submit" class="btn">
                {% if post %}💾 Update Post{% else %}📝 Create Post{% endif %}
            </button>
            <a href="/" class="btn" style="background: var(--text-light); margin-left: 1rem;">Cancel</a>
        </div>
    </form>
</div>
{% endblock %}

{% block extra_js %}
<script>
    // Auto-resize textarea
    const textarea = document.getElementById('content');
    textarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = this.scrollHeight + 'px';
    });
</script>
{% endblock %}
```

#### Template Usage in Routes

```python
from serv.routes import Jinja2Response

class BlogRoute(Route):
    """Template-powered blog routes."""
    
    @handle.GET
    async def home_page(
        self, 
        request: GetRequest,
        db: Inject[Ommi, Options(qualifier="blog")]
    ) -> Annotated[tuple[str, dict], Jinja2Response]:
        # Get recent posts
        posts = []
        recent_posts = await db.find(Post).all().or_raise()
        async for post in recent_posts:
            posts.append(post)
        
        return "home.html", {
            "posts": posts[:5],
            "site_name": "My Blog",
            "site_description": "A modern blog built with Serv"
        }
    
    @handle.GET
    async def create_form(self, request: GetRequest) -> Annotated[tuple[str, dict], Jinja2Response]:
        return "post_form.html", {
            "site_name": "My Blog"
        }
    
    @handle.POST
    async def create_post(
        self, 
        request: PostRequest,
        db: Inject[Ommi, Options(qualifier="blog")]
    ) -> Annotated[tuple[str, dict], Jinja2Response]:
        form_data = await request.form()
        title = form_data.get("title", [""])[0]
        content = form_data.get("content", [""])[0]
        
        if not title or not content:
            return "post_form.html", {
                "error": "Title and content are required",
                "site_name": "My Blog"
            }
        
        post = Post(
            title=title,
            content=content,
            author_id=1,
            created_at=datetime.now().isoformat()
        )
        
        await db.add(post).or_raise()
        
        # Redirect-like response using template
        return "success.html", {
            "message": "Post created successfully!",
            "post_title": title,
            "site_name": "My Blog"
        }
```

#### Template Override System

You can override any extension template by creating a file with the same name in your project's template directory:

```
# To override the blog extension's home.html:
templates/
  blog/
    home.html  # This will be used instead of extensions/blog/templates/home.html
```

This is powerful for customizing third-party extensions without modifying their code.

#### Template Context and Helpers

Templates automatically receive context from your route handlers, and you can add global template functions:

```python
# In your extension listener
@on("app.startup")
async def setup_template_globals(self, app_context: Inject[AppContextProtocol]):
    """Add global template functions."""
    # Template globals would be set up here if the framework supports it
    # This is a placeholder for future template enhancement features
```

## Testing & Development

### Running Tests

```bash
# Run all tests
serv test

# Run specific test file
serv test tests/test_routes.py

# Run with coverage
serv test --coverage

# Run extension tests only
serv test --extensions
```

### Development Mode

```bash
# Start dev server with auto-reload
serv launch --dev

# Start without auto-reload
serv launch --dev --no-reload

# Custom host and port
serv launch --dev --host 0.0.0.0 --port 8080
```

### Interactive Shell

```bash
# Start shell with app context
serv shell

# Use IPython if available
serv shell --ipython
```

In the shell:
```python
# Access your app
app.config

# Test database connections
db = app.container.get(Ommi)
await db.find(User).count().or_raise()

# Test routes manually
from extensions.blog.routes import HomeRoute
route = HomeRoute()
```

### Project Structure Best Practices

```
my-serv-app/
├── serv.config.yaml      # Main configuration
├── extensions/           # Your extensions
│   ├── __init__.py
│   ├── blog/
│   │   ├── __init__.py
│   │   ├── extension.yaml
│   │   ├── blog.py       # Main extension
│   │   ├── models.py     # Database models
│   │   ├── routes.py     # Route handlers
│   │   └── templates/    # Jinja2 templates
│   └── auth/
│       ├── __init__.py
│       ├── extension.yaml
│       └── auth.py
├── static/               # Static files
│   ├── css/
│   ├── js/
│   └── images/
├── tests/                # Test files
│   ├── test_blog.py
│   └── test_auth.py
└── uploads/              # File uploads
```

## Next Steps

1. **Explore the Documentation**: Check out the full documentation at the project repository
2. **Join the Community**: Contribute to the project or ask questions
3. **Build Something Cool**: Use Serv to build your next web application!

### Useful Resources

- **Repository**: https://github.com/8ly/Serv
- **Examples**: Check the `demos/` directory for complete examples
- **Ommi Documentation**: Learn more about the ORM integration
- **ASGI Specification**: Understanding the underlying protocol

---

Happy coding with Serv! 🚀