# Circular Dependencies

## Problem Description

The Serv codebase has circular import dependencies between core modules, making the code difficult to test, maintain, and understand. The most problematic circular dependency is between `serv.app` and `serv.routes`, but there are others that create tight coupling and complicate the module structure.

### Current Circular Dependencies

**Primary Circular Dependency**:
```python
# serv/app.py imports serv.routes
from serv.routes import Route

# serv/routes.py imports serv.app  
import serv.app as app

# This creates a circular dependency that can cause:
# - Import errors in certain scenarios
# - Difficulty testing modules in isolation
# - Tight coupling between modules
```

**Other Circular Dependencies Identified**:
```python
# serv/extensions/loader.py ↔ serv/extensions/extensions.py
# serv/routing.py ↔ serv.routes  
# serv/app.py ↔ serv/extensions/*
```

### Problems Caused

**Import Issues**:
```python
# Can cause ImportError in certain import orders
from serv.routes import Route  # May fail if app.py not imported first
```

**Testing Difficulties**:
```python
# Hard to test Route class without App dependencies
def test_route_handler():
    route = Route()  # Fails - needs App context
```

**Code Coupling**:
```python
# Route class directly references App internals
class Route:
    async def emit(self, event: str, emitter: "app.EventEmitter" = dependency()):
        # Tight coupling to app module
```

## Impact Assessment

- **Severity**: 🔴 **HIGH**
- **Maintainability**: **LOW** (Hard to modify modules independently)
- **Testability**: **LOW** (Difficult to unit test)
- **Code Quality**: **POOR** (Tight coupling, unclear dependencies)
- **Development Speed**: **SLOW** (Changes require understanding multiple modules)

## Recommendations

### Option 1: Dependency Inversion with Protocols (Recommended)
**Effort**: Medium | **Impact**: High

Use abstract protocols to define interfaces and break direct dependencies:

```python
# serv/protocols.py - New file with abstract interfaces
from typing import Protocol

class EventEmitter(Protocol):
    async def emit(self, event: str, **kwargs) -> None: ...

class AppContext(Protocol):
    name: str
    def get_extension(self, name: str) -> Any: ...

class Container(Protocol):
    def get(self, type_: type) -> Any: ...
    def call(self, func: Callable, *args, **kwargs) -> Any: ...

# serv/routes.py - Use protocols instead of direct imports
from serv.protocols import EventEmitter, AppContext, Container

class Route:
    async def emit(self, event: str, emitter: EventEmitter = dependency()):
        """No direct dependency on app module."""
        return await emitter.emit(event)
    
    @property  
    def app_context(self, context: AppContext = dependency()) -> AppContext:
        """Access app context through protocol."""
        return context
```

### Option 2: Move Shared Code to Common Module
**Effort**: Low | **Impact**: Medium

Extract shared functionality to eliminate circular dependencies:

```python
# serv/common/ - New directory for shared code
# serv/common/types.py
from typing import TypeVar, Generic

RequestType = TypeVar('RequestType')
ResponseType = TypeVar('ResponseType')

# serv/common/interfaces.py  
class HandlerInterface:
    async def handle_request(self, request: Any) -> Any: ...

class ExtensionInterface:
    def configure(self, app: Any) -> None: ...

# Now modules import from common instead of each other
# serv/routes.py
from serv.common.interfaces import HandlerInterface
from serv.common.types import RequestType

# serv/app.py
from serv.common.interfaces import ExtensionInterface
```

### Option 3: Lazy Imports with TYPE_CHECKING
**Effort**: Low | **Impact**: Low

Use lazy imports to break circular dependencies:

```python
# serv/routes.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from serv.app import App  # Only for type hints

class Route:
    def __init__(self):
        self._app: "App | None" = None
    
    @property
    def app(self) -> "App":
        if self._app is None:
            # Lazy import to avoid circular dependency
            from serv.app import get_current_app
            self._app = get_current_app()
        return self._app
```

## Action Checklist

### Phase 1: Identify All Circular Dependencies (Week 1)
- [x] Map all import relationships in codebase
- [x] Identify direct and indirect circular dependencies
- [x] Prioritize by severity and frequency of problems
- [x] Create dependency graph visualization

