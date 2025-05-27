# Your First App

In this tutorial, we'll build a complete blog application using Serv. You'll learn about routing, templates, forms, extensions, and more!

## What We'll Build

We're going to create a simple blog with the following features:

- Homepage listing all blog posts
- Individual post pages
- Admin interface to create new posts
- Form handling and validation
- Template rendering with Jinja2
- Extension-based architecture

## Project Setup

### 1. Create the Project Structure

First, let's create our project directory:

```bash
mkdir serv-blog
cd serv-blog
```

Create the following directory structure:

```
serv-blog/
├── app.py
├── serv.config.yaml
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── post.html
│   └── admin/
│       └── create_post.html
└── extensions/
    └── blog/
        ├── __init__.py
        ├── main.py
        ├── models.py
        └── extension.yaml
```

### 2. Install Dependencies

```bash
pip install getserving uvicorn
```

## Building the Application

### 1. Create the Data Models

First, let's create simple data models for our blog posts. Create `extensions/blog/models.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class BlogPost:
    id: int
    title: str
    content: str
    author: str
    created_at: datetime
    
    def __post_init__(self):
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)

class BlogStorage:
    """Simple in-memory storage for blog posts"""
    
    def __init__(self):
        self.posts: List[BlogPost] = []
        self.next_id = 1
        
        # Add some sample data
        self.add_post("Welcome to Serv Blog", 
                     "This is your first blog post using Serv!", 
                     "Admin")
        self.add_post("Getting Started", 
                     "Learn how to build amazing web apps with Serv.", 
                     "Admin")
    
    def add_post(self, title: str, content: str, author: str) -> BlogPost:
        post = BlogPost(
            id=self.next_id,
            title=title,
            content=content,
            author=author,
            created_at=datetime.now()
        )
        self.posts.append(post)
        self.next_id += 1
        return post
    
    def get_all_posts(self) -> List[BlogPost]:
        return sorted(self.posts, key=lambda p: p.created_at, reverse=True)
    
    def get_post_by_id(self, post_id: int) -> BlogPost | None:
        for post in self.posts:
            if post.id == post_id:
                return post
        return None
```

### 2. Create the Blog Extension

Now let's create the main blog extension. Create `extensions/blog/main.py`:

```python
from typing import Annotated
from serv.extensions import Extension
from serv.extensions.routing import Router
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.routes import Route, Form
from bevy import dependency
import json

from .models import BlogStorage, BlogPost

