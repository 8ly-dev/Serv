# Route Class Complexity

## Problem Description

The Route class in `serv/routes.py` has become a monolithic class trying to handle too many responsibilities. It manages HTTP method routing, form handling, error handling, response type inference, parameter injection, and handler discovery - violating the Single Responsibility Principle and creating maintenance nightmares.

### Current Complexity Analysis

**File**: `serv/routes.py` (~1100 lines)

**Multiple Responsibilities**:
1. **HTTP Method Routing**: Discovering and calling handle_* methods
2. **Form Handling**: Processing form data and matching to Form classes
3. **Error Handling**: Managing exception handlers 
4. **Response Type Inference**: Analyzing annotations to wrap responses
5. **Parameter Injection**: Extracting and injecting headers, cookies, queries
6. **Handler Selection**: Complex algorithm to choose best handler match
7. **Signature Analysis**: Introspecting method signatures for routing

### Code Complexity Indicators

**Handler Discovery Mechanisms** (Too Many):
```python
# 1. Naming convention handlers
def handle_get(self): pass

# 2. Decorator-based handlers  
@handle.GET
def get_users(self): pass

# 3. Form handlers via type signatures
def handle_user_form(self, form: UserForm): pass

# 4. Error handlers via type signatures
def handle_error(self, error: ValueError): pass
```

**Complex Handler Selection Logic** (200+ lines):
```python
def _handle_request(self, request, container, path_params):
    # 80 lines of form handler logic
    if self.__form_handlers__.get(method):
        # Complex form matching...
    
    # 120 lines of method handler logic  
    if not handler and method in self.__method_handlers__:
        # Complex signature analysis...
        # Multiple handler compatibility checking...
        # Scoring and ranking system...
    
    # More complex response wrapping logic...
```

**Signature Analysis Complexity**:
```python
def _analyze_handler_signature(self, handler_sig, request: Request) -> dict:
    """100+ lines of complex parameter analysis."""
    # Type hint extraction
    # Injection marker detection  
    # Parameter requirement analysis
    # Scoring algorithm
    # Compatibility checking
```

## Impact Assessment

- **Severity**: 🔴 **CRITICAL**
- **Maintainability**: **VERY LOW** (Hard to modify without breaking)
- **Testability**: **LOW** (Complex interactions, many code paths)
- **Performance**: **POOR** (O(n) handler selection, repeated analysis)
- **Developer Experience**: **POOR** (Hard to understand, multiple patterns)

## Recommendations

### Option 1: Split Route Class by Responsibility (Recommended)
**Effort**: High | **Impact**: Critical

Break the Route class into focused, single-responsibility classes:

```python
# New focused classes
class RouteHandler:
    """Handles a single HTTP endpoint with one clear purpose."""
    
    def __init__(self, method: str, path: str, handler: Callable):
        self.method = method
        self.path = path
        self.handler = handler
        self.signature = inspect.signature(handler)
        self.response_wrapper = self._analyze_response_type()
    
    async def handle_request(self, request: Request) -> Response:
        """Single responsibility: handle one request."""
        params = await self._extract_parameters(request)
        result = await self.handler(**params)
        return self._wrap_response(result)

class RouteRegistry:
    """Manages collection of route handlers."""
    
    def __init__(self):
        self._routes: dict[str, list[RouteHandler]] = defaultdict(list)
        self._route_tree = self._build_route_tree()
    
    def add_route(self, handler: RouteHandler):
        """Add a route handler to registry."""
        self._routes[handler.method].append(handler)
        self._rebuild_route_tree()
    
    def resolve_route(self, method: str, path: str) -> RouteHandler | None:
        """O(1) route resolution using trie."""
        return self._route_tree.resolve(method, path)

class ParameterInjector:
    """Handles parameter injection from requests."""
    
    def __init__(self, container: Container):
        self.container = container
    
    async def extract_parameters(self, handler_sig: Signature, request: Request) -> dict:
        """Extract and inject parameters for handler."""
        # Focused responsibility for parameter handling
        
class ResponseWrapper:
    """Handles response type inference and wrapping."""
    
    def wrap_response(self, result: Any, wrapper_type: type) -> Response:
        """Convert handler result to Response object."""
        # Focused responsibility for response handling

# New Route class (much simpler)
class Route:
    """Declarative route definition using decorators only."""
    
    @handle.GET
    async def get_users(self, request: GetRequest) -> Annotated[list, JsonResponse]:
        return await self.user_service.get_all()
    
    @handle.POST  
    async def create_user(self, form: UserForm) -> Annotated[dict, JsonResponse]:
        user = await self.user_service.create(form)
        return {"user": user}
```

### Option 2: Use Composition Pattern
**Effort**: Medium | **Impact**: High

Keep Route class but compose it from smaller components:

```python
class Route:
    def __init__(self):
        self.handler_registry = HandlerRegistry()
        self.parameter_injector = ParameterInjector()
        self.response_wrapper = ResponseWrapper()
        self.form_processor = FormProcessor()
        self.error_handler = ErrorHandler()
    
    async def __call__(self, request: Request, **path_params):
        # Delegate to focused components
        handler = self.handler_registry.find_handler(request.method, path_params)
        params = await self.parameter_injector.extract(handler, request)
        result = await handler(**params)
        return self.response_wrapper.wrap(result, handler.response_type)
```

### Option 3: Plugin-Based Route Architecture
**Effort**: Very High | **Impact**: High

Make routing completely pluggable:

