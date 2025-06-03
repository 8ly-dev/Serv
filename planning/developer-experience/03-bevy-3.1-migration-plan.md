# Bevy 3.1+ Migration Plan

## Overview

This document provides a comprehensive migration plan for upgrading the Serv framework from Bevy 3.0 beta patterns to Bevy 3.1+ patterns. The migration involves updating dependency injection patterns throughout the codebase, tests, demos, and documentation.

## Current State Analysis

### Bevy Version Status
- **Current**: `bevy>=3.1.0b1` (already upgraded dependency)
- **Pattern Usage**: Primarily Bevy 3.0 beta patterns (`@inject`, `dependency()`)
- **Scope**: Framework-wide usage in core, extensions, tests, and documentation

### Key Patterns Requiring Migration

1. **Decorator Migration**: `@inject` → `@injectable` (+ `@auto_inject` where appropriate)
2. **Parameter Migration**: `dependency()` → `Inject[T]` type annotations
3. **Container API**: `container.instances[Type]` → `container.add()` patterns
4. **Hook Registration**: Add `type_factory.register_hook(registry)` for auto-creation

## Risk Assessment

| Component | Risk Level | Complexity | Impact |
|-----------|------------|------------|---------|
| Core Framework | **HIGH** | Complex container patterns | Framework stability |
| Extension System | **HIGH** | Event handling with DI | Extension compatibility |
| Custom Injectors | **CRITICAL** | Uses internal Bevy hooks | Core functionality |
| Test Infrastructure | **HIGH** | Direct container manipulation | Development workflow |
| Documentation | **MEDIUM** | Extensive examples to update | User experience |
| Demo Applications | **LOW** | Standard DI patterns | Example consistency |

## Migration Strategy

### Phase 1: Foundation (Core Framework)
**Estimated Time**: 3-4 days

#### Phase 1 Tasks
- [ ] **1.1** Update core imports in `serv/__init__.py`
- [ ] **1.2** Migrate `serv/app.py` DI patterns
- [ ] **1.3** Update `serv/routing.py` container usage
- [ ] **1.4** Migrate `serv/routes.py` base class patterns
- [ ] **1.5** Update `serv/requests.py` and `serv/responses.py`
- [ ] **1.6** Add type_factory hook registration to app initialization
- [ ] **1.7** Run core tests to ensure basic functionality

#### Phase 1 Critical Files
```
serv/app.py                    # EventEmitter, container setup
serv/routing.py               # get_current_router() function
serv/routes.py                # Route.__call__() method
serv/requests.py              # Request handling
serv/responses.py             # Response building
```

### Phase 2: Custom Injection System (Critical Path)
**Estimated Time**: 2-3 days

#### Phase 2 Tasks
- [ ] **2.1** Analyze `serv/injectors.py` hook compatibility
- [ ] **2.2** Update custom injection hooks for Bevy 3.1+
- [ ] **2.3** Migrate Header, Cookie, Query parameter injection
- [ ] **2.4** Update WebSocket injection patterns
- [ ] **2.5** Test custom injector functionality
- [ ] **2.6** Validate HTTP parameter extraction works

#### Phase 2 Critical Files
```
serv/injectors.py             # Custom hooks (@hooks.CREATE_INSTANCE)
serv/websocket.py             # WebSocket frame injection
```

### Phase 3: Extension System
**Estimated Time**: 2-3 days

#### Phase 3 Tasks
- [ ] **3.1** Update `serv/extensions/extensions.py` base classes
- [ ] **3.2** Migrate `serv/extensions/loader.py` patterns
- [ ] **3.3** Update `serv/extensions/middleware.py` DI usage
- [ ] **3.4** Migrate `serv/extensions/router_extension.py`
- [ ] **3.5** Test extension loading and event handling
- [ ] **3.6** Validate middleware lifecycle works

#### Phase 3 Critical Files
```
serv/extensions/extensions.py  # Listener base class, event emission
serv/extensions/loader.py      # Extension loading patterns
serv/extensions/middleware.py  # Middleware DI patterns
serv/extensions/router_extension.py  # Router extension DI
```

### Phase 4: Test Infrastructure
**Estimated Time**: 2-3 days

#### Phase 4 Tasks
- [ ] **4.1** Update `tests/conftest.py` test infrastructure
- [ ] **4.2** Migrate `tests/helpers.py` DI utilities
- [ ] **4.3** Update container branching in extension tests
- [ ] **4.4** Migrate mock injection patterns
- [ ] **4.5** Update E2E test infrastructure
- [ ] **4.6** Run full test suite validation

#### Phase 4 Critical Files
```
tests/conftest.py             # Core test fixtures
tests/helpers.py              # RouteAddingExtension, test utilities
tests/test_extensions.py      # Container manipulation tests
tests/test_event_emit.py      # Event system tests
tests/e2e/helpers.py          # E2E test infrastructure
```

### Phase 5: Demo Applications
**Estimated Time**: 1-2 days

