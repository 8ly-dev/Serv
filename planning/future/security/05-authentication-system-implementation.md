# Authentication System Implementation Plan

## Overview

This document outlines the comprehensive implementation plan for Serv's authentication framework, based on the provided specification. The system will provide a complete abstraction layer for authentication providers while maintaining framework-managed security.

## Architecture Overview

### Core Design Principles

1. **Complete Abstraction Layer**: Auth providers implement interfaces without storage/framework knowledge
2. **Framework-Managed Security**: Consumers access auth state through framework-managed request context
3. **Snake-case Interfaces**: All interfaces follow Python naming conventions
4. **Hot-Swappable Providers**: Change auth methods via config without code changes
5. **Unified Security**: Consistent auditing, rate limiting, and policy enforcement

### Directory Structure

```
serv/auth/                           # Core interfaces (abstract base classes)
├── __init__.py
├── auth_provider.py                 # AuthProvider interface
├── session_manager.py               # SessionManager interface  
├── policy_engine.py                 # PolicyEngine interface
├── token_service.py                 # TokenService interface
├── rate_limiter.py                  # RateLimiter interface
├── audit_logger.py                  # AuditLogger interface
├── role_registry.py                 # RoleRegistry interface
├── credential_vault.py              # CredentialVault interface
├── middleware.py                    # Base auth middleware classes
├── utils.py                         # Shared utilities (fingerprinting, etc.)
└── types.py                         # Shared data types and enums

serv/bundled/auth/                   # Bundled implementations
├── __init__.py
├── storage/                         # Storage backend implementations
│   ├── __init__.py
│   └── ommi_storage.py             # Ommi-based storage backend (supports in-memory SQLite)
├── providers/                       # Authentication provider implementations
│   ├── __init__.py
│   ├── basic_auth.py               # Basic HTTP authentication
│   ├── jwt_provider.py             # JWT token authentication
│   ├── cookie_session.py           # Cookie-based sessions
│   └── api_key.py                  # API key authentication
├── limiters/                        # Rate limiting implementations
│   ├── __init__.py
│   ├── leaky_bucket.py             # Leaky bucket algorithm
│   └── fixed_window.py             # Fixed window algorithm
├── policies/                        # Policy engine implementations
│   ├── __init__.py
│   └── role_based.py               # Role-based access control
└── config.py                       # Configuration schemas and loading
```

## Phase 1: Core Interfaces Design

### 1.1 AuthProvider Interface

**Location**: `serv/auth/auth_provider.py`

**Key Components**:
- `AuthProvider` abstract base class
- `AuthResult`, `ValidationResult`, `RefreshResult` data classes
- `AuthStatus` enum for standardized status codes

**Methods**:
- `initiate_auth(request_context: dict) -> AuthResult`
- `validate_credential(credential_payload: dict) -> ValidationResult`
- `refresh_session(session_data: dict) -> RefreshResult`

**Events Emitted**:
- Authentication success/failure events
- Credential change events

### 1.2 SessionManager Interface

**Location**: `serv/auth/session_manager.py`

**Key Components**:
- `SessionManager` abstract base class
- `Session` data class with unified schema
- Device fingerprint binding support

**Methods**:
- `create_session(user_context: dict, fingerprint: str) -> Session`
- `validate_session(session_id: str, fingerprint: str) -> Optional[Session]`
- `invalidate_session(session_id: str) -> bool`
- `invalidate_user_sessions(user_id: str) -> int`

### 1.3 PolicyEngine Interface

**Location**: `serv/auth/policy_engine.py`

**Key Components**:
- `PolicyEngine` abstract base class
- `PolicyDecision` data class with detailed reasoning
- Action descriptor format: `"resource_type:action"`

**Methods**:
- `evaluate(user_context: dict, action_descriptor: str) -> PolicyDecision`
- `register_policy(policy_name: str, policy_func: Callable) -> None`

### 1.4 TokenService Interface

**Location**: `serv/auth/token_service.py`

**Key Components**:
- `TokenService` abstract base class
- `Token` data class with metadata
- Support for timed tokens and refresh tokens

**Methods**:
- `generate_token(payload: dict, expires_in: Optional[int]) -> Token`
- `validate_token(token_str: str) -> Optional[Token]`
- `refresh_token(refresh_token: str) -> Optional[Token]`
- `revoke_token(token_str: str) -> bool`

### 1.5 RateLimiter Interface

**Location**: `serv/auth/rate_limiter.py`

**Key Components**:
- `RateLimiter` abstract base class
- `RateLimitResult` data class with quota information
- Support for multiple limiting strategies

