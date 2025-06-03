# Missing Authentication and Session Management

## Problem Description

The Serv framework lacks a built-in authentication and session management system, leaving developers to implement their own solutions without security guidance. This creates risks of insecure implementations, session hijacking, CSRF attacks, and poor password handling practices.

### Current State Analysis

**No Built-in Authentication Framework**:
- No session management utilities
- No CSRF protection
- No secure cookie handling
- No password hashing utilities
- No authentication decorators or middleware

**Security Risks in Current Approach**:
```python
# Developers might implement insecure patterns like:
class LoginRoute(Route):
    async def handle_post(self, request: PostRequest) -> Response:
        username = request.form.get('username')
        password = request.form.get('password')
        
        # SECURITY ISSUES:
        # 1. No CSRF protection
        # 2. No rate limiting
        # 3. No secure password comparison
        # 4. No session management
        if self.check_password(username, password):  # Timing attack vulnerable
            # Insecure session creation
            response = JsonResponse({'status': 'success'})
            response.set_cookie('user_id', str(user.id))  # Not secure!
            return response
```

### Common Insecure Patterns

1. **Plain Text Passwords**: No guidance leads to poor password storage
2. **Insecure Sessions**: Raw cookies without security flags
3. **No CSRF Protection**: Forms vulnerable to cross-site request forgery
4. **Timing Attacks**: Direct string comparison for passwords
5. **Session Fixation**: No session regeneration after login

## Impact Assessment

- **Severity**: 🔴 **HIGH**
- **CVSS Score**: 8.5 (High)
- **Attack Vector**: Network
- **Impact**: Authentication bypass, session hijacking, data breach
- **Affected Components**: All applications requiring authentication

## Recommendations

### Option 1: Comprehensive Authentication Framework (Recommended)
**Effort**: High | **Impact**: Critical

Build a complete authentication system with secure defaults:

```python
from serv.auth import AuthManager, SessionManager, PasswordManager
from serv.security import CSRFProtection, RateLimiter

class AuthConfig:
    secret_key: str
    session_lifetime: timedelta = timedelta(hours=24)
    csrf_protection: bool = True
    rate_limiting: bool = True
    secure_cookies: bool = True
    password_min_length: int = 8

class AuthManager:
    def __init__(self, config: AuthConfig):
        self.config = config
        self.session_manager = SessionManager(config)
        self.password_manager = PasswordManager()
        self.csrf = CSRFProtection(config.secret_key)
    
    def hash_password(self, password: str) -> str:
        """Securely hash password using Argon2."""
        return self.password_manager.hash_password(password)
    
    def verify_password(self, password: str, hash: str) -> bool:
        """Verify password with timing attack protection."""
        return self.password_manager.verify_password(password, hash)
    
    def create_session(self, user_id: str, request: Request) -> str:
        """Create secure session with CSRF token."""
        session_id = self.session_manager.create_session(user_id)
        csrf_token = self.csrf.generate_token(session_id)
        return session_id, csrf_token
    
    def authenticate_request(self, request: Request) -> User | None:
        """Authenticate request using session."""
        session_id = self._extract_session_id(request)
        if not session_id:
            return None
        
        return self.session_manager.get_user_from_session(session_id)

# Secure authentication decorators
def require_auth(handler):
    """Decorator requiring authentication."""
    async def wrapper(self, request: Request, auth: AuthManager = dependency()):
        user = auth.authenticate_request(request)
        if not user:
            return RedirectResponse('/login')
        
        return await handler(self, request, user)
    return wrapper

def require_csrf(handler):
    """Decorator requiring CSRF token."""
    async def wrapper(self, request: Request, auth: AuthManager = dependency()):
        if not auth.csrf.verify_token(request):
            raise CSRFError("Invalid CSRF token")
        
        return await handler(self, request)
    return wrapper
```

### Option 2: Session-Only Framework
**Effort**: Medium | **Impact**: High

Implement just session management with secure defaults:

```python
class SecureSessionManager:
    def __init__(self, secret_key: str, secure: bool = True):
        self.secret_key = secret_key
        self.secure = secure
        self.sessions: dict[str, SessionData] = {}
    
    def create_session(self, user_data: dict) -> str:
        """Create cryptographically secure session."""
        session_id = secrets.token_urlsafe(32)
        session_data = SessionData(
            id=session_id,
            data=user_data,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        
        self.sessions[session_id] = session_data
        return session_id
    
    def create_session_cookie(self, session_id: str) -> str:
        """Create secure session cookie."""
        # Sign the session ID to prevent tampering
        signer = itsdangerous.TimestampSigner(self.secret_key)
        signed_session = signer.sign(session_id)
        
        cookie_options = {
            'httponly': True,      # Prevent XSS
            'secure': self.secure, # HTTPS only
            'samesite': 'Strict',  # CSRF protection
            'max_age': 86400       # 24 hours
        }
        
        return signed_session, cookie_options
```

### Option 3: Authentication Middleware
**Effort**: Low | **Impact**: Medium

Provide authentication middleware that developers can customize:

```python
class AuthenticationMiddleware:
    def __init__(self, authenticator: Callable[[Request], User | None]):
        self.authenticator = authenticator
    
    async def __call__(self, request: Request, call_next):
        # Add user to request if authenticated
        user = await self.authenticator(request)
        request.state.user = user
        
        response = await call_next(request)
        
        # Add security headers
        if not user and request.url.path.startswith('/admin'):
            return RedirectResponse('/login')
        
        return response

# Usage example
def jwt_authenticator(request: Request) -> User | None:
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return get_user_by_id(payload['user_id'])
    except jwt.InvalidTokenError:
        return None

app.add_middleware(AuthenticationMiddleware(jwt_authenticator))
```