```python
class RoutePlugin(Protocol):
    def can_handle(self, request: Request) -> bool: ...
    async def handle(self, request: Request) -> Response: ...

class MethodRoutePlugin(RoutePlugin):
    """Handles HTTP method routing."""
    
class FormRoutePlugin(RoutePlugin):
    """Handles form submissions."""
    
class Route:
    def __init__(self):
        self.plugins: list[RoutePlugin] = [
            MethodRoutePlugin(),
            FormRoutePlugin(),
            ErrorRoutePlugin()
        ]
    
    async def __call__(self, request: Request):
        for plugin in self.plugins:
            if plugin.can_handle(request):
                return await plugin.handle(request)
```

## Action Checklist

### Phase 1: Design New Architecture (Week 1)
- [ ] Design RouteHandler class interface
- [ ] Design RouteRegistry with route tree
- [ ] Design ParameterInjector interface
- [ ] Design ResponseWrapper interface
- [ ] Create migration plan for existing Route classes

### Phase 2: Implement Core Components (Week 2)
- [ ] Implement RouteHandler class
- [ ] Implement O(1) route resolution with trie
- [ ] Implement ParameterInjector
- [ ] Implement ResponseWrapper
- [ ] Create comprehensive tests for each component

### Phase 3: Migrate Route Class (Week 3)
- [ ] Create new simplified Route base class
- [ ] Implement decorator-only route definition
- [ ] Migrate existing routes to new pattern
- [ ] Update documentation and examples

### Phase 4: Performance & Polish (Week 4)
- [ ] Optimize route resolution performance
- [ ] Add caching for parameter analysis
- [ ] Implement benchmarking suite
- [ ] Update CLI to generate new route patterns

### New Architecture Design

**Directory Structure**:
```
serv/routing/
├── __init__.py
├── handler.py          # RouteHandler class
├── registry.py         # RouteRegistry with route tree
├── injection.py        # ParameterInjector
├── responses.py        # ResponseWrapper  
├── forms.py           # FormProcessor
└── errors.py          # ErrorHandler
```

**Simplified Route Definition**:
```python
from serv import Route, handle
from serv.responses import JsonResponse

class UserRoute(Route):
    """Handle user-related endpoints."""
    
    @handle.GET
    async def list_users(self) -> Annotated[list[dict], JsonResponse]:
        """GET /users - List all users."""
        return await self.user_service.get_all()
    
    @handle.POST
    async def create_user(self, form: UserForm) -> Annotated[dict, JsonResponse]:
        """POST /users - Create new user."""
        user = await self.user_service.create(form.dict())
        return {"user": user, "message": "User created successfully"}
    
    @handle.GET("/{user_id}")
    async def get_user(self, user_id: int) -> Annotated[dict, JsonResponse]:
        """GET /users/{id} - Get specific user."""
        user = await self.user_service.get_by_id(user_id)
        return {"user": user}
```

**Route Registration**:
```python
# Automatic registration via decorators
app.add_routes(UserRoute, prefix="/users")

# Or explicit registration
router = Router()
router.add_route("/users", UserRoute)
app.include_router(router)
```

### Performance Improvements

**Route Resolution Optimization**:
```python
class RouteTree:
    """Trie-based route resolution for O(1) lookup."""
    
    def __init__(self):
        self.root = {}
    
    def add_route(self, pattern: str, handler: RouteHandler):
        """Add route to trie."""
        node = self.root
        for segment in pattern.split('/'):
            if segment not in node:
                node[segment] = {}
            node = node[segment]
        node['__handler__'] = handler
    
    def resolve(self, path: str) -> RouteHandler | None:
        """O(1) route resolution."""
        node = self.root
        for segment in path.split('/'):
            if segment in node:
                node = node[segment]
            elif '__param__' in node:
                node = node['__param__']
            else:
                return None
        return node.get('__handler__')
```

### Backwards Compatibility Strategy

1. **Phase 1**: Keep old Route class working alongside new system
2. **Phase 2**: Add deprecation warnings for old patterns
3. **Phase 3**: Provide automated migration tools
4. **Phase 4**: Remove old patterns in next major version

### Testing Strategy

```python
def test_route_handler_isolation():
    """Test that RouteHandler has single responsibility."""
    handler = RouteHandler('GET', '/users', get_users_handler)
    
    # Should only handle request processing
    assert hasattr(handler, 'handle_request')
    assert not hasattr(handler, 'resolve_route')  # Registry responsibility
    assert not hasattr(handler, 'inject_parameters')  # Injector responsibility

def test_route_resolution_performance():
    """Test O(1) route resolution performance."""
    registry = RouteRegistry()
    
    # Add 1000 routes
    for i in range(1000):
        registry.add_route(f'/route{i}', mock_handler)
    
    # Resolution should be constant time
    start = time.time()
    for i in range(100):
        registry.resolve('GET', '/route500')
    duration = time.time() - start
    
    # Should be < 1ms total for 100 resolutions
    assert duration < 0.001
```

### Migration Tools

```python
# CLI command to migrate existing routes
$ serv migrate routes --from=legacy --to=decorators

# Automated code transformation
class LegacyRoute(Route):
    def handle_get(self, request):
        return {"users": []}

# Becomes:
class ModernRoute(Route):
    @handle.GET
    async def list_users(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
        return {"users": []}
```

This refactoring will significantly improve code maintainability, performance, and developer experience while maintaining the framework's powerful routing capabilities.