**Methods**:
- `check_limit(identifier: str, action: str) -> RateLimitResult`
- `track_attempt(identifier: str, action: str) -> None`
- `reset_limits(identifier: str) -> None`

**Granularity Options**:
- Per-IP address limiting
- Per-user account limiting  
- Per-endpoint limiting
- Custom identifier limiting
- Configurable combination rules

### 1.6 AuditLogger Interface

**Location**: `serv/auth/audit_logger.py`

**Key Components**:
- `AuditLogger` abstract base class
- `AuditEvent` data class with standardized schema
- Immutable log structure enforcement

**Event Schema**:
- `audit_id`: Unique event identifier
- `timestamp`: ISO format timestamp
- `event_type`: Standardized event type
- `actor_info`: User/system performing action
- `resource_info`: Target resource information
- `outcome`: Success/failure/error
- `metadata`: Additional context

**Methods**:
- `log_event(event: AuditEvent) -> None`
- `query_events(filters: dict) -> List[AuditEvent]`

### 1.7 RoleRegistry Interface

**Location**: `serv/auth/role_registry.py`

**Key Components**:
- `RoleRegistry` abstract base class
- `Role` and `Permission` data classes
- Dynamic role/permission definitions
- Callback system for privilege changes

**Methods**:
- `define_role(role_name: str, permissions: Set[str]) -> Role`
- `assign_role(user_id: str, role_name: str) -> None`
- `check_permission(user_id: str, permission: str) -> bool`
- `on_role_change(callback: Callable) -> None`

### 1.8 CredentialVault Interface

**Location**: `serv/auth/credential_vault.py`

**Key Components**:
- `CredentialVault` abstract base class
- `Credential` data class with secure metadata
- Encryption/hashing abstraction

**Methods**:
- `store_credential(user_id: str, credential_type: str, data: bytes) -> str`
- `verify_credential(credential_id: str, input_data: bytes) -> bool`
- `update_credential(credential_id: str, new_data: bytes) -> bool`
- `revoke_credential(credential_id: str) -> bool`

## Phase 2: Configuration System

### 2.1 Configuration Schema Extension

**Location**: `serv/config.py` (extend existing)

Add new configuration sections:

```yaml
# serv.config.yaml
databases:
  auth_db:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "sqlite:///auth.db"
  main_db:  
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "${DATABASE_URL}"
    pool_size: 10

auth:
  providers:
    - type: jwt
      config:
        secret_key: "${JWT_SECRET}"  # Environment variable support
        algorithm: "HS256"
        expires_in: 3600
    - type: cookie_session
      config:
        session_timeout: 7200
        secure_cookies: true
  storage:
    backend: "serv.bundled.auth.storage.ommi_storage"
    database: "auth_db"  # References databases.auth_db
  rate_limiting:
    login_attempts: "5/min"
    token_generation: "10/min"
    api_requests: "100/min"
  audit:
    enabled: true
    events: ["login", "logout", "permission_denied", "credential_change"]
    retention_days: 90
  policies:
    default_role: "user"
    require_mfa: false
  security:
    fingerprint_required: true
    session_invalidation_on_role_change: true
    timing_protection:
      enabled: true
      minimum_auth_time: 2.0  # seconds
      minimum_token_time: 1.0  # seconds
```

### 2.2 Environment Variable Loading

Support for secure configuration loading:
- `${VAR_NAME}` syntax for environment variables
- Required vs optional environment variables
- Validation of configuration values
- Secure defaults for development

## Phase 3: Utilities and Middleware

### 3.1 Device Fingerprinting

**Location**: `serv/auth/utils.py`

**Basic Implementation**:
- IP address
- User-Agent header
- Accept-Language header
- Session cookie presence
- Custom header values

**Extensible Design**:
- Pluggable fingerprint strategies
- Configurable data collection
- Privacy-conscious defaults

### 3.2 Timing Attack Protection

**Location**: `serv/auth/utils.py`

**MinimumRuntime Context Manager**:
```python
import asyncio
import time
from typing import Optional

class MinimumRuntime:
    """
    Context manager that ensures authentication operations take a minimum time.
    Prevents timing attacks where response time reveals information about
    user existence, password correctness, etc.
    """
    
    def __init__(self, seconds: float):
        self.minimum_seconds = seconds
        self.start_time: Optional[float] = None
    
    async def __aenter__(self):
        self.start_time = time.perf_counter()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is None:
            return
            
        elapsed = time.perf_counter() - self.start_time
        remaining = self.minimum_seconds - elapsed
        
        if remaining > 0:
            await asyncio.sleep(remaining)

# Usage in auth providers
async def authenticate_user(username: str, password: str) -> AuthResult:
    async with MinimumRuntime(seconds=2.0):  # Always take at least 2 seconds
        # Fast path: user doesn't exist
        user = await get_user(username)
        if not user:
            return AuthResult(status=AuthStatus.INVALID_CREDENTIALS)
        
        # Slow path: verify password
        if not verify_password(password, user.password_hash):
            return AuthResult(status=AuthStatus.INVALID_CREDENTIALS)
            
        return AuthResult(status=AuthStatus.SUCCESS, user_id=user.id)
    # Context manager ensures consistent 2+ second response time
```

