# Missing Security Headers

## Problem Description

The Serv framework does not set essential security headers by default, leaving applications vulnerable to various attacks including clickjacking, content sniffing attacks, and missing HTTPS enforcement. Modern web applications require security headers to protect against common attack vectors.

### Current State

**No Security Headers Set**: The framework's response classes don't include any security headers by default:

```python
# serv/responses.py - No security headers
class Response:
    def __init__(self, status_code: int, body: str | bytes | None = None, 
                 headers: dict[str, str] | None = None):
        self.headers = headers or {}  # Empty by default
```

**Missing Critical Headers**:
- No Content Security Policy (CSP)
- No X-Frame-Options (clickjacking protection)  
- No X-Content-Type-Options (MIME sniffing protection)
- No Strict-Transport-Security (HTTPS enforcement)
- No Referrer-Policy (referrer leakage protection)

## Impact Assessment

- **Severity**: 🟡 **MEDIUM**
- **CVSS Score**: 6.1 (Medium)
- **Attack Vector**: Network
- **Impact**: Clickjacking, content sniffing, HTTPS downgrade attacks
- **Affected Components**: All HTTP responses

## Recommendations

### Option 1: Security Headers Middleware (Recommended)
**Effort**: Low | **Impact**: High

```python
class SecurityHeadersMiddleware:
    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig()
    
    async def __call__(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': self.config.frame_options,
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': self.config.referrer_policy,
            'Content-Security-Policy': self.config.csp_policy,
        }
        
        # Add HSTS only for HTTPS
        if request.url.scheme == 'https':
            security_headers['Strict-Transport-Security'] = f'max-age={self.config.hsts_max_age}; includeSubDomains'
        
        response.headers.update(security_headers)
        return response
```

## Action Checklist

### Phase 1: Basic Security Headers (Week 1)
- [ ] Create SecurityHeadersMiddleware
- [ ] Add default security headers configuration
- [ ] Implement CSP policy builder
- [ ] Add HSTS support for HTTPS

### Phase 2: Advanced Configuration (Week 1)
- [ ] Add environment-specific header configs
- [ ] Create CSP violation reporting
- [ ] Add header customization per route
- [ ] Implement security header testing

### Code Changes Required

```python
# serv/security/headers.py
class SecurityConfig:
    frame_options: str = "DENY"
    csp_policy: str = "default-src 'self'"
    referrer_policy: str = "strict-origin-when-cross-origin" 
    hsts_max_age: int = 31536000  # 1 year

# Add to App class
app.add_middleware(SecurityHeadersMiddleware())
```

### Testing Strategy

```python
def test_security_headers_present():
    response = client.get("/")
    assert "X-Content-Type-Options" in response.headers
    assert "X-Frame-Options" in response.headers
    assert "Content-Security-Policy" in response.headers
```