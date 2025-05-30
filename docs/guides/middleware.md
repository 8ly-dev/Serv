# Middleware

Middleware in Serv provides a powerful way to add cross-cutting concerns to your application. This guide covers how to create, configure, and use middleware effectively using Serv's CLI-first approach and extension-based architecture.

## What is Middleware?

Middleware are async generator functions that execute during the request/response cycle. They can:

- Process requests before they reach route handlers
- Modify responses before they're sent to clients
- Perform authentication and authorization
- Log requests and responses
- Handle errors and add security headers
- Implement rate limiting and caching

## Middleware Architecture

### Core Principles

Serv middleware follows these principles:

- **Extension-Based**: Middleware is organized within extensions
- **CLI-Created**: Use CLI commands to create middleware
- **Declarative Configuration**: Middleware is configured in `extension.yaml` files
- **Dependency Injection**: Full access to Serv's DI system

### Middleware Structure

Middleware in Serv is organized within extensions:

```
extensions/
└── my_extension/
    ├── extension.yaml
    ├── middleware_auth.py
    ├── middleware_logging.py
    └── middleware_cors.py
```

## Creating Middleware

### Using the CLI

The recommended way to create middleware is using the Serv CLI:

```bash
# Create a extension first (if you don't have one)
serv create extension --name "Security"

# Create middleware within the extension
serv create middleware --name "auth_check" --extension "security"

# Create another middleware
serv create middleware --name "rate_limiter" --extension "security"
```

### Generated Middleware Structure

After running the commands above, you'll have:

**extensions/security/extension.yaml:**
```yaml
name: Security
description: A cool Serv extension.
version: 0.1.0
author: Your Name

middleware:
  - entry: middleware_auth_check:auth_check_middleware
    config:
      timeout: 30
  - entry: middleware_rate_limiter:rate_limiter_middleware
    config:
      requests_per_minute: 60
```

**extensions/security/middleware_auth_check.py:**
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
    
    # Code here runs before the request is handled
    print(f"Checking auth for {request.path}")
    
    yield  # Continue to next middleware/handler
    
    # Code here runs after the request is handled
    print("Auth check completed")
```

## Basic Middleware Patterns

### Request Logging Middleware

```python
import time
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency

async def logging_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Log all requests with timing information"""
    
    start_time = time.time()
    print(f"→ {request.method} {request.path}")
    
    yield  # Process the request
    
    duration = time.time() - start_time
    print(f"← {request.method} {request.path} ({response.status_code}) {duration:.3f}s")
    
    # Add timing header
    response.add_header("X-Response-Time", f"{duration:.3f}s")
```

### Authentication Middleware

```python
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency

async def auth_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Check authentication for protected routes"""
    
    # Skip auth for public routes
    if request.path.startswith("/public") or request.path == "/":
        yield
        return
    
    # Check for authentication token
    auth_header = request.headers.get("authorization")
    if not auth_header:
        response.set_status(401)
        response.content_type("application/json")
        response.body('{"error": "Authentication required"}')
        return  # Don't yield - stop processing
    
    # Validate token (implement your validation logic)
    if not is_valid_token(auth_header):
        response.set_status(401)
        response.content_type("application/json")
        response.body('{"error": "Invalid token"}')
        return
    
    # Add user info to request context for route handlers
    user = get_user_from_token(auth_header)
    request.context['user'] = user
    
    yield  # Continue processing

def is_valid_token(token: str) -> bool:
    """Implement your token validation logic"""
    return token.startswith("Bearer ") and len(token) > 20

def get_user_from_token(token: str) -> dict:
    """Extract user information from token"""
    return {"id": 123, "username": "user", "role": "user"}
```

### CORS Middleware

```python
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency

async def cors_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Handle CORS (Cross-Origin Resource Sharing)"""
    
    # Handle preflight requests
    if request.method == "OPTIONS":
        response.add_header("Access-Control-Allow-Origin", "*")
        response.add_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        response.add_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        response.add_header("Access-Control-Max-Age", "86400")
        response.set_status(200)
        response.body("")
        return
    
    yield  # Process the request
    
    # Add CORS headers to all responses
    response.add_header("Access-Control-Allow-Origin", "*")
    response.add_header("Access-Control-Allow-Credentials", "true")
```

### Rate Limiting Middleware

```python
import time
from collections import defaultdict
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency

# Simple in-memory rate limiter (use Redis in production)
request_counts = defaultdict(list)

async def rate_limiter_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Rate limit requests by IP address"""
    
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    window_size = 60  # 1 minute window
    max_requests = 60  # 60 requests per minute
    
    # Clean old requests (outside the time window)
    request_counts[client_ip] = [
        req_time for req_time in request_counts[client_ip]
        if current_time - req_time < window_size
    ]
    
    # Check rate limit
    if len(request_counts[client_ip]) >= max_requests:
        response.set_status(429)
        response.content_type("application/json")
        response.add_header("Retry-After", "60")
        response.body('{"error": "Rate limit exceeded", "retry_after": 60}')
        return
    
    # Record this request
    request_counts[client_ip].append(current_time)
    
    # Add rate limit headers
    remaining = max_requests - len(request_counts[client_ip])
    response.add_header("X-RateLimit-Limit", str(max_requests))
    response.add_header("X-RateLimit-Remaining", str(remaining))
    response.add_header("X-RateLimit-Reset", str(int(current_time + window_size)))
    
    yield  # Continue processing
```

## Advanced Middleware Patterns

### Error Handling Middleware

```python
import traceback
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency

async def error_handler_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Global error handling middleware"""
    
    try:
        yield  # Process the request
    except ValueError as e:
        # Handle validation errors
        response.set_status(400)
        response.content_type("application/json")
        response.body(f'{{"error": "Bad request", "message": "{str(e)}"}}')
    except PermissionError as e:
        # Handle permission errors
        response.set_status(403)
        response.content_type("application/json")
        response.body(f'{{"error": "Forbidden", "message": "{str(e)}"}}')
    except FileNotFoundError as e:
        # Handle not found errors
        response.set_status(404)
        response.content_type("application/json")
        response.body(f'{{"error": "Not found", "message": "{str(e)}"}}')
    except Exception as e:
        # Handle all other errors
        print(f"Unhandled error: {e}")
        print(traceback.format_exc())
        
        response.set_status(500)
        response.content_type("application/json")
        response.body('{"error": "Internal server error"}')
```

### Security Headers Middleware

```python
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency

async def security_headers_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Add security headers to all responses"""
    
    yield  # Process the request
    
    # Add security headers
    response.add_header("X-Content-Type-Options", "nosniff")
    response.add_header("X-Frame-Options", "DENY")
    response.add_header("X-XSS-Protection", "1; mode=block")
    response.add_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    response.add_header("Referrer-Policy", "strict-origin-when-cross-origin")
    response.add_header("Content-Security-Policy", "default-src 'self'")
```

### Database Transaction Middleware

```python
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency
import asyncpg

async def database_transaction_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency(),
    db_pool: asyncpg.Pool = dependency()
) -> AsyncIterator[None]:
    """Wrap requests in database transactions"""
    
    # Only use transactions for write operations
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        async with db_pool.acquire() as connection:
            async with connection.transaction():
                # Make connection available to route handlers
                request.context['db_connection'] = connection
                
                try:
                    yield  # Process the request
                    # Transaction commits automatically if no exception
                except Exception:
                    # Transaction rolls back automatically on exception
                    raise
    else:
        # For read operations, just use a connection from the pool
        async with db_pool.acquire() as connection:
            request.context['db_connection'] = connection
            yield
```

## Middleware Configuration

### Extension Configuration

Configure middleware in your extension's `extension.yaml`:

```yaml
name: Security
description: Security middleware for the application
version: 1.0.0
author: Your Name

middleware:
  - entry: middleware_auth:auth_middleware
    config:
      secret_key: "your-secret-key"
      token_expiry: 3600
      
  - entry: middleware_rate_limiter:rate_limiter_middleware
    config:
      requests_per_minute: 100
      window_size: 60
      
  - entry: middleware_cors:cors_middleware
    config:
      allowed_origins: ["http://localhost:3000", "https://myapp.com"]
      allowed_methods: ["GET", "POST", "PUT", "DELETE"]
```

### Accessing Configuration in Middleware

```python
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency

async def configurable_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Middleware that uses configuration"""
    
    # Access middleware configuration
    # (This would be injected by the extension system)
    config = getattr(configurable_middleware, '_config', {})
    
    max_requests = config.get('requests_per_minute', 60)
    window_size = config.get('window_size', 60)
    
    # Use configuration in middleware logic
    if should_rate_limit(request, max_requests, window_size):
        response.set_status(429)
        response.body('{"error": "Rate limit exceeded"}')
        return
    
    yield

def should_rate_limit(request, max_requests, window_size):
    """Implement rate limiting logic"""
    return False  # Placeholder
```

### Application-Level Configuration Override

Override middleware configuration in `serv.config.yaml`:

```yaml
site_info:
  name: "My Application"

extensions:
  - extension: security
    settings:
      middleware:
        auth_middleware:
          secret_key: "production-secret-key"
          token_expiry: 7200
        rate_limiter_middleware:
          requests_per_minute: 200
```

## Middleware Execution Order

### Understanding Middleware Flow

Middleware executes in a specific order:

1. **Request Phase**: Middleware executes in the order they're registered
2. **Response Phase**: Middleware executes in reverse order (LIFO)

```python
# Middleware execution order:
# Request:  A → B → C → Route Handler
# Response: Route Handler → C → B → A

async def middleware_a():
    print("A: Before")
    yield
    print("A: After")

async def middleware_b():
    print("B: Before")
    yield
    print("B: After")

async def middleware_c():
    print("C: Before")
    yield
    print("C: After")

# Output:
# A: Before
# B: Before  
# C: Before
# [Route Handler Executes]
# C: After
# B: After
# A: After
```

### Extension-Level Ordering

Control middleware order within extensions:

```yaml
name: Security
middleware:
  # These execute in order
  - entry: middleware_cors:cors_middleware        # 1st
  - entry: middleware_auth:auth_middleware        # 2nd
  - entry: middleware_rate_limiter:rate_limiter_middleware  # 3rd
```

### Global Middleware Order

Control order across extensions by extension loading order in `serv.config.yaml`:

```yaml
extensions:
  - extension: logging      # Logging middleware runs first
  - extension: security     # Security middleware runs second
  - extension: api          # API-specific middleware runs last
```

## Conditional Middleware

### Path-Based Middleware

```python
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency

async def api_only_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Middleware that only runs for API routes"""
    
    if not request.path.startswith("/api/"):
        # Skip this middleware for non-API routes
        yield
        return
    
    # API-specific logic here
    response.add_header("X-API-Version", "v1")
    
    yield
```

### Method-Based Middleware

```python
async def write_only_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Middleware that only runs for write operations"""
    
    if request.method not in ["POST", "PUT", "DELETE", "PATCH"]:
        yield
        return
    
    # Write operation logic (validation, logging, etc.)
    print(f"Write operation: {request.method} {request.path}")
    
    yield
```

### Header-Based Middleware

```python
async def api_version_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Route to different handlers based on API version"""
    
    api_version = request.headers.get("X-API-Version", "v1")
    
    if api_version == "v2":
        # Add v2-specific processing
        request.context['api_version'] = "v2"
        response.add_header("X-API-Version", "v2")
    else:
        # Default to v1
        request.context['api_version'] = "v1"
        response.add_header("X-API-Version", "v1")
    
    yield
```

## Testing Middleware

### Unit Testing Middleware

```python
import pytest
from unittest.mock import Mock, AsyncMock
from extensions.security.middleware_auth import auth_middleware

@pytest.mark.asyncio
async def test_auth_middleware_success():
    """Test successful authentication"""
    request = Mock()
    request.path = "/protected"
    request.headers = {"authorization": "Bearer valid-token"}
    request.context = {}
    
    response = Mock()
    
    # Create async generator
    middleware_gen = auth_middleware(request=request, response=response)
    
    # Should yield without setting error status
    await middleware_gen.__anext__()
    
    # Check that user was added to context
    assert "user" in request.context
    assert request.context["user"]["username"] == "user"

@pytest.mark.asyncio
async def test_auth_middleware_missing_token():
    """Test missing authentication token"""
    request = Mock()
    request.path = "/protected"
    request.headers = {}
    
    response = Mock()
    
    middleware_gen = auth_middleware(request=request, response=response)
    
    # Should not yield (stops processing)
    with pytest.raises(StopAsyncIteration):
        await middleware_gen.__anext__()
    
    # Check that 401 status was set
    response.set_status.assert_called_with(401)