**Security Benefits**:
- Prevents username enumeration via timing
- Prevents password validation timing attacks
- Consistent response times for all auth attempts
- Configurable minimum runtime per operation

### 3.3 Base Middleware Classes

**Location**: `serv/auth/middleware.py`

**Components**:
- `AuthenticationMiddleware`: Base class for auth checks
- `AuthorizationMiddleware`: Base class for permission checks
- `SecurityHeadersMiddleware`: Automatic security headers
- `RateLimitMiddleware`: Request rate limiting

### 3.4 Route Decorator Enhancements

**Location**: Extend existing route decorators in `serv/routes.py`

**New Features**:
- `@handle(require_auth=True)`: Require authentication
- `@handle(require_permission="admin")`: Require specific permission
- `@handle(require_permissions=["read", "write"])`: Require multiple permissions (ALL required)
- `@handle(require_any_permission=["admin", "moderator"])`: Require any of the listed permissions  
- `@handle(require_role="moderator")`: Require specific role
- `@handle(require_roles=["admin", "moderator"])`: Require any of the listed roles
- `@handle(auth_optional=True)`: Optional auth (user context if available)

**Integration**:
- Auth interfaces available through dependency injection
- User context automatically injected when authenticated
- Policy engine integration for permission checks
- Error handling respects dev/prod mode settings

**Permission Logic**:
- `require_permission`: Single permission required
- `require_permissions`: ALL permissions in list required (AND logic)
- `require_any_permission`: ANY permission in list required (OR logic)
- `require_role` / `require_roles`: Same logic as permissions but for roles
- Multiple auth decorators can be combined on same route
- Policy engine evaluates all requirements before allowing access

**Example Usage**:
```python
from serv.routes import Route
from serv.auth import PolicyEngine, Session
from bevy import dependency

class ProtectedRoute(Route):
    # Single permission
    @handle(require_auth=True, require_permission="read_posts")
    async def handle_get(self, request: GetRequest, user_session: Session = dependency()):
        return f"Hello, {user_session.user_context['username']}"
    
    # Multiple permissions (ALL required)
    @handle(require_permissions=["read_posts", "write_posts"])
    async def handle_post(self, request: PostRequest, user_session: Session = dependency()):
        return "Can read AND write posts"
    
    # Any of multiple permissions (OR logic)
    @handle(require_any_permission=["admin", "moderator", "super_user"])
    async def handle_delete(self, request: DeleteRequest, user_session: Session = dependency()):
        return "Has admin OR moderator OR super_user permission"
    
    # Complex permission requirements
    @handle(
        require_auth=True,
        require_permissions=["read_posts", "access_api"],  # Must have both
        require_any_permission=["premium", "admin"]        # Must have either
    )
    async def handle_premium_api(self, request: GetRequest, user_session: Session = dependency()):
        return "Premium API access with multiple permission checks"
```

## Phase 4: Bundled Implementations

### 4.1 Storage Backend

#### Ommi Storage Backend
**Location**: `serv/bundled/auth/storage/ommi_storage.py`

**Features**:
- User account storage
- Session management
- Credential storage with encryption
- Audit log persistence
- Role/permission storage
- Uses existing database connections from DI container
- References configured database by name

**Integration**:
- Receives database name from auth configuration
- Injects the database connection using dependency injection
- No direct database connection management
- Leverages the database lifecycle management system

**Example Implementation**:
```python
from ommi import Ommi
from bevy import dependency

class OmmiAuthStorage:
    def __init__(self, database_name: str):
        self.database_name = database_name
    
    async def store_user(
        self, 
        user_data: dict,
        db: Ommi = dependency(name=f"db_{self.database_name}")
    ):
        # Use the injected database connection
        user = AuthUser(**user_data)
        await db.add(user).or_raise()
    
    async def get_user(
        self, 
        user_id: str,
        db: Ommi = dependency(name=f"db_{self.database_name}")
    ):
        return await db.find(AuthUser.id == user_id).one.or_none()
```

