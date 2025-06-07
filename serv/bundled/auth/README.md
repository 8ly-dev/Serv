# Serv Authentication System - Bundled Implementations

This package provides production-ready implementations of the Serv authentication interfaces using battle-tested security libraries.

## Overview

The bundled authentication system includes:

- **JWT Authentication Provider** - Secure JWT-based authentication using PyJWT
- **Memory Rate Limiter** - In-memory rate limiting with sliding window algorithms
- **Ommi Session Storage** - Database-backed session storage using Ommi ORM
- **Bcrypt Credential Vault** - Secure password hashing using bcrypt

## Security Features

✅ **Timing Attack Protection** - Uses cryptography library for constant-time operations  
✅ **Algorithm Confusion Protection** - Explicit JWT algorithm validation  
✅ **Secure Password Hashing** - bcrypt with configurable work factors  
✅ **Device Fingerprinting** - Session binding to prevent hijacking  
✅ **Rate Limiting** - Configurable limits with multiple algorithms  
✅ **Comprehensive Logging** - Security event monitoring and audit trails  

## Quick Start

### 1. Install Dependencies

```bash
uv add --extra auth
```

### 2. Configure Authentication

Create or update your `serv.config.yaml`:

```yaml
auth:
  providers:
    - type: jwt
      config:
        secret_key: "${JWT_SECRET}"
        algorithm: "HS256"
        token_expiry_minutes: 60
  
  storage:
    backend: "serv.bundled.auth.storage.ommi_storage:OmmiSessionStorage"
    database_qualifier: "auth"
  
  credential_vault:
    backend: "serv.bundled.auth.vaults.bcrypt_vault:BcryptCredentialVault"
    bcrypt_rounds: 12
  
  rate_limiting:
    backend: "serv.bundled.auth.limiters.memory_limiter:MemoryRateLimiter"
    default_limits:
      login: "5/min"
      api_request: "100/hour"
```

### 3. Set Environment Variables

```bash
export JWT_SECRET="your-super-secret-jwt-key-at-least-32-characters-long"
```

### 4. Create Database Tables

```sql
-- Credentials table
CREATE TABLE credentials (
    credential_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    credential_type TEXT NOT NULL,
    credential_data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    metadata TEXT NOT NULL DEFAULT '{}'
);

-- Sessions table
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    user_context TEXT NOT NULL,
    device_fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_activity TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);
```

### 5. Protect Your Routes

```python
from serv.auth.decorators import auth_handle
from serv.routes import Route, handle
from serv.requests import GetRequest
from serv.responses import JsonResponse
from typing import Annotated

class MyRoutes(Route):
    @auth_handle.authenticated()
    @handle.GET
    async def protected_endpoint(
        self, request: GetRequest
    ) -> Annotated[dict, JsonResponse]:
        user_id = request.user_context.get("user_id")
        return {"message": f"Hello, {user_id}!"}
    
    @auth_handle.with_permission("admin")
    @handle.GET
    async def admin_endpoint(
        self, request: GetRequest
    ) -> Annotated[dict, JsonResponse]:
        return {"message": "Admin access granted"}
```

## Components

### JWT Authentication Provider

Secure JWT token generation and validation:

```python
from serv.bundled.auth.providers.jwt_provider import JWTAuthProvider

provider = JWTAuthProvider(
    secret_key="your-secret-key",
    algorithm="HS256",
    token_expiry_minutes=60
)

# Generate token
result = await provider.validate_credentials("jwt", {
    "user_id": "user123",
    "role": "user"
})

# Authenticate request
auth_result = await provider.authenticate_request(request)
```

### Memory Rate Limiter

In-memory rate limiting with sliding windows:

```python
from serv.bundled.auth.limiters.memory_limiter import MemoryRateLimiter

limiter = MemoryRateLimiter(
    default_limits={
        "login": "5/min",
        "api_request": "100/hour"
    }
)

# Check rate limit
result = await limiter.check_rate_limit("user123", "login")
if not result.allowed:
    # Rate limited - retry after result.retry_after seconds
    pass
```

