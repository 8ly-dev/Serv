# Testing

Testing is essential for building reliable web applications. Serv provides comprehensive testing support through pytest integration, test fixtures, and testing utilities. This guide covers how to effectively test Serv applications at all levels.

## Overview

Serv's testing approach:

1. **Pytest Integration**: Built on pytest with async support
2. **Test Fixtures**: Pre-configured fixtures for common testing scenarios
3. **HTTP Client Testing**: HTTPX AsyncClient for end-to-end testing
4. **Extension Testing**: Isolated testing of extensions and components
5. **Mocking Support**: Easy mocking of dependencies and external services

## Testing Architecture

### Test Types

Serv supports multiple levels of testing:

- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete request/response cycles
- **Extension Tests**: Test extension functionality in isolation
- **Middleware Tests**: Test middleware behavior

### Test Structure

```
tests/
├── conftest.py              # Global test fixtures
├── unit/                    # Unit tests
│   ├── test_models.py
│   ├── test_utils.py
│   └── test_validators.py
├── integration/             # Integration tests
│   ├── test_database.py
│   ├── test_auth_flow.py
│   └── test_api_endpoints.py
├── e2e/                     # End-to-end tests
│   ├── conftest.py
│   ├── test_user_journey.py
│   └── test_complete_flows.py
└── extensions/                 # Extension-specific tests
    ├── test_auth_extension.py
    ├── test_blog_extension.py
    └── test_api_extension.py
```

## Setting Up Testing

### Install Testing Dependencies

```bash
pip install pytest pytest-asyncio httpx
```

### Basic Test Configuration

**pytest.ini:**
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
```

### Global Test Fixtures

**tests/conftest.py:**
```python
import asyncio
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, Any
from unittest.mock import patch

from serv.app import App
from serv.extensions import Extension


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def app() -> App:
    """Create a test app instance."""
    return App(dev_mode=True)


