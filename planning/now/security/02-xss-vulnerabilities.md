# XSS Vulnerabilities and Template System Overhaul

## Problem Description

The Serv framework is vulnerable to Cross-Site Scripting (XSS) attacks through template rendering. The current template system has fundamental design flaws that create security vulnerabilities and architectural issues:

1. **No Auto-Escaping**: Jinja2 environments are created without `autoescape=True`, allowing raw HTML injection
2. **Ad-hoc Template Creation**: Each `Jinja2Response` creates its own Environment instance without centralized security controls
3. **Inconsistent Template Resolution**: Template path resolution is hardcoded and inconsistent across extensions
4. **No Template Override Support**: Extensions cannot override core templates or each other's templates

### Current Vulnerable Code

**File**: `serv/routes.py` (lines 187-196)
```python
class Jinja2Response(Response):
    def render(self) -> AsyncGenerator[str, object]:
        from jinja2 import Environment, FileSystemLoader
        
        template_locations = self._get_template_locations(self.created_by)
        
        # SECURITY ISSUE: No auto-escaping enabled
        env = Environment(
            loader=FileSystemLoader(template_locations), 
            enable_async=True
            # Missing: autoescape=True
        )
        template = env.get_template(self.template)
        return template.generate_async(**self.context)
```

**File**: `serv/templates/error/500.html`
```html
<h1>Internal Server Error</h1>
<p>Error: {{ error_str }}</p>         <!-- UNESCAPED - XSS RISK -->
<p>Path: {{ request_path }}</p>       <!-- UNESCAPED - XSS RISK -->

<div class="traceback">
    <pre>{{ traceback }}</pre>        <!-- UNESCAPED - XSS RISK -->
</div>
```

### Attack Scenarios

1. **Error Page XSS**: Malicious URLs that cause errors can inject JavaScript:
   ```
   GET /../../<script>alert('XSS')</script>
   ```

2. **Template Context XSS**: User data in template context executes as JavaScript:
   ```python
   # Vulnerable route handler
   async def handle_get(self, name: str) -> Annotated[str, Jinja2Response]:
       return Jinja2Response("profile.html", {"name": name})  # XSS if name contains <script>
   ```

3. **Form Data XSS**: Form submissions that redisplay unescaped data

## Impact Assessment

- **Severity**: 🔴 **HIGH**
- **CVSS Score**: 8.1 (High)
- **Attack Vector**: Network (via crafted requests)
- **Impact**: Client-side code execution, session hijacking, data theft
- **Affected Components**: All template rendering, error pages, extension templates

## Solution: Centralized Template Factory System

We will implement a complete overhaul of the template system with a centralized factory that provides secure, per-extension template environments with proper path resolution.

### Architecture Overview

```
TemplateFactory (singleton)
├── App Template Environment (for error pages, core templates)
│   ├── ./templates/
│   └── [site-packages]/serv/templates/
└── Extension Template Environments (lazily created per extension)
    ├── ./templates/[extension_name]/     (override location)
    └── ./[extensions_dir]/[extension_name]/templates/
```

### Core Components

#### 1. TemplateFactory Class

```python
from typing import Dict, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from bevy import dependency

class TemplateFactory:
    """Centralized factory for creating secure Jinja2 environments."""
    
    def __init__(self):
        self._extension_environments: Dict[str, Environment] = {}
        self._app_environment: Optional[Environment] = None
    
    def get_app_environment(self) -> Environment:
        """Get template environment for App-level templates (error pages, etc.)."""
        if self._app_environment is None:
            template_paths = [
                Path.cwd() / "templates",
                Path(__file__).parent / "templates"  # serv/templates
            ]
            self._app_environment = self._create_secure_environment(template_paths)
        return self._app_environment
    
    def get_extension_environment(self, extension_spec) -> Environment:
        """Get lazily-created template environment for a specific extension."""
        ext_name = extension_spec.name
        
        if ext_name not in self._extension_environments:
            template_paths = [
                Path.cwd() / "templates" / ext_name,           # Override location
                extension_spec.path / "templates"              # Extension templates
            ]
            # Filter to only existing paths
            existing_paths = [p for p in template_paths if p.exists()]
            
            if existing_paths:
                self._extension_environments[ext_name] = self._create_secure_environment(existing_paths)
            else:
                raise RuntimeError(f"No template directories found for extension '{ext_name}'")
                
        return self._extension_environments[ext_name]
    
    def _create_secure_environment(self, template_paths: list[Path]) -> Environment:
        """Create a secure Jinja2 environment with auto-escaping enabled."""
        return Environment(
            loader=FileSystemLoader([str(p) for p in template_paths]),
            enable_async=True,
            autoescape=select_autoescape(['html', 'xml', 'htm']),  # Smart auto-escaping
            trim_blocks=True,
            lstrip_blocks=True,
            # Security: Prevent access to private attributes
            finalize=lambda x: x if x is not None else ''
        )
    
    def render_template(self, template_name: str, context: dict, extension_spec=None) -> str:
        """Convenience method to render a template."""
        if extension_spec:
            env = self.get_extension_environment(extension_spec)
        else:
            env = self.get_app_environment()
            
        template = env.get_template(template_name)
        return template.render(**context)
    
    async def render_template_async(self, template_name: str, context: dict, extension_spec=None) -> AsyncGenerator[str, None]:
        """Async template rendering."""
        if extension_spec:
            env = self.get_extension_environment(extension_spec)
        else:
            env = self.get_app_environment()
            
        template = env.get_template(template_name)
        async for chunk in template.generate_async(**context):
            yield chunk
```