### Ommi Session Storage

Database-backed session storage:

```python
from serv.bundled.auth.storage.ommi_storage import OmmiSessionStorage

storage = OmmiSessionStorage(
    database_qualifier="auth",
    session_timeout_hours=24
)

# Create session
session = await storage.create_session(
    user_context={"user_id": "user123"},
    device_fingerprint="fingerprint"
)

# Get session
session = await storage.get_session(session_id)
```

### Bcrypt Credential Vault

Secure password hashing and verification:

```python
from serv.bundled.auth.vaults.bcrypt_vault import BcryptCredentialVault

vault = BcryptCredentialVault(
    database_qualifier="auth",
    bcrypt_rounds=12
)

# Store password
credential = await vault.store_credential(
    user_id="user123",
    credential_type="password",
    credential_data={"password": "securepassword"}
)

# Verify password
result = await vault.verify_credential(
    user_id="user123",
    credential_type="password",
    credential_data={"password": "securepassword"}
)
```

## Configuration Examples

See `examples/config_examples.yaml` for comprehensive configuration examples including:

- Development configuration
- Production configuration  
- High-security configuration
- Microservice configuration
- Multi-database setups

## Usage Examples

See `examples/usage_examples.py` for complete code examples including:

- Basic authentication setup
- Route protection with decorators
- Login/logout implementation
- Middleware configuration
- Testing authentication flows

## Security Considerations

### JWT Security

- Uses explicit algorithm validation to prevent algorithm confusion attacks
- Configurable token expiration times
- Support for issuer and audience claims
- Comprehensive error handling

### Password Security

- bcrypt with configurable work factors (4-31 rounds)
- Automatic salt generation for each password
- Timing attack protection during verification
- Minimum password length enforcement

### Session Security

- Device fingerprint binding to prevent session hijacking
- Automatic session cleanup and expiration
- Secure session ID generation using cryptographically secure random
- Database persistence for scalability

### Rate Limiting

- Sliding window algorithm for accurate limiting
- Configurable limits per action type
- Memory-efficient cleanup of expired entries
- Protection against resource exhaustion attacks

## Performance Considerations

### Development vs Production

**Development Settings:**
- Lower bcrypt rounds (10) for faster authentication
- Relaxed fingerprint validation
- Higher rate limits
- Shorter cleanup intervals

**Production Settings:**
- Higher bcrypt rounds (12-15) for maximum security
- Strict fingerprint validation
- Conservative rate limits
- Longer cleanup intervals for efficiency

### Scaling

**Single Instance:**
- Memory rate limiter is suitable
- SQLite database for small applications

**Multi-Instance:**
- Consider Redis-backed rate limiter (future implementation)
- PostgreSQL or other shared database for sessions/credentials
- Shared JWT secrets across instances

## Troubleshooting

### Common Issues

1. **ImportError for cryptography**
   ```bash
   uv add --extra auth  # Install auth dependencies
   ```

2. **JWT algorithm confusion**
   - Always specify allowed algorithms explicitly
   - Never accept 'none' algorithm in production

3. **bcrypt too slow**
   - Reduce bcrypt_rounds for development
   - Consider async bcrypt for high-concurrency applications

4. **Rate limiting not working**
   - Check rate limit string format (e.g., "5/min", "100/hour")
   - Ensure cleanup is running periodically

5. **Session fingerprint mismatches**
   - Set `strict_fingerprint_validation: false` for development
   - Check if users have changing IP addresses (mobile networks)

### Debug Logging

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger("serv.bundled.auth").setLevel(logging.DEBUG)
```

## Contributing

When contributing to the authentication system:

1. **Security First** - All changes must maintain or improve security
2. **Test Coverage** - Add tests for all new functionality
3. **Documentation** - Update examples and documentation
4. **Backwards Compatibility** - Maintain interface compatibility
5. **Performance** - Consider performance implications of changes

## License

This authentication system is part of the Serv framework and follows the same MIT license.