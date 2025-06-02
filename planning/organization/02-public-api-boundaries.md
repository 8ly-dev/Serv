# Public API Boundaries

## Problem Description

The Serv framework's main `__init__.py` only exposes 3 items (`App`, `handle`, `WebSocket`), forcing users to import common functionality from submodules. This creates a poor developer experience and unclear API boundaries between public and internal APIs.

### Current API Exposure

**Main Package (`serv/__init__.py`)**:
```python
__all__ = ["App", "handle", "WebSocket"]
```

**What Users Actually Need**:
```python
# Users have to do this:
from serv import App
from serv.routes import Route  
from serv.responses import JsonResponse, HtmlResponse
from serv.requests import GetRequest, PostRequest
from serv.extensions import Extension

# Instead of this (what they expect):
from serv import App, Route, JsonResponse, Extension
```

### Real-World Usage Examples

**Current Required Imports** (Poor DX):
```python
from serv import App, handle
from serv.routes import Route
from serv.responses import JsonResponse, HtmlResponse, TextResponse
from serv.requests import GetRequest, PostRequest  
from serv.extensions import Extension
from serv.routing import Router
from typing import Annotated

class UserRoute(Route):
    @handle.GET
    async def get_users(self) -> Annotated[list, JsonResponse]:
        return [{"id": 1, "name": "John"}]
```

**Desired Imports** (Good DX):
```python
from serv import (
    App, Route, Extension, Router,
    JsonResponse, HtmlResponse, TextResponse,
    GetRequest, PostRequest,
    handle
)
from typing import Annotated

class UserRoute(Route):
    @handle.GET  
    async def get_users(self) -> Annotated[list, JsonResponse]:
        return [{"id": 1, "name": "John"}]
```

### Documentation vs Reality Gap

**Quick Start Documentation Shows**:
```python
from serv import App
from serv.routes import Route
# Multiple imports from different modules
```

**Other Frameworks Comparison**:
```python
# FastAPI (good API boundaries)
from fastapi import FastAPI, HTTPException, Depends

# Flask (good API boundaries)  
from flask import Flask, request, jsonify

# Django (good API boundaries)
from django.http import JsonResponse
from django.views import View
```

## Impact Assessment

- **Severity**: 🔴 **HIGH** (Poor first impression)
- **Developer Experience**: **POOR** (Too many import statements)
- **Learning Curve**: **STEEP** (Users must learn internal structure)
- **Framework Adoption**: **NEGATIVE** (Compared poorly to competitors)

## Recommendations

### Option 1: Expand Main Package Exports (Recommended)
**Effort**: Low | **Impact**: High

**Expand `serv/__init__.py` to include commonly used classes**:
```python
# serv/__init__.py
from .app import App
from .routes import Route
from .extensions import Extension, Listener
from .routing import Router
from .requests import Request, GetRequest, PostRequest, PutRequest, DeleteRequest, PatchRequest, OptionsRequest, HeadRequest
from .responses import (
    Response, JsonResponse, HtmlResponse, TextResponse, 
    FileResponse, RedirectResponse, StreamingResponse, 
    ServerSentEventsResponse, Jinja2Response, ResponseBuilder
)
from .routes import handle
from .websocket import WebSocket
from .injectors import Query, Header, Cookie

__all__ = [
    # Core framework
    "App", "Route", "Extension", "Listener", "Router",
    
    # Request types
    "Request", "GetRequest", "PostRequest", "PutRequest", 
    "DeleteRequest", "PatchRequest", "OptionsRequest", "HeadRequest",
    
    # Response types  
    "Response", "JsonResponse", "HtmlResponse", "TextResponse",
    "FileResponse", "RedirectResponse", "StreamingResponse",
    "ServerSentEventsResponse", "Jinja2Response", "ResponseBuilder",
    
    # Utilities
    "handle", "WebSocket", "Query", "Header", "Cookie"
]
```

