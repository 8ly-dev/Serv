# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Testing:**
- `pytest` - Run all tests
- `pytest tests/e2e/` - Run end-to-end tests
- `pytest tests/test_specific_file.py` - Run specific test file
- `pytest -k "test_name"` - Run tests matching pattern

**Code Quality:**
- `ruff check` - Run linting
- `ruff format` - Format code
- `pre-commit run --all-files` - Run pre-commit hooks

**CLI:**
- `python -m serv launch --help` - Show CLI help
- `python -m serv launch --config ./serv.config.yaml` - Launch with config
- `python -m serv launch --plugin-dirs ./plugins` - Launch with custom plugin directory
- `uvicorn main:app --reload` - Standard ASGI server for development

**Documentation:**
- `mkdocs serve` - Serve documentation locally
- `mkdocs build` - Build documentation

## Architecture Overview

**Core Framework (ASGI-based):**
- `serv/app.py` - Main App class, ASGI entry point, event emission, lifespan management
- `serv/routing.py` - URL routing, path matching, Router class
- `serv/routes.py` - Route base class with signature-based handler system (handle_get, handle_post, etc.)
- `serv/requests.py` - Type-safe request objects (GetRequest, PostRequest, etc.)
- `serv/responses.py` - Response builders and structured response types

**Extension System:**
- Extensions are the primary way to add functionality
- `serv/extensions/` - Extension loading, middleware, router extensions
- Extensions use `extension.yaml` for metadata (name, version, entry points, middleware)
- App config uses `serv.config.yaml` to enable extensions and override settings
- Extensions inherit from base classes and use event listeners (on_app_request_begin, etc.)

**Dependency Injection:**
- Built on `bevy` library for clean, testable code
- Heavy use of `dependency()` and `inject()` throughout codebase
- Request objects and services are injected into route handlers

**Request/Response Handling:**
- Type-annotated route handlers with automatic response type inference
- Built-in form parsing, multipart handling, cookie/query parameter extraction
- ResponseBuilder provides fluent API for constructing responses

## Key Patterns

**Route Definition:**
```python
class MyRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[str, TextResponse]:
        return "Hello World"
```

**Extension Development:**
```python
class MyExtension(Extension):
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_route("/path", handler, methods=["GET"])
```

**Testing:**
- Use `create_test_client()` from conftest.py for e2e testing
- `AppBuilder` for fluent test app construction
- Mock `find_extension_spec` is auto-applied to prevent hanging in tests

## Extension Configuration

**Directory Structure:**
```
extensions/
  my_extension/
    __init__.py
    main.py              # Contains Extension subclass
    extension.yaml       # Metadata and configuration
```

**Config Files:**
- `extension.yaml` - Extension metadata, entry points, default settings
- `serv.config.yaml` - App-level config to enable extensions and override settings

## Development Notes

- Framework emphasizes extensibility over rigid structure
- Heavy use of async/await throughout
- Type hints are extensive and meaningful for IDE support
- Pre-commit hooks enforce code quality (ruff formatting/linting)
- Tests are comprehensive with both unit and e2e coverage
- Documentation is generated with mkdocs and mkdocstrings