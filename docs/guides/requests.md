# Request Handling

Serv provides powerful request handling capabilities through specialized request objects and automatic parameter injection. This guide covers everything you need to know about processing HTTP requests in Serv applications.

## Overview

Serv's request handling features:

1. **Signature-Based Routing**: Automatic handler selection based on method signatures
2. **Parameter Injection**: Direct injection of query params, headers, and cookies via annotations
3. **Typed Request Objects**: Specialized request classes for different HTTP methods
4. **Body Parsing**: JSON, form data, and file uploads with automatic form matching
5. **Route Classes**: Clean separation using Route classes with multiple handlers per method

## Request Types

Serv provides specialized request classes for different HTTP methods:

### Basic Request Types

```python
from serv.routes import Route, GetRequest, PostRequest, PutRequest, DeleteRequest
from typing import Annotated
from serv.responses import JsonResponse

class ApiRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Handle GET requests"""
        return {"method": "GET", "path": request.path}
    
    async def handle_post(self, request: PostRequest) -> Annotated[dict, JsonResponse]:
        """Handle POST requests"""
        return {"method": "POST", "path": request.path}
    
    async def handle_put(self, request: PutRequest) -> Annotated[dict, JsonResponse]:
        """Handle PUT requests"""
        return {"method": "PUT", "path": request.path}
    
    async def handle_delete(self, request: DeleteRequest) -> Annotated[dict, JsonResponse]:
        """Handle DELETE requests"""
        return {"method": "DELETE", "path": request.path}
```

### Request Object Properties

All request objects provide access to common HTTP request data:

```python
from serv.routes import Route, GetRequest
from typing import Annotated
from serv.responses import JsonResponse

class RequestInfoRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Display request information"""
        return {
            "method": request.method,
            "path": request.path,
            "query_string": request.query_string,
            "headers": dict(request.headers),
            "client": request.client,
            "scheme": request.scheme,
            "server": request.server,
            "path_params": request.path_params,
            "query_params": dict(request.query_params)
        }
```

## Path Parameters

### Basic Path Parameters

Extract path parameters from URL patterns:

```python
from serv.routes import Route, GetRequest
from typing import Annotated
from serv.responses import JsonResponse

class UserRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Get user by ID from path parameter"""
        user_id = request.path_params.get("user_id")
        
        if not user_id:
            return {"error": "User ID is required"}
        
        # Fetch user data
        user = await self.get_user(user_id)
        
        return {"user": user}
    
    async def get_user(self, user_id: str):
        """Mock user retrieval"""
        return {
            "id": user_id,
            "name": f"User {user_id}",
            "email": f"user{user_id}@example.com"
        }
```

**Extension configuration:**
```yaml
routers:
  - name: main_router
    routes:
      - path: /users/{user_id}
        handler: route_user:UserRoute
```

### Multiple Path Parameters

Handle multiple path parameters:

```python
class PostRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Get post by user ID and post ID"""
        user_id = request.path_params.get("user_id")
        post_id = request.path_params.get("post_id")
        
        if not user_id or not post_id:
            return {"error": "Both user_id and post_id are required"}
        
        post = await self.get_post(user_id, post_id)
        return {"post": post}
    
    async def get_post(self, user_id: str, post_id: str):
        """Mock post retrieval"""
        return {
            "id": post_id,
            "user_id": user_id,
            "title": f"Post {post_id} by User {user_id}",
            "content": "Sample post content"
        }
```

**Extension configuration:**
```yaml
routers:
  - name: main_router
    routes:
      - path: /users/{user_id}/posts/{post_id}
        handler: route_post:PostRoute
```

### Path Parameter Validation

Validate and convert path parameters:

```python
from serv.exceptions import HTTPBadRequestException, HTTPNotFoundException

class ValidatedUserRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Get user with validated ID"""
        user_id_str = request.path_params.get("user_id")
        
        # Validate user ID is numeric
        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            raise HTTPBadRequestException("User ID must be a number")
        
        # Validate user ID is positive
        if user_id <= 0:
            raise HTTPBadRequestException("User ID must be positive")
        
        # Check if user exists
        user = await self.get_user(user_id)
        if not user:
            raise HTTPNotFoundException(f"User {user_id} not found")
        
        return {"user": user}
    
    async def get_user(self, user_id: int):
        """Get user by numeric ID"""
        # Mock database lookup
        if user_id > 1000:
            return None  # User not found
        
        return {
            "id": user_id,
            "name": f"User {user_id}",
            "email": f"user{user_id}@example.com"
        }
```

