# Proposed Routing Code Structure

## New Module Organization

### 1. HTTP Layer Separation
Create a dedicated `serv/http/` package for HTTP-specific concerns:

```
serv/http/
├── __init__.py
├── requests.py       # Request objects (GetRequest, PostRequest, etc.)
├── responses.py      # Response builders and types
├── forms.py          # Form processing, multipart handling
├── validation.py     # Request validation, parameter coercion
└── middleware.py     # HTTP-specific middleware utilities
```

**Responsibilities:**
- **requests.py**: HTTP request objects, parameter parsing, query/form data access
- **responses.py**: Response builders, status codes, headers, content types
- **forms.py**: Form data parsing, multipart handling, file uploads
- **validation.py**: Request validation, type coercion, parameter extraction
- **middleware.py**: HTTP middleware utilities, request/response processing

### 2. Routing Layer Refactoring
Reorganize `serv/routing/` as a proper package:

```
serv/routing/
├── __init__.py       # Public API exports
├── router.py         # Core Router class (path matching only)
├── handlers.py       # Route handler base class and decorators
├── registry.py       # Route registration and lookup
├── resolver.py       # Route resolution logic
├── patterns.py       # URL pattern compilation and matching
└── websockets.py     # WebSocket routing (extracted from router.py)
```

**Responsibilities:**
- **router.py**: Core Router class, route registration, mounting sub-routers
- **handlers.py**: Route base class, method decorators (`@handles`)
- **registry.py**: Route storage, lookup, and organization
- **resolver.py**: Route resolution logic, parameter extraction
- **patterns.py**: URL pattern compilation, path matching algorithms
- **websockets.py**: WebSocket-specific routing logic

### 3. Application Layer Restructuring
Break down `serv/app.py` into focused modules:

```
serv/app/
├── __init__.py       # App class and public API
├── core.py           # Core App class (ASGI implementation)
├── lifecycle.py      # Request lifecycle management
├── middleware.py     # Middleware orchestration
├── extensions.py     # Extension system integration
└── factory.py        # App factory and builder patterns
```

**Responsibilities:**
- **core.py**: Core App class, ASGI implementation, basic request handling
- **lifecycle.py**: Request lifecycle events, context management
- **middleware.py**: Middleware stack management, ordering, execution
- **extensions.py**: Extension loading, coordination, event management
- **factory.py**: App creation utilities, configuration handling

### 4. Dependency Injection Layer
Create focused DI utilities:

```
serv/di/
├── __init__.py
├── injection.py      # Parameter injection logic
├── containers.py     # Request-scoped containers
└── resolvers.py      # Dependency resolution strategies
```

## Module Responsibilities Matrix

| Module | Routing | HTTP | App | DI | Extensions |
|--------|---------|------|-----|----|-----------| 
| `routing/router.py` | ✓ | | | | |
| `routing/handlers.py` | ✓ | | | ✓ | |
| `routing/resolver.py` | ✓ | | | | |
| `http/requests.py` | | ✓ | | | |
| `http/responses.py` | | ✓ | | | |
| `http/forms.py` | | ✓ | | | |
| `app/core.py` | | | ✓ | | |
| `app/middleware.py` | | | ✓ | | |
| `app/extensions.py` | | | ✓ | | ✓ |
| `di/injection.py` | | | | ✓ | |

## Class Breakdown

### Current `routes.py` (1,138 lines) → Multiple Modules

**Extract to `http/requests.py` (~200 lines):**
- `GetRequest`, `PostRequest`, etc. classes
- Request parameter parsing
- Query string handling

**Extract to `http/forms.py` (~300 lines):**
- Form data processing
- Multipart handling
- File upload logic
- Form validation

**Extract to `routing/handlers.py` (~400 lines):**
- `Route` base class
- `@handles` decorators
- Method selection logic
- Handler signature inspection

**Extract to `di/injection.py` (~200 lines):**
- Parameter injection logic
- Dependency resolution
- Container integration

**Remaining coordination (~38 lines):**
- Import/export statements
- Backward compatibility shims

### Current `app.py` (1,112 lines) → Multiple Modules