### 4.2 Authentication Providers

#### Basic Auth Provider
**Location**: `serv/bundled/auth/providers/basic_auth.py`

**Features**:
- HTTP Basic Authentication
- Username/password validation
- Rate limiting integration

#### JWT Provider
**Location**: `serv/bundled/auth/providers/jwt_provider.py`

**Features**:
- JWT token generation and validation
- Configurable algorithms (HS256, RS256, etc.)
- Token refresh support
- Proper security practices

#### Cookie Session Provider
**Location**: `serv/bundled/auth/providers/cookie_session.py`

**Features**:
- Secure session cookies
- CSRF protection
- Session hijacking prevention
- Device fingerprint binding

#### API Key Provider
**Location**: `serv/bundled/auth/providers/api_key.py`

**Features**:
- API key generation and validation
- Key scoping and permissions
- Usage tracking
- Key rotation support

### 4.3 Rate Limiters

#### Leaky Bucket
**Location**: `serv/bundled/auth/limiters/leaky_bucket.py`

**Features**:
- Smooth rate limiting
- Burst capacity handling
- Memory efficient implementation

#### Fixed Window
**Location**: `serv/bundled/auth/limiters/fixed_window.py`

**Features**:
- Simple time-window limiting
- Reset at fixed intervals
- Easy to understand behavior

## Phase 5: Security Dependencies

### 5.1 Add Required Dependencies

**Add to `pyproject.toml`**:
```toml
dependencies = [
    # ... existing dependencies ...
    "bcrypt>=4.0.0",           # Password hashing
    "cryptography>=42.0.0",    # Encryption utilities
    "pyjwt>=2.8.0",           # JWT token handling
    "ommi>=1.0.0",            # Database ORM
]
```

### 5.2 Initial Security Features (Minimal Scope)

**Password Authentication**:
- Use bcrypt for password hashing
- Standard password policies (minimum length, basic complexity)
- Salt generation and verification

**Token Security**:
- Basic JWT token handling
- Token expiration enforcement
- Secure random token generation

**Session Security**:
- HttpOnly and Secure cookie flags
- Basic session management
- Session fixation prevention

**Error Handling**:
- Development mode: Detailed error messages for debugging
- Production mode: Vague error messages for security
- Mode detection from app configuration

**Future Security Enhancements** (Not in initial scope):
- Multi-factor authentication
- Advanced password policies
- Account lockout mechanisms  
- Password expiration policies
- Advanced CSRF protection

## Phase 6: Testing Strategy

### 6.1 Unit Tests

**Coverage Areas**:
- All interface implementations
- Configuration loading and validation
- Security utility functions
- Rate limiting algorithms
- Token generation and validation

### 6.2 Integration Tests

**Test Scenarios**:
- Complete authentication flows
- Middleware integration
- Database operations
- Rate limiting enforcement
- Audit logging verification

### 6.3 Security Test Suite

**Location**: `tests/security/`

#### 6.3.1 Authentication Attack Vectors

**Brute Force Attacks**:
```python
# tests/security/test_brute_force.py
async def test_password_brute_force_protection():
    """Test rate limiting prevents password brute force attacks"""
    
async def test_token_brute_force_protection():
    """Test rate limiting prevents token guessing attacks"""
    
async def test_account_lockout_after_failed_attempts():
    """Test accounts get locked after multiple failed attempts"""
```

**Credential Attacks**:
```python
# tests/security/test_credentials.py
async def test_weak_password_rejection():
    """Test weak passwords are rejected"""
    
async def test_password_hash_security():
    """Test passwords are properly hashed with salt"""
    
async def test_credential_stuffing_protection():
    """Test protection against credential stuffing attacks"""
    
async def test_password_timing_attack_resistance():
    """Test password verification is timing-attack resistant"""
    
async def test_minimum_runtime_context_manager():
    """Test MinimumRuntime ensures consistent response times"""
    
async def test_authentication_timing_consistency():
    """Test authentication operations have consistent timing"""
```

#### 6.3.2 Session Security Attacks

**Session Hijacking**:
```python
# tests/security/test_session_security.py
async def test_session_fixation_protection():
    """Test new session ID generated on login"""
    
async def test_session_hijacking_protection():
    """Test session tied to device fingerprint"""
    
async def test_concurrent_session_limits():
    """Test limits on concurrent sessions per user"""
    
async def test_session_invalidation_on_privilege_change():
    """Test sessions invalidated when user permissions change"""
```

**Session Management**:
```python
async def test_secure_session_cookies():
    """Test session cookies have security flags (HttpOnly, Secure, SameSite)"""
    
async def test_session_timeout_enforcement():
    """Test sessions expire after configured timeout"""
    
async def test_idle_session_timeout():
    """Test sessions expire after period of inactivity"""
```

