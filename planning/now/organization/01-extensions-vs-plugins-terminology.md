# Serv Framework: Extension Terminology Standardization

## Overview

The Serv framework uses a comprehensive extension system to provide modular functionality. This document establishes the official terminology and provides a plan to ensure consistent usage throughout the project.

## Official Terminology

**Extensions**: Modular packages that extend framework functionality at startup. Extensions are the primary mechanism for adding features to Serv applications.

**Extension Components**:
- **Listener**: Event-driven components that respond to application lifecycle events
- **Route**: HTTP request handlers that define API endpoints  
- **Middleware**: Request/response processing components that run in the request pipeline

## Extension Architecture

### Directory Structure
```
extensions/
  my_extension/
    __init__.py
    main.py              # Contains Listener subclass
    extension.yaml       # Metadata and configuration
    routes/              # Route handlers (optional)
    middleware/          # Middleware components (optional)
```

### Configuration Files
```yaml
# extension.yaml - Extension metadata
name: My Extension
description: Extension description
version: 1.0.0
author: Author Name

listeners:
  - main:MyExtensionListener

routers:
  - name: api
    routes:
      - path: /api/endpoint
        handler: routes.api:ApiRoute

middleware:
  - entry: middleware.auth:authenticate
```

```yaml
# serv.config.yaml - Application configuration
extensions:
  - extension: my_extension
    config:
      setting: value
```

### Extension Components

**Listener Example**:
```python
from serv.extensions import Listener
from serv.routes import on

class MyExtensionListener(Listener):
    @on("app.startup")
    async def setup(self, router: Router = dependency()):
        router.add_route("/path", MyRoute, methods=["GET"])
```

**Route Example**:
```python
from serv.routes import Route, handles
from serv.requests import GetRequest
from serv.responses import TextResponse

class MyRoute(Route):
    @handles.GET
    async def handle_get(self, request: GetRequest) -> Annotated[str, TextResponse]:
        return "Hello from extension!"
```

**Middleware Example**:
```python
async def my_middleware(request: Request, call_next):
    # Pre-processing
    response = await call_next(request)
    # Post-processing
    return response
```

## Current Status Analysis

### ✅ Already Standardized
- **Core Framework**: All classes use "extension" terminology (`Listener`, `ExtensionSpec`, `ExtensionLoader`)
- **CLI Commands**: All commands use "extension" (`serv create extension`, `serv extension list`)
- **Configuration**: Primary config uses `extensions:` key
- **Documentation**: 95% of docs use "extension" terminology
- **Code Structure**: Main directories use `extensions/` naming

### ❌ Remaining Issues
1. **Demo Directory**: `demos/plugin_middleware_demo/` → should be `extension_middleware_demo`
2. **Legacy Cache**: `serv/bundled/plugins/` contains only cached files
3. **Documentation**: CLAUDE.md example uses `--plugin-dirs` flag
4. **Test Comments**: One test helper uses "plugin" in comment
5. **Missing Backward Compatibility**: No support for legacy `plugins:` config key

## Implementation Plan

### Priority: High (Professional Image Impact)
**Effort**: Low | **Impact**: High

The framework is already 95% standardized on "extensions" terminology. Completing this standardization will:
- Eliminate developer confusion
- Improve professional appearance
- Provide clear, consistent documentation
- Establish authoritative terminology guidelines

## Action Checklist

### Phase 1: File System Cleanup
- [ ] Remove legacy `serv/bundled/plugins/` directory (cached files only)
- [ ] Rename `demos/plugin_middleware_demo/` to `demos/extension_middleware_demo/`
- [ ] Update demo README files to use consistent terminology

### Phase 2: Documentation Updates
- [ ] Fix CLAUDE.md `--plugin-dirs` example to use `--extension-dirs`
- [ ] Update test comment in `tests/helpers.py` from "plugin" to "extension"
- [ ] Add terminology section to main documentation
- [ ] Update any remaining demo documentation

### Phase 3: Backward Compatibility (Optional)
- [ ] Add configuration support for legacy `plugins:` key with deprecation warning
- [ ] Add CLI hints for plugin-related commands
- [ ] Create migration guide for legacy configurations

