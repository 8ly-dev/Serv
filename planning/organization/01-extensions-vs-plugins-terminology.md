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

## Recommendations

### Option 1: Standardize on "Extensions" (Recommended)
**Effort**: Low | **Impact**: High

**Rationale**: "Extensions" appears to be the primary term used in the codebase:
- Main directory is `serv/extensions/`
- CLI uses `serv create extension`
- Configuration files use `extensions:` key
- Core classes are named `Extension`, `ExtensionSpec`, etc.

**Changes Required**:
```bash
# Directory renames
mv serv/bundled/plugins/ → [REMOVE - duplicate]
mv demos/plugin_middleware_demo/ → demos/extension_middleware_demo/

# File content updates
s/plugin/extension/g (with careful review)
s/Plugin/Extension/g (class names, if any)
```

### Option 2: Standardize on "Plugins" 
**Effort**: High | **Impact**: High

**Not Recommended**: Would require changing:
- All CLI commands
- Core class names (`Extension` → `Plugin`)
- Main directory structure
- Most configuration files

### Option 3: Support Both with Clear Aliases
**Effort**: Medium | **Impact**: Medium

**Not Recommended**: Would perpetuate confusion and add complexity.

## Action Checklist

### Phase 1: Audit and Plan (Day 1)
- [ ] Complete audit of all "plugin" vs "extension" usage
- [ ] Create mapping of files/directories to rename
- [ ] Identify breaking changes (if any)
- [ ] Plan backward compatibility strategy

### Phase 2: File System Changes (Day 2)
- [ ] Remove duplicate `serv/bundled/plugins/` directory
- [ ] Rename `demos/plugin_middleware_demo/` to `demos/extension_middleware_demo/`
- [ ] Update any other directory names containing "plugin"
- [ ] Update file names if any contain "plugin"

### Phase 3: Content Updates (Day 3)
- [ ] Update all documentation files to use "extension"
- [ ] Update demo README files
- [ ] Update comments in code files
- [ ] Update variable names where appropriate
- [ ] Update configuration examples

### Phase 4: Legacy Support (Day 4)
- [ ] Add configuration alias support for legacy "plugins" key
- [ ] Add helpful error messages for deprecated terms
- [ ] Update migration documentation
- [ ] Test backward compatibility

### Detailed Changes Required

**Directory Structure Changes**:
```bash
# Remove duplicate directory
rm -rf serv/bundled/plugins/

# Rename demo directory
mv demos/plugin_middleware_demo/ demos/extension_middleware_demo/
```

**Documentation Updates**:
```markdown
# Before
This guide shows how to create a plugin for Serv.

# After  
This guide shows how to create an extension for Serv.
```

**Configuration Updates**:
```yaml
# Before (inconsistent)
plugins:
  - welcome
  
# After (consistent)
extensions:
  - welcome
```

**Code Comments Updates**:
```python
# Before
# Load plugin from directory

# After
# Load extension from directory
```

### Backward Compatibility Strategy

**Configuration Compatibility**:
```python
# In config loading code
class ConfigLoader:
    def load_config(self, config_data: dict) -> Config:
        # Support legacy "plugins" key
        if "plugins" in config_data and "extensions" not in config_data:
            logger.warning(
                "Configuration key 'plugins' is deprecated. "
                "Please use 'extensions' instead."
            )
            config_data["extensions"] = config_data.pop("plugins")
        
        return Config(**config_data)
```

**CLI Hints**:
```python
# In CLI error handling
def handle_unknown_command(command: str):
    if "plugin" in command.lower():
        suggest = command.replace("plugin", "extension")
        print(f"Command '{command}' not found.")
        print(f"Did you mean '{suggest}'?")
        print("Note: This framework uses 'extensions', not 'plugins'.")
```

### Testing Strategy

**Terminology Consistency Tests**:
```python
def test_no_plugin_references():
    """Ensure no 'plugin' references in user-facing content."""
    # Check documentation files
    doc_files = Path("docs").glob("**/*.md")
    for doc_file in doc_files:
        content = doc_file.read_text()
        # Allow some exceptions (like "plugins vs extensions" explanation)
        if "plugin" in content.lower() and "deprecated" not in content.lower():
            pytest.fail(f"Found 'plugin' reference in {doc_file}")
    
    # Check demo files
    demo_files = Path("demos").glob("**/README.md")
    for demo_file in demo_files:
        content = demo_file.read_text()
        assert "plugin" not in content.lower(), f"Found 'plugin' in {demo_file}"

def test_configuration_compatibility():
    """Test that legacy 'plugins' config key still works."""
    legacy_config = {"plugins": ["welcome"]}
    config = ConfigLoader().load_config(legacy_config)
    assert "welcome" in config.extensions

def test_cli_command_consistency():
    """Test that CLI uses consistent terminology."""
    result = subprocess.run(["serv", "create", "--help"], capture_output=True, text=True)
    help_text = result.stdout
    
    # Should mention "extension" not "plugin"
    assert "extension" in help_text
    assert "plugin" not in help_text
```

### Documentation Updates

**Create Terminology Guide**:
```markdown
# docs/reference/terminology.md

# Terminology

## Extensions
Serv uses the term "extensions" to refer to modular components that extend framework functionality.

### Legacy Note
Older documentation may reference "plugins". This is deprecated terminology - all functionality described as "plugins" should now be referred to as "extensions".

### Migration
If you have existing configuration using the `plugins:` key, it will continue to work but you should update to use `extensions:` instead.
```

**Update Main Documentation**:
- [ ] Update README.md to use consistent terminology
- [ ] Update getting started guide
- [ ] Update all tutorial content
- [ ] Update API reference documentation

### Migration Communication

**Release Notes**:
```markdown
## Terminology Standardization

We've standardized on "extensions" throughout the framework for consistency:

**Changed:**
- Demo directory renamed: `plugin_middleware_demo` → `extension_middleware_demo`
- Documentation updated to use "extensions" consistently

**Backward Compatibility:**
- Configuration files using `plugins:` key still work (with deprecation warning)
- CLI provides helpful suggestions for plugin-related commands

**Action Required:**
- Update your configuration files to use `extensions:` instead of `plugins:`
- Update any documentation to use "extensions" terminology
```

### Long-term Maintenance

**Style Guide Addition**:
```markdown
# Contributing Guidelines

## Terminology
- Always use "extension" when referring to framework add-ons
- Never use "plugin" in new code or documentation
- When discussing other frameworks, clarify: "FastAPI plugins (called extensions in Serv)"
```

**Automated Checks**:
```bash
# Add to pre-commit hooks
pre-commit:
  - repo: local
    hooks:
      - id: check-terminology
        name: Check for plugin terminology
        entry: bash -c 'grep -r "plugin" docs/ README.md && exit 1 || exit 0'
        language: system
```

This standardization will significantly improve the professional image of the framework and reduce developer confusion.