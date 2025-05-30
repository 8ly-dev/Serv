# Serv: The Extensible Python Web Framework 🚀

> [!WARNING]
> **Serv is currently in alpha and is NOT recommended for production use. APIs are subject to change.**

**Build web applications your way.** Serv is a modern ASGI web framework that puts extensions first, letting you craft everything from simple APIs to complex web applications using a powerful CLI and modular architecture.

## ✨ Why Serv?

- **🔧 CLI-First Development**: Get started in seconds with powerful scaffolding
- **🧩 Extension-Driven**: Build features as reusable extensions
- **🎯 Smart Routing**: Signature-based route handlers that just work
- **⚡ Modern Architecture**: ASGI-native with dependency injection
- **🧪 Test-Friendly**: Built-in testing patterns and utilities

## 🚀 Quick Start

### Installation

```bash
pip install getserving
```

### Create Your First App

```bash
# Initialize a new Serv project
serv create app

# Create your first extension
serv create extension --name users

# Add a route to handle user data
serv create route --name user-api --path /api/users

# Enable the extension
serv extension enable users

# Start developing
serv launch --dev
```

Your site is running at http://127.0.0.1:8000 🎉

## 🏗️ Core Concepts

### Extensions Are Everything

In Serv, functionality lives in **extensions**. Each extension is a self-contained module in the `extensions/` directory:

```
my-project/
├── serv.config.yaml      # App configuration
└── extensions/           # Your extensions
    └── users/
        ├── extension.yaml
        └── main.py
```

### Routes with Personality

Routes in Serv are **classes** that handle HTTP methods intelligently:

```python
from typing import Annotated
from serv.routes import Route, handle
from serv.responses import JsonResponse, HtmlResponse

class UserRoute(Route):
    @handle.GET
    async def get_user(self) -> Annotated[dict, JsonResponse]:
        return {"id": 1, "name": "John Doe"}
    
    @handle.POST
    async def create_user(self, name: str) -> Annotated[str, HtmlResponse]:
        return f"<h1>Created user: {name}</h1>"
```

### Smart Parameter Injection

Routes automatically inject what you need:

```python
from serv.injectors import Query, Header, Cookie

class SearchRoute(Route):
    @handle.GET
    async def search_basic(self) -> Annotated[dict, JsonResponse]:
        """Handles /search with no parameters"""
        return {"results": ["default", "results"]}
    
    @handle.GET 
    async def search_with_query(
        self, 
        q: Annotated[str, Query("q")]
    ) -> Annotated[dict, JsonResponse]:
        """Handles /search?q=something"""
        return {"query": q, "results": [f"result for {q}"]}
    
    @handle.GET
    async def search_authenticated(
        self,
        q: Annotated[str, Query("q")],
        auth: Annotated[str, Header("Authorization")]
    ) -> Annotated[dict, JsonResponse]:
        """Handles /search?q=something with Authorization header"""
        return {"query": q, "authenticated": True}
```

Serv automatically picks the **most specific** handler based on available request data.

## 🔧 Building with the CLI

### Project Management

```bash
# Initialize new project
serv create app

# Validate your configuration
serv config validate

# Show current settings
serv config show
```

### Extension Development

```bash
# Create an extension
serv create extension --name blog

# Add components to your extension
serv create route --name article --path /articles
serv create listener --name email-notifications  
serv create middleware --name rate-limiting

# Manage extensions
serv extension list
serv extension enable blog
serv extension validate blog
```

### Development & Testing

```bash
# Start development server with auto-reload
serv launch --dev

# Run tests
serv test

# Interactive debugging shell
serv shell
```

## 🧩 Extension Patterns

### Extension Structure

Each extension follows a standard pattern:

```yaml
# extensions/blog/extension.yaml
name: Blog
description: A simple blog system
version: 1.0.0
author: You

listeners:
  - main:BlogExtension

# Optional: Define routes declaratively
routers:
  - name: blog_router
    routes:
      - path: /blog
        handler: main:BlogHomeRoute
      - path: /blog/{slug}
        handler: main:BlogPostRoute
```