@pytest_asyncio.fixture
async def client(app: App) -> AsyncClient:
    """Basic test client fixture."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, 
        base_url="http://testserver", 
        timeout=5.0
    ) as c:
        yield c


@asynccontextmanager
async def create_test_client(
    app_factory: Callable[[], App] = None,
    extensions: list[Extension] = None,
    config: dict[str, Any] = None,
    base_url: str = "http://testserver",
    use_lifespan: bool = True,
    timeout: float = 5.0,
) -> AsyncGenerator[AsyncClient]:
    """
    Create a test client for end-to-end testing with a fully configured App.
    
    Args:
        app_factory: Optional function that returns a fully configured App instance
        extensions: Optional list of extensions to add to the app
        config: Optional configuration to use when creating the app
        base_url: Base URL to use for requests
        use_lifespan: Whether to use the app's lifespan context
        timeout: Request timeout in seconds
    
    Returns:
        An AsyncClient configured to communicate with the app
    """
    # Create the app
    if app_factory:
        app = app_factory()
    else:
        app = App(dev_mode=True)
        
        # Add extensions if provided
        if extensions:
            for extension in extensions:
                app.add_extension(extension)
    
    # Set up the transport
    transport = ASGITransport(app=app)
    
    # Use lifespan if requested
    if use_lifespan:
        lifespan_mgr = LifespanManager(app)
        async with lifespan_mgr.lifespan():
            async with AsyncClient(
                transport=transport, 
                base_url=base_url, 
                timeout=timeout
            ) as client:
                yield client
    else:
        async with AsyncClient(
            transport=transport, 
            base_url=base_url, 
            timeout=timeout
        ) as client:
            yield client


@pytest_asyncio.fixture
async def app_test_client():
    """
    Fixture that returns the create_test_client function.
    
    Usage:
        @pytest.mark.asyncio
        async def test_custom_app(app_test_client):
            async with app_test_client(extensions=[MyExtension()]) as client:
                response = await client.get("/my-endpoint")
                assert response.status_code == 200
    """
    return create_test_client


class LifespanManager:
    """Manage application lifespan for testing."""
    
    def __init__(self, app: App):
        self.app = app
        self.receive_queue = asyncio.Queue()
        self.send_queue = asyncio.Queue()
        self.lifespan_task = None
    
    async def receive(self):
        return await self.receive_queue.get()
    
    async def send(self, message):
        await self.send_queue.put(message)
    
    async def startup(self):
        self.lifespan_task = asyncio.create_task(
            self.app.handle_lifespan({"type": "lifespan"}, self.receive, self.send)
        )
        await self.receive_queue.put({"type": "lifespan.startup"})
        startup_complete = await self.send_queue.get()
        if startup_complete["type"] != "lifespan.startup.complete":
            raise RuntimeError(f"Unexpected response: {startup_complete}")
    
    async def shutdown(self):
        if not self.lifespan_task:
            raise RuntimeError("Cannot shutdown: lifespan task not started.")
        await self.receive_queue.put({"type": "lifespan.shutdown"})
        shutdown_complete = await self.send_queue.get()
        if shutdown_complete["type"] != "lifespan.shutdown.complete":
            raise RuntimeError(f"Unexpected response: {shutdown_complete}")
        self.lifespan_task.cancel()
        try:
            await self.lifespan_task
        except asyncio.CancelledError:
            pass
    
    @asynccontextmanager
    async def lifespan(self):
        await self.startup()
        try:
            yield
        finally:
            await self.shutdown()
```

## Unit Testing

### Testing Models and Data Classes

**tests/unit/test_models.py:**
```python
import pytest
from datetime import datetime
from extensions.blog.models import BlogPost, BlogStorage

def test_blog_post_creation():
    """Test BlogPost data class creation."""
    post = BlogPost(
        id=1,
        title="Test Post",
        content="This is a test post",
        author="Test Author",
        created_at=datetime.now()
    )
    
    assert post.id == 1
    assert post.title == "Test Post"
    assert post.content == "This is a test post"
    assert post.author == "Test Author"
    assert isinstance(post.created_at, datetime)

def test_blog_storage_operations():
    """Test BlogStorage operations."""
    storage = BlogStorage()
    
    # Test adding a post
    post = storage.add_post(
        title="New Post",
        content="New content",
        author="Author"
    )
    
    assert post.id is not None
    assert post.title == "New Post"
    assert len(storage.get_all_posts()) == 3  # Including sample data
    
    # Test getting post by ID
    retrieved_post = storage.get_post_by_id(post.id)
    assert retrieved_post is not None
    assert retrieved_post.title == "New Post"
    
    # Test getting non-existent post
    non_existent = storage.get_post_by_id(999)
    assert non_existent is None

def test_blog_post_string_conversion():
    """Test BlogPost __post_init__ method."""
    # Test with string datetime
    post = BlogPost(
        id=1,
        title="Test",
        content="Content",
        author="Author",
        created_at="2023-01-01T12:00:00"
    )
    
    assert isinstance(post.created_at, datetime)
    assert post.created_at.year == 2023
```

### Testing Utility Functions

**tests/unit/test_utils.py:**
```python
import pytest
from extensions.auth.utils import hash_password, verify_password, validate_email

def test_password_hashing():
    """Test password hashing and verification."""
    password = "test_password_123"
    
    # Test hashing
    hashed = hash_password(password)
    assert hashed != password
    assert len(hashed) > 0
    
    # Test verification
    assert verify_password(password, hashed)
    assert not verify_password("wrong_password", hashed)

def test_email_validation():
    """Test email validation function."""
    # Valid emails
    assert validate_email("user@example.com")
    assert validate_email("test.email+tag@domain.co.uk")
    assert validate_email("user123@test-domain.org")
    
    # Invalid emails
    assert not validate_email("invalid-email")
    assert not validate_email("@domain.com")
    assert not validate_email("user@")
    assert not validate_email("")
    assert not validate_email(None)

@pytest.mark.parametrize("email,expected", [
    ("valid@example.com", True),
    ("another.valid@test.org", True),
    ("invalid-email", False),
    ("@invalid.com", False),
    ("user@", False),
    ("", False),
])
def test_email_validation_parametrized(email, expected):
    """Test email validation with multiple cases."""
    assert validate_email(email) == expected
```

### Testing Form Validation

**tests/unit/test_validators.py:**
```python
import pytest
from dataclasses import dataclass
from extensions.auth.validators import validate_registration_form, ValidationError

@dataclass
class MockRegistrationForm:
    username: str
    email: str
    password: str
    confirm_password: str

def test_valid_registration_form():
    """Test validation of valid registration form."""
    form = MockRegistrationForm(
        username="testuser",
        email="test@example.com",
        password="password123",
        confirm_password="password123"
    )
    
    # Should not raise any exception
    validate_registration_form(form)

def test_invalid_username():
    """Test validation with invalid username."""
    form = MockRegistrationForm(
        username="ab",  # Too short
        email="test@example.com",
        password="password123",
        confirm_password="password123"
    )
    
    with pytest.raises(ValidationError) as exc_info:
        validate_registration_form(form)
    
    assert "username" in str(exc_info.value).lower()

def test_password_mismatch():
    """Test validation with password mismatch."""
    form = MockRegistrationForm(
        username="testuser",
        email="test@example.com",
        password="password123",
        confirm_password="different_password"
    )
    
    with pytest.raises(ValidationError) as exc_info:
        validate_registration_form(form)
    
    assert "password" in str(exc_info.value).lower()

def test_multiple_validation_errors():
    """Test validation with multiple errors."""
    form = MockRegistrationForm(
        username="",  # Empty username
        email="invalid-email",  # Invalid email
        password="123",  # Too short
        confirm_password="456"  # Mismatch
    )
    
    with pytest.raises(ValidationError) as exc_info:
        validate_registration_form(form)
    
    error_message = str(exc_info.value)
    assert "username" in error_message.lower()
    assert "email" in error_message.lower()
    assert "password" in error_message.lower()
```

## Integration Testing

### Testing Route Handlers

**tests/integration/test_routes.py:**
```python
import pytest
from httpx import AsyncClient
from serv.app import App
from extensions.blog.blog_extension import BlogExtension

@pytest.mark.asyncio
async def test_blog_homepage():
    """Test blog homepage route."""
    app = App(dev_mode=True)
    app.add_extension(BlogExtension())
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "blog" in response.text.lower()

@pytest.mark.asyncio
async def test_blog_post_detail():
    """Test individual blog post route."""
    app = App(dev_mode=True)
    app.add_extension(BlogExtension())
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test valid post ID
        response = await client.get("/post/1")
        assert response.status_code == 200
        
        # Test invalid post ID
        response = await client.get("/post/999")
        assert response.status_code == 404
        
        # Test non-numeric post ID
        response = await client.get("/post/invalid")
        assert response.status_code == 400

@pytest.mark.asyncio
async def test_api_posts_endpoint():
    """Test API posts endpoint."""
    app = App(dev_mode=True)
    app.add_extension(BlogExtension())
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/posts")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Check post structure
        post = data[0]
        assert "id" in post
        assert "title" in post
        assert "content" in post
        assert "author" in post
        assert "created_at" in post
```

### Testing Form Handling

**tests/integration/test_forms.py:**
```python
import pytest
from httpx import AsyncClient
from serv.app import App
from extensions.blog.blog_extension import BlogExtension

@pytest.mark.asyncio
async def test_create_post_form():
    """Test blog post creation form."""
    app = App(dev_mode=True)
    app.add_extension(BlogExtension())
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test GET request (show form)
        response = await client.get("/admin")
        assert response.status_code == 200
        assert "form" in response.text.lower()
        
        # Test POST request (submit form)
        form_data = {
            "title": "Test Post",
            "content": "This is a test post content",
            "author": "Test Author"
        }
        
        response = await client.post("/admin", data=form_data)
        assert response.status_code == 200
        
        # Verify post was created by checking the homepage
        homepage_response = await client.get("/")
        assert "Test Post" in homepage_response.text

@pytest.mark.asyncio
async def test_form_validation():
    """Test form validation errors."""
    app = App(dev_mode=True)
    app.add_extension(BlogExtension())
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test with missing required fields
        form_data = {
            "title": "",  # Empty title
            "content": "Content",
            "author": "Author"
        }
        
        response = await client.post("/admin", data=form_data)
        assert response.status_code == 400
        assert "error" in response.text.lower()

@pytest.mark.asyncio
async def test_file_upload():
    """Test file upload handling."""
    app = App(dev_mode=True)
    app.add_extension(BlogExtension())
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a test file
        files = {
            "image": ("test.jpg", b"fake image data", "image/jpeg")
        }
        
        form_data = {
            "title": "Post with Image",
            "content": "Content with image",
            "author": "Author"
        }
        
        response = await client.post("/admin", data=form_data, files=files)
        assert response.status_code == 200
```

### Testing Authentication Flow

**tests/integration/test_auth_flow.py:**
```python
import pytest
from httpx import AsyncClient
from serv.app import App
from extensions.auth.auth_extension import AuthExtension

@pytest.mark.asyncio
async def test_login_flow():
    """Test complete login flow."""
    app = App(dev_mode=True)
    app.add_extension(AuthExtension())
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test login page
        response = await client.get("/login")
        assert response.status_code == 200
        assert "login" in response.text.lower()
        
        # Test login with valid credentials
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        
        response = await client.post("/login", data=login_data)
        assert response.status_code == 302  # Redirect after login
        
        # Check that session cookie was set
        assert "session_id" in response.cookies
        
        # Test accessing protected route
        response = await client.get("/dashboard")
        assert response.status_code == 200
        assert "dashboard" in response.text.lower()

@pytest.mark.asyncio
async def test_login_with_invalid_credentials():
    """Test login with invalid credentials."""
    app = App(dev_mode=True)
    app.add_extension(AuthExtension())
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        login_data = {
            "username": "admin",
            "password": "wrong_password"
        }
        
        response = await client.post("/login", data=login_data)
        assert response.status_code == 400
        assert "invalid" in response.text.lower()

@pytest.mark.asyncio
async def test_logout_flow():
    """Test logout flow."""
    app = App(dev_mode=True)
    app.add_extension(AuthExtension())
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Login first
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        await client.post("/login", data=login_data)
        
        # Test logout
        response = await client.post("/logout")
        assert response.status_code == 302  # Redirect after logout
        
        # Check that session cookie was cleared
        assert response.cookies.get("session_id") == ""
        
        # Test that protected route is no longer accessible
        response = await client.get("/dashboard")
        assert response.status_code == 302  # Redirect to login

@pytest.mark.asyncio
async def test_registration_flow():
    """Test user registration flow."""
    app = App(dev_mode=True)
    app.add_extension(AuthExtension())
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test registration page
        response = await client.get("/register")
        assert response.status_code == 200
        assert "register" in response.text.lower()
        
        # Test registration with valid data
        registration_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "confirm_password": "password123"
        }
        
        response = await client.post("/register", data=registration_data)
        assert response.status_code == 302  # Redirect after registration
        
        # Check that user is automatically logged in
        assert "session_id" in response.cookies
        
        # Test accessing dashboard
        response = await client.get("/dashboard")
        assert response.status_code == 200
        assert "newuser" in response.text
```

## End-to-End Testing

### Testing Complete User Journeys

**tests/e2e/test_user_journey.py:**
```python
import pytest
from httpx import AsyncClient
from tests.conftest import create_test_client
from extensions.blog.blog_extension import BlogExtension
from extensions.auth.auth_extension import AuthExtension

@pytest.mark.asyncio
async def test_complete_blog_user_journey():
    """Test complete user journey from registration to posting."""
    
    def create_blog_app():
        app = App(dev_mode=True)
        app.add_extension(AuthExtension())
        app.add_extension(BlogExtension())
        return app
    
    async with create_test_client(app_factory=create_blog_app) as client:
        # 1. Visit homepage
        response = await client.get("/")
        assert response.status_code == 200
        
        # 2. Register new user
        registration_data = {
            "username": "blogger",
            "email": "blogger@example.com",
            "password": "password123",
            "confirm_password": "password123"
        }
        
        response = await client.post("/register", data=registration_data)
        assert response.status_code == 302
        
        # 3. Access dashboard
        response = await client.get("/dashboard")
        assert response.status_code == 200
        assert "blogger" in response.text
        
        # 4. Create a new blog post
        post_data = {
            "title": "My First Post",
            "content": "This is my first blog post!",
            "author": "blogger"
        }
        
        response = await client.post("/admin", data=post_data)
        assert response.status_code == 200
        
        # 5. View the post on homepage
        response = await client.get("/")
        assert "My First Post" in response.text
        
        # 6. View individual post
        response = await client.get("/post/3")  # Assuming it's the 3rd post
        assert response.status_code == 200
        assert "My First Post" in response.text
        assert "This is my first blog post!" in response.text
        
        # 7. Logout
        response = await client.post("/logout")
        assert response.status_code == 302
        
        # 8. Verify logout worked
        response = await client.get("/dashboard")
        assert response.status_code == 302  # Redirect to login

@pytest.mark.asyncio
async def test_api_user_journey():
    """Test API user journey with authentication."""
    
    def create_api_app():
        app = App(dev_mode=True)
        app.add_extension(AuthExtension())
        app.add_extension(BlogExtension())
        return app
    
    async with create_test_client(app_factory=create_api_app) as client:
        # 1. Try API without authentication
        response = await client.get("/api/posts")
        assert response.status_code == 401
        
        # 2. Login to get session
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        await client.post("/login", data=login_data)
        
        # 3. Access API with session
        response = await client.get("/api/posts")
        assert response.status_code == 200
        
        posts = response.json()
        assert isinstance(posts, list)
        assert len(posts) > 0
        
        # 4. Create post via API
        post_data = {
            "title": "API Created Post",
            "content": "Created via API",
            "author": "admin"
        }
        
        response = await client.post("/api/posts", json=post_data)
        assert response.status_code == 201
        
        created_post = response.json()
        assert created_post["title"] == "API Created Post"
        
        # 5. Verify post appears in list
        response = await client.get("/api/posts")
        posts = response.json()
        
        api_post = next(
            (p for p in posts if p["title"] == "API Created Post"), 
            None
        )
        assert api_post is not None
```

### Testing Error Scenarios

**tests/e2e/test_error_scenarios.py:**
```python
import pytest
from httpx import AsyncClient
from tests.conftest import create_test_client
from extensions.blog.blog_extension import BlogExtension

@pytest.mark.asyncio
async def test_404_handling():
    """Test 404 error handling."""
    async with create_test_client(extensions=[BlogExtension()]) as client:
        response = await client.get("/nonexistent-page")
        assert response.status_code == 404
        assert "not found" in response.text.lower()

@pytest.mark.asyncio
async def test_500_error_handling():
    """Test 500 error handling."""
    # Create a extension that raises an error
    class ErrorExtension(Extension):
        async def on_app_request_begin(self, router):
            router.add_route("/error", self.error_handler)
        
        async def error_handler(self, response):
            raise Exception("Test error")
    
    async with create_test_client(extensions=[ErrorExtension()]) as client:
        response = await client.get("/error")
        assert response.status_code == 500

@pytest.mark.asyncio
async def test_malformed_request_handling():
    """Test handling of malformed requests."""
    async with create_test_client(extensions=[BlogExtension()]) as client:
        # Test with invalid JSON
        response = await client.post(
            "/api/posts",
            data="invalid json",
            headers={"content-type": "application/json"}
        )
        assert response.status_code == 400

@pytest.mark.asyncio
async def test_large_request_handling():
    """Test handling of large requests."""
    async with create_test_client(extensions=[BlogExtension()]) as client:
        # Create a very large payload
        large_content = "x" * (10 * 1024 * 1024)  # 10MB
        
        response = await client.post(
            "/admin",
            data={
                "title": "Large Post",
                "content": large_content,
                "author": "Test"
            }
        )
        
        # Should handle gracefully (either accept or reject with proper error)
        assert response.status_code in [200, 413, 400]
```

## Extension Testing

### Testing Extension Functionality

**tests/extensions/test_blog_extension.py:**
```python
import pytest
from serv.app import App
from extensions.blog.blog_extension import BlogExtension
from extensions.blog.models import BlogStorage

@pytest.mark.asyncio
async def test_blog_extension_initialization():
    """Test blog extension initialization."""
    extension = BlogExtension()
    
    assert hasattr(extension, 'storage')
    assert isinstance(extension.storage, BlogStorage)
    assert len(extension.storage.get_all_posts()) > 0  # Has sample data

@pytest.mark.asyncio
async def test_blog_extension_routes():
    """Test that blog extension registers routes correctly."""
    app = App(dev_mode=True)
    extension = BlogExtension()
    app.add_extension(extension)
    
    # Test that routes are registered
    # This would require access to app's router, which might need
    # additional testing utilities

@pytest.mark.asyncio
async def test_blog_extension_with_custom_storage():
    """Test blog extension with custom storage."""
    custom_storage = BlogStorage()
    custom_storage.add_post("Custom Post", "Custom content", "Custom Author")
    
    extension = BlogExtension()
    extension.storage = custom_storage
    
    posts = extension.storage.get_all_posts()
    custom_post = next(
        (p for p in posts if p.title == "Custom Post"), 
        None
    )
    assert custom_post is not None
    assert custom_post.content == "Custom content"

class TestBlogExtensionIntegration:
    """Integration tests for blog extension."""
    
    @pytest.mark.asyncio
    async def test_extension_with_app(self, app_test_client):
        """Test blog extension integrated with app."""
        extension = BlogExtension()
        
        async with app_test_client(extensions=[extension]) as client:
            # Test homepage
            response = await client.get("/")
            assert response.status_code == 200
            
            # Test API endpoint
            response = await client.get("/api/posts")
            assert response.status_code == 200
            
            posts = response.json()
            assert len(posts) > 0
    
    @pytest.mark.asyncio
    async def test_extension_post_creation(self, app_test_client):
        """Test post creation through extension."""
        extension = BlogExtension()
        
        async with app_test_client(extensions=[extension]) as client:
            # Create a post
            post_data = {
                "title": "Integration Test Post",
                "content": "Created during integration test",
                "author": "Test Suite"
            }
            
            response = await client.post("/admin", data=post_data)
            assert response.status_code == 200
            
            # Verify post was created
            response = await client.get("/api/posts")
            posts = response.json()
            
            test_post = next(
                (p for p in posts if p["title"] == "Integration Test Post"),
                None
            )
            assert test_post is not None
```

### Testing Extension Dependencies

**tests/extensions/test_extension_dependencies.py:**
```python
import pytest
from serv.app import App
from extensions.auth.auth_extension import AuthExtension
from extensions.blog.blog_extension import BlogExtension

@pytest.mark.asyncio
async def test_extensions_work_together():
    """Test that multiple extensions work together correctly."""
    app = App(dev_mode=True)
    
    # Add extensions in order
    auth_extension = AuthExtension()
    blog_extension = BlogExtension()
    
    app.add_extension(auth_extension)
    app.add_extension(blog_extension)
    
    # Test that both extensions are active
    # This would require testing the actual functionality

@pytest.mark.asyncio
async def test_extension_middleware_interaction():
    """Test extension middleware interactions."""
    app = App(dev_mode=True)
    
    # Add auth extension (provides auth middleware)
    auth_extension = AuthExtension()
    app.add_extension(auth_extension)
    
    # Add blog extension (uses auth middleware)
    blog_extension = BlogExtension()
    app.add_extension(blog_extension)
    
    # Test that auth middleware protects blog routes
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test protected route without auth
        response = await client.get("/admin")
        assert response.status_code == 302  # Redirect to login
        
        # Login and test again
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        await client.post("/login", data=login_data)
        
        response = await client.get("/admin")
        assert response.status_code == 200
```

## Middleware Testing

### Testing Middleware Behavior

**tests/test_middleware.py:**
```python
import pytest
from typing import AsyncIterator
from httpx import AsyncClient
from serv.app import App
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency

async def test_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Test middleware that adds headers."""
    # Before request processing
    response.add_header("X-Test-Before", "active")
    
    yield  # Process request
    
    # After request processing
    response.add_header("X-Test-After", "active")