#### 2. Updated Jinja2Response

```python
class Jinja2Response(Response):
    def __init__(self, template: str, context: dict[str, Any], status_code: int = 200):
        super().__init__(status_code)
        self.template = template
        self.context = context
        self.headers["Content-Type"] = "text/html; charset=utf-8"

    def render(self) -> AsyncGenerator[str, object]:
        """Render template using injected factory."""
        from serv.injectors import get_global_container
        container = get_global_container()
        
        def _render():
            template_factory: TemplateFactory = dependency()
            return template_factory.render_template_async(
                self.template, 
                self.context, 
                extension_spec=self.created_by
            )
        
        return container.call(_render)
```

#### 3. App Error Handling Integration

```python
# In serv/app.py
from serv.injectors import inject

class App:
    def __init__(self):
        # ... existing initialization
        # TemplateFactory will be injected when needed
        pass
    
    @inject
    async def handle_error(self, request, exc, template_factory: TemplateFactory = dependency()):
        """Render error pages using injected template factory."""
        if isinstance(exc, HTTPException):
            status_code = exc.status_code
            template_name = f"error/{status_code}.html"
        else:
            status_code = 500
            template_name = "error/500.html"
            
        context = {
            "error_str": str(exc),
            "request_path": request.url.path,
            "status_code": status_code
        }
        
        try:
            content = await template_factory.render_template_async(
                template_name, context
            )
            return Response(content, status_code=status_code, headers={"Content-Type": "text/html"})
        except TemplateNotFound:
            # Fallback to plain text error
            return Response(f"Error {status_code}: {exc}", status_code=status_code)
```

#### 4. DI Container Setup

```python
# In serv/app.py - App initialization
class App:
    def __init__(self):
        # ... existing initialization
        
        # Register TemplateFactory in DI container
        self.container.add_singleton(TemplateFactory, TemplateFactory())
        
        # ... rest of initialization
```

### Template Path Resolution

#### For Extensions
1. `./templates/[extension_name]/` - **Override location** (highest priority)
2. `./[extensions_dir]/[extension_name]/templates/` - **Extension templates** (fallback)

#### For App-level Templates
1. `./templates/` - **Project templates** (highest priority)  
2. `[site-packages]/serv/templates/` - **Framework templates** (fallback)

### Security Features

1. **Auto-Escaping**: All environments use `select_autoescape(['html', 'xml', 'htm'])`
2. **Attribute Access Control**: `finalize` function prevents None values from breaking templates
3. **Path Validation**: Only existing template directories are added to loaders
4. **Centralized Control**: All template security settings managed in one place

### Breaking Changes

This is a **clean break** with no backwards compatibility:

1. **Jinja2Response API**: No changes to public API, but internal implementation completely rewritten to use DI
2. **Template Path Resolution**: New resolution order may affect existing templates
3. **Auto-Escaping**: Templates that relied on unescaped HTML will break and must use `|safe` filter
4. **Environment Creation**: Extensions can no longer create their own Jinja2 environments
5. **Dependency Injection**: TemplateFactory must be registered in DI container for template rendering to work

## Implementation Plan

### Phase 1: Core Template Factory (Week 1)
- [ ] Implement `TemplateFactory` class with singleton pattern
- [ ] Add secure environment creation with auto-escaping
- [ ] Implement template path resolution logic
- [ ] Add async template rendering support