#### 6.3.3 Token Security Attacks

**JWT Token Attacks**:
```python
# tests/security/test_token_security.py
async def test_jwt_signature_verification():
    """Test JWT signatures are properly verified"""
    
async def test_jwt_algorithm_confusion():
    """Test protection against algorithm confusion attacks"""
    
async def test_jwt_token_tampering():
    """Test tampered tokens are rejected"""
    
async def test_jwt_expiration_enforcement():
    """Test expired tokens are rejected"""
    
async def test_jwt_none_algorithm_protection():
    """Test 'none' algorithm is not accepted"""
```

**Token Leakage**:
```python
async def test_token_not_logged():
    """Test tokens are not logged in plaintext"""
    
async def test_token_not_in_error_messages():
    """Test tokens don't appear in error messages"""
    
async def test_refresh_token_security():
    """Test refresh tokens are securely handled"""
```

#### 6.3.4 Authorization Bypass Attacks

**Permission Escalation**:
```python
# tests/security/test_authorization_bypass.py
async def test_horizontal_privilege_escalation():
    """Test users cannot access other users' resources"""
    
async def test_vertical_privilege_escalation():
    """Test users cannot escalate to higher privileges"""
    
async def test_role_manipulation_protection():
    """Test role assignments cannot be manipulated"""
    
async def test_permission_bypass_attempts():
    """Test various permission bypass techniques"""
```

**Direct Object Reference**:
```python
async def test_insecure_direct_object_references():
    """Test IDOR protection in auth endpoints"""
    
async def test_user_enumeration_protection():
    """Test protection against user enumeration attacks"""
```

#### 6.3.5 Injection Attacks

**SQL Injection**:
```python
# tests/security/test_injection_attacks.py
async def test_sql_injection_in_auth():
    """Test SQL injection protection in authentication"""
    
async def test_sql_injection_in_user_lookup():
    """Test SQL injection protection in user queries"""
    
async def test_parameterized_queries():
    """Test all database queries use parameterization"""
```

**NoSQL Injection**:
```python
async def test_nosql_injection_protection():
    """Test NoSQL injection protection if applicable"""
```

#### 6.3.6 Cross-Site Attacks

**CSRF Protection**:
```python
# tests/security/test_csrf_protection.py
async def test_csrf_token_validation():
    """Test CSRF tokens are validated"""
    
async def test_samesite_cookie_protection():
    """Test SameSite cookie attribute provides CSRF protection"""
    
async def test_state_changing_operations_protected():
    """Test state-changing auth operations require CSRF protection"""
```

**XSS Protection**:
```python
# tests/security/test_xss_protection.py
async def test_auth_response_xss_protection():
    """Test auth responses don't contain XSS vulnerabilities"""
    
async def test_user_input_sanitization():
    """Test user input is properly sanitized"""
    
async def test_content_type_headers():
    """Test proper Content-Type headers prevent XSS"""
```

#### 6.3.7 Information Disclosure

**Error Message Leakage**:
```python
# tests/security/test_information_disclosure.py
async def test_generic_error_messages():
    """Test error messages don't leak sensitive information"""
    
async def test_user_enumeration_via_timing():
    """Test timing attacks for user enumeration are prevented"""
    
async def test_user_enumeration_via_responses():
    """Test response differences don't reveal user existence"""
    
async def test_stack_traces_not_exposed():
    """Test stack traces are not exposed in production"""
```

**Sensitive Data Exposure**:
```python
async def test_password_not_in_logs():
    """Test passwords are never logged"""
    
async def test_sensitive_data_not_cached():
    """Test sensitive auth data is not cached"""
    
async def test_debug_info_not_exposed():
    """Test debug information is not exposed in production"""
```

#### 6.3.8 Rate Limiting and DoS

**Denial of Service**:
```python
# tests/security/test_dos_protection.py
async def test_login_rate_limiting():
    """Test login attempts are rate limited"""
    
async def test_token_generation_rate_limiting():
    """Test token generation is rate limited"""
    
async def test_api_endpoint_rate_limiting():
    """Test auth API endpoints are rate limited"""
    
async def test_resource_exhaustion_protection():
    """Test protection against resource exhaustion attacks"""
```

#### 6.3.9 Cryptographic Security