@pytest.mark.asyncio
async def test_middleware_adds_headers():
    """Test that middleware adds headers correctly."""
    app = App(dev_mode=True)
    app.add_middleware(test_middleware)
    
    # Add a simple route
    class SimpleExtension(Extension):
        async def on_app_request_begin(self, router):
            router.add_route("/test", self.handler)
        
        async def handler(self, response: ResponseBuilder = dependency()):
            response.body("OK")
    
    app.add_extension(SimpleExtension())
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/test")
        
        assert response.status_code == 200
        assert response.text == "OK"
        assert response.headers.get("X-Test-Before") == "active"
        assert response.headers.get("X-Test-After") == "active"

@pytest.mark.asyncio
async def test_middleware_error_handling():
    """Test middleware error handling."""
    
    async def error_middleware(
        request: Request = dependency(),
        response: ResponseBuilder = dependency()
    ) -> AsyncIterator[None]:
        try:
            yield
        except Exception as e:
            response.set_status(500)
            response.body(f"Middleware caught error: {str(e)}")
    
    app = App(dev_mode=True)
    app.add_middleware(error_middleware)
    
    # Add a route that raises an error
    class ErrorExtension(Extension):
        async def on_app_request_begin(self, router):
            router.add_route("/error", self.error_handler)
        
        async def error_handler(self, response: ResponseBuilder = dependency()):
            raise ValueError("Test error")
    
    app.add_extension(ErrorExtension())
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/error")
        
        assert response.status_code == 500
        assert "Middleware caught error" in response.text

