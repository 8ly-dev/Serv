# Implementation Checklist

This document provides a detailed, actionable checklist for implementing the routing refactoring. Each task should be completed and validated before moving to the next.

## Pre-Migration Setup

### Environment Preparation
- [ ] Create feature branch: `git checkout -b routing-refactor`
- [ ] Document current test coverage: `uv run pytest --cov=serv --cov-report=term`
- [ ] Run full test suite and record baseline: `uv run pytest tests/`
- [ ] Benchmark current performance (route resolution, request processing)
- [ ] Document current import patterns used in demos/extensions

### Code Analysis
- [ ] Review all imports of `serv.routing`, `serv.routes`, `serv.app` across codebase
- [ ] Identify all public APIs that must be preserved
- [ ] Document extension system integration points
- [ ] List all demos/examples that must continue working

## Phase 1: Foundation Setup ⏱️ 1-2 days

### Directory Structure Creation
- [ ] Create `serv/http/` directory
- [ ] Create `serv/http/__init__.py`
- [ ] Create `serv/routing/` directory (populate existing empty dir)
- [ ] Create `serv/routing/__init__.py`
- [ ] Create `serv/app/` directory
- [ ] Create `serv/app/__init__.py`
- [ ] Create `serv/di/` directory
- [ ] Create `serv/di/__init__.py`

### Import Compatibility Layer
- [ ] Set up `serv/http/__init__.py` with re-exports from current modules
- [ ] Set up `serv/routing/__init__.py` with re-exports from current modules
- [ ] Set up `serv/app/__init__.py` with re-exports from current modules
- [ ] Test new import paths work: `from serv.http import GetRequest`
- [ ] Test old import paths still work: `from serv.requests import GetRequest`

### Validation
- [ ] Run full test suite: `uv run pytest tests/`
- [ ] Run linting: `uv run ruff check`
- [ ] Run formatting: `uv run ruff format`
- [ ] Test demo applications still work
- [ ] Commit checkpoint: "Phase 1: Foundation setup complete"

## Phase 2: HTTP Layer Extraction ⏱️ 2-3 days

### Step 2.1: Extract Request Classes
- [ ] Create `serv/http/requests.py`
- [ ] Copy `GetRequest`, `PostRequest`, etc. from `routes.py` to `http/requests.py`
- [ ] Copy request parameter parsing utilities
- [ ] Copy query string handling functions
- [ ] Update `serv/http/__init__.py` to export from `requests.py`
- [ ] Add backward compatibility imports to `serv/routes.py`
- [ ] Test: `uv run pytest tests/test_*request*.py`

### Step 2.2: Extract Response Classes
- [ ] Create `serv/http/responses.py`
- [ ] Move response builders from current modules to `http/responses.py`
- [ ] Move status code utilities
- [ ] Move content type handling
- [ ] Update `serv/http/__init__.py` to export from `responses.py`
- [ ] Add backward compatibility imports
- [ ] Test: `uv run pytest tests/test_*response*.py`

### Step 2.3: Extract Form Processing
- [ ] Create `serv/http/forms.py`
- [ ] Move form data parsing logic from `routes.py`
- [ ] Move multipart handling code
- [ ] Move file upload processing
- [ ] Update imports and backward compatibility
- [ ] Test: `uv run pytest tests/test_*form*.py tests/test_*multipart*.py`

### Step 2.4: Extract HTTP Validation
- [ ] Create `serv/http/validation.py`
- [ ] Move parameter coercion logic
- [ ] Move type validation utilities
- [ ] Move request validation functions
- [ ] Update imports and backward compatibility
- [ ] Test: `uv run pytest tests/test_*validation*.py`

### Step 2.5: Create HTTP Middleware Utilities
- [ ] Create `serv/http/middleware.py`
- [ ] Move HTTP-specific middleware utilities
- [ ] Move request/response processing helpers
- [ ] Update imports and backward compatibility
- [ ] Test: `uv run pytest tests/test_*middleware*.py`

### Validation
- [ ] Run full test suite: `uv run pytest tests/`
- [ ] Test form submissions work in demos
- [ ] Test file uploads work
- [ ] Test request/response processing works
- [ ] Run performance benchmark (should be same as baseline)
- [ ] Commit checkpoint: "Phase 2: HTTP layer extraction complete"

## Phase 3: Routing Layer Refactoring ⏱️ 3-4 days

### Step 3.1: Extract URL Pattern Logic
- [ ] Create `serv/routing/patterns.py`
- [ ] Move URL pattern compilation from `routing.py`
- [ ] Move path matching algorithms
- [ ] Move parameter extraction logic
- [ ] Update imports in `routing.py`
- [ ] Test: `uv run pytest tests/test_*routing*.py -k pattern`

### Step 3.2: Extract Route Resolution
- [ ] Create `serv/routing/resolver.py`
- [ ] Move route resolution algorithms from `routing.py`
- [ ] Move method matching logic
- [ ] Move parameter binding code
- [ ] Update imports in `routing.py`
- [ ] Test: `uv run pytest tests/test_*routing*.py -k resolve`