**Encryption and Hashing**:
```python
# tests/security/test_cryptographic_security.py
async def test_secure_random_generation():
    """Test cryptographically secure random number generation"""
    
async def test_password_hashing_strength():
    """Test password hashing uses appropriate work factors"""
    
async def test_salt_generation():
    """Test proper salt generation for password hashing"""
    
async def test_key_derivation_security():
    """Test secure key derivation functions"""
    
async def test_encryption_algorithm_security():
    """Test use of secure encryption algorithms"""
```

#### 6.3.10 Configuration Security

**Secure Defaults**:
```python
# tests/security/test_configuration_security.py
async def test_secure_default_configuration():
    """Test default configuration is secure"""
    
async def test_insecure_configuration_warnings():
    """Test warnings for insecure configuration"""
    
async def test_secret_key_validation():
    """Test secret keys meet security requirements"""
    
async def test_environment_variable_security():
    """Test environment variables are handled securely"""
```

#### 6.3.11 Multi-Factor Authentication Security

**MFA Bypass** (Future enhancement):
```python
# tests/security/test_mfa_security.py
async def test_mfa_bypass_prevention():
    """Test MFA cannot be bypassed"""
    
async def test_backup_code_security():
    """Test backup codes are securely generated and stored"""
    
async def test_totp_timing_window():
    """Test TOTP timing window is appropriate"""
```

#### 6.3.12 Third-Party Integration Security

**OAuth Security**:
```python
# tests/security/test_oauth_security.py
async def test_oauth_state_parameter():
    """Test OAuth state parameter prevents CSRF"""
    
async def test_oauth_redirect_uri_validation():
    """Test OAuth redirect URI validation"""
    
async def test_oauth_scope_validation():
    """Test OAuth scope validation"""
```

### 6.4 Security Test Execution

#### 6.4.1 Automated Security Testing with Test App Client

**Location**: `tests/security/conftest.py`

```python
# Security testing fixtures and utilities
import pytest
from pathlib import Path
from serv import create_test_app_client

@pytest.fixture
async def security_test_client():
    """Client configured for security testing with auth system enabled"""
    config_path = Path("tests/security/auth_test_config.yaml")
    async with create_test_app_client(
        config_path,
        dev=True,  # Enable detailed error messages for debugging
        extension_dirs="tests/security/auth_extensions"
    ) as client:
        yield client

@pytest.fixture
async def production_test_client():
    """Client configured for production-mode security testing"""
    config_path = Path("tests/security/auth_prod_config.yaml")
    async with create_test_app_client(
        config_path,
        dev=False,  # Disable detailed errors for production testing
        extension_dirs="tests/security/auth_extensions"
    ) as client:
        yield client

@pytest.fixture
async def isolated_auth_client():
    """Client with isolated auth configuration for specific tests"""
    config_path = Path("tests/security/isolated_auth_config.yaml")
    async with create_test_app_client(
        config_path,
        extension_dirs="tests/security/isolated_extensions",
        use_lifespan=True  # Ensure proper auth system initialization
    ) as client:
        yield client

@pytest.fixture  
def malicious_payloads():
    """Common malicious payloads for testing"""
    return {
        "sql_injection": [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "1' UNION SELECT username, password FROM users--"
        ],
        "xss_payloads": [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>"
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd"
        ],
        "command_injection": [
            "; ls -la",
            "| cat /etc/passwd",
            "&& rm -rf /"
        ]
    }
    
@pytest.fixture
def timing_attack_detector():
    """Utility to detect timing attack vulnerabilities"""
    import time
    import statistics
    
    class TimingDetector:
        def __init__(self, samples=50, threshold_ms=50):
            self.samples = samples
            self.threshold_ms = threshold_ms
            
        async def measure_response_times(self, client, requests_func):
            """Measure response times for a series of requests"""
            times = []
            for _ in range(self.samples):
                start = time.perf_counter()
                await requests_func(client)
                end = time.perf_counter()
                times.append((end - start) * 1000)  # Convert to milliseconds
            return times
            
        def analyze_timing_vulnerability(self, times_valid, times_invalid):
            """Analyze if timing differences indicate vulnerability"""
            valid_median = statistics.median(times_valid)
            invalid_median = statistics.median(times_invalid)
            difference = abs(valid_median - invalid_median)
            
            return {
                "vulnerable": difference > self.threshold_ms,
                "difference_ms": difference,
                "valid_median": valid_median,
                "invalid_median": invalid_median,
                "threshold_ms": self.threshold_ms
            }
    
    return TimingDetector()

@pytest.fixture
async def authenticated_client(security_test_client):
    """Client with valid authentication token"""
    # Login to get authentication token
    login_response = await security_test_client.post("/auth/login", json={
        "username": "test_user",
        "password": "test_password"
    })
    assert login_response.status_code == 200
    
    # Extract token from response
    token = login_response.json()["token"]
    
    # Set authorization header for subsequent requests
    security_test_client.headers.update({"Authorization": f"Bearer {token}"})
    
    return security_test_client

@pytest.fixture
async def admin_client(security_test_client):
    """Client authenticated as admin user"""
    login_response = await security_test_client.post("/auth/login", json={
        "username": "admin_user",
        "password": "admin_password"
    })
    assert login_response.status_code == 200
    
    token = login_response.json()["token"]
    security_test_client.headers.update({"Authorization": f"Bearer {token}"})
    
    return security_test_client
```