@pytest.mark.asyncio
async def test_middleware_order():
    """Test middleware execution order."""
    execution_order = []
    
    async def middleware_1(
        request: Request = dependency(),
        response: ResponseBuilder = dependency()
    ) -> AsyncIterator[None]:
        execution_order.append("1-before")
        yield
        execution_order.append("1-after")
    
    async def middleware_2(
        request: Request = dependency(),
        response: ResponseBuilder = dependency()
    ) -> AsyncIterator[None]:
        execution_order.append("2-before")
        yield
        execution_order.append("2-after")
    
    app = App(dev_mode=True)
    app.add_middleware(middleware_1)
    app.add_middleware(middleware_2)
    
    # Add a simple route
    class SimpleExtension(Extension):
        async def on_app_request_begin(self, router):
            router.add_route("/test", self.handler)
        
        async def handler(self, response: ResponseBuilder = dependency()):
            execution_order.append("handler")
            response.body("OK")
    
    app.add_extension(SimpleExtension())
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/test")
        
        assert response.status_code == 200
        # Middleware executes in LIFO order for request phase
        # and FIFO order for response phase
        expected_order = [
            "2-before", "1-before", "handler", "1-after", "2-after"
        ]
        assert execution_order == expected_order
```

## Mocking and Test Doubles

### Mocking External Dependencies

**tests/test_mocking.py:**
```python
import pytest
from unittest.mock import Mock, patch, AsyncMock
from httpx import AsyncClient
from serv.app import App
from extensions.email.email_extension import EmailExtension