### Step 3.3: Extract WebSocket Routing
- [ ] Create `serv/routing/websockets.py`
- [ ] Move WebSocket route matching from `routing.py`
- [ ] Move WebSocket path resolution
- [ ] Move WebSocket-specific utilities
- [ ] Update imports in `routing.py`
- [ ] Test: `uv run pytest tests/test_*websocket*.py`

### Step 3.4: Extract Route Handlers
- [ ] Create `serv/routing/handlers.py`
- [ ] Move `Route` base class from `routes.py`
- [ ] Move `@handles` decorators
- [ ] Move method selection logic
- [ ] Move handler signature inspection
- [ ] Update `serv/routing/__init__.py` exports
- [ ] Add backward compatibility to `serv/routes.py`
- [ ] Test: `uv run pytest tests/test_*route*.py`

### Step 3.5: Create Route Registry
- [ ] Create `serv/routing/registry.py`
- [ ] Extract route storage logic from `routing.py`
- [ ] Add route lookup utilities
- [ ] Add registry management functions
- [ ] Update `Router` class to use registry
- [ ] Test: `uv run pytest tests/test_*routing*.py -k registry`

### Step 3.6: Slim Down Core Router
- [ ] Refactor `serv/routing/router.py` to use extracted modules
- [ ] Keep only: route registration API, sub-router mounting, public interface
- [ ] Remove extracted functionality
- [ ] Update imports to use new modules
- [ ] Update `serv/routing/__init__.py` exports
- [ ] Test: `uv run pytest tests/test_*routing*.py`

### Validation
- [ ] Run full test suite: `uv run pytest tests/`
- [ ] Test URL generation: `router.url_for()`
- [ ] Test sub-router mounting works
- [ ] Test WebSocket routing works
- [ ] Test route resolution performance (should match baseline)
- [ ] Test demo applications with complex routing
- [ ] Commit checkpoint: "Phase 3: Routing layer refactoring complete"

## Phase 4: Application Layer Restructuring ⏱️ 2-3 days

### Step 4.1: Extract Middleware Management
- [ ] Create `serv/app/middleware.py`
- [ ] Move middleware stack management from `app.py`
- [ ] Move middleware execution order logic
- [ ] Move built-in middleware classes
- [ ] Update `App` class to use middleware module
- [ ] Test: `uv run pytest tests/test_*middleware*.py`

### Step 4.2: Extract Extension System
- [ ] Create `serv/app/extensions.py`
- [ ] Move extension loading logic from `app.py`
- [ ] Move extension coordination code
- [ ] Move configuration integration
- [ ] Update `App` class to use extensions module
- [ ] Test: `uv run pytest tests/test_*extension*.py`

### Step 4.3: Extract Lifecycle Management
- [ ] Create `serv/app/lifecycle.py`
- [ ] Move request lifecycle events from `app.py`
- [ ] Move context management code
- [ ] Move event emission and handling
- [ ] Update `App` class to use lifecycle module
- [ ] Test: `uv run pytest tests/test_*lifespan*.py tests/test_*event*.py`

### Step 4.4: Create Core App Class
- [ ] Create `serv/app/core.py`
- [ ] Move core `App` class (ASGI implementation only)
- [ ] Keep only: ASGI interface, basic request handling
- [ ] Remove extracted functionality
- [ ] Update `serv/app/__init__.py` to export from `core.py`
- [ ] Add backward compatibility to `serv/app.py`
- [ ] Test: `uv run pytest tests/test_*app*.py`

### Step 4.5: Create App Factory
- [ ] Create `serv/app/factory.py`
- [ ] Move app creation utilities
- [ ] Move configuration handling
- [ ] Add builder pattern utilities
- [ ] Test: `uv run pytest tests/test_*factory*.py`

### Validation
- [ ] Run full test suite: `uv run pytest tests/`
- [ ] Test ASGI interface works
- [ ] Test middleware stack works
- [ ] Test extension system works
- [ ] Test request lifecycle works
- [ ] Test all demo applications
- [ ] Run performance benchmark
- [ ] Commit checkpoint: "Phase 4: Application layer restructuring complete"

## Phase 5: Dependency Injection Extraction ⏱️ 1-2 days

### Step 5.1: Extract Injection Logic
- [ ] Create `serv/di/injection.py`
- [ ] Move parameter injection logic from `routes.py`
- [ ] Move dependency resolution code
- [ ] Move container integration utilities
- [ ] Update route handlers to use DI module
- [ ] Test: `uv run pytest tests/test_*injection*.py`

### Step 5.2: Extract Container Management
- [ ] Create `serv/di/containers.py`
- [ ] Move request-scoped container logic
- [ ] Move container lifecycle management
- [ ] Move container utilities
- [ ] Update app to use container module
- [ ] Test: `uv run pytest tests/test_*container*.py`

### Step 5.3: Create Dependency Resolvers
- [ ] Create `serv/di/resolvers.py`
- [ ] Move dependency resolution strategies
- [ ] Add resolver utilities
- [ ] Update DI system to use resolvers
- [ ] Test: `uv run pytest tests/test_*resolver*.py`