### Phase 2: Integration (Week 1) 
- [ ] Update `Jinja2Response` to use `TemplateFactory`
- [ ] Update `App` error handling to use template factory
- [ ] Remove old template location methods from routes
- [ ] Update extension loading to register with template factory

### Phase 3: Template Updates (Week 2)
- [ ] Audit all existing templates for auto-escaping compatibility  
- [ ] Update error templates to use proper escaping
- [ ] Add `|safe` filters where raw HTML is intentionally needed
- [ ] Create template override examples in documentation

### Phase 4: Testing & Security (Week 2)
- [ ] Comprehensive XSS prevention tests
- [ ] Template path resolution tests
- [ ] Extension template environment isolation tests
- [ ] Performance benchmarking of new system

## Comprehensive Testing & Implementation Checklist

### Core Implementation
- [ ] **TemplateFactory DI implementation**
  - [ ] Register TemplateFactory as singleton in DI container
  - [ ] Per-extension environment caching
  - [ ] Lazy environment creation
  - [ ] Proper resource cleanup on app shutdown

- [ ] **Secure Environment Creation**
  - [ ] `autoescape=select_autoescape(['html', 'xml', 'htm'])` enabled
  - [ ] `trim_blocks=True` and `lstrip_blocks=True` for clean output
  - [ ] `finalize` function to handle None values
  - [ ] Async rendering support with `enable_async=True`

- [ ] **Template Path Resolution**
  - [ ] App-level paths: `./templates/` → `serv/templates/`
  - [ ] Extension paths: `./templates/[ext]/` → `./extensions/[ext]/templates/`
  - [ ] Path existence validation before adding to loader
  - [ ] Proper handling of missing template directories

### Integration Updates
- [ ] **Jinja2Response Overhaul**
  - [ ] Remove `_get_template_locations` method
  - [ ] Use DI to inject TemplateFactory in `render()` method
  - [ ] Pass `self.created_by` as extension_spec
  - [ ] Maintain same public API for backwards compatibility

- [ ] **App Error Handling**
  - [ ] Add `@inject` decorator to `handle_error` method
  - [ ] Inject TemplateFactory via dependency injection
  - [ ] Proper context building with escaped error messages
  - [ ] Fallback to plain text when templates missing
  - [ ] Handle all HTTP status codes (404, 405, 500, etc.)

- [ ] **DI Container Integration**
  - [ ] Register TemplateFactory as singleton in App container
  - [ ] Ensure TemplateFactory is available throughout application lifecycle
  - [ ] Update global container to include TemplateFactory
  - [ ] Test DI injection works in all contexts (routes, error handlers, etc.)

- [ ] **Extension Integration**
  - [ ] Remove extension-specific environment creation
  - [ ] Ensure extension specs are passed to template factory
  - [ ] Update extension template discovery
  - [ ] Test extension template isolation

### Security Testing
- [ ] **XSS Prevention Tests**
  - [ ] `test_xss_script_tag_escaping()` - Basic `<script>` tag escaping
  - [ ] `test_xss_event_handler_escaping()` - Event handlers like `onload=`
  - [ ] `test_xss_javascript_url_escaping()` - `javascript:` URLs
  - [ ] `test_xss_html_entity_escaping()` - HTML entities and Unicode
  - [ ] `test_xss_css_injection_escaping()` - CSS injection via style attributes

- [ ] **Template Context Security**
  - [ ] `test_error_page_path_escaping()` - Request paths in error pages
  - [ ] `test_form_data_escaping()` - User form input redisplay
  - [ ] `test_query_parameter_escaping()` - URL query parameters
  - [ ] `test_header_value_escaping()` - HTTP header values in templates
  - [ ] `test_none_value_handling()` - None/null values in context

- [ ] **Safe Content Tests**
  - [ ] `test_safe_filter_allows_html()` - `|safe` filter functionality
  - [ ] `test_markdown_to_html_safe()` - Markdown rendering with `|safe`
  - [ ] `test_trusted_admin_content()` - Admin-generated HTML content
  - [ ] `test_intentional_html_rendering()` - Legitimate HTML use cases

### Functional Testing
- [ ] **Template Resolution Tests**
  - [ ] `test_app_template_resolution_order()` - `./templates/` before `serv/templates/`
  - [ ] `test_extension_template_resolution_order()` - Override before extension
  - [ ] `test_missing_template_directory()` - Graceful handling of missing dirs
  - [ ] `test_template_override_behavior()` - Local templates override bundled
  - [ ] `test_multiple_extension_isolation()` - Extensions can't access each other's templates