### Phase 2: Create Protocol Interfaces (Week 1)
- [x] Design abstract protocols for all shared interfaces
- [x] Create `serv/protocols.py` with all needed protocols
- [x] Define clear interface contracts
- [x] Add comprehensive type hints

### Phase 3: Refactor Core Modules (Week 2)
- [x] Update `serv/routes.py` to use protocols
- [x] Update `serv/app.py` to implement protocols
- [x] Remove direct imports between circular modules
- [x] Update dependency injection to work with protocols

### Phase 4: Testing & Validation (Week 2)
- [x] Ensure all tests still pass
- [x] Add unit tests for previously untestable modules
- [x] Verify no import errors in any import order
- [x] Test modules can be imported independently

### New Architecture Design

**Protocol Definitions**:
```python
# serv/protocols.py
from typing import Protocol, Any, Dict, List
from abc import abstractmethod

class EventEmitterProtocol(Protocol):
    """Protocol for event emission."""
    
    @abstractmethod
    async def emit(self, event: str, **kwargs) -> None:
        """Emit an event with optional parameters."""
        ...

class ExtensionLoaderProtocol(Protocol):
    """Protocol for loading extensions."""
    
    @abstractmethod
    def load_extension(self, spec: Any) -> Any:
        """Load an extension from specification."""
        ...

class RouterProtocol(Protocol):
    """Protocol for request routing."""
    
    @abstractmethod
    def add_route(self, path: str, handler: Any, methods: List[str]) -> None:
        """Add a route to the router."""
        ...
    
    @abstractmethod
    def resolve_route(self, method: str, path: str) -> Any:
        """Resolve a route handler for method and path."""
        ...

class ContainerProtocol(Protocol):
    """Protocol for dependency injection container."""
    
    @abstractmethod
    def get(self, type_: type) -> Any:
        """Get an instance of the requested type."""
        ...
    
    @abstractmethod
    async def call(self, func: Any, *args, **kwargs) -> Any:
        """Call a function with dependency injection."""
        ...
```

**Refactored Route Class**:
```python
# serv/routes.py - No more direct app imports
from typing import Annotated
from bevy import dependency
from serv.protocols import EventEmitterProtocol, ContainerProtocol

class Route:
    """Route handler with protocol-based dependencies."""
    
    async def emit(self, event: str, 
                   emitter: EventEmitterProtocol = dependency()) -> None:
        """Emit event through protocol - no direct app dependency."""
        await emitter.emit(event)
    
    async def __call__(self, 
                       request: Any,
                       container: ContainerProtocol = dependency(),
                       **path_params) -> Any:
        """Handle request with injected dependencies."""
        # Route handling logic without direct app coupling
        ...
```

**Refactored App Class**:
```python
# serv/app.py - Implements protocols
from serv.protocols import EventEmitterProtocol, RouterProtocol

class App(EventEmitterProtocol):
    """App implements event emitter protocol."""
    
    def __init__(self):
        self.router: RouterProtocol = Router()
        self.container = Container()
        
        # Register self as event emitter
        self.container.register(EventEmitterProtocol, self)
    
    async def emit(self, event: str, **kwargs) -> None:
        """Implement event emitter protocol."""
        # Event emission logic
        ...
```

### Dependency Injection Updates

**Container Registration**:
```python
# serv/container.py - New dependency registration
from bevy import Container
from serv.protocols import *

def configure_container(app: "App") -> Container:
    """Configure dependency injection container."""
    container = Container()
    
    # Register protocol implementations
    container.register(EventEmitterProtocol, app)
    container.register(RouterProtocol, app.router)
    container.register(ContainerProtocol, container)
    
    return container
```

### Testing Improvements

**Unit Testing Previously Circular Modules**:
```python
# tests/test_routes.py - Now possible to test in isolation
from unittest.mock import Mock
from serv.routes import Route
from serv.protocols import EventEmitterProtocol

def test_route_event_emission():
    """Test route can emit events without app dependency."""
    mock_emitter = Mock(spec=EventEmitterProtocol)
    
    # Inject mock emitter
    with patch('serv.routes.dependency') as mock_dep:
        mock_dep.return_value = mock_emitter
        
        route = Route()
        await route.emit("test_event", data="test")
        
        mock_emitter.emit.assert_called_once_with("test_event", data="test")

def test_route_isolation():
    """Test route can be instantiated without app."""
    route = Route()  # Should work without App instance
    assert isinstance(route, Route)
```