### Option 2: Create Subpackage Exports
**Effort**: Medium | **Impact**: Medium

**Organize exports by category**:
```python
# serv/__init__.py
from .core import *
from .web import *
from .extensions import *

# serv/core.py
__all__ = ["App", "Router"]

# serv/web.py  
__all__ = ["Route", "JsonResponse", "GetRequest", "handle"]

# serv/extensions.py
__all__ = ["Extension", "Listener"]
```

### Option 3: Layered API Approach
**Effort**: High | **Impact**: High

**Provide both simple and advanced APIs**:
```python
# serv/__init__.py - Simple API
from .simple import *

# serv/simple.py - High-level API
__all__ = ["App", "Route", "JsonResponse", "handle"]

# serv/advanced.py - Full API
__all__ = ["Router", "Extension", "Middleware", "Container"]
```

## Action Checklist

### Phase 1: Design Public API (Week 1)
- [ ] Audit all classes/functions that should be public
- [ ] Design logical groupings for exports
- [ ] Identify internal vs public APIs
- [ ] Plan backward compatibility strategy

### Phase 2: Implement Expanded Exports (Week 1)  
- [ ] Update `serv/__init__.py` with comprehensive exports
- [ ] Add `__all__` definitions to all public modules
- [ ] Ensure import statements work correctly
- [ ] Test performance impact of expanded imports

### Phase 3: Update Documentation (Week 1)
- [ ] Update all code examples to use main package imports
- [ ] Update getting started guide
- [ ] Update API reference documentation
- [ ] Update demo applications

### Phase 4: Testing & Validation (Week 1)
- [ ] Test all public API imports work
- [ ] Verify no circular import issues
- [ ] Test IDE auto-completion works
- [ ] Validate backward compatibility

### New Public API Design

**Categories for Public Export**:

1. **Core Framework**:
   - `App` - Main application class
   - `Router` - URL routing
   - `Route` - Base route class

2. **Request/Response**:
   - Request classes: `GetRequest`, `PostRequest`, etc.
   - Response classes: `JsonResponse`, `HtmlResponse`, etc.
   - `ResponseBuilder` - Response construction

3. **Extensions**:
   - `Extension` - Base extension class
   - `Listener` - Event listener base

4. **Utilities**:
   - `handle` - Route decorators
   - `WebSocket` - WebSocket support
   - Injectors: `Query`, `Header`, `Cookie`

**Example Updated `__init__.py`**:
```python
"""
Serv - A modern Python web framework built for extensibility.

This module provides the public API for the Serv framework.
"""

# Core framework components
from .app import App
from .routing import Router  
from .routes import Route, handle

# Request and response types
from .requests import (
    Request, GetRequest, PostRequest, PutRequest, DeleteRequest,
    PatchRequest, OptionsRequest, HeadRequest
)
from .responses import (
    Response, ResponseBuilder,
    JsonResponse, HtmlResponse, TextResponse, 
    FileResponse, RedirectResponse, 
    StreamingResponse, ServerSentEventsResponse,
    Jinja2Response
)

# Extension system
from .extensions import Extension, Listener

# WebSocket support
from .websocket import WebSocket

# Dependency injection utilities
from .injectors import Query, Header, Cookie

# Define public API
__all__ = [
    # Core framework
    "App", "Router", "Route", "handle",
    
    # Request types
    "Request", "GetRequest", "PostRequest", "PutRequest", 
    "DeleteRequest", "PatchRequest", "OptionsRequest", "HeadRequest",
    
    # Response types
    "Response", "ResponseBuilder", "JsonResponse", "HtmlResponse", 
    "TextResponse", "FileResponse", "RedirectResponse", 
    "StreamingResponse", "ServerSentEventsResponse", "Jinja2Response",
    
    # Extension system
    "Extension", "Listener",
    
    # Additional utilities
    "WebSocket", "Query", "Header", "Cookie"
]

# Version information
__version__ = "0.1.0"
```

