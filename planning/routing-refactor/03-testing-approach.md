# Testing Approach for Routing Refactoring

## Overview

This document outlines the comprehensive testing strategy to ensure the routing refactoring maintains functionality, performance, and backward compatibility throughout the migration process.

## Testing Philosophy

1. **Test-First Migration**: Validate existing functionality before making changes
2. **Continuous Validation**: Run tests after every significant change
3. **Comprehensive Coverage**: Test both public APIs and internal behavior
4. **Performance Monitoring**: Ensure no regressions in speed or memory usage
5. **Backward Compatibility**: Verify existing code continues to work

## Pre-Migration Testing Baseline

### Step 1: Establish Current Test Coverage
```bash
# Run coverage analysis on current codebase
uv run pytest --cov=serv --cov-report=html --cov-report=term
```

**Target Coverage Areas:**
- `serv/routing.py` - Router class functionality
- `serv/routes.py` - Route class and decorators
- `serv/app.py` - App class and ASGI implementation
- Integration between modules

### Step 2: Document Current Test Results
Create baseline metrics:
- Test execution time
- Memory usage during tests
- Coverage percentages by module
- Performance benchmarks

### Step 3: Identify Test Gaps
**Areas likely needing additional tests:**
- Error handling edge cases
- Extension system integration
- WebSocket routing
- Complex route resolution scenarios
- Middleware interaction

## Phase-by-Phase Testing Strategy

### Phase 1: Foundation Setup Testing

**Test Focus:** Import compatibility and structure validation

**Test Types:**
```python
# Test new import paths work
def test_new_import_paths():
    from serv.http import GetRequest
    from serv.routing import Router
    from serv.app import App
    assert GetRequest is not None
    assert Router is not None
    assert App is not None

# Test old import paths still work
def test_backward_compatibility_imports():
    from serv.routes import Route
    from serv.routing import Router  
    from serv.requests import GetRequest
    assert Route is not None
    assert Router is not None
    assert GetRequest is not None
```

**Validation Checklist:**
- [ ] All existing tests pass without modification
- [ ] New import paths work correctly
- [ ] Old import paths still work
- [ ] No circular import errors
- [ ] Module loading time unchanged

### Phase 2: HTTP Layer Testing

**Test Focus:** HTTP request/response handling, form processing

**Specific Test Areas:**
```python
# Test request object functionality
def test_request_objects_work():
    # Test GetRequest, PostRequest, etc.
    # Test parameter parsing
    # Test query string handling

# Test form processing
def test_form_processing():
    # Test multipart handling
    # Test file uploads
    # Test form validation

# Test response building
def test_response_objects():
    # Test response builders
    # Test status codes
    # Test headers
```

**Integration Tests:**
- Request objects work with routing
- Form processing integrates with routes
- Response objects work with ASGI

**Performance Tests:**
- Request parsing speed
- Form processing performance
- Memory usage of request objects

### Phase 3: Routing Layer Testing

**Test Focus:** Route registration, resolution, and URL generation

**Core Functionality Tests:**
```python
# Test route registration
def test_route_registration():
    router = Router()
    router.add_route("/test", handler, ["GET"])
    # Verify route is registered correctly

# Test route resolution  
def test_route_resolution():
    # Test path matching
    # Test parameter extraction
    # Test method matching

# Test URL generation
def test_url_generation():
    # Test url_for functionality
    # Test parameter substitution
    # Test complex URL patterns
```

**WebSocket Tests:**
```python
def test_websocket_routing():
    # Test WebSocket route registration
    # Test WebSocket path resolution
    # Test WebSocket parameter extraction
```

**Performance Critical Tests:**
- Route resolution speed
- Pattern compilation time
- Memory usage of route storage

### Phase 4: Application Layer Testing

**Test Focus:** ASGI implementation, middleware, extensions

**ASGI Tests:**
```python
async def test_asgi_interface():
    # Test ASGI app callable
    # Test request/response cycle
    # Test error handling
```

**Middleware Tests:**
```python
def test_middleware_stack():
    # Test middleware ordering
    # Test middleware execution
    # Test middleware error handling
```

**Extension Tests:**
```python
def test_extension_system():
    # Test extension loading
    # Test extension event handling
    # Test extension route registration
```

### Phase 5: Dependency Injection Testing

**Test Focus:** Parameter injection and container management

**DI Tests:**
```python
def test_dependency_injection():
    # Test parameter injection
    # Test dependency resolution
    # Test container scoping
```

## Test Categories

### 1. Unit Tests
**Scope:** Individual classes and functions
**Location:** `tests/test_*.py`

**Key Areas:**
- Router path matching logic
- Route method selection
- Request parameter parsing
- Response building
- Form processing

### 2. Integration Tests  
**Scope:** Inter-module communication
**Location:** `tests/test_integration_*.py`

**Key Areas:**
- Router + Route integration
- App + Router integration
- Extension + Core integration
- HTTP + Routing integration

### 3. End-to-End Tests
**Scope:** Full request/response cycle
**Location:** `tests/e2e/`