## Action Checklist

### Phase 1: Core Authentication Framework (Week 1-2)
- [ ] Create secure password hashing utilities (Argon2/bcrypt)
- [ ] Implement secure session management
- [ ] Add CSRF protection framework
- [ ] Create authentication decorators

### Phase 2: Session Security (Week 2)
- [ ] Implement secure cookie handling
- [ ] Add session regeneration on login
- [ ] Create session cleanup/expiration
- [ ] Add rate limiting for authentication attempts

### Phase 3: Advanced Features (Week 3)
- [ ] Add two-factor authentication support
- [ ] Implement remember me functionality
- [ ] Create password reset workflow
- [ ] Add OAuth2/OpenID Connect support

### Phase 4: Integration & Documentation (Week 4)
- [ ] Create authentication middleware
- [ ] Add integration with existing request/response system
- [ ] Write comprehensive authentication guide
- [ ] Create example applications

### Code Changes Required

1. **New Authentication Module**:
   ```
   serv/auth/
   ├── __init__.py
   ├── manager.py          # Main AuthManager
   ├── sessions.py         # Session management
   ├── passwords.py        # Password hashing
   ├── csrf.py            # CSRF protection
   ├── decorators.py      # Authentication decorators
   └── middleware.py      # Authentication middleware
   ```

2. **Security Utilities**:
   ```
   serv/security/
   ├── __init__.py
   ├── cookies.py         # Secure cookie utilities
   ├── tokens.py          # Token generation/verification
   ├── rate_limit.py      # Rate limiting
   └── timing.py          # Timing attack protection
   ```

3. **Configuration Updates**:
   ```python
   # serv/config.py additions
   class AuthConfig:
       secret_key: str
       session_backend: str = "memory"  # memory, redis, database
       session_lifetime: int = 86400    # 24 hours
       csrf_protection: bool = True
       secure_cookies: bool = True
       rate_limit_attempts: int = 5
       rate_limit_window: int = 300     # 5 minutes
   ```

### Example Usage

```python
from serv import App, Route
from serv.auth import AuthManager, require_auth, require_csrf
from serv.responses import JsonResponse, HtmlResponse

app = App()
auth = AuthManager(secret_key="your-secret-key")

class LoginRoute(Route):
    @require_csrf
    async def handle_post(self, request: PostRequest) -> JsonResponse:
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = await self.authenticate_user(username, password)
        if user:
            session_id, csrf_token = auth.create_session(user.id, request)
            
            response = JsonResponse({'status': 'success', 'csrf_token': csrf_token})
            response.set_cookie('session_id', session_id, **auth.secure_cookie_options)
            return response
        else:
            return JsonResponse({'error': 'Invalid credentials'}, status_code=401)

class ProtectedRoute(Route):
    @require_auth
    async def handle_get(self, request: GetRequest, user: User) -> JsonResponse:
        return JsonResponse({'user_id': user.id, 'username': user.username})
```

### Testing Strategy

```python
def test_password_hashing():
    """Test secure password hashing."""
    auth = AuthManager()
    password = "test_password_123"
    
    hash1 = auth.hash_password(password)
    hash2 = auth.hash_password(password)
    
    # Hashes should be different (salt)
    assert hash1 != hash2
    
    # Both should verify correctly
    assert auth.verify_password(password, hash1)
    assert auth.verify_password(password, hash2)
    
    # Wrong password should fail
    assert not auth.verify_password("wrong_password", hash1)

def test_session_security():
    """Test session creation and validation."""
    auth = AuthManager(secret_key="test-key")
    
    session_id, csrf_token = auth.create_session("user123", mock_request)
    
    # Session should be retrievable
    user = auth.get_user_from_session(session_id)
    assert user.id == "user123"
    
    # CSRF token should validate
    assert auth.csrf.verify_token(mock_request_with_token(csrf_token))

def test_timing_attack_protection():
    """Test that password verification is timing-safe."""
    auth = AuthManager()
    valid_hash = auth.hash_password("correct_password")
    
    import time
    
    # Time verification with correct password
    start = time.time()
    auth.verify_password("correct_password", valid_hash)
    correct_time = time.time() - start
    
    # Time verification with wrong password
    start = time.time()
    auth.verify_password("wrong_password", valid_hash)
    wrong_time = time.time() - start
    
    # Times should be roughly equal (within 10ms)
    assert abs(correct_time - wrong_time) < 0.01
```

### Security Considerations

- Use Argon2 or bcrypt for password hashing (never SHA/MD5)
- Generate cryptographically secure session IDs
- Implement proper session cleanup and expiration
- Use constant-time comparison for password verification
- Add rate limiting to prevent brute force attacks
- Implement CSRF protection for state-changing operations
- Use secure cookie flags (HttpOnly, Secure, SameSite)
- Consider implementing account lockout after failed attempts

### Dependencies

Add to `pyproject.toml`:
```toml
dependencies = [
    "argon2-cffi>=21.0.0",      # Secure password hashing
    "itsdangerous>=2.0.0",      # Token signing/verification
    "cryptography>=3.0.0",      # Cryptographic utilities
]
```