#### 6.4.2 Security Test Configuration Files

**Test Configurations for Different Scenarios**:

```yaml
# tests/security/auth_test_config.yaml
site_info:
  name: "Auth Security Test App"
  description: "Test application for authentication security testing"

databases:
  auth_test_db:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "sqlite:///:memory:"  # In-memory for fast tests

auth:
  providers:
    - type: jwt
      config:
        secret_key: "test_secret_key_for_testing_only"
        algorithm: "HS256"
        expires_in: 3600
    - type: cookie_session
      config:
        session_timeout: 7200
        secure_cookies: false  # For testing
  storage:
    backend: "serv.bundled.auth.storage.ommi_storage"
    database: "auth_test_db"
  rate_limiting:
    login_attempts: "10/min"  # More lenient for testing
    token_generation: "20/min"
    api_requests: "200/min"
  audit:
    enabled: true
    events: ["login", "logout", "permission_denied", "credential_change"]
  security:
    fingerprint_required: true
    timing_protection:
      enabled: true
      minimum_auth_time: 0.1  # Faster for tests
      minimum_token_time: 0.05

extensions:
  - auth_test_extension
```

```yaml
# tests/security/auth_prod_config.yaml (Production-like settings)
site_info:
  name: "Auth Production Test App"
  description: "Test application simulating production auth settings"

databases:
  auth_prod_db:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "sqlite:///test_prod_auth.db"

auth:
  providers:
    - type: jwt
      config:
        secret_key: "production_strength_secret_key_minimum_32_chars"
        algorithm: "HS256"
        expires_in: 900  # Shorter expiration
  storage:
    backend: "serv.bundled.auth.storage.ommi_storage"
    database: "auth_prod_db"
  rate_limiting:
    login_attempts: "3/min"  # Strict rate limiting
    token_generation: "5/min"
    api_requests: "50/min"
  audit:
    enabled: true
    events: ["login", "logout", "permission_denied", "credential_change", "rate_limit_exceeded"]
  security:
    fingerprint_required: true
    session_invalidation_on_role_change: true
    timing_protection:
      enabled: true
      minimum_auth_time: 2.0  # Production timing
      minimum_token_time: 1.0

extensions:
  - auth_test_extension
```

#### 6.4.2 Security Test Categories

**Test Markers**:
```python
# pytest markers for security tests
@pytest.mark.security              # All security tests
@pytest.mark.auth_security         # Authentication security
@pytest.mark.session_security      # Session security
@pytest.mark.injection             # Injection attacks
@pytest.mark.privilege_escalation  # Privilege escalation
@pytest.mark.dos                   # Denial of service
@pytest.mark.information_disclosure # Information disclosure
```

**Test Execution**:
```bash
# Run all security tests
pytest -m security

# Run specific security categories
pytest -m auth_security
pytest -m injection
pytest -m privilege_escalation

# Run security tests with detailed output
pytest -m security -v --tb=short

# Generate security test report
pytest -m security --html=security_report.html
```

#### 6.4.3 Security Test Metrics

**Coverage Requirements**:
- 100% coverage of authentication flows
- 100% coverage of authorization checks
- 100% coverage of input validation
- All security-critical code paths tested

**Performance Benchmarks**:
- Rate limiting effectiveness measurements
- Timing attack resistance validation
- Resource usage under attack scenarios

#### 6.4.4 Continuous Security Testing

**CI/CD Integration**:
```yaml
# Security testing in CI pipeline
security_tests:
  script:
    - pytest -m security --junit-xml=security_results.xml
    - python scripts/security_test_analysis.py
  artifacts:
    reports:
      junit: security_results.xml
```

**Security Regression Testing**:
- All security tests run on every commit
- Security-specific test suite for releases
- Automated security vulnerability scanning

## Phase 7: Documentation and Examples

### 7.1 Developer Documentation

**Documentation Sections**:
- Quick start guide
- Configuration reference
- Provider development guide
- Security best practices
- Migration guide

### 7.2 Example Extensions

