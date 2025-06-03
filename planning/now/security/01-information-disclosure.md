# Configurable Error Detail Levels for Secure Error Handling

## Current Issue

The Serv framework's error handling system currently exposes dangerous levels of detail by default, including stack traces, file paths, and implementation details. This creates information disclosure vulnerabilities where even development mode settings can expose sensitive information if accidentally used in production.

**Current vulnerable code in `serv/app.py`:**
```python
async def _internal_error_handler(self, request: Request, error: Exception) -> Response:
    if self.dev_mode:
        # Exposes sensitive information!
        full_traceback = "".join(traceback.format_exception(error))
        context = {
            "error_str": str(error),
            "traceback": full_traceback,  # SECURITY RISK
            "request_path": request.path,  # Potential XSS + info disclosure
            "app_name": self.name,
        }
        return HtmlResponse(await self._render_template("error/500.html", context), status_code=500)
```

The fundamental problem is that the current binary `dev_mode` setting makes it too easy to accidentally expose dangerous error details in production environments.

## Desired Solution

Implement a configurable error detail level system with the following design principles:

1. **Safe defaults**: Default error output should be safe even if accidentally enabled in production
2. **Granular control**: Multiple levels of error detail exposure
3. **CLI integration**: Development CLI should use safe defaults with explicit flags for more detail
4. **No backwards compatibility**: Clean break from the current unsafe system

### Error Detail Levels

```python
class ErrorDetailLevel(Enum):
    NONE = "none"           # Generic error page only
    MINIMAL = "minimal"     # Error ID and basic message
    BASIC = "basic"         # Error type and sanitized message  
    DETAILED = "detailed"   # Full stack trace (dev use only)
```

### Default Behavior

- **Production default**: `NONE` - Only shows generic error page
- **Development CLI default**: `MINIMAL` - Shows error ID and basic message (safe for accidental production use)
- **Explicit override**: CLI flag `--error-detail=detailed` to enable full stack traces when needed

## Implementation Plan

### 1. Core Error Handling System

Update `serv/app.py` to implement configurable error detail levels:

```python
class App:
    def __init__(self, error_detail_level: ErrorDetailLevel = ErrorDetailLevel.NONE):
        self.error_detail_level = error_detail_level
    
    async def _internal_error_handler(self, request: Request, error: Exception) -> Response:
        # Always log full details for debugging
        error_id = str(uuid.uuid4())
        logger.error(f"Error {error_id}: {error}", exc_info=True)
        
        # Determine response content based on detail level
        if self.error_detail_level == ErrorDetailLevel.NONE:
            context = {"error_id": error_id}
            template = "error/500-generic.html"
        elif self.error_detail_level == ErrorDetailLevel.MINIMAL:
            context = {"error_id": error_id, "error_type": type(error).__name__}
            template = "error/500-minimal.html"
        elif self.error_detail_level == ErrorDetailLevel.BASIC:
            context = {
                "error_id": error_id,
                "error_type": type(error).__name__,
                "error_message": self._sanitize_error_message(str(error))
            }
            template = "error/500-basic.html"
        else:  # DETAILED
            context = {
                "error_id": error_id,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "traceback": "".join(traceback.format_exception(error)),
                "request_path": escape(request.path)
            }
            template = "error/500-detailed.html"
            
        return HtmlResponse(await self._render_template(template, context), status_code=500)
```

### 2. CLI Integration

Update `serv/cli.py` to use safe defaults with explicit override:

```python
def add_launch_command(parser):
    launch_parser = parser.add_parser("launch")
    launch_parser.add_argument(
        "--error-detail",
        choices=["none", "minimal", "basic", "detailed"],
        default="minimal",  # Safe default for development
        help="Error detail level (default: minimal)"
    )
    launch_parser.add_argument(
        "--debug-errors",
        action="store_true",
        help="Shortcut for --error-detail=detailed"
    )
```

### 3. Configuration System

Add error detail configuration to `serv/config.py`:

```python
@dataclass
class ServConfig:
    error_detail_level: ErrorDetailLevel = ErrorDetailLevel.NONE
    # Remove dev_mode completely - replaced by explicit error detail control
```

### 4. Template Updates

Create separate error templates for each detail level:
- `serv/templates/error/500-generic.html` - Basic "something went wrong" page
- `serv/templates/error/500-minimal.html` - Error ID and type
- `serv/templates/error/500-basic.html` - Sanitized error message
- `serv/templates/error/500-detailed.html` - Full debugging information

## Action Checklist

### Phase 1: Core Implementation
- [ ] Remove `dev_mode` parameter from App class
- [ ] Implement `ErrorDetailLevel` enum in `serv/exceptions.py`
- [ ] Update `App.__init__()` to accept `error_detail_level` parameter
- [ ] Rewrite `_internal_error_handler()` method with new logic
- [ ] Add `_sanitize_error_message()` method to remove sensitive paths/data
- [ ] Create four new error templates with appropriate detail levels
- [ ] Remove existing `serv/templates/error/500.html`

### Phase 2: CLI Integration
- [ ] Update CLI launch command to include `--error-detail` flag
- [ ] Add `--debug-errors` shortcut flag for `--error-detail=detailed`
- [ ] Set default CLI error detail level to "minimal"
- [ ] Update CLI help text and documentation
- [ ] Remove all references to `dev_mode` from CLI

### Phase 3: Configuration Updates
- [ ] Remove `dev_mode` from `ServConfig` dataclass
- [ ] Add `error_detail_level` to configuration schema
- [ ] Update default configuration files to use `ErrorDetailLevel.NONE`
- [ ] Update configuration validation and parsing

### Phase 4: Testing & Validation
- [ ] Write security tests for each error detail level
- [ ] Test CLI flag behavior and defaults
- [ ] Verify no sensitive information leaks in "minimal" mode
- [ ] Test error ID generation and logging
- [ ] Add integration tests for error handling

### Phase 5: Documentation Updates
- [ ] Update all documentation to remove `dev_mode` references
- [ ] Document new error detail level system
- [ ] Add security guidance for error detail levels
- [ ] Update CLI reference documentation
- [ ] Create migration guide for existing applications

### Files to Modify
1. `serv/app.py` - Complete rewrite of error handling
2. `serv/exceptions.py` - Add ErrorDetailLevel enum
3. `serv/config.py` - Remove dev_mode, add error_detail_level
4. `serv/cli.py` - Update launch command arguments
5. `serv/templates/error/` - Replace existing templates with new ones
6. `tests/` - Update all tests that reference dev_mode
7. `docs/` - Update documentation

### Breaking Changes
- **No backwards compatibility support** - `dev_mode` parameter removed entirely
- Applications must explicitly set error detail levels
- Default behavior is more secure (no error details by default)
- CLI behavior changes - development mode is now "minimal" by default