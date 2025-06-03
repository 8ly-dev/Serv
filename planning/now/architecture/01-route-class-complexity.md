# Route Class Complexity

## Problem Description

The Route class in `serv/routes.py` has become a monolithic class trying to handle too many responsibilities. It manages HTTP method routing, form handling, error handling, response type inference, parameter injection, and handler discovery - violating the Single Responsibility Principle and creating maintenance nightmares.

### Current Complexity Analysis

**File**: `serv/routes.py` (1100 lines - VALIDATED 2025)

**Multiple Responsibilities**:
1. **HTTP Method Routing**: Discovering and calling handle_* methods
2. **Form Handling**: Processing form data and matching to Form classes
3. **Error Handling**: Managing exception handlers 
4. **Response Type Inference**: Analyzing annotations to wrap responses
5. **Parameter Injection**: Extracting and injecting headers, cookies, queries
6. **Handler Selection**: Complex algorithm to choose best handler match
7. **Signature Analysis**: Introspecting method signatures for routing

### Code Complexity Indicators

**Handler Discovery Mechanisms** (CURRENT STATE - 2025):
```python
# 1. Decorator-based handlers (@handle decorator) - PRIMARY METHOD
@handle.GET
def get_users(self): pass

# 2. Form handlers using decorators + type signatures (MODERN)
@handle.POST
def submit_form(self, form: UserForm): pass

# 3. Error handlers via type signatures (naming convention)
def handle_error(self, error: ValueError): pass

# 4. Multiple handlers per method with signature scoring
@handle.GET
def get_by_id(self, user_id: Annotated[str, Query("id")]): pass
@handle.GET  
def get_all(self): pass  # Fallback handler

# LEGACY ISSUES:
# - Form.__form_method__ still exists but should be removed
# - Route.__form_handlers__ indexed by HTTP method (legacy)
# - Documentation shows handle_ naming but code doesn't support it
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

- **Severity**: 🔴 **CRITICAL** (CONFIRMED 2025)
- **Maintainability**: **VERY LOW** (Hard to modify without breaking)
- **Testability**: **LOW** (Complex interactions, many code paths)
- **Performance**: **POOR** (O(n) handler selection, repeated analysis)
- **Developer Experience**: **POOR** (Hard to understand, multiple patterns)
- **Current Status**: **ACTIVELY PROBLEMATIC** (Recent Bevy update shows integration complexity)

### Recent Evidence (2025)
- **Documentation Inconsistency**: `handle_` examples in docs but no code support (misleading)
- **Form Handling Inconsistency**: Tests use `@handle.POST` + form params, but Route class still has `Form.__form_method__` logic
- **Bevy Integration**: Recent updates to `@injectable` and `Inject` show DI complexity
- **Handler Selection**: Multi-handler selection logic still causes performance issues  
- **Signature Analysis**: Parameter extraction complexity increased with new DI patterns
- **Error Handling**: Complex error path through `_error_handler` with container.call recursion
- **Mixed Patterns**: Modern usage is decorator-only, but legacy form indexing remains in code

## Solution: Split Route Class by Responsibility

### Current Framework Context
- **Ommi ORM Integration**: New database requirements affect route complexity
- **Bevy 3.1 DI**: Enhanced dependency injection capabilities (but adds Route complexity)
- **Extension System**: Mature extension architecture
- **Performance Focus**: Production usage reveals performance bottlenecks
- **Breaking Changes**: Recent Bevy updates required Route class modifications
- **Maintenance Burden**: Complex Route class slows down framework development

### Option 1: Split Route Class by Responsibility (RECOMMENDED)
**Effort**: High | **Impact**: Critical | **Priority**: HIGH

Break the Route class into focused, single-responsibility classes with modern DI integration:

```python
# New focused classes
class RouteHandler:
    """Handles a single HTTP endpoint with one clear purpose."""
    
    def __init__(self, method: str, path: str, handler: Callable, container: Container):
        self.method = method
        self.path = path
        self.handler = handler
        self.container = container
        self.signature = inspect.signature(handler)
        self.response_wrapper = self._analyze_response_type()
        self.param_injector = ParameterInjector(container)
    
    async def handle_request(self, request: Request, **path_params) -> Response:
        """Single responsibility: handle one request with modern DI."""
        params = await self.param_injector.extract_parameters(
            self.signature, request, path_params
        )
        result = await self.container.call(self.handler, **params)
        return self.response_wrapper.wrap_response(result)

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
    """Handles parameter injection from requests with Bevy 3.1 support."""
    
    def __init__(self, container: Container):
        self.container = container
    
    async def extract_parameters(
        self, 
        handler_sig: Signature, 
        request: Request, 
        path_params: dict,
        form_data: dict | None = None
    ) -> dict:
        """Extract and inject parameters using modern DI patterns."""
        # Simplified, focused parameter extraction
        # Support for Header, Cookie, Query, Path, Form, and Container injection
        # Uses Bevy 3.1 qualifiers for complex injection scenarios
        