@pytest.mark.asyncio
async def test_email_service_mock():
    """Test mocking external email service."""
    
    with patch('extensions.email.email_service.send_email') as mock_send:
        mock_send.return_value = {"status": "sent", "id": "12345"}
        
        app = App(dev_mode=True)
        app.add_extension(EmailExtension())
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            email_data = {
                "to": "test@example.com",
                "subject": "Test Email",
                "body": "This is a test email"
            }
            
            response = await client.post("/send-email", json=email_data)
            
            assert response.status_code == 200
            assert mock_send.called
            assert mock_send.call_args[0][0] == "test@example.com"

@pytest.mark.asyncio
async def test_database_mock():
    """Test mocking database operations."""
    
    mock_db = Mock()
    mock_db.fetch_all.return_value = [
        {"id": 1, "title": "Mocked Post", "content": "Mocked content"}
    ]
    
    with patch('extensions.blog.models.get_database', return_value=mock_db):
        app = App(dev_mode=True)
        app.add_extension(BlogExtension())
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/posts")
            
            assert response.status_code == 200
            posts = response.json()
            assert len(posts) == 1
            assert posts[0]["title"] == "Mocked Post"

@pytest.mark.asyncio
async def test_async_service_mock():
    """Test mocking async services."""
    
    async def mock_async_operation():
        return {"result": "mocked"}
    
    with patch('extensions.api.external_service.fetch_data', new=mock_async_operation):
        app = App(dev_mode=True)
        app.add_extension(APIExtension())
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/external-data")
            
            assert response.status_code == 200
            data = response.json()
            assert data["result"] == "mocked"

