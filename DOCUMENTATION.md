# Serv Framework Documentation

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Core Concepts](#core-concepts)
4. [API Reference](#api-reference)
5. [Advanced Topics](#advanced-topics)
6. [Examples & Patterns](#examples--patterns)
7. [Testing](#testing)
8. [Deployment](#deployment)

---

## Introduction

Serv is a modern, type-safe ASGI web framework for Python 3.13+ that emphasizes extensibility, clean architecture, and developer experience. Built on top of Starlette, it provides a powerful routing system, dependency injection, and comprehensive configuration management while maintaining minimal boilerplate.

### Key Features

- **Type-Safe Routing**: Automatic response type inference with full type hints
- **Dependency Injection**: Clean, testable code with bevy-based DI
- **Smart Parameter Injection**: Automatic extraction of cookies, headers, path params, and query params
- **Configuration Management**: Environment-based YAML configuration with model injection
- **Authentication System**: Flexible credential provider protocol
- **Error Handling**: Beautiful error pages with theming support
- **Testing Utilities**: Built-in e2e testing support
- **ASGI Native**: Full async/await support with Starlette foundation

### Philosophy

Serv follows these core principles:

1. **Type Safety First**: Leverage Python's type system for better IDE support and fewer runtime errors
2. **Minimal Boilerplate**: Focus on your business logic, not framework ceremony
3. **Extensibility**: Everything is customizable through a clean extension system
4. **Testability**: Dependency injection and testing utilities make testing a breeze
5. **Modern Python**: Built for Python 3.13+ with the latest language features

---

## Getting Started

### Installation

```bash
pip install serving
```

For development with auto-reload:

```bash
pip install "serving[server]"
```

### Your First Application

#### 1. Create Project Structure

```
my_app/
├── serving.prod.yaml    # Production config
├── serving.dev.yaml     # Development config
├── routes.py           # Your routes
└── templates/          # Jinja2 templates (optional)
```

#### 2. Define Routes

Create `routes.py`:

```python
from serving.router import Router
from serving.types import HTML, JSON, PlainText, Jinja2
from serving.injectors import QueryParam, PathParam

app = Router()

@app.route("/")
async def home() -> PlainText:
    return "Welcome to Serv!"

@app.route("/api/hello")
async def hello_json() -> JSON:
    return {"message": "Hello, World!", "framework": "Serv"}

@app.route("/users/{user_id}")
async def user_profile(user_id: PathParam[int]) -> HTML:
    return f"<h1>User Profile</h1><p>User ID: {user_id}</p>"

@app.route("/search")
async def search(q: QueryParam[str]) -> JSON:
    return {"query": q, "results": [f"Result for {q}"]}

@app.route("/about")
async def about_page() -> Jinja2:
    return "about.html", {"version": "1.0.0", "author": "You"}
```

#### 3. Configure Your Application

Create `serving.dev.yaml`:

```yaml
routers:
  - entrypoint: routes:app
    routes:
      - path: /
      - path: /api/hello
      - path: /users/{user_id}
      - path: /search
      - path: /about

templates:
  directory: templates
```

Create `serving.prod.yaml` with production settings:

```yaml
routers:
  - entrypoint: routes:app
    routes:
      - path: /
        permissions:
          - public:view
      - path: /api/hello
        permissions:
          - api:access
      - path: /users/{user_id}
        permissions:
          - users:view
      - path: /search
      - path: /about

auth:
  credential_provider: auth:ProductionCredentialProvider

templates:
  directory: templates
```

#### 4. Run Your Application

Development mode:
```bash
serv -e dev --reload
```

Production mode:
```bash
serv -e prod --host 0.0.0.0 --port 8000
```

---

## Core Concepts

### Routing System

Serv's routing system is built on top of Starlette but provides enhanced type safety and automatic response handling.

#### Basic Routing

```python
from serving.router import Router
from serving.types import PlainText, HTML, JSON

app = Router()

@app.route("/")
async def index() -> PlainText:
    return "Home Page"

@app.route("/api/data", methods={"GET", "POST"})
async def api_endpoint() -> JSON:
    return {"status": "success"}
```

#### Path Parameters

Path parameters are automatically extracted and type-converted:

```python
@app.route("/users/{user_id}/posts/{post_id}")
async def user_post(user_id: int, post_id: int) -> JSON:
    return {"user": user_id, "post": post_id}
```

#### Response Types

Serv supports multiple response types with automatic content-type handling:

```python
from serving.types import PlainText, HTML, JSON, Jinja2

@app.route("/text")
async def plain_text() -> PlainText:
    return "Plain text response"

@app.route("/html")
async def html_page() -> HTML:
    return "<h1>HTML Response</h1>"

@app.route("/json")
async def json_api() -> JSON:
    return {"key": "value"}

@app.route("/template")
async def template_page() -> Jinja2:
    return "template.html", {"data": "context"}
```

### Dependency Injection

Serv uses the bevy library for dependency injection, providing clean separation of concerns and testability.

#### Basic Injection

```python
from bevy import dependency
from starlette.requests import Request

@app.route("/request-info")
async def request_info(request: Request = dependency()) -> JSON:
    return {
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers)
    }
```

#### Parameter Injection

Serv provides specialized injectors for common web parameters:

```python
from serving.injectors import Cookie, Header, QueryParam, PathParam
from typing import Annotated

@app.route("/api/data")
async def api_data(
    auth_token: Header[str],  # Extracts 'auth-token' header
    session_id: Cookie[str],  # Extracts 'session-id' cookie
    page: QueryParam[int],     # Extracts 'page' query param
    format: Annotated[str, QueryParam("fmt")]  # Custom param name
) -> JSON:
    return {
        "auth": auth_token,
        "session": session_id,
        "page": page,
        "format": format
    }
```

### Configuration System

Serv uses YAML-based configuration with environment support and model injection.

#### Configuration Files

Configuration files follow the pattern `serving.{environment}.yaml`:

```yaml
# serving.dev.yaml
database:
  host: localhost
  port: 5432
  username: devuser
  password: devpass
  database: myapp_dev

server:
  host: 127.0.0.1
  port: 8000
  debug: true
  workers: 1

routers:
  - entrypoint: routes:app
    prefix: /api
    routes:
      - path: /users
        method: GET
      - path: /users/{id}
        method: GET
```

#### Configuration Models

Define configuration models for type-safe config access:

```python
from dataclasses import dataclass
from serving.config import ConfigModel

@dataclass
class DatabaseConfig(ConfigModel, model_key="database"):
    host: str
    port: int
    username: str
    password: str
    database: str
    pool_size: int = 10
    
@dataclass
class ServerConfig(ConfigModel, model_key="server"):
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    workers: int = 1

# Usage in routes
@app.route("/db-info")
async def db_info(db_config: DatabaseConfig = dependency()) -> JSON:
    return {
        "host": db_config.host,
        "database": db_config.database,
        "pool_size": db_config.pool_size
    }
```

### Authentication

Serv provides a flexible authentication system based on credential providers.

#### Credential Provider Protocol

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class CredentialProvider(Protocol):
    def has_credentials(self, permissions: set[str]) -> bool:
        """Check if the current request has the required permissions."""
        ...
```

#### Implementation Example

```python
# auth.py
from serving.auth import CredentialProvider
from starlette.requests import Request
from bevy import dependency

class SimpleCredentialProvider:
    def __init__(self):
        self.permissions = set()
    
    def has_credentials(
        self, 
        permissions: set[str],
        request: Request = dependency()
    ) -> bool:
        # Check for API key
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return False
            
        # Validate API key and load permissions
        if api_key == "secret-key":
            user_permissions = {"api:access", "users:view"}
            return permissions.issubset(user_permissions)
        
        return False
```

Configure in YAML:

```yaml
auth:
  credential_provider: auth:SimpleCredentialProvider

routers:
  - entrypoint: routes:app
    routes:
      - path: /protected
        permissions:
          - api:access
```

### Response Utilities

Serv provides utilities for modifying responses:

```python
from serving.response import (
    set_header, 
    set_status_code, 
    set_cookie, 
    delete_cookie, 
    redirect,
    Status
)

@app.route("/set-cookie")
async def set_user_cookie() -> PlainText:
    set_cookie("user_id", "12345")
    set_header("X-Custom-Header", "value")
    set_status_code(Status.CREATED)
    return "Cookie set!"

@app.route("/logout")
async def logout() -> PlainText:
    delete_cookie("session_id")
    redirect("/login")
    return "Redirecting..."  # This won't be reached

@app.route("/api/created")
async def resource_created() -> JSON:
    set_status_code(201)  # Or Status.CREATED
    set_header("Location", "/api/resource/123")
    return {"id": 123, "created": True}
```

---

## API Reference

### Core Classes

#### `Serv`

The main application class that configures and runs your web application.

```python
class Serv:
    def __init__(
        self,
        working_directory: str | Path | None = None,
        environment: str | None = None
    ):
        """
        Initialize Serv application.
        
        Args:
            working_directory: Path to config files directory
            environment: Environment name (e.g., 'dev', 'prod')
                        Falls back to SERV_ENVIRONMENT env var
        """
```

#### `Router`

Handles route registration and HTTP method dispatch.

```python
class Router:
    def route(
        self, 
        path: str, 
        methods: set[str] = {"GET"}
    ) -> Callable:
        """
        Register a route handler.
        
        Args:
            path: URL path pattern with optional parameters
            methods: Set of HTTP methods to handle
        """
```

### Configuration Classes

#### `Config`

Main configuration container.

```python
class Config:
    @classmethod
    def load_config(cls, name: str, directory: str = ".") -> Config:
        """Load configuration from YAML file."""
    
    def get(self, key: str, model: type[T] | None = None) -> T:
        """Get configuration value or model instance."""
```

#### `ConfigModel`

Base class for configuration models.

```python
class ConfigModel:
    """
    Base class for configuration models.
    
    Args:
        model_key: Configuration key to read from
        is_collection: Whether this represents a list of items
    """
```

### Response Types

#### Type Aliases

```python
type JSON = dict | list | str | int | float | bool | None
type PlainText = str
type HTML = str
type Jinja2 = tuple[str, dict]  # (template_name, context)
```

### Injector Types

#### Parameter Injectors

```python
type Cookie[T] = T         # Extract cookie value
type Header[T] = T         # Extract header value  
type PathParam[T] = T      # Extract path parameter
type QueryParam[T] = T     # Extract query parameter
```

Usage with type annotations:

```python
async def handler(
    user_id: PathParam[int],
    session: Cookie[str],
    auth: Header[str],
    page: QueryParam[int]
) -> JSON:
    ...
```

### Response Utilities

#### Functions

```python
def set_header(name: str, value: str) -> None:
    """Set a response header."""

def set_status_code(status_code: int | Status) -> None:
    """Set the response status code."""

def set_cookie(name: str, value: str) -> None:
    """Set a cookie in the response."""

def delete_cookie(name: str) -> None:
    """Delete a cookie."""

def redirect(url: str, status_code: int | Status = Status.TEMPORARY_REDIRECT) -> None:
    """Redirect to another URL."""
```

#### Status Enum

```python
class Status(IntEnum):
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    MOVED_PERMANENTLY = 301
    FOUND = 302
    SEE_OTHER = 303
    NOT_MODIFIED = 304
    TEMPORARY_REDIRECT = 307
    PERMANENT_REDIRECT = 308
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500
```

### Authentication

#### `CredentialProvider` Protocol

```python
class CredentialProvider(Protocol):
    def has_credentials(self, permissions: set[str]) -> bool:
        """
        Check if the current request has required permissions.
        
        Args:
            permissions: Set of required permission strings
            
        Returns:
            True if all permissions are granted
        """
```

---

## Advanced Topics

### Custom Middleware

Create custom middleware using Starlette's middleware system:

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
```

### Error Handling & Theming

#### Custom Error Pages

Configure custom error templates in your configuration:

```yaml
theming:
  error_templates:
    404: errors/404.html
    500: errors/500.html
  default_error_template: errors/default.html
```

Create error templates:

```html
<!-- templates/errors/404.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Page Not Found</title>
</head>
<body>
    <h1>404 - Page Not Found</h1>
    <p>{{ error_message }}</p>
    {% if details %}
    <pre>{{ details }}</pre>
    {% endif %}
</body>
</html>
```

#### Custom Exception Handlers

```python
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

async def custom_404_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Resource not found", "path": str(request.url)}
    )

async def validation_error_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"error": "Validation failed", "details": str(exc)}
    )
```

### Complex Dependency Injection

#### Scoped Dependencies

```python
from bevy import dependency
from dataclasses import dataclass
import uuid

@dataclass
class RequestContext:
    request_id: str
    user_id: str | None = None
    
    @classmethod
    def create(cls, request: Request = dependency()):
        return cls(
            request_id=str(uuid.uuid4()),
            user_id=request.headers.get("X-User-ID")
        )

# Register in your container
serv.container.add(RequestContext, RequestContext.create)

# Use in routes
@app.route("/context")
async def show_context(ctx: RequestContext = dependency()) -> JSON:
    return {
        "request_id": ctx.request_id,
        "user_id": ctx.user_id
    }
```

#### Database Connection Pool

```python
from dataclasses import dataclass
import asyncpg

@dataclass
class DatabasePool:
    pool: asyncpg.Pool
    
    @classmethod
    async def create(cls, config: DatabaseConfig = dependency()):
        pool = await asyncpg.create_pool(
            host=config.host,
            port=config.port,
            user=config.username,
            password=config.password,
            database=config.database,
            min_size=1,
            max_size=config.pool_size
        )
        return cls(pool=pool)

# Usage in routes
@app.route("/users")
async def list_users(db: DatabasePool = dependency()) -> JSON:
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users")
        return [dict(row) for row in rows]
```

### Router Configuration

#### Prefix and Mount Points

```yaml
routers:
  - entrypoint: api.users:router
    prefix: /api/users
    routes:
      - path: /
        method: GET
      - path: /{id}
        method: GET
      - path: /
        method: POST
        permissions:
          - users:create
          
  - entrypoint: api.admin:router
    prefix: /admin
    routes:
      - path: /dashboard
        permissions:
          - admin:access
```

#### Dynamic Route Registration

```python
from serving.router import Router

api_router = Router()

# Register routes dynamically
def register_crud_routes(resource_name: str, model_class):
    @api_router.route(f"/{resource_name}")
    async def list_resources() -> JSON:
        return {"resources": []}
    
    @api_router.route(f"/{resource_name}/{{id}}")
    async def get_resource(id: int) -> JSON:
        return {"id": id, "type": resource_name}
    
    @api_router.route(f"/{resource_name}", methods={"POST"})
    async def create_resource() -> JSON:
        return {"created": True}

# Register for multiple resources
register_crud_routes("users", User)
register_crud_routes("posts", Post)
register_crud_routes("comments", Comment)
```

---

## Examples & Patterns

### RESTful API

```python
from serving.router import Router
from serving.types import JSON
from serving.injectors import PathParam
from serving.response import set_status_code, Status
from dataclasses import dataclass
from typing import List

app = Router()

# In-memory database
users_db = {}
next_id = 1

@dataclass
class User:
    id: int
    name: str
    email: str

@app.route("/api/users", methods={"GET"})
async def list_users() -> JSON:
    return [vars(user) for user in users_db.values()]

@app.route("/api/users/{user_id}", methods={"GET"})
async def get_user(user_id: PathParam[int]) -> JSON:
    if user_id not in users_db:
        set_status_code(Status.NOT_FOUND)
        return {"error": "User not found"}
    return vars(users_db[user_id])

@app.route("/api/users", methods={"POST"})
async def create_user(request: Request = dependency()) -> JSON:
    global next_id
    data = await request.json()
    user = User(id=next_id, name=data["name"], email=data["email"])
    users_db[next_id] = user
    next_id += 1
    set_status_code(Status.CREATED)
    set_header("Location", f"/api/users/{user.id}")
    return vars(user)

@app.route("/api/users/{user_id}", methods={"PUT"})
async def update_user(
    user_id: PathParam[int],
    request: Request = dependency()
) -> JSON:
    if user_id not in users_db:
        set_status_code(Status.NOT_FOUND)
        return {"error": "User not found"}
    
    data = await request.json()
    user = users_db[user_id]
    user.name = data.get("name", user.name)
    user.email = data.get("email", user.email)
    return vars(user)

@app.route("/api/users/{user_id}", methods={"DELETE"})
async def delete_user(user_id: PathParam[int]) -> JSON:
    if user_id not in users_db:
        set_status_code(Status.NOT_FOUND)
        return {"error": "User not found"}
    
    del users_db[user_id]
    set_status_code(Status.NO_CONTENT)
    return {}
```

### Form Handling

```python
from dataclasses import dataclass
from serving.forms import Form, CSRFProtection
from serving.router import Router
from serving.types import Jinja2

app = Router()

@dataclass
class Login(Form, template="login.html"):
    username: str
    password: str
    confirm_password: str

@app.route("/login")
async def show_login() -> Jinja2:
    return "page.html", {"login_form": Login(username="", password="", confirm_password="")}

# login.html
# <form method="post">
#     {{ csrf() }}
#     <input name="username" value="{{ form.username }}">
#     <input name="password" type="password" value="{{ form.password }}">
#     <input name="confirm_password" type="password" value="{{ form.confirm_password }}">
# </form>

# If csrf() is omitted, rendering raises MissingCSRFTokenError

# Disable CSRF explicitly
class Search(Form, template="search.html", csrf=CSRFProtection.Disabled):
    query: str
```

### File Upload

```python
from serving.router import Router
from serving.types import JSON, HTML
from starlette.requests import Request
from bevy import dependency
import aiofiles

app = Router()

@app.route("/upload", methods={"GET"})
async def upload_form() -> HTML:
    return """
    <form method="post" action="/upload" enctype="multipart/form-data">
        <input type="file" name="file" required>
        <button type="submit">Upload</button>
    </form>
    """

@app.route("/upload", methods={"POST"})
async def handle_upload(request: Request = dependency()) -> JSON:
    form = await request.form()
    upload = form["file"]
    
    # Save the file
    async with aiofiles.open(f"uploads/{upload.filename}", "wb") as f:
        content = await upload.read()
        await f.write(content)
    
    return {
        "filename": upload.filename,
        "content_type": upload.content_type,
        "size": len(content)
    }
```

### Session Management

```python
from serving.router import Router
from serving.types import JSON, HTML
from serving.injectors import Cookie
from serving.response import set_cookie, delete_cookie
import secrets
from typing import Dict

app = Router()

# Simple in-memory session store
sessions: Dict[str, dict] = {}

@app.route("/login", methods={"POST"})
async def login(request: Request = dependency()) -> JSON:
    data = await request.json()
    username = data["username"]
    password = data["password"]
    
    # Validate credentials
    if username == "admin" and password == "secret":
        # Create session
        session_id = secrets.token_urlsafe(32)
        sessions[session_id] = {
            "username": username,
            "logged_in": True
        }
        set_cookie("session_id", session_id)
        return {"status": "success", "message": "Logged in"}
    
    set_status_code(Status.UNAUTHORIZED)
    return {"status": "error", "message": "Invalid credentials"}

@app.route("/profile")
async def profile(session_id: Cookie[str]) -> JSON:
    if not session_id or session_id not in sessions:
        set_status_code(Status.UNAUTHORIZED)
        return {"error": "Not logged in"}
    
    session = sessions[session_id]
    return {
        "username": session["username"],
        "logged_in": session["logged_in"]
    }

@app.route("/logout", methods={"POST"})
async def logout(session_id: Cookie[str]) -> JSON:
    if session_id and session_id in sessions:
        del sessions[session_id]
    delete_cookie("session_id")
    return {"status": "success", "message": "Logged out"}
```

### Background Tasks

```python
from serving.router import Router
from serving.types import JSON
from starlette.background import BackgroundTasks
from bevy import dependency
import asyncio

app = Router()

async def send_email(email: str, subject: str, body: str):
    """Simulate sending an email."""
    await asyncio.sleep(2)  # Simulate email sending
    print(f"Email sent to {email}: {subject}")

@app.route("/send-notification", methods={"POST"})
async def send_notification(
    request: Request = dependency(),
    background: BackgroundTasks = dependency()
) -> JSON:
    data = await request.json()
    
    # Add background task
    background.add_task(
        send_email,
        data["email"],
        data["subject"],
        data["body"]
    )
    
    return {
        "status": "success",
        "message": "Notification queued for sending"
    }
```

---

## Testing

### Test Client

Serv provides testing utilities for e2e testing without running a server:

```python
import pytest
from httpx import AsyncClient
from serving.serv import Serv

@pytest.fixture
async def client():
    serv = Serv(working_directory="tests/fixtures", environment="test")
    async with AsyncClient(app=serv.app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_home_page(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Welcome" in response.text

@pytest.mark.asyncio
async def test_api_endpoint(client):
    response = await client.get("/api/users")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_create_user(client):
    response = await client.post(
        "/api/users",
        json={"name": "Test User", "email": "test@example.com"}
    )
    assert response.status_code == 201
    assert response.headers["Location"]
    data = response.json()
    assert data["name"] == "Test User"
```

### Testing with Dependency Injection

```python
import pytest
from bevy import Container
from serving.config import Config
from serving.injectors import handle_config_model_types

@pytest.fixture
def container():
    registry = Registry()
    handle_config_model_types.register_hook(registry)
    container = registry.create_container()
    
    # Add test configuration
    config = Config({
        "database": {
            "host": "test.db",
            "port": 5432,
            "username": "test",
            "password": "test",
            "database": "test_db"
        }
    })
    container.add(config)
    return container

def test_config_injection(container):
    from myapp.models import DatabaseConfig
    
    db_config = container.get(DatabaseConfig)
    assert db_config.host == "test.db"
    assert db_config.database == "test_db"
```

### Mocking External Services

```python
import pytest
from unittest.mock import Mock, AsyncMock
from serving.serv import Serv

@pytest.fixture
def mock_email_service():
    return AsyncMock()

@pytest.fixture
async def app(mock_email_service):
    serv = Serv(environment="test")
    serv.container.add(EmailService, mock_email_service)
    return serv.app

@pytest.mark.asyncio
async def test_send_email_endpoint(client, mock_email_service):
    response = await client.post(
        "/send-email",
        json={
            "to": "user@example.com",
            "subject": "Test",
            "body": "Test message"
        }
    )
    
    assert response.status_code == 200
    mock_email_service.send.assert_called_once_with(
        "user@example.com", "Test", "Test message"
    )
```

---

## Deployment

### ASGI Deployment

Serv applications are standard ASGI applications and can be deployed with any ASGI server.

#### Using Uvicorn

```bash
# Development
uvicorn serving.app:app --reload --host 127.0.0.1 --port 8000

# Production
uvicorn serving.app:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Using Gunicorn with Uvicorn Workers

```bash
gunicorn serving.app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### Using Hypercorn

```bash
hypercorn serving.app:app --bind 0.0.0.0:8000 --workers 4
```

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

# Copy application
COPY . .

# Set environment
ENV SERV_ENVIRONMENT=prod

# Run application
CMD ["uvicorn", "serving.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t my-serv-app .
docker run -p 8000:8000 my-serv-app
```

### Environment Configuration

Use environment variables for deployment configuration:

```bash
export SERV_ENVIRONMENT=prod
export DATABASE_URL=postgresql://user:pass@db:5432/myapp
export SECRET_KEY=your-secret-key
export API_KEY=your-api-key
```

Access in your application:

```python
import os
from dataclasses import dataclass
from serving.config import ConfigModel

@dataclass
class AppConfig(ConfigModel, model_key="app"):
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///app.db")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret")
    api_key: str = os.getenv("API_KEY", "")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
```

### Production Checklist

1. **Security**
   - Enable HTTPS with SSL certificates
   - Set secure headers (HSTS, CSP, etc.)
   - Use environment variables for secrets
   - Implement rate limiting
   - Enable CORS appropriately

2. **Performance**
   - Use a production ASGI server (Uvicorn, Gunicorn)
   - Configure appropriate worker count
   - Enable response caching where appropriate
   - Use a CDN for static assets
   - Implement database connection pooling

3. **Monitoring**
   - Set up application logging
   - Configure error tracking (Sentry, etc.)
   - Implement health check endpoints
   - Monitor performance metrics
   - Set up alerts for critical issues

4. **Database**
   - Use connection pooling
   - Implement database migrations
   - Regular backups
   - Read replicas for scaling

### Example Production Configuration

```yaml
# serving.prod.yaml
server:
  workers: 4
  timeout: 30
  max_connections: 1000

database:
  host: ${DATABASE_HOST}
  port: ${DATABASE_PORT}
  username: ${DATABASE_USER}
  password: ${DATABASE_PASSWORD}
  database: ${DATABASE_NAME}
  pool_size: 20
  max_overflow: 10

cache:
  backend: redis
  url: ${REDIS_URL}
  ttl: 3600

security:
  secret_key: ${SECRET_KEY}
  allowed_hosts:
    - example.com
    - www.example.com
  https_only: true
  
logging:
  level: INFO
  format: json
  output: stdout
  
monitoring:
  sentry_dsn: ${SENTRY_DSN}
  metrics_enabled: true
```

---

## Migration Guide

### From Flask

```python
# Flask
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/users/<int:user_id>")
def get_user(user_id):
    return jsonify({"id": user_id})

# Serv
from serving.router import Router
from serving.types import JSON
from serving.injectors import PathParam

app = Router()

@app.route("/users/{user_id}")
async def get_user(user_id: PathParam[int]) -> JSON:
    return {"id": user_id}
```

### From FastAPI

```python
# FastAPI
from fastapi import FastAPI, Query, Header

app = FastAPI()

@app.get("/items")
async def read_items(q: str = Query(None), auth: str = Header(None)):
    return {"q": q, "auth": auth}

# Serv
from serving.router import Router
from serving.types import JSON
from serving.injectors import QueryParam, Header

app = Router()

@app.route("/items")
async def read_items(
    q: QueryParam[str] | None,
    auth: Header[str] | None
) -> JSON:
    return {"q": q, "auth": auth}
```

### From Django

```python
# Django views.py
from django.http import JsonResponse
from django.views import View

class UserView(View):
    def get(self, request, user_id):
        return JsonResponse({"id": user_id})

# Serv
from serving.router import Router
from serving.types import JSON
from serving.injectors import PathParam

app = Router()

@app.route("/users/{user_id}")
async def get_user(user_id: PathParam[int]) -> JSON:
    return {"id": user_id}
```

---

## Best Practices

### Project Structure

```
my_project/
├── src/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── api.py
│   │   ├── auth.py
│   │   └── web.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── config.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   └── email.py
│   └── middleware/
│       ├── __init__.py
│       └── auth.py
├── templates/
│   ├── base.html
│   └── errors/
│       ├── 404.html
│       └── 500.html
├── tests/
│   ├── __init__.py
│   ├── test_routes.py
│   ├── test_services.py
│   └── fixtures/
│       └── serving.test.yaml
├── serving.dev.yaml
├── serving.prod.yaml
├── pyproject.toml
├── Dockerfile
└── README.md
```

### Type Safety

Always use type hints for better IDE support and runtime validation:

```python
from typing import List, Optional
from serving.types import JSON
from serving.injectors import QueryParam

@app.route("/search")
async def search(
    q: QueryParam[str],
    limit: QueryParam[int] = 10,
    offset: QueryParam[int] = 0,
    tags: QueryParam[List[str]] | None = None
) -> JSON:
    results = await search_database(q, limit, offset, tags or [])
    return {
        "query": q,
        "results": results,
        "total": len(results)
    }
```

### Error Handling

Implement comprehensive error handling:

```python
from serving.router import Router
from serving.types import JSON
from serving.response import set_status_code, Status

app = Router()

class ValidationError(Exception):
    pass

class NotFoundError(Exception):
    pass

@app.route("/api/resource/{id}")
async def get_resource(id: int) -> JSON:
    try:
        resource = await fetch_resource(id)
        if not resource:
            raise NotFoundError(f"Resource {id} not found")
        return resource
    except NotFoundError as e:
        set_status_code(Status.NOT_FOUND)
        return {"error": str(e)}
    except ValidationError as e:
        set_status_code(Status.BAD_REQUEST)
        return {"error": str(e)}
    except Exception as e:
        set_status_code(Status.INTERNAL_SERVER_ERROR)
        return {"error": "Internal server error"}
```

### Logging

Implement structured logging:

```python
import logging
from serving.router import Router
from bevy import dependency

logger = logging.getLogger(__name__)

@app.route("/api/action")
async def perform_action(
    request: Request = dependency()
) -> JSON:
    logger.info(
        "Action performed",
        extra={
            "user_id": request.headers.get("X-User-ID"),
            "action": "perform_action",
            "ip": request.client.host
        }
    )
    
    try:
        result = await do_something()
        logger.info("Action completed successfully")
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(
            "Action failed",
            exc_info=True,
            extra={"error": str(e)}
        )
        raise
```

### Performance Optimization

1. **Use Connection Pooling**

```python
import asyncpg
from contextlib import asynccontextmanager

class DatabaseService:
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.pool = None
    
    async def connect(self):
        self.pool = await asyncpg.create_pool(
            host=self.config.host,
            port=self.config.port,
            user=self.config.username,
            password=self.config.password,
            database=self.config.database,
            min_size=5,
            max_size=20
        )
    
    @asynccontextmanager
    async def acquire(self):
        async with self.pool.acquire() as conn:
            yield conn
```

2. **Implement Caching**

```python
from functools import lru_cache
import asyncio
from datetime import datetime, timedelta

class CacheService:
    def __init__(self):
        self.cache = {}
        self.expiry = {}
    
    async def get_or_set(self, key: str, factory, ttl: int = 3600):
        if key in self.cache:
            if self.expiry[key] > datetime.now():
                return self.cache[key]
        
        value = await factory()
        self.cache[key] = value
        self.expiry[key] = datetime.now() + timedelta(seconds=ttl)
        return value

@app.route("/api/expensive")
async def expensive_operation(cache: CacheService = dependency()) -> JSON:
    result = await cache.get_or_set(
        "expensive_result",
        lambda: perform_expensive_calculation(),
        ttl=3600
    )
    return {"result": result}
```

---

## Troubleshooting

### Common Issues

#### Configuration Not Found

**Error**: `ConfigurationError: serving.prod.yaml not found`

**Solution**: Ensure your configuration file exists in the working directory and matches the environment name.

```bash
# Check current directory
ls serving.*.yaml

# Run with explicit environment
serv -e dev

# Or set environment variable
export SERV_ENVIRONMENT=dev
serv
```

#### Dependency Resolution Error

**Error**: `DependencyResolutionError: No handler found for type`

**Solution**: Ensure the dependency is properly registered in the container:

```python
# Register custom dependencies
serv.container.add(MyService, MyService())

# Or use factory functions
serv.container.add(MyService, lambda: MyService(config))
```

#### Route Not Found

**Error**: 404 errors for defined routes

**Solution**: Ensure routes are registered in your configuration:

```yaml
routers:
  - entrypoint: routes:app
    routes:
      - path: /your-route
```

#### Type Annotation Errors

**Error**: `TypeError: unsupported response type`

**Solution**: Use proper type annotations:

```python
# Correct
from serving.types import JSON

@app.route("/api/data")
async def get_data() -> JSON:  # ✓ Proper type annotation
    return {"data": "value"}

# Incorrect
@app.route("/api/data")
async def get_data():  # ✗ Missing type annotation
    return {"data": "value"}
```

### Performance Issues

#### Slow Response Times

1. **Enable async operations**:
```python
# Use async database queries
async with db.acquire() as conn:
    result = await conn.fetch("SELECT * FROM users")
```

2. **Implement caching**:
```python
from functools import lru_cache

@lru_cache(maxsize=100)
async def get_cached_data(key: str):
    return await fetch_from_database(key)
```

3. **Use connection pooling**:
```python
pool = await asyncpg.create_pool(
    min_size=5,
    max_size=20,
    command_timeout=60
)
```

#### Memory Leaks

1. **Clean up resources**:
```python
async def cleanup():
    await db_pool.close()
    await cache.clear()
    await session.close()

# Register cleanup
app.on_shutdown(cleanup)
```

2. **Use context managers**:
```python
async with acquire_resource() as resource:
    # Resource is automatically cleaned up
    await use_resource(resource)
```

### Debugging Tips

1. **Enable debug mode**:
```yaml
# serving.dev.yaml
server:
  debug: true
  reload: true
```

2. **Use logging extensively**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.route("/debug")
async def debug_endpoint(request: Request = dependency()) -> JSON:
    logger.debug(f"Headers: {dict(request.headers)}")
    logger.debug(f"Query params: {dict(request.query_params)}")
    return {"debug": "info"}
```

3. **Use interactive debugging**:
```python
import pdb

@app.route("/debug")
async def debug_route() -> JSON:
    pdb.set_trace()  # Debugger will stop here
    return {"debug": "info"}
```

---

## Conclusion

Serv provides a modern, type-safe foundation for building web applications in Python. Its focus on dependency injection, type safety, and minimal boilerplate makes it an excellent choice for both small projects and large-scale applications.

### Key Takeaways

- **Type Safety**: Leverage Python's type system for better code quality
- **Dependency Injection**: Write testable, maintainable code
- **Configuration Management**: Environment-based configuration with model validation
- **Extensibility**: Everything can be customized and extended
- **Modern Python**: Built for Python 3.13+ with async/await throughout

### Next Steps

1. Install Serv: `pip install serving`
2. Create your first application following the Getting Started guide
3. Explore the examples in this documentation
4. Join the community and contribute to the project

### Resources

- **GitHub Repository**: [https://github.com/8ly/Serv](https://github.com/8ly/Serv)
- **PyPI Package**: [https://pypi.org/project/serving/](https://pypi.org/project/serving/)
- **Issue Tracker**: [https://github.com/8ly/Serv/issues](https://github.com/8ly/Serv/issues)

### Support

For questions, bug reports, or feature requests, please open an issue on GitHub or reach out to the community.

---

*Serv - Build web applications your way.*