**Key Areas:**
- Complete request processing
- Real HTTP scenarios
- WebSocket connections
- Extension functionality

### 4. Performance Tests
**Scope:** Speed and memory usage
**Location:** `tests/performance/`

**Key Areas:**
- Route resolution performance
- Request processing throughput
- Memory usage patterns
- Import time measurement

### 5. Compatibility Tests
**Scope:** Backward compatibility validation
**Location:** `tests/compatibility/`

**Key Areas:**
- Old import paths
- Existing API usage patterns
- Demo application functionality
- Extension compatibility

## Automated Testing Pipeline

### Continuous Integration
```yaml
# GitHub Actions workflow
name: Routing Refactor Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        run: uv sync
      - name: Run unit tests
        run: uv run pytest tests/ -v
      - name: Run integration tests
        run: uv run pytest tests/integration/ -v
      - name: Run e2e tests
        run: uv run pytest tests/e2e/ -v
      - name: Performance benchmarks
        run: uv run pytest tests/performance/ -v
      - name: Coverage report
        run: uv run pytest --cov=serv --cov-report=xml
```

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: routing-tests
        name: Routing Tests
        entry: uv run pytest tests/test_routing*.py
        language: system
        pass_filenames: false
```

## Test Data and Fixtures

### Common Test Fixtures
```python
# conftest.py additions
@pytest.fixture
def sample_routes():
    """Common route configurations for testing"""
    return [
        ("/", "GET", home_handler),
        ("/api/users", "GET", list_users),
        ("/api/users/{id}", "GET", get_user),
        ("/api/users/{id}", "POST", update_user),
    ]

@pytest.fixture  
def test_app_with_routes(sample_routes):
    """App instance with test routes configured"""
    # Setup app with sample routes
    
@pytest.fixture
def performance_routes():
    """Large number of routes for performance testing"""
    # Generate many routes for load testing
```

### Mock Objects
```python
# Test utilities
class MockExtension:
    """Mock extension for testing extension system"""
    
class MockMiddleware:
    """Mock middleware for testing middleware stack"""
    
class MockHandler:
    """Mock route handler for testing routing logic"""
```

## Performance Testing Strategy

### Benchmarking Framework
```python
import time
import memory_profiler
import pytest

def benchmark_route_resolution(router, num_requests=1000):
    """Benchmark route resolution performance"""
    start_time = time.time()
    for _ in range(num_requests):
        router.resolve_route("/api/users/123", "GET")
    end_time = time.time()
    return (end_time - start_time) / num_requests

@pytest.mark.performance
def test_route_resolution_performance():
    """Ensure route resolution performance is acceptable"""
    # Setup router with many routes
    # Benchmark resolution time
    # Assert performance within acceptable bounds
```

### Memory Testing
```python
@memory_profiler.profile
def test_memory_usage():
    """Monitor memory usage during operations"""
    # Test memory usage of various operations
    # Ensure no memory leaks
```

### Load Testing
```python
async def test_concurrent_requests():
    """Test handling of concurrent requests"""
    # Simulate multiple concurrent requests
    # Ensure no race conditions
    # Validate performance under load
```

## Error Testing

### Exception Handling
```python
def test_route_not_found():
    """Test 404 handling"""
    
def test_method_not_allowed():
    """Test 405 handling"""
    
def test_invalid_route_pattern():
    """Test route registration error handling"""
    
def test_extension_loading_failure():
    """Test extension system error handling"""
```

### Edge Cases
```python
def test_empty_router():
    """Test router with no routes"""
    
def test_malformed_requests():
    """Test handling of malformed HTTP requests"""
    
def test_circular_route_dependencies():
    """Test detection of circular dependencies"""
```

## Regression Testing

### Golden Tests
Create reference outputs for key scenarios:
- Route resolution results
- URL generation outputs
- Request parsing results
- Response formatting

### Snapshot Testing
```python
def test_router_state_snapshot(snapshot):
    """Test router internal state matches expected structure"""
    router = create_test_router()
    snapshot.assert_match(router.serialize_state())
```

## Test Environment Setup

### Docker Test Environment
```dockerfile
# Dockerfile.test
FROM python:3.11
COPY . /app
WORKDIR /app
RUN uv sync
CMD ["uv", "run", "pytest"]
```

### Test Configuration
```python
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    performance: Performance tests
    slow: Slow tests
```

## Success Criteria

### Test Coverage
- [ ] Maintain or improve overall test coverage
- [ ] 100% coverage on critical path functions
- [ ] All new modules have >90% coverage

### Performance
- [ ] No regression in route resolution time
- [ ] No regression in request processing speed
- [ ] Memory usage stable or improved
- [ ] Import time stable or improved

### Functionality  
- [ ] All existing tests pass
- [ ] Demo applications work unchanged
- [ ] Extension system fully functional
- [ ] WebSocket routing works correctly

### Quality
- [ ] No new test flakiness
- [ ] Tests run in reasonable time (<5 minutes)
- [ ] Clear test failure messages
- [ ] Good test organization and readability