**Example Implementations**:
- Simple username/password auth
- OAuth2 integration example
- Multi-factor authentication
- Custom policy engine
- Advanced rate limiting

## Implementation Sequence

### Week 1: Core Interfaces
1. Design and implement all abstract base classes
2. Create shared data types and enums
3. Define configuration schema
4. Add basic utilities (fingerprinting)

### Week 2: Bundled Storage
1. Implement Ommi storage backend that references database names
2. Integrate with database dependency injection system
3. Add auth-specific data models (users, sessions, etc.)
4. Test with different database configurations

### Week 3: Authentication Providers
1. Implement basic auth provider
2. Create JWT provider with security
3. Build cookie session provider
4. Add API key provider

### Week 4: Supporting Systems
1. Implement rate limiting algorithms
2. Create audit logging system
3. Build role registry with callbacks
4. Add comprehensive middleware
5. Extend route decorators with auth options

### Week 5: Security Testing and Integration
1. Implement comprehensive security test suite
2. Create integration tests
3. Add automated security testing to CI/CD
4. Performance and load testing
5. Security vulnerability assessment

### Week 6: Documentation and Final Validation
1. Complete documentation and examples
2. Security audit and penetration testing
3. Performance optimization
4. Final security validation

## Success Criteria

### Functional Requirements
- [ ] All core interfaces implemented and documented
- [ ] Ommi storage backend fully functional
- [ ] At least 4 authentication providers working
- [ ] Rate limiting with multiple strategies
- [ ] Comprehensive audit logging
- [ ] Role-based access control
- [ ] Configuration-driven provider selection
- [ ] Route decorator auth integration (@handle options)
- [ ] Dependency injection for auth interfaces

### Security Requirements (Initial Scope)
- [ ] Secure password hashing (bcrypt)
- [ ] Basic JWT token handling
- [ ] Basic session management
- [ ] Rate limiting against brute force
- [ ] Audit trail for auth events
- [ ] Input validation and sanitization
- [ ] Standard password policies (length, complexity)
- [ ] Context-aware error handling (dev vs prod modes)
- [ ] Timing attack protection with MinimumRuntime context manager
- [ ] Comprehensive security test suite covering common attack vectors
- [ ] Automated security testing in CI/CD pipeline
- [ ] Security vulnerability assessment and penetration testing

### Developer Experience
- [ ] Clear, intuitive interfaces
- [ ] Comprehensive documentation
- [ ] Working examples for common scenarios
- [ ] Easy configuration and setup
- [ ] Good error messages and debugging
- [ ] Extensible architecture for custom providers

## Risk Assessment

### High Risk Items
- **Security vulnerabilities**: Basic security review required for password handling
- **Performance impact**: Rate limiting and audit logging overhead  
- **Configuration complexity**: Keep initial configuration simple
- **Ommi integration**: Ensure stable integration with Ommi ORM

### Mitigation Strategies
- Focus on security fundamentals (bcrypt, secure sessions)
- Performance testing with realistic loads
- Simple configuration with sensible defaults
- Comprehensive testing including basic security scenarios
- Incremental security enhancement in future releases

## Dependencies and Blockers

### External Dependencies
- Ommi ORM availability and stability
- Security library updates (bcrypt, cryptography)
- Python 3.13 compatibility for all dependencies

### Internal Blockers
- Database integration system (must be implemented first)
- Configuration system enhancements
- Dependency injection system integration
- Middleware framework extensions
- Route decorator system enhancements for auth options

**Note**: Database migrations are deferred to future releases when full database support is added to Serv.

**Critical Dependency**: The auth system requires the database integration system to be implemented first, as auth storage backends reference database connections by name.

## Resolved Decisions

✅ **Storage Backend**: Reference database connections by name, don't manage connections directly  
✅ **Rate Limiting Granularity**: Configurable for all (per-IP, per-user, per-endpoint, custom)  
✅ **Security Scope**: Minimal initial features (password auth with standard policies)  
✅ **Database Migrations**: Deferred to future releases
✅ **Database Integration**: Auth storage backends reference configured databases via DI

## Final Design Decisions

✅ **Extension Integration**: 
- Auth interfaces available through dependency injection
- Extensions should inject from `serv.auth` (not enforced)
- Add auth options to `handle` decorator (require auth, permission levels)

✅ **Backwards Compatibility**: 
- Greenfield project - zero backwards compatibility required

✅ **Configuration**: 
- Users handle dev/prod configs with separate files
- Single set of sensible defaults for all environments

✅ **Error Handling**: 
- Vague errors in production mode
- Detailed errors in development mode
- Mode detection from app configuration