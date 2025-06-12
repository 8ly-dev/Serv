# Migration Strategy

## Overview

This document outlines the step-by-step approach to refactoring the routing code without breaking existing functionality. The strategy prioritizes backward compatibility and incremental changes.

## Migration Principles

1. **Backward Compatibility First**: All public APIs must continue to work
2. **Incremental Changes**: Small, testable steps rather than big-bang refactoring  
3. **Test-Driven**: All changes must pass existing tests
4. **Import Preservation**: Existing import statements must continue to work
5. **Performance Neutral**: No performance regressions during migration

## Phase 1: Foundation Setup (1-2 days)

### Step 1.1: Create New Package Structure
Create the new directory structure without moving code yet:

```bash
mkdir -p serv/http serv/routing serv/app serv/di
touch serv/http/__init__.py serv/routing/__init__.py serv/app/__init__.py serv/di/__init__.py
```

### Step 1.2: Set Up Import Compatibility Layer
Create `__init__.py` files that re-export everything from current modules:

```python
# serv/http/__init__.py
# Re-export from current locations for backward compatibility
from ..requests import *
from ..responses import *

# serv/routing/__init__.py  
from ..routing import Router
from ..routes import Route, handles

# serv/app/__init__.py
from ..app import App
```

### Step 1.3: Update Tests to Use New Import Paths (Optional)
Start using new import paths in tests to validate the structure:

```python
# Instead of: from serv.routes import Route
# Use: from serv.routing import Route
```

**Validation:**
- [ ] All existing tests pass
- [ ] New import paths work
- [ ] Old import paths still work

## Phase 2: HTTP Layer Extraction (2-3 days)

### Step 2.1: Extract Request Classes
Move request-related classes from `routes.py` to `http/requests.py`:

**Target Classes:**
- `GetRequest`, `PostRequest`, `PutRequest`, etc.
- Request parameter parsing logic
- Query string handling utilities

**Process:**
1. Copy classes to `serv/http/requests.py`
2. Update imports in `serv/http/__init__.py`
3. Add backward compatibility imports to `serv/routes.py`
4. Run tests to validate

### Step 2.2: Extract Response Classes  
Move response-related classes to `http/responses.py`:

**Target Classes:**
- Response builders and types
- Status code utilities
- Content type handling

### Step 2.3: Extract Form Processing
Move form-related code to `http/forms.py`:

**Target Functionality:**
- Form data parsing
- Multipart handling
- File upload processing
- Form validation logic

### Step 2.4: Extract HTTP Validation
Move validation logic to `http/validation.py`:

**Target Functionality:**
- Parameter coercion
- Type validation
- Request validation utilities

**Validation:**
- [ ] All HTTP-related functionality works
- [ ] Form processing works correctly
- [ ] File uploads work
- [ ] All existing tests pass

## Phase 3: Routing Layer Refactoring (3-4 days)

### Step 3.1: Extract URL Pattern Logic
Move pattern-related code from `routing.py` to `routing/patterns.py`:

**Target Functionality:**  
- URL pattern compilation
- Path matching algorithms
- Parameter extraction logic

### Step 3.2: Extract Route Resolution
Move resolution logic to `routing/resolver.py`:

**Target Functionality:**
- Route resolution algorithms
- Method matching logic
- Parameter binding

### Step 3.3: Extract WebSocket Routing
Move WebSocket code to `routing/websockets.py`:

**Target Functionality:**
- WebSocket route matching
- WebSocket path resolution
- WebSocket-specific logic

### Step 3.4: Extract Route Handlers
Move Route class and decorators to `routing/handlers.py`:

**Target Classes:**
- `Route` base class
- `@handles` decorators
- Method selection logic
- Handler signature inspection

### Step 3.5: Create Route Registry
Create `routing/registry.py` for route storage:

**Target Functionality:**
- Route storage and organization
- Route lookup utilities
- Registry management

### Step 3.6: Slim Down Core Router
Keep only core functionality in `routing/router.py`:

**Remaining Functionality:**
- Route registration API
- Sub-router mounting
- Public interface methods

**Validation:**
- [ ] All routing functionality works
- [ ] URL generation works
- [ ] Sub-router mounting works
- [ ] WebSocket routing works
- [ ] All existing tests pass

## Phase 4: Application Layer Restructuring (2-3 days)

### Step 4.1: Extract Middleware Management
Move middleware logic to `app/middleware.py`:

**Target Functionality:**
- Middleware stack management
- Middleware execution order
- Built-in middleware classes

