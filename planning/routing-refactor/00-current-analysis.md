# Current Routing Code Analysis

## File Structure and Sizes

### Core Routing Files
- `serv/routing.py` - 788 lines - Router class with path matching and route resolution
- `serv/routes.py` - 1,138 lines - Route base class, request types, form handling, decorators
- `serv/app.py` - 1,112 lines - App class with ASGI implementation and routing integration
- `serv/extensions/router_extension.py` - 118 lines - Extension system for declarative routing
- `serv/protocols.py` - 119 lines - RouterProtocol interface definitions

### Supporting Files
- `serv/requests.py` - Request objects and parsing
- `serv/responses.py` - Response builders and types
- `serv/routing/` - Empty directory (unused)

## Current Responsibilities

### Router Class (`routing.py`)
**Primary Responsibilities:**
- URL pattern matching and compilation
- Route registration (`add_route()`)
- Route resolution (`resolve_route()`, `resolve_websocket()`)
- Path parameter extraction
- URL generation (`url_for()`)
- Sub-router mounting
- WebSocket routing

**Key Methods:**
- `add_route(path, handler, methods, name)`
- `resolve_route(path, method)`
- `resolve_websocket(path)`
- `url_for(name, **params)`
- `mount(path, router)`
- `_match_path(pattern, path)`

### Route Class (`routes.py`)
**Primary Responsibilities:**
- HTTP method handling via decorators (`@handles.GET`, `@handles.POST`)
- Form processing and multipart handling
- Signature-based handler method selection
- Dependency injection integration
- Response type annotation processing
- Request validation and coercion
- Error handling for route execution

**Key Features:**
- Method decorators (`@handles`)
- Automatic parameter injection
- Signature matching for handler selection
- Form data parsing
- File upload handling
- Response type inference

### App Class (`app.py`)
**Primary Responsibilities:**
- ASGI application implementation
- Middleware orchestration
- Router instance management
- Request lifecycle coordination
- Extension system integration
- Error handling and logging
- Template rendering setup

**Routing Integration:**
- Creates router instances per request
- Handles route resolution
- Coordinates with extensions for route registration
- Manages request/response flow

## Problems Identified

### 1. Excessive File Sizes
- `routes.py` (1,138 lines) - Too large, handles multiple concerns
- `app.py` (1,112 lines) - Central orchestrator but too much in one place
- Both files violate Single Responsibility Principle

### 2. Mixed Concerns
- `routes.py` contains:
  - Route handling logic
  - HTTP request/response types
  - Form processing
  - Validation logic
  - Decorator implementations
- `app.py` contains:
  - ASGI implementation
  - Routing coordination
  - Middleware management
  - Extension system
  - Error handling
  - Template setup

### 3. Unclear Module Boundaries
- Router (path matching) vs Route (method handling) responsibilities overlap
- HTTP-specific logic mixed with routing logic
- Extension system tightly coupled in multiple places
- Protocol definitions separated from implementations

### 4. Testing Challenges
- Large classes are harder to unit test
- Mixed concerns make it difficult to isolate functionality
- Circular dependencies between modules

### 5. Import Complexity
- Large modules lead to importing more than needed
- Circular import issues
- Unclear what functionality comes from which module

## Current Request Flow

```
ASGI Request →
App._handle_request() →
emit("app.request.begin") →
Extensions register routes →
Router.resolve_route() →
Route.__call__() →
Route._handle_request() →
Handler method selection →
Dependency injection →
Response processing →
ASGI Response
```

## Extension System Integration

**Current Extension Points:**
1. Route registration via `on("app.request.begin")` listeners
2. Middleware registration via extension configuration
3. Direct router access for programmatic route addition
4. RouterExtension for declarative YAML-based routing

**Issues:**
- Extension routing logic scattered across multiple files
- No clear extension API boundaries
- Tight coupling between extensions and core routing

## Performance Considerations

**Current Performance Characteristics:**
- Route resolution is O(n) where n is number of routes
- Path compilation happens at registration time
- Router instance created per request (potential optimization opportunity)
- Method resolution uses signature inspection (reflection overhead)

## Dependencies and Coupling

**High Coupling Areas:**
- Route class depends on Router for URL generation
- App class tightly coupled to both Router and Route
- Extension system has dependencies on all routing components
- Request/Response types mixed with routing logic

**Import Dependencies:**
```
app.py → routing.py, routes.py, requests.py, responses.py, extensions/
routes.py → requests.py, responses.py, routing.py (for url_for)
routing.py → protocols.py
extensions/router_extension.py → routing.py, routes.py
```

## Backward Compatibility Requirements

**Public APIs that must be preserved:**
- `Router.add_route()`, `Router.resolve_route()`, `Router.url_for()`
- `Route` class and `@handles` decorators
- `App` class constructor and public methods
- Extension registration patterns
- Request/Response object interfaces

**Internal APIs that can change:**
- Private methods (prefixed with `_`)
- Internal class organization
- Module structure (as long as imports work)
- Implementation details of route resolution