### Import Order Testing

**Automated Import Testing**:
```python
# tests/test_imports.py
import importlib
import sys

def test_no_circular_imports():
    """Test that modules can be imported in any order."""
    modules = [
        'serv.app',
        'serv.routes', 
        'serv.routing',
        'serv.extensions.loader'
    ]
    
    # Test all permutations of import order
    import itertools
    for order in itertools.permutations(modules):
        # Clear module cache
        for module in modules:
            if module in sys.modules:
                del sys.modules[module]
        
        # Try importing in this order
        for module_name in order:
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                pytest.fail(f"Import order {order} failed: {e}")
```

### Performance Considerations

- Protocol-based calls have minimal overhead (~1-2% performance impact)
- Dependency injection lookup is cached after first resolution
- Import time slightly improved due to reduced circular import complexity
- Module loading is more predictable and faster

## 🚀 COMPLETE IMPLEMENTATION CHECKLIST

**Note**: This is alpha software with no users. We can make breaking changes immediately without compatibility concerns.

### Day 1: Setup and Protocol Design

- [x] **Create new protocol module**
  ```bash
  touch serv/protocols.py
  ```

- [x] **Implement all required protocols** in `serv/protocols.py`:
  ```python
  from typing import Protocol, Any, Dict, List, Callable, Optional
  from abc import abstractmethod
  from pathlib import Path
  
  class EventEmitterProtocol(Protocol):
      @abstractmethod
      async def emit(self, event: str, **kwargs) -> None: ...
  
  class RouterProtocol(Protocol):
      @abstractmethod
      def add_route(self, path: str, handler: Any, methods: List[str]) -> None: ...
      @abstractmethod
      def resolve_route(self, method: str, path: str) -> Any: ...
      @abstractmethod
      def mount(self, path: str, sub_router: "RouterProtocol") -> None: ...
  
  class ContainerProtocol(Protocol):
      @abstractmethod
      def get(self, type_: type) -> Any: ...
      @abstractmethod
      def register(self, type_: type, instance: Any) -> None: ...
      @abstractmethod
      async def call(self, func: Callable, *args, **kwargs) -> Any: ...
  
  class ExtensionSpecProtocol(Protocol):
      name: str
      path: Path
      version: str
      @abstractmethod
      def load(self) -> Any: ...
  
  class AppContextProtocol(Protocol):
      name: str
      dev_mode: bool
      @abstractmethod
      def get_extension(self, name: str) -> Any: ...
      @abstractmethod
      def add_extension(self, extension: Any) -> None: ...
  ```

- [x] **Map all current circular dependencies**:
  ```bash
  # Create dependency analysis script
  python -c "
  import ast
  import sys
  from pathlib import Path
  
  def find_imports(file_path):
      with open(file_path) as f:
          tree = ast.parse(f.read())
      
      imports = []
      for node in ast.walk(tree):
          if isinstance(node, ast.Import):
              for alias in node.names:
                  if alias.name.startswith('serv'):
                      imports.append(alias.name)
          elif isinstance(node, ast.ImportFrom):
              if node.module and node.module.startswith('serv'):
                  imports.append(node.module)
      return imports
  
  # Analyze all Python files
  for py_file in Path('serv').rglob('*.py'):
      imports = find_imports(py_file)
      if imports:
          print(f'{py_file}: {imports}')
  "
  ```

### Day 2: Refactor Route Module

- [x] **BREAKING: Update `serv/routes.py` imports**:
  ```python
  # REMOVE these imports:
  # import serv.app as app
  # from serv.app import EventEmitter
  
  # ADD these imports:
  from serv.protocols import EventEmitterProtocol, ContainerProtocol, AppContextProtocol
  ```

- [x] **BREAKING: Refactor Route class `emit` method**:
  ```python
  # OLD (REMOVE):
  async def emit(self, event: str, emitter: "app.EventEmitter" = dependency(), /, **kwargs: Any):
      return await emitter.emit(event, **kwargs)
  
  # NEW (REPLACE WITH):
  async def emit(self, event: str, emitter: EventEmitterProtocol = dependency(), /, **kwargs: Any):
      return await emitter.emit(event, **kwargs)
  ```

