# Response Building

Serv provides a flexible response system that allows you to return different types of content with proper HTTP status codes, headers, and content types. This guide covers the essential response types and patterns you'll use in Serv applications.

## Overview

Serv offers multiple ways to build responses:

1. **Type-Annotated Responses**: Use type annotations to specify response types automatically
2. **Response Classes**: Direct instantiation of response objects for full control
3. **ResponseBuilder**: Low-level response building with the dependency injection system
4. **Streaming Responses**: Handle large files and real-time data efficiently

## Basic Response Types

### JSON Responses

JSON responses are the most common for APIs. Serv automatically serializes Python objects to JSON and sets the appropriate content type:

```python
from serv.routes import Route, GetRequest, PostRequest
from serv.responses import JsonResponse
from typing import Annotated

class ApiRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        """Return JSON using type annotation (recommended)"""
        return {
            "message": "Hello, World!",
            "status": "success",
            "data": {
                "users": [
                    {"id": 1, "name": "John Doe"},
                    {"id": 2, "name": "Jane Smith"}
                ]
            }
        }
    
    async def handle_post(self, request: PostRequest) -> JsonResponse:
        """Return JSON using direct response class"""
        data = await request.json()
        
        # Process the data...
        result = {"id": 123, "created": True}
        
        return JsonResponse(result, status_code=201)
```

The type annotation approach (`Annotated[dict, JsonResponse]`) is recommended because it's cleaner and allows Serv to automatically wrap your return value. The direct response class approach gives you more control over status codes and headers.

### HTML Responses

HTML responses are used for web pages and server-rendered content:

```python
from serv.responses import HtmlResponse

class WebRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[str, HtmlResponse]:
        """Return HTML using type annotation"""
        name = request.query_params.get("name", "World")
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Welcome</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .greeting {{ color: #007bff; font-size: 24px; }}
            </style>
        </head>
        <body>
            <h1 class="greeting">Hello, {name}!</h1>
            <p>Welcome to our Serv application.</p>
        </body>
        </html>
        """
```

### File Downloads

File responses handle binary content and downloads:

```python
from serv.responses import FileResponse
import os

class DownloadRoute(Route):
    async def handle_get(self, request: GetRequest) -> FileResponse:
        """Serve file downloads"""
        filename = request.path_params.get("filename")
        
        # Validate filename for security
        if not filename or ".." in filename:
            raise HTTPBadRequestException("Invalid filename")
        
        file_path = f"uploads/{filename}"
        if not os.path.exists(file_path):
            raise HTTPNotFoundException("File not found")
        
        # Read file content
        with open(file_path, "rb") as f:
            file_content = f.read()
        
        # Determine content type based on extension
        content_type = "application/octet-stream"
        if filename.endswith(".pdf"):
            content_type = "application/pdf"
        elif filename.endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif filename.endswith(".png"):
            content_type = "image/png"
        
        return FileResponse(
            file=file_content,
            filename=filename,
            content_type=content_type
        )
```

## Streaming Responses

Streaming responses are essential for handling large files, real-time data, or when you want to start sending data before it's fully processed.

### Basic Streaming

```python
from serv.responses import StreamingResponse
import asyncio
import json

class StreamRoute(Route):
    async def handle_get(self, request: GetRequest) -> StreamingResponse:
        """Stream data to client"""
        
        async def generate_data():
            """Generate streaming data"""
            for i in range(100):
                data = {"count": i, "timestamp": time.time()}
                yield f"data: {json.dumps(data)}\n"
                await asyncio.sleep(0.1)  # Simulate processing time
        
        return StreamingResponse(
            generate_data(),
            media_type="text/plain"
        )
```

### Server-Sent Events (SSE)

Server-Sent Events provide real-time updates to web browsers:

```python
from serv.responses import ServerSentEventsResponse
import time

class EventStreamRoute(Route):
    async def handle_get(self, request: GetRequest) -> ServerSentEventsResponse:
        """Real-time event stream for web browsers"""
        
        async def event_stream():
            """Generate SSE events"""
            event_id = 0
            
            while True:
                event_id += 1
                
                # Send structured SSE event
                yield f"id: {event_id}\n"
                yield f"event: update\n"
                yield f"data: {json.dumps({'message': f'Event {event_id}', 'time': time.time()})}\n\n"
                
                await asyncio.sleep(1)  # Send event every second
                
                # Stop after 10 events for demo
                if event_id >= 10:
                    break
        
        return ServerSentEventsResponse(event_stream())
```

The corresponding HTML client would look like:

```html
<script>
const eventSource = new EventSource('/events');
eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};
</script>
```

### Large File Streaming

For large files, streaming prevents memory issues:

```python
class LargeFileRoute(Route):
    async def handle_get(self, request: GetRequest) -> StreamingResponse:
        """Stream large files efficiently"""
        file_path = "large_file.csv"
        
        async def file_streamer():
            """Stream file in chunks"""
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    yield chunk
        
        return StreamingResponse(
            file_streamer(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=data.csv"}
        )
```

## Advanced Response Patterns

### Custom Response Classes

Create specialized response types for your application:

```python
from serv.responses import Response
import xml.etree.ElementTree as ET

class XmlResponse(Response):
    """Custom XML response"""
    
    def __init__(self, data: dict, status_code: int = 200):
        # Convert dict to XML
        xml_content = self._dict_to_xml(data)
        
        super().__init__(
            status_code=status_code,
            body=xml_content,
            headers={"Content-Type": "application/xml"}
        )
    
    def _dict_to_xml(self, data: dict, root_name: str = "response") -> str:
        """Convert dictionary to XML string"""
        root = ET.Element(root_name)
        
        def add_element(parent, key, value):
            element = ET.SubElement(parent, key)
            if isinstance(value, dict):
                for k, v in value.items():
                    add_element(element, k, v)
            elif isinstance(value, list):
                for item in value:
                    add_element(element, "item", item)
            else:
                element.text = str(value)
        
        for key, value in data.items():
            add_element(root, key, value)
        
        return ET.tostring(root, encoding="unicode")

class XmlApiRoute(Route):
    async def handle_get(self, request: GetRequest) -> XmlResponse:
        """Return XML response"""
        data = {
            "users": [
                {"id": "1", "name": "John Doe"},
                {"id": "2", "name": "Jane Smith"}
            ]
        }
        
        return XmlResponse(data)
```

### Error Responses

Standardize error responses across your application:

```python
class ErrorResponse(JsonResponse):
    """Standardized error response"""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = None, 
        details: dict = None,
        status_code: int = 400
    ):
        error_data = {
            "error": {
                "message": message,
                "code": error_code or "GENERIC_ERROR",
                "timestamp": time.time()
            }
        }
        
        if details:
            error_data["error"]["details"] = details
        
        super().__init__(error_data, status_code)

class ApiErrorRoute(Route):
    async def handle_post(self, request: PostRequest) -> JsonResponse:
        """API with standardized error handling"""
        try:
            data = await request.json()
            
            # Validate input
            if not data.get("email"):
                return ErrorResponse(
                    message="Email is required",
                    error_code="MISSING_EMAIL",
                    status_code=400
                )
            
            # Process request...
            result = await self.process_data(data)
            
            return JsonResponse({"result": result})
            
        except ValueError:
            return ErrorResponse(
                message="Invalid JSON format",
                error_code="INVALID_JSON",
                status_code=400
            )
        
        except Exception as e:
            return ErrorResponse(
                message="Internal server error",
                error_code="INTERNAL_ERROR",
                details={"exception": str(e)},
                status_code=500
            )
```

## Response Headers and Status Codes

### Setting Custom Headers

Add custom headers to responses:

```python
class HeaderRoute(Route):
    async def handle_get(self, request: GetRequest) -> JsonResponse:
        """Response with custom headers"""
        data = {"message": "Success"}
        
        response = JsonResponse(data)
        response.headers["X-Custom-Header"] = "MyValue"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Rate-Limit"] = "100"
        
        return response
```

### Status Codes

Use appropriate HTTP status codes:

```python
class StatusCodeRoute(Route):
    async def handle_post(self, request: PostRequest) -> JsonResponse:
        """Create resource with 201 status"""
        data = await request.json()
        
        # Create resource...
        resource_id = 123
        
        return JsonResponse(
            {"id": resource_id, "message": "Created"},
            status_code=201
        )
    
    async def handle_delete(self, request: DeleteRequest) -> JsonResponse:
        """Delete resource with 204 status"""
        resource_id = request.path_params.get("id")
        
        # Delete resource...
        
        return JsonResponse(
            {"message": "Deleted"},
            status_code=204
        )
```

## Best Practices

### 1. Use Type Annotations

Type annotations make your code cleaner and enable automatic response wrapping:

```python
# Good: Clean and automatic
async def handle_get(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
    return {"message": "Hello"}

# Avoid: More verbose
async def handle_get(self, request: GetRequest) -> JsonResponse:
    return JsonResponse({"message": "Hello"})
```

### 2. Handle Errors Gracefully

Always provide meaningful error responses:

```python
# Good: Specific error handling
async def handle_post(self, request: PostRequest):
    try:
        data = await request.json()
    except ValueError:
        return ErrorResponse("Invalid JSON", "INVALID_JSON", status_code=400)
    
    if not data.get("email"):
        return ErrorResponse("Email required", "MISSING_EMAIL", status_code=400)

# Avoid: Generic error handling
async def handle_post(self, request: PostRequest):
    data = await request.json()  # Could fail
    # Process without validation
```

### 3. Use Streaming for Large Data

Stream responses when dealing with large datasets or real-time data:

```python
# Good: Stream large responses
async def handle_get(self, request: GetRequest) -> StreamingResponse:
    async def generate_csv():
        yield "id,name,email\n"
        for user in await self.get_all_users():  # Could be millions
            yield f"{user.id},{user.name},{user.email}\n"
    
    return StreamingResponse(generate_csv(), media_type="text/csv")

# Avoid: Loading everything into memory
async def handle_get(self, request: GetRequest) -> JsonResponse:
    users = await self.get_all_users()  # Memory intensive
    return JsonResponse(users)
```

### 4. Set Appropriate Content Types

Always use the correct content type for your responses:

```python
# Good: Explicit content types
return StreamingResponse(data, media_type="application/json")
return FileResponse(file, filename="data.pdf", content_type="application/pdf")

# Avoid: Generic content types
return StreamingResponse(data)  # Defaults to text/plain
```

## Development Workflow

### 1. Plan Your Response Types

Identify what types of responses your application needs:
- JSON for APIs
- HTML for web pages
- Files for downloads
- Streaming for large data or real-time updates

### 2. Create Response Classes

Use the CLI to create routes and implement appropriate response types:

```bash
serv create route --name "api" --path "/api/users" --extension "api"
```

### 3. Implement Error Handling

Add proper error responses for validation, authentication, and server errors.

### 4. Test Response Types

Test different response types and edge cases to ensure proper behavior.

## Next Steps

- **[Error Handling](error-handling.md)** - Learn comprehensive error handling patterns
- **[Templates](templates.md)** - Use template engines for HTML responses
- **[Testing](testing.md)** - Test your response handling logic
- **[Deployment](deployment.md)** - Deploy applications with proper response handling 