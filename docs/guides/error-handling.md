# Error Handling

Effective error handling is crucial for building robust web applications. Serv provides comprehensive error handling capabilities including custom exceptions, error middleware, logging integration, and graceful error responses. This guide covers everything you need to know about handling errors in Serv applications.

## Overview

Serv's error handling features:

1. **HTTP Exceptions**: Built-in exceptions for common HTTP errors
2. **Custom Error Pages**: Create custom error responses and pages
3. **Error Middleware**: Centralized error handling and logging
4. **Exception Propagation**: Proper exception handling throughout the stack
5. **Development vs Production**: Different error handling for different environments

## HTTP Exceptions

### Built-in HTTP Exceptions

Serv provides exceptions for common HTTP status codes:

```python
from serv.routes import Route, GetRequest, PostRequest
from serv.exceptions import (
    HTTPBadRequestException,
    HTTPUnauthorizedException,
    HTTPForbiddenException,
    HTTPNotFoundException,
    HTTPMethodNotAllowedException,
    HTTPInternalServerErrorException
)
from typing import Annotated
from serv.responses import JsonResponse

class ErrorExampleRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Demonstrate various HTTP exceptions"""
        error_type = request.query_params.get("error", "none")
        
        if error_type == "bad_request":
            raise HTTPBadRequestException("Invalid request parameters")
        
        elif error_type == "unauthorized":
            raise HTTPUnauthorizedException("Authentication required")
        
        elif error_type == "forbidden":
            raise HTTPForbiddenException("Access denied")
        
        elif error_type == "not_found":
            raise HTTPNotFoundException("Resource not found")
        
        elif error_type == "method_not_allowed":
            raise HTTPMethodNotAllowedException("Method not allowed")
        
        elif error_type == "internal_error":
            raise HTTPInternalServerErrorException("Internal server error")
        
        return {"message": "No error requested"}
```

### Custom HTTP Exceptions

Create your own HTTP exceptions for specific use cases:

```python
from serv.exceptions import HTTPException

class HTTPValidationException(HTTPException):
    """Custom validation error exception"""
    
    def __init__(self, message: str, field: str = None, details: dict = None):
        self.field = field
        self.details = details or {}
        super().__init__(status_code=422, detail=message)

class HTTPRateLimitException(HTTPException):
    """Rate limit exceeded exception"""
    
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)}
        )

class HTTPMaintenanceException(HTTPException):
    """Service maintenance exception"""
    
    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(status_code=503, detail=message)

class ValidationRoute(Route):
    async def handle_post(self, request: PostRequest) -> Annotated[dict, JsonResponse]:
        """Route with custom validation errors"""
        data = await request.json()
        
        # Validate email
        email = data.get("email", "").strip()
        if not email:
            raise HTTPValidationException("Email is required", field="email")
        
        if "@" not in email:
            raise HTTPValidationException(
                "Invalid email format",
                field="email",
                details={"provided": email, "expected_format": "user@domain.com"}
            )
        
        # Check rate limiting
        if await self.is_rate_limited(request):
            raise HTTPRateLimitException(retry_after=120)
        
        # Check maintenance mode
        if await self.is_maintenance_mode():
            raise HTTPMaintenanceException("System is under maintenance")
        
        return {"message": "Validation passed"}
    
    async def is_rate_limited(self, request) -> bool:
        """Check if request is rate limited"""
        # Implement rate limiting logic
        return False
    
    async def is_maintenance_mode(self) -> bool:
        """Check if system is in maintenance mode"""
        # Check maintenance flag
        return False
```

## Error Middleware

### Global Error Handler

Create middleware to handle all errors consistently:

```python
import logging
import traceback
from serv.middleware import Middleware
from serv.responses import JsonResponse, HtmlResponse
from serv.exceptions import HTTPException

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware(Middleware):
    """Global error handling middleware"""
    
    async def __call__(self, request, call_next):
        try:
            response = await call_next(request)
            return response
            
        except HTTPException as e:
            # Handle known HTTP exceptions
            return await self.handle_http_exception(request, e)
            
        except Exception as e:
            # Handle unexpected exceptions
            return await self.handle_unexpected_exception(request, e)
    
    async def handle_http_exception(self, request, exception: HTTPException):
        """Handle HTTP exceptions with proper responses"""
        logger.warning(
            f"HTTP {exception.status_code}: {exception.detail}",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": exception.status_code
            }
        )
        
        # Determine response format based on Accept header
        accept = request.headers.get("accept", "")
        
        if "application/json" in accept or request.url.path.startswith("/api/"):
            # Return JSON error for API requests
            error_data = {
                "error": {
                    "code": exception.status_code,
                    "message": exception.detail,
                    "type": exception.__class__.__name__
                }
            }
            
            # Add custom exception data if available
            if hasattr(exception, 'field'):
                error_data["error"]["field"] = exception.field
            
            if hasattr(exception, 'details'):
                error_data["error"]["details"] = exception.details
            
            return JsonResponse(
                error_data,
                status_code=exception.status_code,
                headers=getattr(exception, 'headers', None)
            )
        
        else:
            # Return HTML error page for web requests
            return await self.render_error_page(request, exception)
    
    async def handle_unexpected_exception(self, request, exception: Exception):
        """Handle unexpected exceptions"""
        logger.exception(
            f"Unexpected error: {str(exception)}",
            extra={
                "path": request.url.path,
                "method": request.method,
                "exception_type": exception.__class__.__name__
            }
        )
        
        # In development, show detailed error
        if request.app.debug:
            error_data = {
                "error": {
                    "code": 500,
                    "message": str(exception),
                    "type": exception.__class__.__name__,
                    "traceback": traceback.format_exc().split('\n')
                }
            }
        else:
            # In production, show generic error
            error_data = {
                "error": {
                    "code": 500,
                    "message": "Internal server error",
                    "type": "InternalServerError"
                }
            }
        
        accept = request.headers.get("accept", "")
        
        if "application/json" in accept or request.url.path.startswith("/api/"):
            return JsonResponse(error_data, status_code=500)
        else:
            return await self.render_error_page(request, HTTPInternalServerErrorException())
    
    async def render_error_page(self, request, exception: HTTPException):
        """Render HTML error page"""
        error_templates = {
            400: "errors/400.html",
            401: "errors/401.html",
            403: "errors/403.html",
            404: "errors/404.html",
            500: "errors/500.html"
        }
        
        template_name = error_templates.get(exception.status_code, "errors/generic.html")
        
        # Try to render custom error template
        try:
            # If you have a template engine, render the template
            html_content = await self.render_template(template_name, {
                "error": exception,
                "request": request
            })
        except:
            # Fallback to simple HTML
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Error {exception.status_code}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; text-align: center; }}
                    .error-container {{ max-width: 600px; margin: 0 auto; }}
                    .error-code {{ font-size: 72px; color: #dc3545; margin: 20px 0; }}
                    .error-message {{ font-size: 24px; color: #6c757d; margin: 20px 0; }}
                    .back-link {{ margin-top: 30px; }}
                    .back-link a {{ color: #007bff; text-decoration: none; }}
                </style>
            </head>
            <body>
                <div class="error-container">
                    <div class="error-code">{exception.status_code}</div>
                    <div class="error-message">{exception.detail}</div>
                    <div class="back-link">
                        <a href="/">← Back to Home</a>
                    </div>
                </div>
            </body>
            </html>
            """
        
        return HtmlResponse(html_content, status_code=exception.status_code)
    
    async def render_template(self, template_name: str, context: dict) -> str:
        """Render template (implement based on your template engine)"""
        # This would integrate with your template engine
        # For example, with Jinja2:
        # return await self.template_engine.render(template_name, context)
        raise NotImplementedError("Template rendering not implemented")
```

### Logging Middleware

Add detailed logging for debugging:

```python
import time
import uuid
from serv.middleware import Middleware

class LoggingMiddleware(Middleware):
    """Request/response logging middleware"""
    
    async def __call__(self, request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        # Log request
        start_time = time.time()
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
                "user_agent": request.headers.get("user-agent", ""),
                "client_ip": request.client.host if request.client else None
            }
        )
        
        try:
            response = await call_next(request)
            
            # Log successful response
            duration = time.time() - start_time
            logger.info(
                f"Request completed",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2)
                }
            )
            
            return response
            
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            logger.error(
                f"Request failed",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "error_type": e.__class__.__name__,
                    "duration_ms": round(duration * 1000, 2)
                }
            )
            raise
```