#### Phase 5 Tasks
- [ ] **5.1** Update SSE Dashboard demo extension
- [ ] **5.2** Migrate WebSocket Chat demo
- [ ] **5.3** Update any other demo extensions
- [ ] **5.4** Test demo functionality
- [ ] **5.5** Validate demo README instructions

#### Phase 5 Files
```
demos/sse_dashboard/extensions/dashboard/main.py
demos/websocket_chat/extensions/websocket_chat/main.py
```

### Phase 6: Documentation Updates
**Estimated Time**: 3-4 days

#### Phase 6 Tasks
- [ ] **6.1** Update `docs/guides/dependency-injection.md` (primary DI guide)
- [ ] **6.2** Migrate `docs/guides/extensions.md` examples
- [ ] **6.3** Update `docs/guides/routing.md` DI patterns
- [ ] **6.4** Migrate `docs/guides/middleware.md` examples
- [ ] **6.5** Update `docs/guides/testing.md` patterns
- [ ] **6.6** Update getting-started tutorials
- [ ] **6.7** Update `docs/guides/requests.md` examples
- [ ] **6.8** Regenerate API reference documentation

#### Phase 6 Critical Files
```
docs/guides/dependency-injection.md  # 550+ lines, primary DI guide
docs/guides/extensions.md            # 790 lines, extension patterns
docs/guides/routing.md               # 890+ lines, route DI patterns
docs/guides/middleware.md            # 828 lines, middleware DI
docs/guides/testing.md               # 1800+ lines, testing patterns
docs/getting-started/first-app.md    # Tutorial examples
docs/getting-started/quick-start.md  # CLI tutorial examples
```

## Detailed Action Checklist

### Core Framework Migration

#### App Class (`serv/app.py`)
- [ ] Replace `@inject` decorators with `@injectable`
- [ ] Update `dependency()` parameters to `Inject[T]`
- [ ] Add `type_factory.register_hook(self._registry)` in `__init__`
- [ ] Update EventEmitter DI patterns
- [ ] Test container branching still works for request isolation

#### Routing (`serv/routing.py`)
- [ ] Update `get_current_router()` function signature
- [ ] Replace `container: Container = dependency()` with `Inject[Container]`
- [ ] Update `@inject` decorator usage
- [ ] Test routing functionality

#### Routes (`serv/routes.py`)
- [ ] Update Route `__call__` method DI patterns
- [ ] Migrate parameter injection to `Inject[T]` patterns
- [ ] Update response builder injection
- [ ] Test route handler invocation

### Custom Injectors (`serv/injectors.py`)
- [ ] Research Bevy 3.1+ hooks API compatibility
- [ ] Update `@hooks.CREATE_INSTANCE` decorators if needed
- [ ] Migrate Header, Cookie, Query injection patterns
- [ ] Update WebSocket frame type handling
- [ ] Test custom injection still works
- [ ] Validate parameter extraction functionality

### Extension System Migration

#### Extensions Base (`serv/extensions/extensions.py`)
- [ ] Update Listener base class DI patterns
- [ ] Migrate event emission methods
- [ ] Update `@inject` decorators to `@injectable`
- [ ] Update `dependency()` parameters to `Inject[T]`
- [ ] Test extension event handling

#### Extension Loader (`serv/extensions/loader.py`)
- [ ] Update any DI patterns in extension loading
- [ ] Test extension discovery and loading
- [ ] Validate extension initialization

#### Middleware (`serv/extensions/middleware.py`)
- [ ] Update middleware lifecycle DI patterns
- [ ] Migrate `container.call()` usage
- [ ] Update async context handling
- [ ] Test middleware execution

### Test Infrastructure Migration

#### Core Test Infrastructure (`tests/conftest.py`)
- [ ] Update global mocking patterns
- [ ] Migrate container setup fixtures
- [ ] Update autouse fixtures
- [ ] Test fixture isolation

#### Test Helpers (`tests/helpers.py`)
- [ ] Update RouteAddingExtension DI patterns
- [ ] Migrate `container.call()` usage in helpers
- [ ] Update `dependency()` parameters to `Inject[T]`
- [ ] Test helper functionality

#### Extension Tests (`tests/test_extensions.py`)
- [ ] Replace `container.instances[Type]` with `container.add()`
- [ ] Update `get_container().branch()` to `get_container().child()`
- [ ] Migrate mock injection patterns
- [ ] Test extension functionality

#### Event System Tests (`tests/test_event_emit.py`)
- [ ] Update container setup fixtures
- [ ] Migrate event emitter registration
- [ ] Update protocol registration patterns
- [ ] Test event emission

### Demo Applications Migration

#### SSE Dashboard (`demos/sse_dashboard/extensions/dashboard/main.py`)
- [ ] Update extension class DI patterns
- [ ] Migrate route handler injection
- [ ] Update event listener patterns
- [ ] Test SSE functionality

#### WebSocket Chat (`demos/websocket_chat/extensions/websocket_chat/main.py`)
- [ ] Update WebSocket injection patterns
- [ ] Migrate route handlers
- [ ] Test WebSocket functionality