## Query Parameters

### Basic Query Parameters with Signature-Based Routing

Use parameter injection for clean, automatic query parameter handling:

```python
from serv.injectors import Query
from serv.exceptions import HTTPBadRequestException

class SearchRoute(Route):
    async def handle_get(self) -> Annotated[dict, JsonResponse]:
        """Default search - no parameters"""
        results = await self.get_default_results()
        return {"results": results, "message": "Default search results"}
    
    async def handle_get_with_query(
        self,
        query: Annotated[str, Query("q")]
    ) -> Annotated[dict, JsonResponse]:
        """Search with query string only"""
        results = await self.search(query)
        return {"query": query, "results": results}
    
    async def handle_get_paginated(
        self,
        query: Annotated[str, Query("q")],
        page: Annotated[str, Query("page", default="1")],
        limit: Annotated[str, Query("limit", default="10")]
    ) -> Annotated[dict, JsonResponse]:
        """Search with pagination"""
        # Convert and validate parameters
        try:
            page_num = int(page)
            limit_num = int(limit)
        except ValueError:
            raise HTTPBadRequestException("Page and limit must be numbers")
        
        if page_num < 1:
            raise HTTPBadRequestException("Page must be >= 1")
        
        if limit_num < 1 or limit_num > 100:
            raise HTTPBadRequestException("Limit must be between 1 and 100")
        
        # Perform paginated search
        results = await self.search_paginated(query, page_num, limit_num)
        
        return {
            "query": query,
            "page": page_num,
            "limit": limit_num,
            "results": results,
            "total": len(results)
        }
    
    async def handle_get_advanced(
        self,
        query: Annotated[str, Query("q")],
        page: Annotated[str, Query("page", default="1")],
        limit: Annotated[str, Query("limit", default="10")],
        sort: Annotated[str, Query("sort", default="created_at")],
        category: Annotated[str, Query("category", default=None)]
    ) -> Annotated[dict, JsonResponse]:
        """Advanced search with all options"""
        page_num = int(page)
        limit_num = int(limit)
        
        results = await self.advanced_search(query, page_num, limit_num, sort, category)
        
        return {
            "query": query,
            "page": page_num,
            "limit": limit_num,
            "sort": sort,
            "category": category,
            "results": results
        }
```

**Request routing examples:**
- `GET /search` → `handle_get` (no parameters)
- `GET /search?q=python` → `handle_get_with_query` (has query only)
- `GET /search?q=python&page=2` → `handle_get_paginated` (has query and pagination)
- `GET /search?q=python&page=2&sort=date&category=tech` → `handle_get_advanced` (most specific)

### Multiple Values for Same Parameter

Handle query parameters with multiple values:

```python
class FilterRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Filter with multiple values"""
        # Get multiple values for the same parameter
        categories = request.query_params.getlist("category")
        tags = request.query_params.getlist("tag")
        
        # Get single values with defaults
        min_price = float(request.query_params.get("min_price", "0"))
        max_price = float(request.query_params.get("max_price", "1000"))
        
        # Apply filters
        products = await self.filter_products(categories, tags, min_price, max_price)
        
        return {
            "filters": {
                "categories": categories,
                "tags": tags,
                "min_price": min_price,
                "max_price": max_price
            },
            "products": products
        }
    
    async def filter_products(self, categories, tags, min_price, max_price):
        """Mock product filtering"""
        return [
            {
                "id": 1,
                "name": "Product 1",
                "categories": categories[:1] if categories else ["general"],
                "tags": tags[:2] if tags else ["sample"],
                "price": (min_price + max_price) / 2
            }
        ]
```

**Example URLs:**
```
/filter?category=electronics&category=computers&tag=laptop&tag=gaming&min_price=500&max_price=2000
```

## Headers

### Accessing Headers

Read HTTP headers from requests using direct access or dependency injection:

```python
from serv.injectors import Header
from typing import Annotated
from bevy import dependency

class HeaderRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Display request headers using direct access"""
        # Get specific headers
        user_agent = request.headers.get("user-agent", "Unknown")
        accept = request.headers.get("accept", "*/*")
        authorization = request.headers.get("authorization")
        
        # Get custom headers
        api_key = request.headers.get("x-api-key")
        client_version = request.headers.get("x-client-version")
        
        return {
            "user_agent": user_agent,
            "accept": accept,
            "has_auth": authorization is not None,
            "api_key": api_key,
            "client_version": client_version,
            "all_headers": dict(request.headers)
        }

class HeaderInjectionRoute(Route):
    async def handle_get(
        self,
        request: GetRequest,
        # Inject specific headers with defaults
        user_agent: Annotated[str, Header("user-agent", "Unknown")] = dependency(),
        api_key: Annotated[str, Header("x-api-key")] = dependency(),
        auth_token: Annotated[str, Header("authorization")] = dependency(),
    ) -> Annotated[dict, JsonResponse]:
        """Display request headers using dependency injection"""
        return {
            "user_agent": user_agent,
            "api_key": api_key,
            "has_auth": auth_token is not None,
            "path": request.path
        }
```

### Header-Based Authentication

Use headers for authentication:

```python
from serv.exceptions import HTTPUnauthorizedException

class AuthenticatedRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Require authentication via header"""
        # Check for API key
        api_key = request.headers.get("x-api-key")
        if not api_key:
            raise HTTPUnauthorizedException("API key required")
        
        # Validate API key
        user = await self.validate_api_key(api_key)
        if not user:
            raise HTTPUnauthorizedException("Invalid API key")
        
        return {
            "message": "Authenticated successfully",
            "user": user
        }
    
    async def validate_api_key(self, api_key: str):
        """Validate API key and return user"""
        # Mock validation
        valid_keys = {
            "key123": {"id": 1, "name": "John Doe"},
            "key456": {"id": 2, "name": "Jane Smith"}
        }
        
        return valid_keys.get(api_key)
```

### Content Negotiation

Handle content negotiation based on Accept header:

```python
from serv.responses import JsonResponse, HtmlResponse, TextResponse

class ContentNegotiationRoute(Route):
    async def handle_get(self, request: GetRequest):
        """Return different content based on Accept header"""
        accept = request.headers.get("accept", "")
        
        data = {
            "message": "Hello, World!",
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
        if "application/json" in accept:
            return JsonResponse(data)
        elif "text/html" in accept:
            html_content = f"""
            <html>
                <body>
                    <h1>{data['message']}</h1>
                    <p>Timestamp: {data['timestamp']}</p>
                </body>
            </html>
            """
            return HtmlResponse(html_content)
        else:
            text_content = f"{data['message']} at {data['timestamp']}"
            return TextResponse(text_content)
```

## Request Body

### JSON Body

Parse JSON request bodies:

```python
from dataclasses import dataclass

@dataclass
class CreateUserRequest:
    name: str
    email: str
    age: int

class UserCreateRoute(Route):
    async def handle_post(self, request: PostRequest) -> Annotated[dict, JsonResponse]:
        """Create user from JSON body"""
        try:
            # Parse JSON body
            data = await request.json()
            
            # Validate required fields
            if not data.get("name"):
                raise HTTPBadRequestException("Name is required")
            
            if not data.get("email") or "@" not in data["email"]:
                raise HTTPBadRequestException("Valid email is required")
            
            # Create user
            user = await self.create_user(data)
            
            return {"user": user, "message": "User created successfully"}
            
        except ValueError as e:
            raise HTTPBadRequestException(f"Invalid JSON: {str(e)}")
    
    async def create_user(self, data):
        """Create user in database"""
        return {
            "id": 123,
            "name": data["name"],
            "email": data["email"],
            "age": data.get("age", 0)
        }
```

### Raw Body

Access raw request body:

```python
class WebhookRoute(Route):
    async def handle_post(self, request: PostRequest) -> Annotated[dict, JsonResponse]:
        """Handle webhook with raw body"""
        # Get raw body as bytes
        body = await request.body()
        
        # Get content type
        content_type = request.headers.get("content-type", "")
        
        # Process based on content type
        if content_type.startswith("application/json"):
            import json
            data = json.loads(body.decode())
        elif content_type.startswith("application/xml"):
            # Handle XML
            data = {"xml": body.decode()}
        else:
            # Handle as text
            data = {"text": body.decode()}
        
        # Process webhook
        result = await self.process_webhook(data, content_type)
        
        return {"status": "processed", "result": result}
    
    async def process_webhook(self, data, content_type):
        """Process webhook data"""
        return {
            "received_at": "2024-01-01T12:00:00Z",
            "content_type": content_type,
            "data_keys": list(data.keys()) if isinstance(data, dict) else None
        }
```