**Extract to `app/core.py` (~300 lines):**
- Core `App` class
- ASGI implementation
- Basic request/response handling

**Extract to `app/lifecycle.py` (~200 lines):**
- Request lifecycle management
- Event emission and handling
- Context management

**Extract to `app/middleware.py` (~250 lines):**
- Middleware stack management
- Middleware execution order
- Built-in middleware

**Extract to `app/extensions.py` (~300 lines):**
- Extension loading and coordination
- Extension event management
- Configuration integration

**Remaining coordination (~62 lines):**
- Import/export statements
- Backward compatibility
- Factory functions

### Current `routing.py` (788 lines) → Focused Modules

**Extract to `routing/patterns.py` (~200 lines):**
- URL pattern compilation
- Path matching algorithms
- Parameter extraction

**Extract to `routing/resolver.py` (~150 lines):**
- Route resolution logic
- Method matching
- WebSocket resolution

**Extract to `routing/websockets.py` (~100 lines):**
- WebSocket routing logic
- WebSocket path matching

**Remaining in `routing/router.py` (~338 lines):**
- Core Router class
- Route registration
- Sub-router mounting
- Public API

## Import Strategy

### Public API Preservation
Maintain backward compatibility through `__init__.py` files:

```python
# serv/__init__.py
from .app import App
from .routing import Router
from .routes import Route, handles
from .requests import GetRequest, PostRequest
from .responses import JSONResponse, HTMLResponse

# serv/routing/__init__.py  
from .router import Router
from .handlers import Route, handles

# serv/http/__init__.py
from .requests import GetRequest, PostRequest
from .responses import JSONResponse, HTMLResponse
```

### Internal Imports
Use relative imports within packages, absolute imports between packages:

```python
# Within routing package
from .patterns import compile_pattern
from .resolver import resolve_route

# Between packages  
from serv.http.requests import GetRequest
from serv.di.injection import inject_parameters
```

## Performance Considerations

### Optimizations Enabled by Refactoring

**1. Lazy Loading:**
- Import only needed modules
- Reduce startup time
- Memory usage optimization

**2. Caching Opportunities:**
- Pattern compilation caching in `patterns.py`
- Route resolution caching in `resolver.py`
- Middleware stack caching in `middleware.py`

**3. Profiling Points:**
- Clear boundaries for performance measurement
- Isolated optimization targets
- Easier to identify bottlenecks

### Potential Performance Impacts

**Import Overhead:**
- More modules = more import statements
- Mitigated by lazy loading and caching

**Function Call Overhead:**
- More abstraction layers
- Mitigated by keeping hot paths direct

## Extension System Integration

### New Extension Points

**Cleaner Extension APIs:**
```python
# Current (scattered across multiple files)
@on("app.request.begin")
async def register_routes(self, router: Router):
    router.add_route("/api", handler)

# Proposed (focused extension points)
@on("routing.setup")
async def setup_routes(self, registry: RouteRegistry):
    registry.register("/api", handler)

@on("http.middleware.setup") 
async def setup_middleware(self, stack: MiddlewareStack):
    stack.add(AuthMiddleware())
```

**Extension Categories:**
- **Routing Extensions**: Route registration, URL patterns
- **HTTP Extensions**: Request/response processing, middleware
- **App Extensions**: Lifecycle, configuration, services

## Migration Benefits

### Development Benefits
- **Easier Testing**: Smaller, focused modules
- **Better IDE Support**: Clearer imports, better autocomplete
- **Reduced Cognitive Load**: Single responsibility per module
- **Easier Debugging**: Clear module boundaries

### Maintenance Benefits  
- **Isolated Changes**: Modifications don't affect unrelated code
- **Clear Documentation**: Each module has focused purpose
- **Better Code Review**: Smaller, focused changes
- **Reduced Merge Conflicts**: Changes isolated to specific areas

### Performance Benefits
- **Lazy Loading**: Import only what's needed
- **Optimization Opportunities**: Clear performance boundaries
- **Memory Efficiency**: Smaller loaded modules
- **Caching Potential**: Focused caching strategies