class TestMockingWithFixtures:
    """Test mocking using pytest fixtures."""
    
    @pytest.fixture
    def mock_email_service(self):
        with patch('extensions.email.email_service.EmailService') as mock:
            mock_instance = Mock()
            mock_instance.send_email = AsyncMock(return_value={"status": "sent"})
            mock.return_value = mock_instance
            yield mock_instance
    
    @pytest.mark.asyncio
    async def test_with_mock_fixture(self, mock_email_service):
        """Test using mock fixture."""
        app = App(dev_mode=True)
        app.add_extension(EmailExtension())
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/send-email", json={
                "to": "test@example.com",
                "subject": "Test",
                "body": "Test body"
            })
            
            assert response.status_code == 200
            assert mock_email_service.send_email.called
```

### Creating Test Doubles

**tests/test_doubles.py:**
```python
import pytest
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime

# Test doubles for models
@dataclass
class MockUser:
    id: int
    username: str
    email: str
    is_active: bool = True

class MockUserStorage:
    """Test double for user storage."""
    
    def __init__(self):
        self.users = [
            MockUser(1, "admin", "admin@example.com"),
            MockUser(2, "user", "user@example.com"),
        ]
        self.next_id = 3
    
    def get_user_by_id(self, user_id: int) -> Optional[MockUser]:
        return next((u for u in self.users if u.id == user_id), None)
    
    def get_user_by_username(self, username: str) -> Optional[MockUser]:
        return next((u for u in self.users if u.username == username), None)
    
    def create_user(self, username: str, email: str) -> MockUser:
        user = MockUser(self.next_id, username, email)
        self.users.append(user)
        self.next_id += 1
        return user

class MockEmailService:
    """Test double for email service."""
    
    def __init__(self):
        self.sent_emails = []
    
    async def send_email(self, to: str, subject: str, body: str) -> dict:
        email = {
            "to": to,
            "subject": subject,
            "body": body,
            "sent_at": datetime.now(),
            "id": f"mock_{len(self.sent_emails) + 1}"
        }
        self.sent_emails.append(email)
        return {"status": "sent", "id": email["id"]}
    
    def get_sent_emails(self) -> List[dict]:
        return self.sent_emails.copy()

@pytest.mark.asyncio
async def test_with_test_doubles():
    """Test using test doubles instead of mocks."""
    
    # Use test doubles
    user_storage = MockUserStorage()
    email_service = MockEmailService()
    
    # Test user creation
    user = user_storage.create_user("newuser", "new@example.com")
    assert user.username == "newuser"
    assert user.id == 3
    
    # Test email sending
    result = await email_service.send_email(
        "test@example.com", 
        "Welcome", 
        "Welcome to our service!"
    )
    
    assert result["status"] == "sent"
    assert len(email_service.get_sent_emails()) == 1
    
    sent_email = email_service.get_sent_emails()[0]
    assert sent_email["to"] == "test@example.com"
    assert sent_email["subject"] == "Welcome"