### Validation
- [ ] Run full test suite: `uv run pytest tests/`
- [ ] Test dependency injection works in routes
- [ ] Test request scoping works
- [ ] Test container lifecycle
- [ ] Test demo applications with DI
- [ ] Commit checkpoint: "Phase 5: Dependency injection extraction complete"

## Phase 6: Cleanup and Optimization ⏱️ 1-2 days

### Step 6.1: Remove Backward Compatibility Shims
- [ ] Identify all temporary compatibility imports
- [ ] Update internal usage to use new modules
- [ ] Remove backward compatibility imports from old modules
- [ ] Update any remaining demo/test imports
- [ ] Test: `uv run pytest tests/`

### Step 6.2: Optimize Imports
- [ ] Remove unused imports throughout codebase
- [ ] Optimize import order (stdlib, third-party, local)
- [ ] Use relative imports within packages
- [ ] Minimize circular dependencies
- [ ] Run: `uv run ruff check --select I`

### Step 6.3: Add Type Hints
- [ ] Add type hints to public API methods
- [ ] Add type hints to inter-module interfaces
- [ ] Add type hints to complex data structures
- [ ] Run: `uv run mypy serv/` (if mypy configured)

### Step 6.4: Update Documentation
- [ ] Update module docstrings
- [ ] Update API reference documentation
- [ ] Update usage examples in docs
- [ ] Create migration guide for users
- [ ] Update CLAUDE.md with new structure

### Step 6.5: Performance Optimization
- [ ] Profile import times: `python -X importtime -c "import serv"`
- [ ] Optimize hot paths identified in profiling
- [ ] Add caching where appropriate
- [ ] Benchmark and compare to baseline

### Final Validation
- [ ] Run full test suite: `uv run pytest tests/`
- [ ] Run end-to-end tests: `uv run pytest tests/e2e/`
- [ ] Run linting: `uv run ruff check`
- [ ] Run formatting: `uv run ruff format`
- [ ] Test all demo applications
- [ ] Run performance benchmarks
- [ ] Check memory usage
- [ ] Commit final: "Phase 6: Cleanup and optimization complete"

## Final Integration and Release

### Documentation Updates
- [ ] Update README.md if needed
- [ ] Update USAGE.md examples
- [ ] Update API documentation
- [ ] Create migration guide for users
- [ ] Update CLAUDE.md instructions

### Release Preparation
- [ ] Create comprehensive changelog
- [ ] Tag release version
- [ ] Prepare release notes
- [ ] Update version numbers if needed

### Post-Release Monitoring
- [ ] Monitor for any reported issues
- [ ] Check CI/CD pipeline
- [ ] Validate demo applications in production-like environment
- [ ] Gather feedback from users

## Success Criteria Validation

### Code Quality
- [ ] No file over 500 lines ✓ Target achieved
- [ ] Clear module boundaries ✓ Each module has single responsibility
- [ ] Reduced cyclomatic complexity ✓ Measured and improved
- [ ] Improved test coverage ✓ Coverage maintained or improved

### Performance
- [ ] No regression in route resolution time ✓ Benchmarked
- [ ] No regression in request handling throughput ✓ Load tested
- [ ] Memory usage maintained or improved ✓ Profiled
- [ ] Import time maintained or improved ✓ Measured

### Functionality
- [ ] All existing tests pass ✓ Full test suite green
- [ ] Demo applications work unchanged ✓ All demos tested
- [ ] Extension system fully functional ✓ Extensions tested
- [ ] WebSocket routing works correctly ✓ WebSocket tests pass

### Maintainability
- [ ] Easier to add new features ✓ Developer experience improved
- [ ] Clearer debugging experience ✓ Module boundaries clear
- [ ] Better IDE support ✓ Import paths optimized
- [ ] Reduced merge conflicts ✓ Smaller, focused files

## Risk Mitigation Checklist

### Testing
- [ ] Comprehensive test coverage maintained
- [ ] Performance regressions detected and fixed
- [ ] Integration issues identified and resolved
- [ ] Backward compatibility validated

### Rollback Plan
- [ ] Each phase committed separately
- [ ] Git tags at stable points
- [ ] Rollback procedure documented
- [ ] Rollback tested on staging environment

### Communication
- [ ] Progress tracked and documented
- [ ] Issues logged and resolved
- [ ] Architectural decisions documented
- [ ] Team informed of changes

## Notes and Issues

### Issues Encountered
_Document any issues encountered during implementation:_

- Issue: [Description]
  - Solution: [How it was resolved]
  - Impact: [Effect on timeline/approach]

### Architectural Decisions
_Document key decisions made during implementation:_

- Decision: [What was decided]
  - Rationale: [Why it was decided]
  - Alternatives: [What other options were considered]

### Performance Notes
_Document any performance findings:_

- Measurement: [What was measured]
- Result: [Performance result]
- Action: [Any optimization taken]

### Future Improvements
_Document potential future improvements identified:_

- Improvement: [Description]
- Benefit: [Expected benefit]
- Effort: [Estimated effort required]