## Application-Level Error Handlers

### Custom Error Handlers

Serv allows you to register custom error handlers at the application level for specific exception types:

```python
from serv.app import App
from serv.exceptions import HTTPNotFoundException, HTTPBadRequestException
from serv.responses import ResponseBuilder
from serv.requests import Request
from bevy import dependency

# Create custom error handlers
async def custom_404_handler(
    error: HTTPNotFoundException,
    response: ResponseBuilder = dependency(),
    request: Request = dependency()
):
    """Custom 404 error handler"""
    response.set_status(404)
    response.content_type("text/html")
    response.body(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Page Not Found</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 100px; }}
            .error-code {{ font-size: 72px; color: #dc3545; }}
            .error-message {{ font-size: 24px; color: #6c757d; }}
        </style>
    </head>
    <body>
        <div class="error-code">404</div>
        <div class="error-message">Oops! The page "{request.path}" was not found.</div>
        <p><a href="/">Return to Home</a></p>
    </body>
    </html>
    """)

async def validation_error_handler(
    error: HTTPBadRequestException,
    response: ResponseBuilder = dependency(),
    request: Request = dependency()
):
    """Custom validation error handler"""
    # Check if this is an API request
    if request.path.startswith("/api/") or "application/json" in request.headers.get("accept", ""):
        response.set_status(400)
        response.content_type("application/json")
        response.body({
            "error": {
                "type": "validation_error",
                "message": str(error),
                "path": request.path,
                "timestamp": time.time()
            }
        })
    else:
        response.set_status(400)
        response.content_type("text/html")
        response.body(f"""
        <h1>Validation Error</h1>
        <p>{str(error)}</p>
        <a href="javascript:history.back()">Go Back</a>
        """)

# Register error handlers with the app
app = App()
app.add_error_handler(HTTPNotFoundException, custom_404_handler)
app.add_error_handler(HTTPBadRequestException, validation_error_handler)
```

### Generic Error Handler

You can also register a catch-all error handler for any unhandled exceptions:

```python
async def generic_error_handler(
    error: Exception,
    response: ResponseBuilder = dependency(),
    request: Request = dependency()
):
    """Handle any unhandled exceptions"""
    import logging
    import traceback
    
    logger = logging.getLogger(__name__)
    logger.exception(f"Unhandled error on {request.path}: {error}")
    
    # In development, show detailed error
    if app.dev_mode:
        response.set_status(500)
        response.content_type("text/html")
        response.body(f"""
        <h1>Internal Server Error</h1>
        <h2>{type(error).__name__}: {str(error)}</h2>
        <pre>{traceback.format_exc()}</pre>
        """)
    else:
        # In production, show generic error
        response.set_status(500)
        response.content_type("text/html")
        response.body("""
        <h1>Internal Server Error</h1>
        <p>Something went wrong. Please try again later.</p>
        """)

app.add_error_handler(Exception, generic_error_handler)
```

## Route-Level Error Handling

### Route Error Handlers

Route classes can define their own error handlers for exceptions that occur within that specific route:

```python
from serv.routes import Route, GetRequest, PostRequest
from serv.responses import JsonResponse, HtmlResponse
from typing import Annotated

class UserRoute(Route):
    """Route with custom error handling"""
    
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Get user by ID"""
        user_id = request.path_params.get("user_id")
        
        if not user_id.isdigit():
            raise ValueError("User ID must be a number")
        
        user = await self.get_user(int(user_id))
        if not user:
            raise HTTPNotFoundException(f"User {user_id} not found")
        
        return {"user": user}
    
    async def handle_post(self, request: PostRequest) -> Annotated[dict, JsonResponse]:
        """Create new user"""
        data = await request.json()
        
        # This might raise a custom exception
        user = await self.create_user(data)
        
        return {"user": user, "message": "User created"}
    
    async def handle_value_error(self, error: ValueError) -> JsonResponse:
        """Handle ValueError exceptions in this route"""
        return JsonResponse(
            {
                "error": "Invalid input",
                "message": str(error),
                "type": "validation_error"
            },
            status_code=400
        )
    
    async def handle_database_error(self, error: DatabaseError) -> JsonResponse:
        """Handle database errors in this route"""
        return JsonResponse(
            {
                "error": "Database error",
                "message": "Unable to process request",
                "type": "database_error"
            },
            status_code=503
        )
    
    async def get_user(self, user_id: int):
        """Mock user retrieval that might fail"""
        if user_id == 999:
            raise DatabaseError("Database connection failed")
        
        return {"id": user_id, "name": f"User {user_id}"}
    
    async def create_user(self, data):
        """Mock user creation that might fail"""
        if not data.get("email"):
            raise ValueError("Email is required")
        
        return {"id": 123, "email": data["email"]}

# Register route error handlers
UserRoute.add_error_handler(ValueError, UserRoute.handle_value_error)
UserRoute.add_error_handler(DatabaseError, UserRoute.handle_database_error)
```

### Error Handler Inheritance

Route error handlers take precedence over application-level handlers. If a route doesn't have a specific error handler, the application-level handler will be used:

```python
class BaseApiRoute(Route):
    """Base route with common error handling"""
    
    async def handle_validation_error(self, error: ValidationError) -> JsonResponse:
        """Common validation error handler for API routes"""
        return JsonResponse(
            {
                "error": "validation_failed",
                "message": str(error),
                "field": getattr(error, 'field', None)
            },
            status_code=422
        )

class ProductRoute(BaseApiRoute):
    """Product route inheriting error handling"""
    
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Get product - uses inherited error handling"""
        product_id = request.path_params.get("product_id")
        
        if not product_id:
            raise ValidationError("Product ID is required", field="product_id")
        
        return {"product": {"id": product_id, "name": "Sample Product"}}

# Register error handler on base class
BaseApiRoute.add_error_handler(ValidationError, BaseApiRoute.handle_validation_error)
```

## Custom Error Pages

### Creating Error Templates

Create custom HTML templates for different error types:

**templates/errors/404.html:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Not Found - 404</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .error-container {
            text-align: center;
            color: white;
            max-width: 600px;
            padding: 40px;
        }
        .error-code {
            font-size: 120px;
            font-weight: bold;
            margin: 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .error-title {
            font-size: 32px;
            margin: 20px 0;
            font-weight: 300;
        }
        .error-description {
            font-size: 18px;
            margin: 30px 0;
            line-height: 1.6;
            opacity: 0.9;
        }
        .action-buttons {
            margin-top: 40px;
        }
        .btn {
            display: inline-block;
            padding: 12px 30px;
            margin: 0 10px;
            background: rgba(255,255,255,0.2);
            color: white;
            text-decoration: none;
            border-radius: 25px;
            border: 2px solid rgba(255,255,255,0.3);
            transition: all 0.3s ease;
        }
        .btn:hover {
            background: rgba(255,255,255,0.3);
            border-color: rgba(255,255,255,0.5);
        }
        .btn-primary {
            background: rgba(255,255,255,0.9);
            color: #667eea;
            border-color: transparent;
        }
        .btn-primary:hover {
            background: white;
        }
    </style>
</head>
<body>
    <div class="error-container">
        <h1 class="error-code">404</h1>
        <h2 class="error-title">Page Not Found</h2>
        <p class="error-description">
            The page you're looking for doesn't exist or has been moved.
            Don't worry, it happens to the best of us!
        </p>
        <div class="action-buttons">
            <a href="/" class="btn btn-primary">Go Home</a>
            <a href="javascript:history.back()" class="btn">Go Back</a>
        </div>
    </div>
</body>
</html>
```

**templates/errors/500.html:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Server Error - 500</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .error-container {
            text-align: center;
            color: white;
            max-width: 600px;
            padding: 40px;
        }
        .error-code {
            font-size: 120px;
            font-weight: bold;
            margin: 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .error-title {
            font-size: 32px;
            margin: 20px 0;
            font-weight: 300;
        }
        .error-description {
            font-size: 18px;
            margin: 30px 0;
            line-height: 1.6;
            opacity: 0.9;
        }
        .action-buttons {
            margin-top: 40px;
        }
        .btn {
            display: inline-block;
            padding: 12px 30px;
            margin: 0 10px;
            background: rgba(255,255,255,0.2);
            color: white;
            text-decoration: none;
            border-radius: 25px;
            border: 2px solid rgba(255,255,255,0.3);
            transition: all 0.3s ease;
        }
        .btn:hover {
            background: rgba(255,255,255,0.3);
            border-color: rgba(255,255,255,0.5);
        }
        .btn-primary {
            background: rgba(255,255,255,0.9);
            color: #ff6b6b;
            border-color: transparent;
        }
        .btn-primary:hover {
            background: white;
        }
    </style>
</head>
<body>
    <div class="error-container">
        <h1 class="error-code">500</h1>
        <h2 class="error-title">Server Error</h2>
        <p class="error-description">
            Something went wrong on our end. We've been notified and are working to fix it.
            Please try again in a few minutes.
        </p>
        <div class="action-buttons">
            <a href="/" class="btn btn-primary">Go Home</a>
            <a href="javascript:location.reload()" class="btn">Try Again</a>
        </div>
    </div>
</body>
</html>
```

### Dynamic Error Pages

Create error pages with dynamic content:

```python
class ErrorPageRoute(Route):
    """Custom error page handler"""
    
    async def handle_get(self, request: GetRequest) -> HtmlResponse:
        """Render custom error page"""
        error_code = request.path_params.get("code", "404")
        
        error_info = {
            "400": {
                "title": "Bad Request",
                "description": "The request could not be understood by the server.",
                "color": "#ffc107"
            },
            "401": {
                "title": "Unauthorized",
                "description": "You need to log in to access this resource.",
                "color": "#fd7e14"
            },
            "403": {
                "title": "Forbidden",
                "description": "You don't have permission to access this resource.",
                "color": "#dc3545"
            },
            "404": {
                "title": "Not Found",
                "description": "The page you're looking for doesn't exist.",
                "color": "#6f42c1"
            },
            "500": {
                "title": "Server Error",
                "description": "Something went wrong on our end.",
                "color": "#e83e8c"
            }
        }
        
        info = error_info.get(error_code, error_info["404"])
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error {error_code} - {info['title']}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background: linear-gradient(135deg, {info['color']} 0%, #333 100%);
                    color: white;
                    margin: 0;
                    padding: 40px;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .container {{
                    text-align: center;
                    max-width: 600px;
                }}
                .code {{ font-size: 100px; margin: 20px 0; }}
                .title {{ font-size: 36px; margin: 20px 0; }}
                .description {{ font-size: 18px; margin: 30px 0; }}
                .actions {{ margin-top: 40px; }}
                .btn {{
                    display: inline-block;
                    padding: 12px 24px;
                    margin: 0 10px;
                    background: rgba(255,255,255,0.2);
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    border: 1px solid rgba(255,255,255,0.3);
                }}
                .btn:hover {{
                    background: rgba(255,255,255,0.3);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="code">{error_code}</div>
                <div class="title">{info['title']}</div>
                <div class="description">{info['description']}</div>
                <div class="actions">
                    <a href="/" class="btn">Go Home</a>
                    <a href="javascript:history.back()" class="btn">Go Back</a>
                </div>
            </div>
        </body>
        </html>
        """
        
        return HtmlResponse(html_content, status_code=int(error_code))
```

## Validation Errors

### Form Validation

Handle form validation errors gracefully:

```python
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class ValidationError:
    field: str
    message: str
    code: str = None

class FormValidationException(HTTPException):
    """Exception for form validation errors"""
    
    def __init__(self, errors: List[ValidationError]):
        self.errors = errors
        error_messages = [f"{error.field}: {error.message}" for error in errors]
        super().__init__(
            status_code=422,
            detail="Validation failed: " + "; ".join(error_messages)
        )

class UserRegistrationRoute(Route):
    async def handle_post(self, request: PostRequest) -> Annotated[dict, JsonResponse]:
        """User registration with comprehensive validation"""
        data = await request.json()
        
        # Validate the form
        errors = await self.validate_registration_form(data)
        
        if errors:
            raise FormValidationException(errors)
        
        # Process registration
        user = await self.create_user(data)
        
        return {"user": user, "message": "Registration successful"}
    
    async def validate_registration_form(self, data: Dict[str, Any]) -> List[ValidationError]:
        """Validate registration form data"""
        errors = []
        
        # Validate name
        name = data.get("name", "").strip()
        if not name:
            errors.append(ValidationError("name", "Name is required", "REQUIRED"))
        elif len(name) < 2:
            errors.append(ValidationError("name", "Name must be at least 2 characters", "MIN_LENGTH"))
        elif len(name) > 50:
            errors.append(ValidationError("name", "Name must be less than 50 characters", "MAX_LENGTH"))
        
        # Validate email
        email = data.get("email", "").strip().lower()
        if not email:
            errors.append(ValidationError("email", "Email is required", "REQUIRED"))
        elif not self.is_valid_email(email):
            errors.append(ValidationError("email", "Invalid email format", "INVALID_FORMAT"))
        elif await self.email_exists(email):
            errors.append(ValidationError("email", "Email already registered", "ALREADY_EXISTS"))
        
        # Validate password
        password = data.get("password", "")
        if not password:
            errors.append(ValidationError("password", "Password is required", "REQUIRED"))
        elif len(password) < 8:
            errors.append(ValidationError("password", "Password must be at least 8 characters", "MIN_LENGTH"))
        elif not self.is_strong_password(password):
            errors.append(ValidationError("password", "Password must contain uppercase, lowercase, and numbers", "WEAK"))
        
        # Validate password confirmation
        password_confirm = data.get("password_confirm", "")
        if password and password != password_confirm:
            errors.append(ValidationError("password_confirm", "Passwords do not match", "MISMATCH"))
        
        # Validate age
        age = data.get("age")
        if age is not None:
            try:
                age = int(age)
                if age < 13:
                    errors.append(ValidationError("age", "Must be at least 13 years old", "MIN_VALUE"))
                elif age > 120:
                    errors.append(ValidationError("age", "Invalid age", "MAX_VALUE"))
            except (ValueError, TypeError):
                errors.append(ValidationError("age", "Age must be a number", "INVALID_TYPE"))
        
        return errors
    
    def is_valid_email(self, email: str) -> bool:
        """Basic email validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    async def email_exists(self, email: str) -> bool:
        """Check if email already exists"""
        # Implement database check
        return False
    
    def is_strong_password(self, password: str) -> bool:
        """Check password strength"""
        import re
        # At least one uppercase, one lowercase, one digit
        return (
            re.search(r'[A-Z]', password) and
            re.search(r'[a-z]', password) and
            re.search(r'\d', password)
        )
    
    async def create_user(self, data: Dict[str, Any]):
        """Create user in database"""
        return {
            "id": 123,
            "name": data["name"],
            "email": data["email"]
        }
```

## Error Recovery

### Retry Mechanisms

Implement retry logic for transient errors:

```python
import asyncio
from typing import Callable, Any

class RetryableRoute(Route):
    """Route with retry mechanisms for external services"""
    
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Get data with retry logic"""
        try:
            # Try to get data from external service with retries
            data = await self.retry_operation(
                self.fetch_external_data,
                max_retries=3,
                delay=1.0,
                backoff=2.0
            )
            
            return {"data": data}
            
        except Exception as e:
            logger.error(f"Failed to fetch data after retries: {str(e)}")
            raise HTTPInternalServerErrorException("Service temporarily unavailable")
    
    async def retry_operation(
        self,
        operation: Callable,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        *args,
        **kwargs
    ) -> Any:
        """Retry an operation with exponential backoff"""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await operation(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                if attempt == max_retries:
                    # Last attempt failed
                    break
                
                # Log retry attempt
                logger.warning(
                    f"Operation failed (attempt {attempt + 1}/{max_retries + 1}): {str(e)}. "
                    f"Retrying in {delay} seconds..."
                )
                
                # Wait before retry
                await asyncio.sleep(delay)
                delay *= backoff  # Exponential backoff
        
        # All retries failed
        raise last_exception
    
    async def fetch_external_data(self):
        """Simulate external service call"""
        import random
        
        # Simulate random failures
        if random.random() < 0.7:  # 70% failure rate for demo
            raise ConnectionError("External service unavailable")
        
        return {"external_data": "success"}
```

### Circuit Breaker Pattern

Implement circuit breaker for failing services:

```python
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """Circuit breaker implementation"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    async def call(self, operation: Callable, *args, **kwargs):
        """Execute operation through circuit breaker"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise HTTPServiceUnavailableException("Circuit breaker is open")
        
        try:
            result = await operation(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.timeout
        )
    
    def _on_success(self):
        """Handle successful operation"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Handle failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

class CircuitBreakerRoute(Route):
    """Route using circuit breaker pattern"""
    
    def __init__(self):
        super().__init__()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=30.0,
            expected_exception=ConnectionError
        )
    
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Get data through circuit breaker"""
        try:
            data = await self.circuit_breaker.call(self.fetch_external_data)
            return {"data": data, "circuit_state": self.circuit_breaker.state.value}
            
        except HTTPException:
            raise
            
        except Exception as e:
            logger.error(f"Circuit breaker operation failed: {str(e)}")
            raise HTTPServiceUnavailableException("External service unavailable")
    
    async def fetch_external_data(self):
        """Simulate external service call"""
        import random
        
        if random.random() < 0.6:  # 60% failure rate for demo
            raise ConnectionError("External service down")
        
        return {"service_data": "available"}
```

## Best Practices

### 1. Use Appropriate Exception Types

```python
# Good: Use specific exceptions
if not user_id:
    raise HTTPBadRequestException("User ID is required")

if not await user_exists(user_id):
    raise HTTPNotFoundException(f"User {user_id} not found")

if not await has_permission(user, resource):
    raise HTTPForbiddenException("Access denied")

# Avoid: Generic exceptions
if not user_id:
    raise Exception("Error")  # Too generic
```

### 2. Log Errors Appropriately

```python
# Good: Structured logging with context
logger.error(
    "Database connection failed",
    extra={
        "user_id": user_id,
        "operation": "fetch_user",
        "database": "users_db",
        "error_code": "CONNECTION_TIMEOUT"
    }
)

# Avoid: Minimal logging
logger.error("Error occurred")  # Not helpful
```

### 3. Provide Helpful Error Messages

```python
# Good: Clear, actionable error messages
raise HTTPBadRequestException(
    "Invalid email format. Please provide a valid email address like 'user@example.com'"
)

# Avoid: Vague error messages
raise HTTPBadRequestException("Invalid input")  # Not helpful
```

### 4. Handle Errors at the Right Level

```python
# Good: Handle errors where you can take action
async def handle_post(self, request: PostRequest):
    try:
        data = await request.json()
    except ValueError:
        raise HTTPBadRequestException("Invalid JSON format")
    
    # Continue processing...

# Avoid: Catching and re-raising without adding value
async def handle_post(self, request: PostRequest):
    try:
        data = await request.json()
    except Exception as e:
        raise e  # Pointless catch and re-raise
```

### 5. Differentiate Development and Production

```python
# Good: Different error handling for different environments
if app.debug:
    # Show detailed errors in development
    error_data = {
        "error": str(exception),
        "traceback": traceback.format_exc(),
        "request_data": await request.json()
    }
else:
    # Show generic errors in production
    error_data = {
        "error": "Internal server error"
    }

# Avoid: Always showing detailed errors
error_data = {
    "error": str(exception),
    "traceback": traceback.format_exc()  # Security risk in production
}
```

## Development Workflow

### 1. Plan Error Scenarios

Identify potential error conditions:
- Invalid input
- Missing resources
- Permission issues
- External service failures
- Database errors

### 2. Create Custom Exceptions

Define exceptions specific to your domain.

### 3. Implement Error Middleware

Set up centralized error handling and logging.

### 4. Create Error Pages

Design user-friendly error pages for web interfaces.

### 5. Test Error Handling

Test various error scenarios and edge cases.

## Next Steps

- **[Testing](testing.md)** - Test your error handling logic
- **[Logging](logging.md)** - Set up comprehensive logging
- **[Monitoring](monitoring.md)** - Monitor errors in production
- **[Security](security.md)** - Secure error handling practices 