```python
# extensions/blog/main.py
from typing import Annotated
from serv.routes import Route, handle, HtmlResponse

class BlogHomeRoute(Route):
    @handle.GET
    async def show_posts(self) -> Annotated[str, HtmlResponse]:
        return "<h1>My Blog</h1><p>Welcome to my blog!</p>"

class BlogPostRoute(Route):
    @handle.GET
    async def show_post(self, slug: str) -> Annotated[str, HtmlResponse]:
        return f"<h1>Post: {slug}</h1><p>Blog post content here.</p>"
```

### Form Handling

```python
from typing import Annotated
from dataclasses import dataclass
from serv.routes import Form, Route, HtmlResponse, handle

@dataclass
class ContactForm(Form):
    name: str
    email: str
    message: str

class ContactRoute(Route):
    @handle.GET
    async def show_form(self) -> Annotated[str, HtmlResponse]:
        return """
        <form method="post">
            <input name="name" placeholder="Name" required>
            <input name="email" type="email" placeholder="Email" required>
            <textarea name="message" placeholder="Message" required></textarea>
            <button type="submit">Send</button>
        </form>
        """
    
    @handle.POST
    async def process_form(self, form: ContactForm) -> Annotated[str, HtmlResponse]:
        # Form is automatically parsed and validated
        return f"Thanks {form.name}! We'll contact you at {form.email}."
```

### Event System

```python
from serv.extensions import Listener, on

class NotificationExtension(Listener):
    @on("user.created")
    async def send_welcome_email(self, user_id: int, email: str):
        await self.send_email(email, "Welcome!")
    
    @on("order.completed")  
    async def send_receipt(self, order_id: int, customer_email: str):
        await self.send_email(customer_email, f"Receipt for order {order_id}")

# Emit events from anywhere in your app
await self.emit("user.created", user_id=123, email="user@example.com")
```

## 🧪 Testing Your Extensions

Serv includes comprehensive testing utilities:

```python
import pytest
from tests.helpers import RouteTestExtension

@pytest.mark.asyncio
async def test_user_route(app, client):
    # Add route to test app
    plugin = RouteTestExtension("/users", UserRoute)
    app.add_extension(plugin)
    
    # Test the route
    response = await client.get("/users")
    assert response.status_code == 200
    
    # Test with parameters
    response = await client.get("/users?search=john")
    assert "john" in response.json()["results"]
```

```python
# Test forms and file uploads
@pytest.mark.asyncio  
async def test_contact_form(app, client):
    plugin = RouteTestExtension("/contact", ContactRoute)
    app.add_extension(plugin)
    
    # Test form submission
    response = await client.post("/contact", data={
        "name": "John",
        "email": "john@example.com", 
        "message": "Hello!"
    })
    assert "Thanks John!" in response.text
```

## 📚 Examples

Check out the comprehensive demos in the `/demos/` directory:

- **[Basic App](demos/basic_app/)** - Simple routes and responses
- **[Extension Demo](demos/extension_middleware_demo/)** - Full extension with middleware  
- **[Signature Routing](demos/signature_routing_demo/)** - Advanced parameter injection
- **[Complex Routes](demos/complex_route_demo/)** - Multi-handler routes

## 🔄 Deployment

### ASGI Deployment

Serv apps are standard ASGI applications:

```python
# main.py
from serv.app import App

app = App(config="serv.config.yaml")
```

```bash
# Production with Gunicorn
gunicorn main:app -k uvicorn.workers.UvicornWorker

# Development with Uvicorn
uvicorn main:app --reload

# Or use Serv's CLI
serv launch --host 0.0.0.0 --port 8000
```

### Configuration

```yaml
# serv.config.yaml
site_info:
  name: "My Web App"
  description: "Built with Serv"

extensions:
  - users      # Load from extensions/users/
  - blog       # Load from extensions/blog/
  - auth:      # Load with custom config
      settings:
        secret_key: "your-secret-key"

middleware:
  - logging
  - rate_limiting
```

## 🤝 Contributing

We welcome contributions! Whether it's:

- 🐛 Bug reports and fixes
- 💡 Feature suggestions and implementations
- 📖 Documentation improvements
- 🧪 Tests and examples

Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

Serv is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

**Ready to serve?** 🍽️ Start building with `serv create app` and discover the power of extension-driven development.