- [ ] **Environment Isolation Tests**  
  - [ ] `test_extension_environment_caching()` - Same extension gets same environment
  - [ ] `test_app_environment_singleton()` - App environment is singleton
  - [ ] `test_extension_context_isolation()` - Extensions can't access other contexts
  - [ ] `test_template_variable_scoping()` - Proper variable scoping per environment
  - [ ] `test_custom_filter_isolation()` - Custom filters don't leak between environments

- [ ] **Async Rendering Tests**
  - [ ] `test_async_template_generation()` - AsyncGenerator functionality
  - [ ] `test_large_template_streaming()` - Large template streaming performance
  - [ ] `test_concurrent_template_rendering()` - Multiple simultaneous renders
  - [ ] `test_async_context_variables()` - Async context variable resolution
  - [ ] `test_template_rendering_cancellation()` - Proper cleanup on cancellation

### Performance & Reliability
- [ ] **Performance Tests**
  - [ ] `test_environment_creation_performance()` - Environment creation speed
  - [ ] `test_template_caching_effectiveness()` - Template compilation caching
  - [ ] `test_concurrent_access_performance()` - Multi-threaded access performance
  - [ ] `test_memory_usage_under_load()` - Memory usage with many extensions
  - [ ] `test_template_rendering_throughput()` - Rendering throughput benchmarks

- [ ] **Error Handling Tests**
  - [ ] `test_template_not_found_handling()` - Missing template graceful failure
  - [ ] `test_template_syntax_error_handling()` - Jinja2 syntax error handling
  - [ ] `test_template_context_error_handling()` - Runtime context errors
  - [ ] `test_filesystem_permission_errors()` - File permission error handling
  - [ ] `test_malformed_template_directory()` - Invalid template directory handling

- [ ] **Resource Management Tests**
  - [ ] `test_environment_cleanup_on_shutdown()` - Proper cleanup when app shuts down
  - [ ] `test_template_loader_resource_cleanup()` - FileSystemLoader cleanup
  - [ ] `test_memory_leak_prevention()` - No memory leaks in long-running apps
  - [ ] `test_file_handle_management()` - Proper file handle cleanup
  - [ ] `test_thread_safety_under_load()` - Thread safety with heavy concurrent use

### Integration Testing
- [ ] **End-to-End Template Flows**
  - [ ] `test_e2e_extension_template_rendering()` - Full extension template flow
  - [ ] `test_e2e_error_page_rendering()` - Complete error page flow
  - [ ] `test_e2e_template_override_workflow()` - Template override end-to-end
  - [ ] `test_e2e_multiple_extensions_templates()` - Multiple extensions with templates
  - [ ] `test_e2e_app_and_extension_templates()` - Mixed app and extension templates

- [ ] **CLI Integration Tests**
  - [ ] `test_cli_extension_with_templates()` - CLI-created extensions work with templates
  - [ ] `test_cli_template_directory_creation()` - CLI creates proper template structure
  - [ ] `test_cli_template_scaffolding()` - Generated templates use new system
  - [ ] `test_cli_extension_template_validation()` - CLI validates template structure

### Backwards Compatibility Validation
- [ ] **Breaking Change Documentation**
  - [ ] Document all breaking changes in upgrade guide
  - [ ] Provide migration examples for common template patterns
  - [ ] Create automated migration script for common cases
  - [ ] Add warnings for deprecated template patterns

- [ ] **Migration Testing**
  - [ ] `test_existing_templates_with_autoescape()` - Existing templates still render
  - [ ] `test_migration_from_old_system()` - Migration path validation
  - [ ] `test_template_compatibility_warnings()` - Proper warnings for breaking changes
  - [ ] `test_safe_filter_migration()` - Templates requiring `|safe` identified

### Documentation & Examples
- [ ] **Documentation Updates**
  - [ ] Update template system documentation
  - [ ] Add security best practices guide
  - [ ] Create template override examples
  - [ ] Document auto-escaping behavior and `|safe` usage
  - [ ] Add performance considerations guide

- [ ] **Example Templates**
  - [ ] Create secure template examples for common patterns
  - [ ] Add example of template override structure
  - [ ] Provide XSS-safe form templates
  - [ ] Create examples for rich content with sanitization

This comprehensive checklist ensures the template system overhaul addresses all XSS vulnerabilities while providing a robust, secure, and performant foundation for template rendering in the Serv framework.