```

### Integration Testing

```python
import pytest
from httpx import AsyncClient
from serv.app import App

@pytest.mark.asyncio
async def test_middleware_integration():
    """Test middleware in full application context"""
    app = App(config="test_config.yaml")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test that middleware adds headers
        response = await client.get("/api/test")
        assert "X-API-Version" in response.headers
        assert response.headers["X-API-Version"] == "v1"
        
        # Test rate limiting
        for _ in range(65):  # Exceed rate limit
            await client.get("/api/test")
        
        response = await client.get("/api/test")
        assert response.status_code == 429
```

### Testing Middleware Configuration

```python
def test_middleware_configuration():
    """Test middleware configuration loading"""
    from extensions.security.middleware_rate_limiter import rate_limiter_middleware
    
    # Mock configuration
    config = {
        "requests_per_minute": 100,
        "window_size": 60
    }
    
    # Test that middleware uses configuration
    rate_limiter_middleware._config = config
    
    # Test middleware behavior with configuration
    # (Implementation depends on how you access config in middleware)
```

## Best Practices

### 1. Use CLI for Middleware Creation

```bash
# Good: Use CLI commands
serv create middleware --name "auth_check" --extension "security"

# Avoid: Manual file creation
```

### 2. Keep Middleware Focused

```python
# Good: Single responsibility
async def auth_middleware():
    """Only handles authentication"""
    pass

async def logging_middleware():
    """Only handles logging"""
    pass

# Avoid: Multiple responsibilities
async def everything_middleware():
    """Handles auth, logging, rate limiting, etc."""
    pass
```

### 3. Handle Errors Gracefully

```python
async def robust_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Middleware with proper error handling"""
    
    try:
        # Pre-processing logic
        result = await some_external_service()
        request.context['service_data'] = result
    except Exception as e:
        # Log error but don't fail the request
        print(f"Service unavailable: {e}")
        request.context['service_data'] = None
    
    yield
    
    try:
        # Post-processing logic
        await cleanup_resources()
    except Exception as e:
        # Log cleanup errors
        print(f"Cleanup failed: {e}")
```

### 4. Use Dependency Injection

```python
async def database_middleware(
    request: Request = dependency(),
    db_pool: asyncpg.Pool = dependency(),
    cache: RedisCache = dependency()
) -> AsyncIterator[None]:
    """Leverage DI for clean middleware"""
    
    # Use injected dependencies
    async with db_pool.acquire() as conn:
        request.context['db'] = conn
        
        # Check cache first
        cached = await cache.get(f"user:{request.user_id}")
        if cached:
            request.context['user'] = cached
        
        yield
```

### 5. Document Middleware Behavior

```python
async def auth_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Authentication middleware.
    
    Checks for valid authentication tokens and adds user information
    to the request context.
    
    Request Context:
        - Adds 'user' dict with user information if authenticated
        
    Response Headers:
        - None
        
    Status Codes:
        - 401: Missing or invalid authentication token
        
    Configuration:
        - secret_key: JWT secret key
        - token_expiry: Token expiration time in seconds
    """
    pass
```

## Development Workflow

### 1. Plan Your Middleware

Identify what cross-cutting concerns your application needs:
- Authentication and authorization
- Request/response logging
- Rate limiting
- CORS handling
- Error handling
- Security headers

### 2. Create Extension and Middleware

```bash
# Create a extension for your middleware
serv create extension --name "Security"

# Add middleware to the extension
serv create middleware --name "auth_check" --extension "security"
serv create middleware --name "rate_limiter" --extension "security"
serv create middleware --name "cors_handler" --extension "security"
```

### 3. Implement Middleware Logic

Edit the generated middleware files to implement your logic.

### 4. Configure Middleware

Update the extension's `extension.yaml` with appropriate configuration.

### 5. Enable and Test

```bash
# Enable the extension
serv extension enable security

# Test the application
serv --dev launch

# Run tests
serv test
```

## Next Steps

- **[Extensions](extensions.md)** - Learn about extension architecture and organization
- **[Routing](routing.md)** - Understand how middleware interacts with routes
- **[Dependency Injection](dependency-injection.md)** - Master DI patterns for middleware
- **[Error Handling](error-handling.md)** - Advanced error handling techniques 