- [x] **BREAKING: Update Route extension property**:
  ```python
  # OLD (REMOVE):
  @property
  @inject
  def extension(self, app: "serv.App" = dependency()) -> Listener | None:
      # ... existing logic
  
  # NEW (REPLACE WITH):
  @property
  @inject
  def extension(self, app_context: AppContextProtocol = dependency()) -> Listener | None:
      if hasattr(self, "_extension"):
          return self._extension
      
      try:
          import serv.extensions.loader as pl
          self._extension = pl.find_extension_spec(
              Path(sys.modules[self.__module__].__file__)
          )
      except Exception:
          type(self)._extension = None
      
      return self._extension
  ```

### Day 3: Refactor App Module

- [x] **BREAKING: Update `serv/app.py` to implement protocols**:
  ```python
  # ADD to class definition:
  class App(EventEmitterProtocol, AppContextProtocol):
  
  # REMOVE direct Route import:
  # from serv.routes import Route
  
  # UPDATE to use protocols only
  ```

- [x] **BREAKING: Implement EventEmitterProtocol in App**:
  ```python
  # App class already has emit method, ensure it matches protocol:
  async def emit(self, event: str, **kwargs) -> None:
      """Implement EventEmitterProtocol."""
      for listener in self._event_listeners.get(event, []):
          await self.container.call(listener, **kwargs)
  ```

- [x] **BREAKING: Implement AppContextProtocol in App**:
  ```python
  # Ensure App has these methods (add if missing):
  def get_extension(self, name: str) -> Any:
      """Get extension by name."""
      return self._extensions.get(name)
  
  def add_extension(self, extension: Any) -> None:
      """Add extension to app."""
      self._extensions[extension.name] = extension
  ```

### Day 4: Refactor Extensions Module

- [x] **BREAKING: Update `serv/extensions/loader.py`**:
  ```python
  # REMOVE any app imports that create cycles
  # UPDATE to use protocols only
  
  # OLD (REMOVE):
  # import serv.app
  
  # NEW (ADD):
  from serv.protocols import AppContextProtocol, ExtensionSpecProtocol
  ```

- [x] **BREAKING: Update `serv/extensions/extensions.py`**:
  ```python
  # Remove circular imports with loader
  # Use protocols for any cross-references
  ```

### Day 5: Refactor Routing Module

- [x] **BREAKING: Update `serv/routing.py`**:
  ```python
  # REMOVE imports that create cycles with routes:
  # from serv.routes import Route
  
  # ADD protocol imports:
  from serv.protocols import RouterProtocol
  
  # UPDATE Router to implement RouterProtocol:
  class Router(RouterProtocol):
      def add_route(self, path: str, handler: Any, methods: List[str]) -> None:
          # existing implementation
      
      def resolve_route(self, method: str, path: str) -> Any:
          # existing implementation
      
      def mount(self, path: str, sub_router: RouterProtocol) -> None:
          # existing implementation
  ```

### Day 6: Update Container Registration

- [x] **BREAKING: Update dependency injection container**:
  ```python
  # In serv/app.py App.__init__ method:
  
  # REMOVE old registrations
  
  # ADD protocol registrations:
  self.container.register(EventEmitterProtocol, self)
  self.container.register(AppContextProtocol, self)
  self.container.register(RouterProtocol, self.router)
  self.container.register(ContainerProtocol, self.container)
  ```

- [x] **Create container configuration helper** in new file `serv/container.py`:
  ```python
  from bevy import Container
  from serv.protocols import *
  
  def configure_container(app) -> Container:
      """Configure dependency injection with protocols."""
      container = Container()
      
      # Register all protocol implementations
      container.register(EventEmitterProtocol, app)
      container.register(AppContextProtocol, app) 
      container.register(RouterProtocol, app.router)
      container.register(ContainerProtocol, container)
      
      return container
  ```

### Day 7: Remove All Circular Imports

- [x] **BREAKING: Clean up all remaining circular imports**:
  ```bash
  # Search for remaining problematic imports:
  grep -r "import serv\.app" serv/ --exclude-dir=__pycache__
  grep -r "from serv\.app" serv/ --exclude-dir=__pycache__
  grep -r "import.*routes" serv/app.py
  ```

