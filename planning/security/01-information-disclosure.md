# Information Disclosure in Error Handling

## Problem Description

The Serv framework exposes detailed error information including stack traces, file paths, and variable values in production environments when `dev_mode=True`. This creates a significant security vulnerability where attackers can gather sensitive information about the system architecture and implementation details.

### Current Vulnerable Code

**File**: `serv/app.py` (lines 608-699)
```python
async def _internal_error_handler(self, request: Request, error: Exception) -> Response:
    if self.dev_mode:
        # This exposes sensitive information in production!
        full_traceback = "".join(traceback.format_exception(error))
        
        context = {
            "error_str": str(error),
            "traceback": full_traceback,  # SECURITY RISK
            "request_path": request.path,  # Potential XSS + info disclosure
            "app_name": self.name,
        }
        
        return HtmlResponse(
            await self._render_template("error/500.html", context),
            status_code=500,
        )
```

**File**: `serv/templates/error/500.html`
```html
<div class="traceback">
    <pre>{{ traceback }}</pre>  <!-- Raw traceback exposed -->
</div>
<p>Error: {{ error_str }}</p>   <!-- Unescaped error message -->
<p>Path: {{ request_path }}</p>  <!-- Potential XSS vector -->
```

### Attack Scenarios

1. **Information Gathering**: Attackers can trigger errors to learn:
   - Internal file structure and paths
   - Python module names and versions
   - Database connection details in stack traces
   - Environment variables in error contexts

2. **Configuration Discovery**: Error messages reveal:
   - Framework internals and implementation details
   - Extension loading paths and structures
   - Development vs production environment details

## Impact Assessment

- **Severity**: 🔴 **HIGH**
- **CVSS Score**: 7.5 (High)
- **Attack Vector**: Network
- **Impact**: Information disclosure leading to further attacks
- **Affected Components**: All error handling, template rendering

## Recommendations

### Option 1: Conditional Error Detail Exposure (Recommended)
**Effort**: Medium | **Impact**: High

Create separate error handling for development vs production:

```python
async def _internal_error_handler(self, request: Request, error: Exception) -> Response:
    # Always log detailed errors for debugging
    logger.error(f"Internal error on {request.path}: {error}", exc_info=True)
    
    if self.dev_mode and self._should_expose_errors(request):
        # Detailed errors only in development
        context = {
            "error_str": str(error),
            "traceback": "".join(traceback.format_exception(error)),
            "request_path": escape(request.path),  # XSS protection
            "app_name": self.name,
        }
        template = "error/500-dev.html"
    else:
        # Generic error in production
        context = {
            "error_id": self._generate_error_id(),
            "app_name": self.name,
        }
        template = "error/500-prod.html"
    
    return HtmlResponse(
        await self._render_template(template, context),
        status_code=500,
    )
```

### Option 2: Configurable Error Detail Levels
**Effort**: High | **Impact**: High

Add granular error reporting configuration:

```python
class ErrorDetailLevel(Enum):
    NONE = "none"           # No error details
    MINIMAL = "minimal"     # Error ID only
    BASIC = "basic"         # Error type and message
    DETAILED = "detailed"   # Full stack trace

class AppConfig:
    error_detail_level: ErrorDetailLevel = ErrorDetailLevel.NONE
    error_detail_ip_allowlist: list[str] = []
```

### Option 3: Error ID System
**Effort**: Low | **Impact**: Medium

Replace error details with error IDs that map to logged details:

```python
def _handle_error(self, error: Exception) -> str:
    error_id = str(uuid.uuid4())
    logger.error(f"Error {error_id}: {error}", exc_info=True)
    return error_id
```

## Action Checklist

### Phase 1: Immediate Fix (Week 1)
- [ ] Create production-safe error templates
- [ ] Implement error ID generation system
- [ ] Add error detail level configuration
- [ ] Update error handler to use conditional logic
- [ ] Add proper HTML escaping for all template variables

### Phase 2: Enhanced Security (Week 2)
- [ ] Implement IP allowlist for detailed errors
- [ ] Add error logging with structured data
- [ ] Create error monitoring dashboard
- [ ] Add rate limiting for error pages

### Phase 3: Testing & Documentation (Week 3)
- [ ] Write security tests for error handling
- [ ] Document secure error handling practices
- [ ] Add penetration testing for information disclosure
- [ ] Create deployment guide for production security

### Code Changes Required

1. **New Files**:
   - `serv/templates/error/500-prod.html` (generic error page)
   - `serv/security/error_handler.py` (secure error handling)
   - `tests/security/test_error_disclosure.py` (security tests)

2. **Modified Files**:
   - `serv/app.py` (update error handler)
   - `serv/config.py` (add error configuration)
   - `serv/templates/error/500.html` (rename to 500-dev.html)

3. **Configuration**:
   - Add `error_detail_level` to default config
   - Document security configuration options

### Testing Strategy

```python
def test_production_error_no_disclosure():
    """Ensure production errors don't expose sensitive info."""
    app = App(dev_mode=False)
    
    # Trigger internal error
    response = client.get("/trigger-error")
    
    assert response.status_code == 500
    assert "traceback" not in response.text.lower()
    assert "file" not in response.text.lower()
    assert "error id" in response.text.lower()

def test_dev_mode_error_disclosure():
    """Ensure dev mode still shows helpful errors."""
    app = App(dev_mode=True)
    
    response = client.get("/trigger-error")
    
    assert response.status_code == 500
    assert "traceback" in response.text.lower()
    # But ensure XSS protection
    assert "&lt;" in response.text or "escaped" in response.text
```

### Security Considerations

- Never log sensitive data even in development
- Implement proper log rotation and retention
- Consider using structured logging for error analysis
- Add monitoring alerts for unusual error patterns
- Ensure error IDs are not predictable (use UUIDs)

### Backwards Compatibility

This change is not backwards compatible as it changes error page content. Consider:
- Adding configuration to maintain old behavior temporarily
- Documenting the security implications of the old behavior
- Providing migration guide for custom error templates