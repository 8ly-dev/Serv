# XSS Vulnerabilities in Template Rendering

## Problem Description

The Serv framework is vulnerable to Cross-Site Scripting (XSS) attacks through template rendering. Error templates and potentially user templates render user-controlled input without proper escaping, allowing attackers to inject malicious JavaScript.

### Current Vulnerable Code

**File**: `serv/templates/error/500.html`
```html
<h1>Internal Server Error</h1>
<p>Error: {{ error_str }}</p>         <!-- UNESCAPED - XSS RISK -->
<p>Path: {{ request_path }}</p>       <!-- UNESCAPED - XSS RISK -->

<div class="traceback">
    <pre>{{ traceback }}</pre>        <!-- UNESCAPED - XSS RISK -->
</div>
```

**File**: `serv/routes.py` (lines 182-191)
```python
class Jinja2Response(Response):
    def render(self) -> AsyncGenerator[str, object]:
        from jinja2 import Environment, FileSystemLoader
        
        # Auto-escaping is NOT enabled by default!
        env = Environment(
            loader=FileSystemLoader(template_locations), 
            enable_async=True
            # Missing: autoescape=True
        )
        template = env.get_template(self.template)
        return template.generate_async(**self.context)
```

### Attack Scenarios

1. **Error Page XSS**: Attacker crafts URL that causes error with malicious path:
   ```
   GET /../../<script>alert('XSS')</script>
   ```
   Results in error page displaying: `Path: /../../<script>alert('XSS')</script>`

2. **Template Context XSS**: User-provided data in template context gets rendered without escaping:
   ```python
   # Vulnerable route handler
   async def handle_get(self, name: str) -> Annotated[str, Jinja2Response]:
       return Jinja2Response("profile.html", {"name": name})  # XSS if name contains <script>
   ```

3. **Form Data XSS**: Form submissions that redisplay data without escaping:
   ```html
   <!-- If comment contains <script>, it executes -->
   <p>Your comment: {{ comment }}</p>
   ```

## Impact Assessment

- **Severity**: 🔴 **HIGH**
- **CVSS Score**: 8.1 (High)
- **Attack Vector**: Network (via crafted requests)
- **Impact**: Client-side code execution, session hijacking, data theft
- **Affected Components**: All template rendering, error pages

## Recommendations

### Option 1: Enable Auto-Escaping Globally (Recommended)
**Effort**: Low | **Impact**: High

Enable Jinja2 auto-escaping by default for all templates:

```python
class Jinja2Response(Response):
    def render(self) -> AsyncGenerator[str, object]:
        from jinja2 import Environment, FileSystemLoader
        
        env = Environment(
            loader=FileSystemLoader(template_locations),
            enable_async=True,
            autoescape=True  # SECURITY: Enable auto-escaping
        )
        template = env.get_template(self.template)
        return template.generate_async(**self.context)
```

### Option 2: Implement Secure Template Factory
**Effort**: Medium | **Impact**: High

Create a centralized template factory with security defaults:

```python
class SecureTemplateEngine:
    def __init__(self, template_dirs: list[Path]):
        self.env = Environment(
            loader=FileSystemLoader(template_dirs),
            enable_async=True,
            autoescape=select_autoescape(['html', 'xml']),  # Smart auto-escaping
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add security filters
        self.env.filters['safe_html'] = self._safe_html_filter
        
    def _safe_html_filter(self, value: str) -> str:
        """Custom filter for HTML sanitization."""
        import bleach
        return bleach.clean(value, tags=['b', 'i', 'em', 'strong'])
```

### Option 3: Template Security Middleware
**Effort**: High | **Impact**: High

Add middleware that validates and sanitizes template context:

```python
class TemplateSanitizationMiddleware:
    async def __call__(self, request, call_next):
        response = await call_next(request)
        
        if isinstance(response, Jinja2Response):
            response.context = self._sanitize_context(response.context)
        
        return response
    
    def _sanitize_context(self, context: dict) -> dict:
        """Recursively sanitize template context."""
        sanitized = {}
        for key, value in context.items():
            if isinstance(value, str):
                sanitized[key] = escape(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_context(value)
            else:
                sanitized[key] = value
        return sanitized
```