### Stream Processing

Handle large request bodies with streaming:

```python
class UploadRoute(Route):
    async def handle_post(self, request: PostRequest) -> Annotated[dict, JsonResponse]:
        """Handle large file upload with streaming"""
        content_length = int(request.headers.get("content-length", "0"))
        
        # Check file size limit (10MB)
        max_size = 10 * 1024 * 1024
        if content_length > max_size:
            raise HTTPBadRequestException("File too large")
        
        # Stream the body
        chunks = []
        async for chunk in request.stream():
            chunks.append(chunk)
        
        # Combine chunks
        body = b"".join(chunks)
        
        # Save file
        filename = await self.save_file(body)
        
        return {
            "filename": filename,
            "size": len(body),
            "message": "File uploaded successfully"
        }
    
    async def save_file(self, content: bytes) -> str:
        """Save uploaded file"""
        import uuid
        filename = f"upload_{uuid.uuid4().hex}.bin"
        
        with open(f"uploads/{filename}", "wb") as f:
            f.write(content)
        
        return filename
```

## Cookies

### Accessing Cookies

Access cookies using direct access or dependency injection:

```python
from serv.injectors import Cookie

class CookieRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Access cookies using direct access"""
        # Get cookies directly from request
        session_id = request.cookies.get("session_id")
        theme = request.cookies.get("theme", "light")
        language = request.cookies.get("language", "en")
        
        return {
            "session_id": session_id,
            "theme": theme,
            "language": language,
            "all_cookies": request.cookies
        }

class CookieInjectionRoute(Route):
    async def handle_get(
        self,
        request: GetRequest,
        # Inject specific cookies with defaults
        session_id: Annotated[str, Cookie("session_id")] = dependency(),
        theme: Annotated[str, Cookie("theme", "light")] = dependency(),
        language: Annotated[str, Cookie("language", "en")] = dependency(),
        user_id: Annotated[str, Cookie("user_id")] = dependency(),
    ) -> Annotated[dict, JsonResponse]:
        """Access cookies using dependency injection"""
        
        # Check if user is logged in
        is_authenticated = session_id is not None and user_id is not None
        
        return {
            "is_authenticated": is_authenticated,
            "user_id": user_id,
            "theme": theme,
            "language": language,
            "path": request.path
        }

class AuthenticatedCookieRoute(Route):
    async def handle_get(
        self,
        request: GetRequest,
        session_id: Annotated[str, Cookie("session_id")] = dependency(),
        user_id: Annotated[str, Cookie("user_id")] = dependency(),
    ) -> Annotated[dict, JsonResponse]:
        """Route that requires authentication via cookies"""
        
        if not session_id or not user_id:
            raise HTTPUnauthorizedException("Authentication required")
        
        # Validate session (in real app, check against database/cache)
        if not await self.validate_session(session_id, user_id):
            raise HTTPUnauthorizedException("Invalid session")
        
        return {
            "message": "Welcome authenticated user",
            "user_id": user_id,
            "session_id": session_id
        }
    
    async def validate_session(self, session_id: str, user_id: str) -> bool:
        """Mock session validation"""
        # In a real application, validate against your session store
        return len(session_id) > 10 and user_id.isdigit()
```

## Advanced Request Handling

### Request Context

Store and access request-specific data:

```python
class ContextRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Use request context for storing data"""
        # Store data in request context
        request.context["user_id"] = 123
        request.context["start_time"] = time.time()
        
        # Process request
        result = await self.process_request(request)
        
        # Calculate processing time
        processing_time = time.time() - request.context["start_time"]
        
        return {
            "result": result,
            "user_id": request.context["user_id"],
            "processing_time": processing_time
        }
    
    async def process_request(self, request):
        """Process request with access to context"""
        user_id = request.context.get("user_id")
        return f"Processed for user {user_id}"
```

### Request Validation

Create reusable request validation:

```python
from typing import Dict, Any

class ValidationMixin:
    """Mixin for request validation"""
    
    def validate_json_body(self, data: Dict[str, Any], required_fields: list):
        """Validate JSON body has required fields"""
        missing_fields = []
        
        for field in required_fields:
            if field not in data or not data[field]:
                missing_fields.append(field)
        
        if missing_fields:
            raise HTTPBadRequestException(f"Missing required fields: {', '.join(missing_fields)}")
    
    def validate_email(self, email: str):
        """Validate email format"""
        if not email or "@" not in email or "." not in email:
            raise HTTPBadRequestException("Invalid email format")
    
    def validate_positive_integer(self, value: str, field_name: str) -> int:
        """Validate and convert to positive integer"""
        try:
            num = int(value)
            if num <= 0:
                raise HTTPBadRequestException(f"{field_name} must be positive")
            return num
        except ValueError:
            raise HTTPBadRequestException(f"{field_name} must be a number")

class ValidatedUserRoute(Route, ValidationMixin):
    async def handle_post(self, request: PostRequest) -> Annotated[dict, JsonResponse]:
        """Create user with validation"""
        data = await request.json()
        
        # Validate required fields
        self.validate_json_body(data, ["name", "email"])
        
        # Validate email format
        self.validate_email(data["email"])
        
        # Validate age if provided
        if "age" in data:
            data["age"] = self.validate_positive_integer(str(data["age"]), "age")
        
        # Create user
        user = await self.create_user(data)
        
        return {"user": user}
```

## Best Practices

### 1. Use Appropriate Request Types

```python
# Good: Use specific request types
class UserRoute(Route):
    async def handle_get(self, request: GetRequest):
        # Handle GET requests
        pass
    
    async def handle_post(self, request: PostRequest):
        # Handle POST requests
        pass

# Avoid: Generic request handling
async def generic_handler(request):
    if request.method == "GET":
        # Handle GET
        pass
    elif request.method == "POST":
        # Handle POST
        pass
```

### 2. Validate Input Early

```python
# Good: Validate immediately
async def handle_post(self, request: PostRequest):
    data = await request.json()
    
    if not data.get("email"):
        raise HTTPBadRequestException("Email is required")
    
    # Continue processing...

# Avoid: Late validation
async def handle_post(self, request: PostRequest):
    data = await request.json()
    
    # Lots of processing...
    
    if not data.get("email"):  # Too late!
        raise HTTPBadRequestException("Email is required")
```

### 3. Handle Errors Gracefully

```python
# Good: Comprehensive error handling
async def handle_post(self, request: PostRequest):
    try:
        data = await request.json()
    except ValueError:
        raise HTTPBadRequestException("Invalid JSON")
    
    try:
        user_id = int(request.path_params["user_id"])
    except (ValueError, KeyError):
        raise HTTPBadRequestException("Invalid user ID")
    
    # Process request...

# Avoid: Letting exceptions bubble up
async def handle_post(self, request: PostRequest):
    data = await request.json()  # Could raise ValueError
    user_id = int(request.path_params["user_id"])  # Could raise ValueError/KeyError
```

### 4. Use Type Hints

```python
# Good: Clear type hints
async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
    return {"message": "Hello"}

# Avoid: No type hints
async def handle_get(self, request):
    return {"message": "Hello"}
```

### 5. Sanitize Input

```python
# Good: Sanitize user input
async def handle_post(self, request: PostRequest):
    data = await request.json()
    
    # Sanitize string inputs
    name = data.get("name", "").strip()[:100]  # Limit length
    email = data.get("email", "").strip().lower()
    
    # Validate after sanitization
    if not name:
        raise HTTPBadRequestException("Name is required")

# Avoid: Using raw input
async def handle_post(self, request: PostRequest):
    data = await request.json()
    name = data.get("name")  # Could be None, empty, or very long
```

## Development Workflow

### 1. Plan Your Request Handling

Identify what data your routes need:
- Path parameters
- Query parameters  
- Headers
- Request body
- File uploads

### 2. Create Route Classes

```bash
serv create route --name "user_api" --path "/api/users" --extension "api"
```

### 3. Implement Request Handlers

Add methods for each HTTP method you need to support.

### 4. Add Validation

Implement proper input validation and error handling.

### 5. Test Request Handling

Test with different types of requests and edge cases.

## Next Steps

- **[Response Building](responses.md)** - Learn how to build and return responses
- **[Forms and File Uploads](forms.md)** - Handle form submissions and file uploads
- **[Authentication](authentication.md)** - Secure your request handlers
- **[Testing](testing.md)** - Test your request handling logic 