# Middleware

Middleware in Serv allows you to process requests and responses at various stages of the request lifecycle. This guide covers how to create and use middleware effectively.

## What is Middleware?

Middleware are functions that execute during the request/response cycle. They can:

- Modify requests before they reach route handlers
- Modify responses before they're sent to clients
- Perform authentication and authorization
- Log requests and responses
- Handle errors
- Add security headers

## Basic Middleware

### Simple Middleware

Here's a basic middleware that logs requests:

```python
from typing import AsyncIterator
from serv.requests import Request
from bevy import dependency

async def logging_middleware(
    request: Request = dependency()
) -> AsyncIterator[None]:
    print(f"Request: {request.method} {request.path}")
    
    yield  # Process the request
    
    print(f"Request completed: {request.method} {request.path}")

# Register the middleware
app.add_middleware(logging_middleware)
```

### Middleware with Response Access

Access and modify responses:

```python
from serv.responses import ResponseBuilder

async def response_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    # Before request processing
    start_time = time.time()
    
    yield  # Process the request
    
    # After request processing
    duration = time.time() - start_time
    response.add_header("X-Response-Time", f"{duration:.3f}s")
```

## Middleware Patterns

### Authentication Middleware

```python
async def auth_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    # Check for authentication token
    token = request.headers.get("Authorization")
    
    if not token:
        response.set_status(401)
        response.content_type("application/json")
        response.body('{"error": "Authentication required"}')
        return  # Don't yield - stop processing
    
    # Validate token
    if not is_valid_token(token):
        response.set_status(401)
        response.content_type("application/json")
        response.body('{"error": "Invalid token"}')
        return
    
    # Add user to request context
    user = get_user_from_token(token)
    request.context['user'] = user
    
    yield  # Continue processing
```

### CORS Middleware

```python
async def cors_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    # Handle preflight requests
    if request.method == "OPTIONS":
        response.add_header("Access-Control-Allow-Origin", "*")
        response.add_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE")
        response.add_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        response.set_status(200)
        response.body("")
        return
    
    yield  # Process the request
    
    # Add CORS headers to response
    response.add_header("Access-Control-Allow-Origin", "*")
```

### Rate Limiting Middleware

```python
import time
from collections import defaultdict

# Simple in-memory rate limiter
request_counts = defaultdict(list)

async def rate_limit_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    client_ip = request.client_ip
    current_time = time.time()
    
    # Clean old requests (older than 1 minute)
    request_counts[client_ip] = [
        req_time for req_time in request_counts[client_ip]
        if current_time - req_time < 60
    ]
    
    # Check rate limit (60 requests per minute)
    if len(request_counts[client_ip]) >= 60:
        response.set_status(429)
        response.content_type("application/json")
        response.body('{"error": "Rate limit exceeded"}')
        return
    
    # Record this request
    request_counts[client_ip].append(current_time)
    
    yield  # Continue processing
```

## Error Handling in Middleware

### Catching Exceptions

```python
async def error_handling_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    try:
        yield  # Process the request
    except ValueError as e:
        response.set_status(400)
        response.content_type("application/json")
        response.body(f'{{"error": "Bad request: {str(e)}"}}')
    except Exception as e:
        response.set_status(500)
        response.content_type("application/json")
        response.body('{"error": "Internal server error"}')
```

### Propagating Exceptions

```python
async def logging_error_middleware(
    request: Request = dependency()
) -> AsyncIterator[None]:
    try:
        yield
    except Exception as e:
        # Log the error
        logger.error(f"Error processing {request.method} {request.path}: {e}")
        # Re-raise to let other middleware handle it
        raise
```

## Middleware with Dependencies

### Using Services

```python
async def database_middleware(
    request: Request = dependency(),
    db_service: DatabaseService = dependency()
) -> AsyncIterator[None]:
    # Start a database transaction
    transaction = await db_service.begin_transaction()
    request.context['db_transaction'] = transaction
    
    try:
        yield  # Process the request
        
        # Commit the transaction
        await transaction.commit()
    except Exception:
        # Rollback on error
        await transaction.rollback()
        raise
```

### Configuration-Based Middleware

```python
class ConfigurableMiddleware:
    def __init__(self, config: dict):
        self.enabled = config.get('enabled', True)
        self.log_level = config.get('log_level', 'INFO')
    
    async def __call__(
        self,
        request: Request = dependency()
    ) -> AsyncIterator[None]:
        if not self.enabled:
            yield
            return
        
        if self.log_level == 'DEBUG':
            print(f"DEBUG: {request.method} {request.path}")
        
        yield

# Register with configuration
config = {'enabled': True, 'log_level': 'DEBUG'}
middleware = ConfigurableMiddleware(config)
app.add_middleware(middleware)
```

## Middleware Order

Middleware executes in the order it's registered:

```python
# First middleware registered
async def first_middleware() -> AsyncIterator[None]:
    print("First: Before")
    yield
    print("First: After")

# Second middleware registered  
async def second_middleware() -> AsyncIterator[None]:
    print("Second: Before")
    yield
    print("Second: After")

app.add_middleware(first_middleware)
app.add_middleware(second_middleware)

# Output for a request:
# First: Before
# Second: Before
# [Route handler executes]
# Second: After
# First: After
```

## Plugin-Based Middleware

### Registering Middleware in Plugins

```python
class SecurityPlugin(Plugin):
    async def on_app_startup(self, app: App = dependency()):
        app.add_middleware(self.security_middleware)
    
    async def security_middleware(
        self,
        request: Request = dependency(),
        response: ResponseBuilder = dependency()
    ) -> AsyncIterator[None]:
        # Add security headers
        yield
        
        response.add_header("X-Content-Type-Options", "nosniff")
        response.add_header("X-Frame-Options", "DENY")
        response.add_header("X-XSS-Protection", "1; mode=block")
```