### Step 4.2: Extract Extension System
Move extension logic to `app/extensions.py`:

**Target Functionality:**
- Extension loading and coordination
- Extension event management
- Configuration integration

### Step 4.3: Extract Lifecycle Management
Move lifecycle logic to `app/lifecycle.py`:

**Target Functionality:**
- Request lifecycle events
- Context management
- Event emission and handling

### Step 4.4: Create Core App Class
Slim down `app/core.py` to essentials:

**Remaining Functionality:**
- ASGI implementation
- Core request handling
- Basic App interface

**Validation:**
- [ ] ASGI interface works
- [ ] Middleware stack works
- [ ] Extension system works
- [ ] Request lifecycle works
- [ ] All existing tests pass

## Phase 5: Dependency Injection Extraction (1-2 days)

### Step 5.1: Extract Injection Logic
Move DI logic to `di/injection.py`:

**Target Functionality:**
- Parameter injection logic
- Dependency resolution
- Container integration

### Step 5.2: Extract Container Management
Create `di/containers.py`:

**Target Functionality:**
- Request-scoped containers
- Container lifecycle
- Container utilities

**Validation:**
- [ ] Dependency injection works
- [ ] Request scoping works
- [ ] All existing tests pass

## Phase 6: Cleanup and Optimization (1-2 days)

### Step 6.1: Remove Backward Compatibility Shims
After validation, remove temporary compatibility imports:

**Process:**
1. Identify all backward compatibility imports
2. Update any remaining internal usage
3. Remove shim imports
4. Update documentation

### Step 6.2: Optimize Imports
Clean up import statements throughout the codebase:

**Tasks:**
- Remove unused imports
- Optimize import order
- Use relative imports within packages
- Minimize circular dependencies

### Step 6.3: Add Type Hints
Improve type hints in the new modules:

**Focus Areas:**
- Public API methods
- Inter-module interfaces
- Complex data structures

### Step 6.4: Update Documentation
Update documentation to reflect new structure:

**Documentation Updates:**
- Module documentation
- API reference updates
- Usage examples
- Migration guide for users

**Validation:**
- [ ] All tests pass
- [ ] Performance is maintained
- [ ] Documentation is updated
- [ ] Type checking passes

## Risk Mitigation

### Testing Strategy
- **Continuous Testing**: Run full test suite after each step
- **Integration Testing**: Focus on inter-module communication
- **Performance Testing**: Monitor performance throughout migration
- **Manual Testing**: Test demo applications

### Rollback Plan
- **Git Branches**: Each phase in separate branch
- **Incremental Commits**: Small, atomic commits
- **Tagged Releases**: Tag stable points for rollback
- **Feature Flags**: If needed, use feature flags for gradual rollout

### Communication
- **Progress Tracking**: Update checklist in planning documents
- **Issue Documentation**: Document any problems encountered
- **Decision Log**: Record architectural decisions made during migration

## Success Metrics

### Code Quality Metrics
- [ ] No file over 500 lines
- [ ] Clear module boundaries
- [ ] Reduced cyclomatic complexity
- [ ] Improved test coverage

### Performance Metrics
- [ ] No regression in route resolution time
- [ ] No regression in request handling throughput
- [ ] Memory usage maintained or improved
- [ ] Import time maintained or improved

### Maintainability Metrics
- [ ] Easier to add new features
- [ ] Clearer debugging experience
- [ ] Better IDE support
- [ ] Reduced merge conflicts

## Timeline Estimate

| Phase | Duration | Description |
|-------|----------|-------------|
| Phase 1 | 1-2 days | Foundation setup |
| Phase 2 | 2-3 days | HTTP layer extraction |
| Phase 3 | 3-4 days | Routing layer refactoring |
| Phase 4 | 2-3 days | Application layer restructuring |
| Phase 5 | 1-2 days | Dependency injection extraction |
| Phase 6 | 1-2 days | Cleanup and optimization |
| **Total** | **10-16 days** | **Complete refactoring** |

## Dependencies and Blockers

### External Dependencies
- No external dependencies required
- All changes are internal reorganization

### Potential Blockers
- **Circular Dependencies**: May need to refactor some interfaces
- **Extension System**: Extension compatibility might need attention
- **Performance Regression**: May need optimization work
- **Test Failures**: Some tests might need updates

### Mitigation Strategies
- **Early Detection**: Run tests continuously
- **Incremental Approach**: Small steps allow easier troubleshooting
- **Rollback Options**: Each phase can be rolled back independently
- **Documentation**: Keep detailed notes on changes made