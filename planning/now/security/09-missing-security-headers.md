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

### Option 1: Automatic Security Headers Middleware (Recommended)
**Effort**: Low | **Impact**: High

Security headers should be **automatically enabled by default** with strict secure defaults. A global flag can disable them when necessary (e.g., for development or legacy compatibility).

```python
class SecurityHeadersMiddleware:
    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig.get_strict_defaults()
    
    async def __call__(self, request: Request, call_next):
        response = await call_next(request)
        
        # Skip if globally disabled
        if self.config.disabled:
            return response
            
        # Add security headers with strict defaults
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

### Configuration in serv.config.yaml

```yaml
security:
  headers:
    enabled: true  # Default: true (automatic)
    warn_on_unsafe: true  # Default: true (warn for unsafe settings)
    
    # Strict secure defaults
    frame_options: "DENY"  # Default: DENY
    csp_policy: "default-src 'self'"  # Default: strict
    referrer_policy: "strict-origin-when-cross-origin"  # Default: strict
    hsts_max_age: 31536000  # Default: 1 year
    
    # Global disable flag (use with caution)
    disabled: false  # Default: false
```

### Warnings for Unsafe Settings

The framework should log warnings when unsafe configurations are detected:

```python
# Warn on unsafe settings
if config.frame_options in ["ALLOWALL", "SAMEORIGIN"]:
    logger.warning("Unsafe X-Frame-Options setting detected. Consider using DENY for maximum protection.")

if "unsafe-inline" in config.csp_policy:
    logger.warning("CSP contains 'unsafe-inline' which reduces XSS protection.")
```

## Action Checklist

### Phase 1: Automatic Security Headers (Week 1)
- [ ] Create SecurityHeadersMiddleware with automatic defaults
- [ ] Add security configuration section to serv.config.yaml schema
- [ ] Implement SecurityConfig with strict defaults
- [ ] Add automatic middleware registration in App class
- [ ] Implement warning system for unsafe configurations

### Phase 2: Advanced Security Features (Week 1)
- [ ] Add environment-specific header configs
- [ ] Create CSP violation reporting
- [ ] Add per-route header customization override
- [ ] Implement comprehensive security header testing

### Code Changes Required

```python
# serv/security/headers.py
class SecurityConfig:
    # Automatic defaults - security by default
    enabled: bool = True
    disabled: bool = False  # Global disable flag
    warn_on_unsafe: bool = True
    
    # Strict secure defaults
    frame_options: str = "DENY"
    csp_policy: str = "default-src 'self'"
    referrer_policy: str = "strict-origin-when-cross-origin" 
    hsts_max_age: int = 31536000  # 1 year
    
    @classmethod
    def get_strict_defaults(cls):
        return cls()

# serv/app.py - Automatic registration
class App:
    def __init__(self, config: AppConfig):
        # Security headers automatically enabled
        security_config = config.security.headers if config.security else SecurityConfig()
        self.add_middleware(SecurityHeadersMiddleware(security_config))

# serv/config.py - Add security section
class AppConfig:
    security: SecuritySectionConfig | None = None
```

### Testing Strategy

```python
def test_security_headers_automatically_enabled():
    """Test that security headers are present by default"""
    response = client.get("/")
    assert "X-Content-Type-Options" in response.headers
    assert "X-Frame-Options" in response.headers
    assert "Content-Security-Policy" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"  # Strict default

def test_security_headers_can_be_disabled():
    """Test global disable flag works"""
    app_config = AppConfig()
    app_config.security.headers.disabled = True
    
    client = create_test_client(app_config)
    response = client.get("/")
    assert "X-Frame-Options" not in response.headers

def test_unsafe_configuration_warnings():
    """Test warnings are logged for unsafe settings"""
    with pytest.warns(UserWarning, match="Unsafe X-Frame-Options"):
        config = SecurityConfig()
        config.frame_options = "ALLOWALL"
        SecurityHeadersMiddleware(config)
```