### Conditional Middleware

```python
class ConditionalPlugin(Plugin):
    async def on_app_startup(self, app: App = dependency()):
        config = self.get_config()
        
        if config.get('enable_auth', False):
            app.add_middleware(self.auth_middleware)
        
        if config.get('enable_logging', True):
            app.add_middleware(self.logging_middleware)
    
    async def auth_middleware(self) -> AsyncIterator[None]:
        # Authentication logic
        yield
    
    async def logging_middleware(self) -> AsyncIterator[None]:
        # Logging logic
        yield
```

## Advanced Middleware Patterns

### Middleware Classes

For complex middleware, use classes:

```python
class AuthenticationMiddleware:
    def __init__(self, secret_key: str, exempt_paths: list = None):
        self.secret_key = secret_key
        self.exempt_paths = exempt_paths or []
    
    async def __call__(
        self,
        request: Request = dependency(),
        response: ResponseBuilder = dependency()
    ) -> AsyncIterator[None]:
        # Skip authentication for exempt paths
        if request.path in self.exempt_paths:
            yield
            return
        
        # Perform authentication
        token = request.headers.get("Authorization")
        if not self.validate_token(token):
            response.set_status(401)
            response.body("Unauthorized")
            return
        
        yield
    
    def validate_token(self, token: str) -> bool:
        # Token validation logic
        return token and token.startswith("Bearer ")

# Register the middleware
auth_middleware = AuthenticationMiddleware(
    secret_key="your-secret-key",
    exempt_paths=["/health", "/login"]
)
app.add_middleware(auth_middleware)
```

### Middleware Factories

Create middleware with different configurations:

```python
def create_cors_middleware(
    allowed_origins: list = None,
    allowed_methods: list = None,
    allowed_headers: list = None
):
    allowed_origins = allowed_origins or ["*"]
    allowed_methods = allowed_methods or ["GET", "POST", "PUT", "DELETE"]
    allowed_headers = allowed_headers or ["Content-Type", "Authorization"]
    
    async def cors_middleware(
        request: Request = dependency(),
        response: ResponseBuilder = dependency()
    ) -> AsyncIterator[None]:
        origin = request.headers.get("Origin")
        
        if request.method == "OPTIONS":
            if "*" in allowed_origins or origin in allowed_origins:
                response.add_header("Access-Control-Allow-Origin", origin or "*")
                response.add_header("Access-Control-Allow-Methods", ", ".join(allowed_methods))
                response.add_header("Access-Control-Allow-Headers", ", ".join(allowed_headers))
            response.set_status(200)
            response.body("")
            return
        
        yield
        
        if "*" in allowed_origins or origin in allowed_origins:
            response.add_header("Access-Control-Allow-Origin", origin or "*")
    
    return cors_middleware

# Use the factory
cors_middleware = create_cors_middleware(
    allowed_origins=["http://localhost:3000", "https://myapp.com"],
    allowed_methods=["GET", "POST"],
    allowed_headers=["Content-Type"]
)
app.add_middleware(cors_middleware)
```

## Testing Middleware

### Unit Testing

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_auth_middleware():
    # Create mocks
    mock_request = Mock(spec=Request)
    mock_request.headers = {"Authorization": "Bearer valid-token"}
    mock_response = Mock(spec=ResponseBuilder)
    
    # Create middleware
    middleware = auth_middleware()
    
    # Test with valid token
    async for _ in middleware:
        pass  # Should not raise or set error status
    
    # Verify no error response was set
    mock_response.set_status.assert_not_called()
```

### Integration Testing

```python
import httpx
import pytest

@pytest.mark.asyncio
async def test_middleware_integration():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # Test without auth header
        response = await client.get("/protected")
        assert response.status_code == 401
        
        # Test with auth header
        headers = {"Authorization": "Bearer valid-token"}
        response = await client.get("/protected", headers=headers)
        assert response.status_code == 200
```

## Best Practices

### 1. Keep Middleware Focused

Each middleware should have a single responsibility:

```python
# Good: Focused on authentication
async def auth_middleware() -> AsyncIterator[None]:
    # Only handle authentication
    yield

# Good: Focused on logging
async def logging_middleware() -> AsyncIterator[None]:
    # Only handle logging
    yield

# Bad: Too many responsibilities
async def everything_middleware() -> AsyncIterator[None]:
    # Authentication, logging, rate limiting, etc.
    yield
```

### 2. Handle Errors Gracefully

```python
async def robust_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    try:
        # Middleware logic
        yield
    except Exception as e:
        # Log the error
        logger.error(f"Middleware error: {e}")
        
        # Don't break the request chain
        if not response._headers_sent:
            response.set_status(500)
            response.body("Internal server error")
```

### 3. Use Type Hints

```python
from typing import AsyncIterator

async def typed_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    yield
```

### 4. Make Middleware Configurable

```python
def create_configurable_middleware(config: dict):
    async def middleware(
        request: Request = dependency()
    ) -> AsyncIterator[None]:
        if config.get('enabled', True):
            # Middleware logic
            pass
        yield
    
    return middleware
```

### 5. Document Middleware Behavior

```python
async def documented_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """
    Authentication middleware that validates JWT tokens.
    
    Checks for Authorization header with Bearer token.
    Sets 401 status if token is missing or invalid.
    Adds user information to request.context if valid.
    
    Exempt paths: /health, /login, /register
    """
    yield
```

## Next Steps

- **[Plugins](plugins.md)** - Learn how to create plugins that register middleware
- **[Dependency Injection](dependency-injection.md)** - Use DI in middleware
- **[Error Handling](error-handling.md)** - Handle errors in middleware
- **[Testing](testing.md)** - Test your middleware effectively 