class ResponseWrapper:
    """Handles response type inference and wrapping."""
    
    def wrap_response(self, result: Any, wrapper_type: type) -> Response:
        """Convert handler result to Response object."""
        # Focused responsibility for response handling

# New Route class (much simpler)
class Route:
    """Declarative route definition using @handles decorator only."""
    
    @handles.GET
    async def get_users(
        self, 
        request: GetRequest,
        db: Ommi = dependency(qualifier="primary")
    ) -> Annotated[list[dict], JsonResponse]:
        users = await db.find(User).all()
        return [user.dict() for user in users]
    
    @handles.POST  
    async def create_user(
        self, 
        form: UserForm,
        db: Ommi = dependency(qualifier="primary")
    ) -> Annotated[dict, JsonResponse]:
        user = await db.create(User(**form.dict()))
        return {"user": user.dict(), "message": "User created"}
```


## Action Checklist

### Phase 0: Clean Up Legacy Code (Week 1) - NEW PRIORITY
- [ ] Remove `Form.__form_method__` attribute (not used in modern pattern)
- [ ] Remove `__form_handlers__` HTTP method indexing
- [ ] Unify form handling to use only `@handle.POST` + type signatures
- [ ] Remove misleading `handle_` examples from Route docstring
- [ ] Update all examples to show correct `@handle` decorator usage
- [ ] Remove unused legacy form processing logic in `_handle_request`

### Phase 1: Design Architecture (Week 1)
- [ ] Design RouteHandler class with Ommi/Bevy 3.1 integration
- [ ] Design RouteRegistry with O(1) route tree resolution
- [ ] Design ParameterInjector with qualifier support
- [ ] Design ResponseWrapper with modern response types
- [ ] Create migration plan for existing Route classes
- [ ] Design integration with existing extension system
- [ ] Plan database integration with new routing architecture

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
# Simple registration
app.add_routes(UserRoute, prefix="/users")
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


## Conclusion

**VERDICT: KEEP AND UPDATE** - This document remains highly relevant and accurately describes current critical issues.

### Key Findings
- Route class complexity has **increased** since original analysis
- **Multiple inconsistencies found**:
  - `handle_` methods shown in examples but not supported in code
  - `Form.__form_method__` still exists but modern pattern uses `@handle.POST`
  - Legacy form indexing by HTTP method vs modern decorator approach
- Only `@handle` decorators actually work for HTTP methods
- Recent Bevy integration changes demonstrate the maintenance burden
- File size remains exactly at predicted ~1100 lines
- Signature analysis and handler selection complexity still critical issues
- New DI patterns (`@injectable`, `Inject`) add more complexity
- **Code-usage mismatch**: Tests/examples use modern patterns, implementation has legacy code

### Immediate Actions Needed
1. **Fix documentation inconsistency** - Remove misleading `handle_` examples from docstrings
2. **Remove legacy form logic** - Remove `Form.__form_method__` and HTTP method indexing for forms
3. **Unify form handling** - Forms should only use `@handle.POST` + type signatures, not separate logic paths
4. **Prioritize Route refactoring** - This is blocking framework development
5. **Update examples** to show only `@handle` decorator patterns
6. **Plan migration strategy** for existing Route classes
7. **Consider performance impact** of current O(n) handler selection

### Updated Timeline
Given framework maturity and production usage:
- **Phase 1 (Design)**: 2 weeks (higher complexity than originally estimated)
- **Phase 2 (Implementation)**: 3 weeks (integration with Ommi/Bevy 3.1)
- **Phase 3 (Migration)**: 2 weeks (existing codebase migration)
- **Phase 4 (Performance)**: 1 week (benchmarking and optimization)

This refactoring will significantly improve code maintainability, performance, and developer experience while maintaining the framework's powerful routing capabilities. **The need for this refactoring has become more urgent, not less.**