### Documentation Migration

#### Primary DI Guide (`docs/guides/dependency-injection.md`)
- [ ] Update all import examples
- [ ] Migrate `dependency()` usage to `Inject[T]`
- [ ] Update container registration examples
- [ ] Update testing patterns
- [ ] Add Bevy 3.1+ best practices section
- [ ] Update troubleshooting section

#### Extensions Guide (`docs/guides/extensions.md`)
- [ ] Update extension creation examples
- [ ] Migrate DI patterns in extension code
- [ ] Update service integration examples
- [ ] Update database integration patterns

#### Routing Guide (`docs/guides/routing.md`)
- [ ] Update route handler examples
- [ ] Migrate parameter injection patterns
- [ ] Update request/response injection examples
- [ ] Update testing examples

#### Middleware Guide (`docs/guides/middleware.md`)
- [ ] Update middleware function signatures
- [ ] Migrate service injection examples
- [ ] Update database connection examples
- [ ] Update testing patterns

#### Testing Guide (`docs/guides/testing.md`)
- [ ] Update test fixture patterns
- [ ] Migrate mocking dependency examples
- [ ] Update integration testing patterns
- [ ] Update `container.call()` examples
- [ ] Add Bevy 3.1+ testing best practices

#### Getting Started Tutorials
- [ ] Update `docs/getting-started/first-app.md` examples
- [ ] Update `docs/getting-started/quick-start.md` CLI examples
- [ ] Ensure generated code uses new patterns

## Migration Commands Reference

### Before Migration
```python
# Old Bevy 3.0 beta patterns
from bevy import inject, dependency
from bevy.containers import Container

@inject
def handler(service: MyService = dependency()):
    return service.process()

# Container usage
container.instances[MyService] = service_instance
await container.call(handler)
```

### After Migration
```python
# New Bevy 3.1+ patterns
from bevy import injectable, auto_inject, Inject, get_container
from bevy.bundled.type_factory_hook import type_factory

# Set up container with type factory
container = get_container()
type_factory.register_hook(container.registry)

@auto_inject
@injectable
def handler(service: Inject[MyService]):
    return service.process()

# Container usage
container.add(MyService, service_instance)
result = handler()  # Uses global container
```

## Validation Strategy

### Phase Validation
After each phase, run these validation steps:

1. **Unit Tests**: `uv run pytest tests/`
2. **E2E Tests**: `uv run pytest tests/e2e/`
3. **Demo Validation**: Test each updated demo manually
4. **Documentation**: Build docs and check for errors
5. **Linting**: `uv run ruff check` and `uv run ruff format`

### Integration Testing
- [ ] Test extension loading and initialization
- [ ] Test request/response handling with DI
- [ ] Test middleware execution with DI
- [ ] Test WebSocket handling with DI
- [ ] Test event system with DI
- [ ] Test custom parameter injection (Header, Cookie, Query)

### Performance Testing
- [ ] Benchmark request handling performance
- [ ] Test memory usage with new container patterns
- [ ] Validate container branching performance

## Rollback Strategy

If migration issues are encountered:

1. **Git Branching**: Use feature branch for migration work
2. **Incremental Commits**: Commit after each successful phase
3. **Testing Gates**: Don't proceed to next phase if tests fail
4. **Documentation**: Keep old examples until migration is complete

## Post-Migration Tasks

- [ ] Update CLAUDE.md with new DI patterns
- [ ] Add migration guide to documentation
- [ ] Update CI/CD pipeline if needed
- [ ] Create developer communication about changes
- [ ] Update any external integration examples
- [ ] Bump the Serv version to 0.2.0
- [ ] Validate linter rules and tests pass, then create a pull request for review

## Estimated Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Core Framework | 3-4 days | None |
| Phase 2: Custom Injectors | 2-3 days | Phase 1 complete |
| Phase 3: Extension System | 2-3 days | Phase 1, 2 complete |
| Phase 4: Test Infrastructure | 2-3 days | Phase 1, 2, 3 complete |
| Phase 5: Demo Applications | 1-2 days | Phase 1, 2, 3 complete |
| Phase 6: Documentation | 3-4 days | All phases complete |

**Total Estimated Time**: 13-19 days

## Success Criteria

- [ ] All tests passing with new Bevy patterns
- [ ] All demos functional
- [ ] Documentation updated and accurate
- [ ] No performance regressions
- [ ] Clean code style maintained
- [ ] Extension system fully functional
- [ ] Custom injection patterns working

## Notes

- The migration should not maintain backward compatibility at all
- Focus on maintaining the current developer experience
- Ensure all custom injection patterns continue to work
- Test thoroughly at each phase before proceeding
- Document any breaking changes for extension developers
- Make changes in a feature branch for easy rollback
- Commit changes as you go, this likely should be done after each task
- Create new tests as you go to ensure changes do what you expect

---

**References:**
- Bevy 3.1+ Quick Start Guide: `ai_docs/bevy-quickstart.md`
- Current Bevy usage analysis in planning phases
- Framework architecture documentation