```

## Performance Testing

### Load Testing

**tests/performance/test_load.py:**
```python
import pytest
import asyncio
import time
from httpx import AsyncClient
from tests.conftest import create_test_client
from extensions.blog.blog_extension import BlogExtension

@pytest.mark.slow
@pytest.mark.asyncio
async def test_concurrent_requests():
    """Test handling of concurrent requests."""
    
    async def make_request(client: AsyncClient, path: str) -> dict:
        start_time = time.time()
        response = await client.get(path)
        end_time = time.time()
        
        return {
            "status_code": response.status_code,
            "response_time": end_time - start_time,
            "path": path
        }
    
    async with create_test_client(extensions=[BlogExtension()]) as client:
        # Make 50 concurrent requests
        tasks = []
        for i in range(50):
            path = "/" if i % 2 == 0 else "/api/posts"
            tasks.append(make_request(client, path))
        
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        successful_requests = [r for r in results if r["status_code"] == 200]
        assert len(successful_requests) == 50
        
        # Check response times
        avg_response_time = sum(r["response_time"] for r in results) / len(results)
        max_response_time = max(r["response_time"] for r in results)
        
        print(f"Average response time: {avg_response_time:.3f}s")
        print(f"Max response time: {max_response_time:.3f}s")
        
        # Assert reasonable performance
        assert avg_response_time < 1.0  # Average under 1 second
        assert max_response_time < 5.0  # Max under 5 seconds

@pytest.mark.slow
@pytest.mark.asyncio
async def test_memory_usage():
    """Test memory usage under load."""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    async with create_test_client(extensions=[BlogExtension()]) as client:
        # Make many requests to test for memory leaks
        for i in range(100):
            response = await client.get("/")
            assert response.status_code == 200
            
            if i % 10 == 0:
                current_memory = process.memory_info().rss
                memory_increase = current_memory - initial_memory
                print(f"Request {i}: Memory increase: {memory_increase / 1024 / 1024:.2f} MB")
    
    final_memory = process.memory_info().rss
    total_increase = final_memory - initial_memory
    
    # Assert memory usage is reasonable (less than 100MB increase)
    assert total_increase < 100 * 1024 * 1024
```

## Test Organization and Best Practices

### Test Configuration

**pytest.ini:**
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=serv
    --cov=extensions
    --cov-report=html
    --cov-report=term-missing
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
    auth: Authentication related tests
    database: Database related tests
```

### Test Utilities

**tests/utils.py:**
```python
from typing import Any, Dict, List
from httpx import AsyncClient
from serv.app import App

class TestDataBuilder:
    """Builder for creating test data."""
    
    @staticmethod
    def create_user_data(**overrides) -> Dict[str, Any]:
        """Create user test data."""
        default_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
            "confirm_password": "password123"
        }
        default_data.update(overrides)
        return default_data
    
    @staticmethod
    def create_post_data(**overrides) -> Dict[str, Any]:
        """Create blog post test data."""
        default_data = {
            "title": "Test Post",
            "content": "This is test content",
            "author": "Test Author"
        }
        default_data.update(overrides)
        return default_data

class APITestHelper:
    """Helper for API testing."""
    
    def __init__(self, client: AsyncClient):
        self.client = client
        self.auth_token = None
    
    async def login(self, username: str = "admin", password: str = "admin123"):
        """Login and store session."""
        response = await self.client.post("/login", data={
            "username": username,
            "password": password
        })
        assert response.status_code == 302
        return response
    
    async def logout(self):
        """Logout and clear session."""
        response = await self.client.post("/logout")
        assert response.status_code == 302
        return response
    
    async def create_post(self, **post_data):
        """Create a blog post."""
        data = TestDataBuilder.create_post_data(**post_data)
        response = await self.client.post("/admin", data=data)
        return response
    
    async def get_posts(self):
        """Get all posts via API."""
        response = await self.client.get("/api/posts")
        assert response.status_code == 200
        return response.json()

def assert_valid_post(post: Dict[str, Any]):
    """Assert that a post has valid structure."""
    required_fields = ["id", "title", "content", "author", "created_at"]
    for field in required_fields:
        assert field in post, f"Post missing required field: {field}"
    
    assert isinstance(post["id"], int)
    assert len(post["title"]) > 0
    assert len(post["content"]) > 0
    assert len(post["author"]) > 0

def assert_valid_user(user: Dict[str, Any]):
    """Assert that a user has valid structure."""
    required_fields = ["id", "username", "email", "is_active"]
    for field in required_fields:
        assert field in user, f"User missing required field: {field}"
    
    assert isinstance(user["id"], int)
    assert "@" in user["email"]
    assert isinstance(user["is_active"], bool)
```

### Test Patterns