class BlogExtension(Extension):
    def __init__(self):
        self.storage = BlogStorage()
    
    async def on_app_startup(self):
        """Initialize the blog extension"""
        print("Blog extension started!")
    
    async def on_app_request_begin(self, router: Router = dependency()):
        """Register routes for each request"""
        # Register our route handlers
        router.add_route("/", self.homepage)
        router.add_route("/post/{post_id}", self.view_post)
        router.add_route("/admin", AdminRoute(self.storage))
        router.add_route("/api/posts", self.api_posts)
    
    async def homepage(self, response: ResponseBuilder = dependency()):
        """Homepage showing all blog posts"""
        posts = self.storage.get_all_posts()
        
        html = self._render_template("index.html", {
            "title": "Serv Blog",
            "posts": posts
        })
        
        response.content_type("text/html")
        response.body(html)
    
    async def view_post(self, post_id: str, response: ResponseBuilder = dependency()):
        """View a single blog post"""
        try:
            post_id_int = int(post_id)
            post = self.storage.get_post_by_id(post_id_int)
            
            if not post:
                response.set_status(404)
                response.content_type("text/html")
                response.body("<h1>Post Not Found</h1>")
                return
            
            html = self._render_template("post.html", {
                "title": post.title,
                "post": post
            })
            
            response.content_type("text/html")
            response.body(html)
            
        except ValueError:
            response.set_status(400)
            response.content_type("text/html")
            response.body("<h1>Invalid Post ID</h1>")
    
    async def api_posts(self, response: ResponseBuilder = dependency()):
        """API endpoint returning posts as JSON"""
        posts = self.storage.get_all_posts()
        posts_data = [
            {
                "id": post.id,
                "title": post.title,
                "content": post.content,
                "author": post.author,
                "created_at": post.created_at.isoformat()
            }
            for post in posts
        ]
        
        response.content_type("application/json")
        response.body(json.dumps(posts_data, indent=2))
    
    def _render_template(self, template_name: str, context: dict) -> str:
        """Simple template rendering"""
        # In a real app, you'd use Jinja2 or another template engine
        # For now, we'll use simple string formatting
        
        if template_name == "index.html":
            posts_html = ""
            for post in context["posts"]:
                posts_html += f"""
                <article class="post-preview">
                    <h2><a href="/post/{post.id}">{post.title}</a></h2>
                    <p class="meta">By {post.author} on {post.created_at.strftime('%B %d, %Y')}</p>
                    <p>{post.content[:200]}...</p>
                </article>
                """
            
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{context['title']}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                    .post-preview {{ border-bottom: 1px solid #eee; padding: 20px 0; }}
                    .meta {{ color: #666; font-size: 0.9em; }}
                    a {{ color: #007bff; text-decoration: none; }}
                    a:hover {{ text-decoration: underline; }}
                    .nav {{ margin-bottom: 30px; }}
                </style>
            </head>
            <body>
                <nav class="nav">
                    <a href="/">Home</a> | 
                    <a href="/admin">Admin</a> | 
                    <a href="/api/posts">API</a>
                </nav>
                <h1>{context['title']}</h1>
                {posts_html}
            </body>
            </html>
            """
        
        elif template_name == "post.html":
            post = context["post"]
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{context['title']}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                    .meta {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
                    .content {{ line-height: 1.6; }}
                    a {{ color: #007bff; text-decoration: none; }}
                    a:hover {{ text-decoration: underline; }}
                    .nav {{ margin-bottom: 30px; }}
                </style>
            </head>
            <body>
                <nav class="nav">
                    <a href="/">← Back to Home</a>
                </nav>
                <article>
                    <h1>{post.title}</h1>
                    <p class="meta">By {post.author} on {post.created_at.strftime('%B %d, %Y')}</p>
                    <div class="content">
                        {post.content.replace(chr(10), '<br>')}
                    </div>
                </article>
            </body>
            </html>
            """
        
        return "<h1>Template not found</h1>"

class CreatePostForm(Form):
    title: str
    content: str
    author: str

class AdminRoute(Route):
    def __init__(self, storage: BlogStorage):
        self.storage = storage
    
    async def show_admin_page(self, request: Request, response: ResponseBuilder = dependency()):
        """Show the admin page with create post form"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin - Create Post</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }
                .form-group { margin-bottom: 15px; }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                input, textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
                textarea { height: 200px; resize: vertical; }
                button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
                button:hover { background: #0056b3; }
                .nav { margin-bottom: 30px; }
                a { color: #007bff; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <nav class="nav">
                <a href="/">← Back to Home</a>
            </nav>
            <h1>Create New Post</h1>
            <form method="POST" action="/admin">
                <div class="form-group">
                    <label for="title">Title:</label>
                    <input type="text" id="title" name="title" required>
                </div>
                <div class="form-group">
                    <label for="author">Author:</label>
                    <input type="text" id="author" name="author" required>
                </div>
                <div class="form-group">
                    <label for="content">Content:</label>
                    <textarea id="content" name="content" required></textarea>
                </div>
                <button type="submit">Create Post</button>
            </form>
        </body>
        </html>
        """
        
        response.content_type("text/html")
        response.body(html)
    
    async def create_post(self, form: CreatePostForm, response: ResponseBuilder = dependency()):
        """Handle post creation"""
        # Create the new post
        post = self.storage.add_post(form.title, form.content, form.author)
        
        # Redirect to the new post
        response.set_status(302)
        response.add_header("Location", f"/post/{post.id}")
        response.body("")
```

### 3. Create the Extension Configuration

Create `extensions/blog/extension.yaml`:

```yaml
name: Blog Extension
description: A simple blog extension for Serv
version: 1.0.0
author: Your Name
entry: blog.main:BlogExtension

settings:
  posts_per_page: 10
  allow_comments: false
```

### 4. Create the Main Application

Create `app.py`:

```python
from serv import App

# Create the app with extension directory
app = App(
    config="./serv.config.yaml",
    extension_dir="./extensions"
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
```

### 5. Create the Configuration File

Create `serv.config.yaml`:

```yaml
extensions:
  - extension: blog
    settings:
      posts_per_page: 5
      allow_comments: true
```

### 6. Initialize the Extension Package

Create `extensions/blog/__init__.py`:

```python
# Blog extension package
```

## Running the Application

Now let's run our blog application:

```bash
python app.py
```

Visit the following URLs to test your application:

- `http://localhost:8000/` - Homepage with blog posts
- `http://localhost:8000/post/1` - View individual post
- `http://localhost:8000/admin` - Admin interface to create posts
- `http://localhost:8000/api/posts` - JSON API endpoint

## Understanding the Code

### Extension Architecture

Our blog is implemented as a extension, which makes it:

- **Modular**: Easy to enable/disable
- **Reusable**: Can be used in multiple applications
- **Configurable**: Settings can be overridden via configuration

### Route Handling

We used two different routing approaches:

1. **Function-based routes**: Simple handlers like `homepage()` and `view_post()`
2. **Class-based routes**: The `AdminRoute` class for more complex logic

### Form Handling

The `CreatePostForm` class automatically handles form data parsing and validation:

```python
class CreatePostForm(Form):
    title: str
    content: str
    author: str
```

### Dependency Injection

Notice how we inject dependencies throughout the application:

```python
async def homepage(self, response: ResponseBuilder = dependency()):
    # ResponseBuilder is automatically injected
```

## Extending the Application

Here are some ideas for extending this blog:

### Add Database Support

Replace the in-memory storage with a real database:

```python
import sqlite3
from contextlib import asynccontextmanager

class DatabaseStorage:
    def __init__(self, db_path: str = "blog.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
```

### Add Authentication

Create an authentication extension:

```python
class AuthExtension(Extension):
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_route("/login", self.login_page)
        router.add_route("/logout", self.logout)
    
    async def login_page(self, response: ResponseBuilder = dependency()):
        # Implement login logic
        pass
```

### Add Comments

Extend the models to support comments:

```python
@dataclass
class Comment:
    id: int
    post_id: int
    author: str
    content: str
    created_at: datetime
```

### Add Rich Templates

Use Jinja2 for proper template rendering:

```python
from jinja2 import Environment, FileSystemLoader

class BlogExtension(Extension):
    def __init__(self):
        self.storage = BlogStorage()
        self.jinja_env = Environment(
            loader=FileSystemLoader('templates')
        )
    
    def _render_template(self, template_name: str, context: dict) -> str:
        template = self.jinja_env.get_template(template_name)
        return template.render(**context)
```

## Next Steps

Congratulations! You've built a complete blog application with Serv. You've learned about:

- ✅ Extension architecture
- ✅ Routing (both function and class-based)
- ✅ Form handling
- ✅ Template rendering
- ✅ Configuration management
- ✅ API endpoints

### Continue Learning

- **[Configuration](configuration.md)** - Learn about advanced configuration options
- **[Routing Guide](../guides/routing.md)** - Master advanced routing techniques
- **[Extension Development](../guides/extensions.md)** - Build more sophisticated extensions
- **[Middleware](../guides/middleware.md)** - Add cross-cutting concerns to your app

### Explore More Examples

- **[Authentication Example](../examples/authentication.md)** - Add user authentication
- **[Database Integration](../examples/database.md)** - Connect to real databases
- **[API Development](../examples/api.md)** - Build REST APIs with Serv 