### Phase 4: Long-term Maintenance
- [ ] Add terminology checks to linting/pre-commit hooks
- [ ] Update contributing guidelines with terminology standards
- [ ] Create automated tests for terminology consistency

## Specific Changes Required

### File System Changes
```bash
# Remove cached legacy directory
rm -rf serv/bundled/plugins/

# Rename demo directory  
mv demos/plugin_middleware_demo/ demos/extension_middleware_demo/
```

### Documentation Fixes
```diff
# CLAUDE.md
- python -m serv --plugin-dirs ./plugins launch
+ python -m serv --extension-dirs ./extensions launch

# tests/helpers.py  
- "A test plugin that adds routes"
+ "A test extension that adds routes"
```

### New Documentation Section
```markdown
# Terminology Guide (docs/reference/terminology.md)

## Extensions
Serv uses "extensions" to refer to modular components that extend framework functionality.

### Components:
- **Listener**: Event-driven extension components
- **Route**: HTTP request handlers  
- **Middleware**: Request/response processing components

### Legacy Note:
Older references to "plugins" are deprecated. All functionality should use "extensions" terminology.
```

## Optional Backward Compatibility

### Configuration Support
```python
# In serv/config.py - Add legacy key support
def load_config(config_data: dict) -> Config:
    # Support legacy "plugins" key with deprecation warning
    if "plugins" in config_data and "extensions" not in config_data:
        logger.warning(
            "Configuration key 'plugins' is deprecated. "
            "Please use 'extensions' instead."
        )
        config_data["extensions"] = config_data.pop("plugins")
    
    return Config(**config_data)
```

### CLI Enhancement
```python
# In serv/cli.py - Add helpful hints
def handle_unknown_command(command: str):
    if "plugin" in command.lower():
        suggest = command.replace("plugin", "extension")
        print(f"Command '{command}' not found.")
        print(f"Did you mean '{suggest}'?")
        print("Note: Serv uses 'extensions', not 'plugins'.")
```

## Testing Strategy

### Automated Terminology Checks
```python
def test_terminology_consistency():
    """Ensure consistent extension terminology in user-facing content."""
    # Check documentation
    doc_files = Path("docs").glob("**/*.md") 
    for doc_file in doc_files:
        content = doc_file.read_text()
        if "plugin" in content.lower() and "deprecated" not in content.lower():
            pytest.fail(f"Found 'plugin' reference in {doc_file}")

def test_demo_consistency():
    """Check demo directories use extension terminology."""
    demo_dirs = [d.name for d in Path("demos").iterdir() if d.is_dir()]
    plugin_dirs = [d for d in demo_dirs if "plugin" in d.lower()]
    assert not plugin_dirs, f"Demo directories still using 'plugin': {plugin_dirs}"
```

### Pre-commit Hook
```yaml
# .pre-commit-config.yaml addition
- repo: local
  hooks:
    - id: check-terminology
      name: Check extension terminology
      entry: bash -c 'if grep -r "plugin" docs/ demos/ --exclude-dir=__pycache__ | grep -v "deprecated\|legacy"; then exit 1; fi'
      language: system
```

## Long-term Guidelines

### Contributing Standards
```markdown
# docs/contributing.md addition

## Terminology Standards
- Use "extension" for framework add-ons, never "plugin"
- Extension components: Listener, Route, Middleware
- When referencing other frameworks: "FastAPI plugins (called extensions in Serv)"
- Deprecation notices required for any legacy "plugin" references
```

### Style Guide
- **Extensions**: Modular packages that extend framework functionality
- **Listeners**: Event-driven components within extensions  
- **Routes**: HTTP handlers within extensions
- **Middleware**: Request/response processors within extensions

## Migration Path

### For Existing Users
1. **Immediate**: No action required (99% already using extensions)
2. **Recommended**: Update any `plugins:` config keys to `extensions:`
3. **Future**: Legacy support may be removed in major version updates

### For Contributors  
1. Always use "extension" terminology in new code
2. Update "plugin" references when editing existing files
3. Follow terminology guidelines in documentation updates

This plan ensures complete standardization while maintaining backward compatibility and establishing clear guidelines for future development.