**tests/patterns/test_patterns.py:**
```python
import pytest
from httpx import AsyncClient
from tests.utils import APITestHelper, TestDataBuilder, assert_valid_post

class TestBlogAPIPatterns:
    """Test patterns for blog API."""
    
    @pytest.mark.asyncio
    async def test_crud_pattern(self, app_test_client):
        """Test CRUD operations pattern."""
        async with app_test_client(extensions=[BlogExtension()]) as client:
            helper = APITestHelper(client)
            await helper.login()
            
            # Create
            post_data = TestDataBuilder.create_post_data(title="CRUD Test Post")
            create_response = await helper.create_post(**post_data)
            assert create_response.status_code == 200
            
            # Read
            posts = await helper.get_posts()
            crud_post = next(
                (p for p in posts if p["title"] == "CRUD Test Post"),
                None
            )
            assert crud_post is not None
            assert_valid_post(crud_post)
            
            # Update (if implemented)
            # update_response = await client.put(f"/api/posts/{crud_post['id']}", ...)
            
            # Delete (if implemented)
            # delete_response = await client.delete(f"/api/posts/{crud_post['id']}")
    
    @pytest.mark.asyncio
    async def test_authentication_pattern(self, app_test_client):
        """Test authentication pattern."""
        async with app_test_client(extensions=[AuthExtension(), BlogExtension()]) as client:
            helper = APITestHelper(client)
            
            # Test unauthenticated access
            response = await client.get("/dashboard")
            assert response.status_code == 302  # Redirect to login
            
            # Test authentication
            await helper.login()
            
            # Test authenticated access
            response = await client.get("/dashboard")
            assert response.status_code == 200
            
            # Test logout
            await helper.logout()
            
            # Test access after logout
            response = await client.get("/dashboard")
            assert response.status_code == 302  # Redirect to login again
    
    @pytest.mark.asyncio
    async def test_error_handling_pattern(self, app_test_client):
        """Test error handling pattern."""
        async with app_test_client(extensions=[BlogExtension()]) as client:
            # Test 404
            response = await client.get("/nonexistent")
            assert response.status_code == 404
            
            # Test 400 (bad request)
            response = await client.post("/admin", data={})  # Missing required fields
            assert response.status_code == 400
            
            # Test 405 (method not allowed)
            response = await client.delete("/")  # DELETE not allowed on homepage
            assert response.status_code == 405
```

## Best Practices

### 1. Test Organization

```python
# Good: Organize tests by functionality
tests/
├── unit/
│   ├── test_models.py
│   ├── test_validators.py
│   └── test_utils.py
├── integration/
│   ├── test_auth_flow.py
│   ├── test_api_endpoints.py
│   └── test_form_handling.py
└── e2e/
    ├── test_user_journeys.py
    └── test_complete_flows.py

# Avoid: Mixing test types in single files
```

### 2. Use Descriptive Test Names

```python
# Good: Descriptive test names
def test_user_registration_with_valid_data_creates_user_and_logs_in():
    pass

def test_login_with_invalid_password_returns_400_error():
    pass

# Avoid: Vague test names
def test_user_stuff():
    pass

def test_login():
    pass
```

### 3. Follow AAA Pattern

```python
# Good: Arrange, Act, Assert pattern
@pytest.mark.asyncio
async def test_blog_post_creation():
    # Arrange
    app = App(dev_mode=True)
    app.add_extension(BlogExtension())
    post_data = {
        "title": "Test Post",
        "content": "Test content",
        "author": "Test Author"
    }
    
    # Act
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/admin", data=post_data)
    
    # Assert
    assert response.status_code == 200
    assert "Test Post" in response.text
```

### 4. Use Fixtures for Common Setup

```python
# Good: Use fixtures for repeated setup
@pytest.fixture
async def authenticated_client(app_test_client):
    async with app_test_client(extensions=[AuthExtension()]) as client:
        await client.post("/login", data={
            "username": "admin",
            "password": "admin123"
        })
        yield client

@pytest.mark.asyncio
async def test_protected_route(authenticated_client):
    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
```

### 5. Test Edge Cases

```python
# Good: Test edge cases and error conditions
@pytest.mark.asyncio
async def test_post_creation_with_empty_title():
    """Test that empty title is rejected."""
    # Test implementation

@pytest.mark.asyncio
async def test_post_creation_with_very_long_title():
    """Test that very long titles are handled properly."""
    # Test implementation

@pytest.mark.asyncio
async def test_post_creation_with_special_characters():
    """Test that special characters in content are handled."""
    # Test implementation
```

### 6. Mock External Dependencies

```python
# Good: Mock external services
@patch('extensions.email.email_service.send_email')
@pytest.mark.asyncio
async def test_user_registration_sends_welcome_email(mock_send_email):
    mock_send_email.return_value = {"status": "sent"}
    
    # Test registration
    # Verify email was sent
    assert mock_send_email.called

# Avoid: Testing against real external services in unit tests
```

## Running Tests

### Using Serv CLI (Recommended)

Serv provides a built-in test command that integrates with your application:

```bash
# Run all tests
serv test

# Run only extension tests
serv test --extensions

# Run only end-to-end tests
serv test --e2e

# Run with coverage report
serv test --coverage

# Run specific test file
serv test tests/test_auth.py

# Verbose output with coverage
serv test --verbose --coverage
```

### Direct pytest Execution

You can also run tests directly with pytest:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_auth.py

# Run tests with specific marker
pytest -m unit
pytest -m integration
pytest -m e2e

# Run tests with coverage
pytest --cov=serv --cov=extensions

# Run tests in parallel
pytest -n auto
```

### Test Configuration

```bash
# Run with verbose output
pytest -v

# Run with detailed output on failures
pytest -vvv

# Stop on first failure
pytest -x

# Run only failed tests from last run
pytest --lf

# Run tests matching pattern
pytest -k "test_auth"
```

## Next Steps

- **[Deployment](deployment.md)** - Deploy tested applications
- **[Performance](performance.md)** - Performance testing and optimization
- **[Monitoring](monitoring.md)** - Monitor applications in production 