### Module `__all__` Definitions

**Add to all public modules**:
```python
# serv/routes.py
__all__ = ["Route", "handle", "Form"]

# serv/responses.py  
__all__ = [
    "Response", "ResponseBuilder", "JsonResponse", 
    "HtmlResponse", "TextResponse", "FileResponse",
    "RedirectResponse", "StreamingResponse", 
    "ServerSentEventsResponse", "Jinja2Response"
]

# serv/requests.py
__all__ = [
    "Request", "GetRequest", "PostRequest", "PutRequest",
    "DeleteRequest", "PatchRequest", "OptionsRequest", "HeadRequest"
]

# serv/extensions.py
__all__ = ["Extension", "Listener"]

# serv/routing.py
__all__ = ["Router"]
```

### Documentation Updates

**Updated Quick Start Example**:
```python
# Before (many imports)
from serv import App, handle
from serv.routes import Route
from serv.responses import JsonResponse
from serv.requests import GetRequest
from typing import Annotated

# After (clean imports)
from serv import App, Route, JsonResponse, GetRequest, handle
from typing import Annotated

class HelloRoute(Route):
    @handle.GET
    async def hello(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        return {"message": "Hello World!"}

app = App()
app.add_route("/", HelloRoute)
```

**Updated Tutorial Examples**:
```python
# All examples can now use clean imports
from serv import (
    App, Route, Extension,
    JsonResponse, HtmlResponse, 
    GetRequest, PostRequest,
    handle, Query
)
```

### Testing Strategy

**Import Testing**:
```python
def test_public_api_imports():
    """Test that all public API items can be imported from main package."""
    # Core framework
    from serv import App, Router, Route, handle
    
    # Request types
    from serv import Request, GetRequest, PostRequest
    
    # Response types
    from serv import JsonResponse, HtmlResponse, TextResponse
    
    # Extension system
    from serv import Extension, Listener
    
    # Utilities
    from serv import WebSocket, Query, Header, Cookie
    
    # Verify types are correct
    assert issubclass(Route, object)
    assert callable(handle.GET)
    assert issubclass(JsonResponse, Response)

def test_backward_compatibility():
    """Test that existing import patterns still work."""
    # Old imports should still work
    from serv.routes import Route
    from serv.responses import JsonResponse
    from serv.requests import GetRequest
    
    assert Route is not None
    assert JsonResponse is not None

def test_no_circular_imports():
    """Test that expanded exports don't create circular imports."""
    import importlib
    import sys
    
    # Clear module cache
    for module in list(sys.modules.keys()):
        if module.startswith('serv'):
            del sys.modules[module]
    
    # Import main package (should not fail)
    serv = importlib.import_module('serv')
    
    # Verify key exports exist
    assert hasattr(serv, 'App')
    assert hasattr(serv, 'Route')
    assert hasattr(serv, 'JsonResponse')
```

### Performance Considerations

**Import Time Impact**:
- Expanded imports may increase initial import time by ~10-20ms
- Consider lazy imports for less commonly used items
- Use `typing.TYPE_CHECKING` for type-only imports

**Lazy Import Example**:
```python
# serv/__init__.py
import typing

# Always available
from .app import App
from .routes import Route, handle

# Lazy imports for less common items
if typing.TYPE_CHECKING:
    from .websocket import WebSocket

def __getattr__(name: str):
    if name == "WebSocket":
        from .websocket import WebSocket
        return WebSocket
    raise AttributeError(f"module 'serv' has no attribute '{name}'")
```

### IDE Support Improvements

**Better Auto-completion**:
With expanded exports, IDEs will provide better auto-completion when users type `from serv import`.

**Type Checking**:
All exported types will be properly recognized by type checkers like mypy and PyLance.

This change will dramatically improve the developer experience and make Serv more competitive with other modern Python frameworks.