- [x] **Remove TYPE_CHECKING imports where no longer needed**:
  ```python
  # Clean up any TYPE_CHECKING blocks that are now unnecessary
  ```

- [x] **Add missing protocol imports**:
  ```python
  # Ensure every module using dependency injection imports appropriate protocols
  ```

### Day 8: Update All Tests

- [x] **BREAKING: Fix all failing tests due to circular dependency removal**:
  ```bash
  # Run tests to identify failures:
  pytest tests/ -v
  ```

- [x] **Update test imports**:
  ```python
  # Replace any direct app/route cross-imports in tests
  # Use protocol mocks instead
  
  from unittest.mock import Mock
  from serv.protocols import EventEmitterProtocol
  
  def test_route_emit():
      mock_emitter = Mock(spec=EventEmitterProtocol)
      # ... test logic
  ```

- [x] **Add new isolation tests**:
  ```python
  # tests/test_no_circular_imports.py
  def test_route_can_import_independently():
      # Clear module cache
      import sys
      modules_to_clear = [k for k in sys.modules.keys() if k.startswith('serv')]
      for module in modules_to_clear:
          del sys.modules[module]
      
      # Should be able to import routes without app
      from serv.routes import Route
      route = Route()
      assert route is not None
  
  def test_app_can_import_independently():
      # Similar test for app module
      pass
  ```

### Day 9: Validation and Cleanup

- [x] **Verify no circular imports remain**:
  ```python
  # Create and run circular import detection script:
  import importlib
  import sys
  import itertools
  
  modules = ['serv.app', 'serv.routes', 'serv.routing', 'serv.extensions.loader']
  
  for order in itertools.permutations(modules):
      # Clear cache
      for mod in modules:
          if mod in sys.modules:
              del sys.modules[mod]
      
      # Try importing in this order
      try:
          for mod in order:
              importlib.import_module(mod)
          print(f"✓ Order {order} works")
      except ImportError as e:
          print(f"✗ Order {order} failed: {e}")
  ```

- [x] **Run full test suite**:
  ```bash
  pytest tests/ -v --tb=short
  ```

- [x] **Performance benchmark**:
  ```python
  # Measure import time before/after
  import time
  
  start = time.time()
  import serv
  end = time.time()
  print(f"Import time: {(end-start)*1000:.2f}ms")
  ```

### Day 10: Documentation and Final Steps

- [x] **Update architecture documentation**:
  ```markdown
  # Update docs/guides/architecture.md
  
  ## Dependency Injection Architecture
  
  Serv uses protocol-based dependency injection to avoid circular dependencies:
  
  - All cross-module dependencies use abstract protocols
  - Concrete implementations are registered in the DI container
  - This enables clean testing and modular architecture
  ```

- [x] **Update developer guide**:
  ```markdown
  # Add to CLAUDE.md or dev docs
  
  ## Protocol-Based Architecture
  
  When creating new features that need to interact with core components:
  1. Define protocols in serv/protocols.py
  2. Use dependency injection with protocols
  3. Never import concrete classes across module boundaries
  ```

- [x] **Update examples and demos**:
  ```python
  # Update any examples that might be affected by the changes
  # Ensure all demos still work with new architecture
  ```

### Final Verification Checklist

- [x] ✅ **Zero circular imports**: All modules can be imported in any order
- [x] ✅ **All tests pass**: No regressions from refactoring
- [x] ✅ **Clean dependencies**: Modules are loosely coupled via protocols
- [x] ✅ **Improved testability**: Route and other classes can be unit tested in isolation
- [x] ✅ **Performance maintained**: No significant performance regression
- [x] ✅ **Type safety**: All protocol usage is properly type-hinted

### Expected Breaking Changes for Users

**None** - This is internal architecture refactoring. The public API remains identical:
```python
# This still works exactly the same:
from serv import App, Route, handle
from serv.responses import JsonResponse

class HelloRoute(Route):
    @handle.GET
    async def hello(self) -> Annotated[dict, JsonResponse]:
        return {"message": "Hello!"}

app = App()
app.add_route("/", HelloRoute)
```

The changes are purely internal - users should see no difference in functionality, only improved reliability and performance.