## Action Checklist

### Phase 1: Immediate XSS Prevention (Week 1)
- [ ] Enable Jinja2 auto-escaping in `Jinja2Response` class
- [ ] Update all error templates to use proper escaping
- [ ] Add CSP headers to all responses
- [ ] Implement HTML entity escaping for user input

### Phase 2: Enhanced Template Security (Week 1)
- [ ] Create secure template engine factory
- [ ] Add HTML sanitization for rich content
- [ ] Implement template security middleware
- [ ] Add template context validation

### Phase 3: Security Headers & Policies (Week 2)
- [ ] Implement Content Security Policy (CSP)
- [ ] Add X-XSS-Protection headers
- [ ] Add X-Content-Type-Options: nosniff
- [ ] Add X-Frame-Options: DENY

### Code Changes Required

1. **Modified Files**:
   ```
   serv/routes.py                    # Enable auto-escaping
   serv/templates/error/*.html       # Fix unescaped variables  
   serv/responses.py                 # Add security headers
   serv/app.py                       # Update error handling
   ```

2. **New Files**:
   ```
   serv/security/__init__.py         # Security utilities
   serv/security/templates.py        # Secure template engine
   serv/security/headers.py          # Security headers middleware
   tests/security/test_xss.py        # XSS protection tests
   ```

### Template Updates

**Before** (vulnerable):
```html
<h1>Welcome {{ user.name }}</h1>
<p>Path: {{ request.path }}</p>
<div>{{ user.bio }}</div>
```

**After** (secure):
```html
<h1>Welcome {{ user.name|e }}</h1>                    <!-- Manual escaping -->
<p>Path: {{ request.path|e }}</p>                     <!-- Manual escaping -->
<div>{{ user.bio|safe_html }}</div>                   <!-- Rich content sanitization -->
```

Or with auto-escaping enabled:
```html
<h1>Welcome {{ user.name }}</h1>                      <!-- Auto-escaped -->
<p>Path: {{ request.path }}</p>                       <!-- Auto-escaped -->
<div>{{ user.bio|safe }}</div>                        <!-- Explicitly safe content -->
```

### Security Headers Implementation

```python
class SecurityHeadersMiddleware:
    async def __call__(self, request, call_next):
        response = await call_next(request)
        
        # Add security headers
        response.headers.update({
            'Content-Security-Policy': "default-src 'self'",
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
        })
        
        return response
```

### Testing Strategy

```python
def test_xss_prevention_in_templates():
    """Test that templates properly escape XSS payloads."""
    xss_payload = "<script>alert('XSS')</script>"
    
    response = client.get(f"/profile?name={xss_payload}")
    
    # Should be escaped
    assert "&lt;script&gt;" in response.text
    assert "<script>" not in response.text

def test_error_page_xss_prevention():
    """Test that error pages don't execute JavaScript from URLs."""
    xss_path = "/<script>alert('XSS')</script>"
    
    response = client.get(xss_path)
    
    assert response.status_code == 404
    assert "&lt;script&gt;" in response.text
    assert "<script>" not in response.text

def test_csp_headers_present():
    """Test that CSP headers are set."""
    response = client.get("/")
    
    assert "Content-Security-Policy" in response.headers
    assert "X-XSS-Protection" in response.headers
```

### Configuration Updates

Add security configuration to `serv.config.yaml`:
```yaml
security:
  templates:
    auto_escape: true
    allowed_tags: ['b', 'i', 'em', 'strong', 'p', 'br']
  headers:
    csp: "default-src 'self'; script-src 'self'"
    frame_options: "DENY"
    content_type_options: "nosniff"
```

### Backwards Compatibility

This change may break templates that rely on unescaped HTML. Provide migration path:

1. **Gradual Migration**: Add configuration flag to disable auto-escaping temporarily
2. **Template Audit Tool**: Create tool to scan templates for potential XSS issues
3. **Migration Guide**: Document how to update templates for auto-escaping

### Performance Considerations

- Auto-escaping adds minimal overhead (~1-2% template rendering time)
- HTML sanitization is more expensive - use only where needed
- Consider caching sanitized content for frequently rendered templates