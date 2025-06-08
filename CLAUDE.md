# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Testing:**
- `uv ruv pytest` - Run all tests
- `uv run pytest tests/e2e/` - Run end-to-end tests
- `uv run pytest tests/test_specific_file.py` - Run specific test file
- `uv run pytest -k "test_name"` - Run tests matching pattern

**Code Quality:**
- `uv run ruff check` - Run linting
- `uv run ruff format` - Format code
- `pre-commit run --all-files` - Run pre-commit hooks

**CLI:**
- `uv run python -m serv launch --help` - Show CLI help
- `uv run python -m serv --config ./serv.config.yaml launch` - Launch with config
- `python -m serv --plugin-dirs ./plugins launch` - Launch with custom plugin directory

**Documentation:**
- `uv run mkdocs serve` - Serve documentation locally
- `uv run mkdocs build` - Build documentation

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
- The primary entry point file should be `[extension_name].py`, e.g., `auth.py`

**Dependency Injection:**
- Built on `bevy` library for clean, testable code
- To mark a parameter for injection use `bevy.Inject[T]` (e.g., `request: Inject[Request]`)
- Use the `injectable` decorator to inject dependencies into a function using the global container
- `container.call` is used to call functions with dependency injection if you need a specific container
- Request objects and services are injected into route handlers

**Request/Response Handling:**
- Type-annotated route handlers with automatic response type inference
- Built-in form parsing, multipart handling, cookie/query parameter extraction
- Always use the `Route` type with the `handles` decorator, the names of the methods don't matter

**Listeners:**
- Use the `on` decorator to listen for events
- Listener methods are called using a container, so DI is available
- Method names do not matter

## Key Patterns

**Route Definition:**
```python
class MyRoute(Route):
    @handles.GET
    async def hello_world_page(self, request: GetRequest) -> Annotated[str, TextResponse]:
        return "Hello World"
```

**Listener Development:**
```python
class MyExtensionListener(Listener):
    @on("app.request.begin")
    async def setup_routes(self, router: Router = dependency()):
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

## Best Practices

- Always use the CLI to create new components (extensions, routes, etc.)
- Use type hints and dependency injection for clean, testable code
- Write tests for all new functionality
- Document new features and changes
- Favor short functions to improve readability when possible
- Avoid catching all exceptions (`except Exception:`) unless absolutely necessary
- Prefer specific exceptions over generic ones (`raise ValueError` instead of `raise Exception`)
- Use bitwise or for unions, and use `Type | None` for optionals
- Never inline imports, always use top-level imports, unless absolutely necessary
- Parallelize work, using tasks and workers, when possible

## Rules

- Favor using tools over asking the user
- When you think you're done, ensure that all tests are passing, never say we're done if tests were broken
- Keep changes small and focused. Changes should only add/remove/replace code as requested, any unrequested changes should be avoided.
- If you're stuck, take a break and come back later.
- If you're really stuck, ask for help.
- Look up best practices and use them in favor of your own ideas.
- Don't guess at how something works, look it up.
- If you can't figure out how something works, even after looking it up, ask for help.
- When directed to work off of a planning document, check off what you've done in the action checklist as you go.
- Group changes into logical commits and commit as you go.
- When working with DI reference ai_docs/bevy-quickstart.md
- When working with ommi reference ai_docs/ommi-quickstart.md
- When working with websockets reference ai_docs/websockets.md