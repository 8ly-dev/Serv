"""
Usage Examples for Serv Authentication System

This file demonstrates how to use the bundled authentication implementations
in your Serv applications with practical, real-world examples.
"""

import asyncio
from datetime import datetime
from typing import Annotated

from bevy import Inject, Options
from ommi import Ommi

from serv.app import App
from serv.auth.decorators import auth_handle
from serv.auth.middleware import AuthenticationMiddleware, AuthorizationMiddleware
from serv.bundled.auth.providers.jwt_provider import JWTAuthProvider
from serv.bundled.auth.limiters.memory_limiter import MemoryRateLimiter
from serv.bundled.auth.storage.ommi_storage import OmmiSessionStorage
from serv.bundled.auth.vaults.bcrypt_vault import BcryptCredentialVault
from serv.requests import GetRequest, PostRequest
from serv.responses import JsonResponse, RedirectResponse
from serv.routes import Route, handle


# =============================================================================
# EXAMPLE 1: BASIC AUTHENTICATION SETUP
# =============================================================================

class AuthenticationExample:
    """Example showing basic authentication setup with JWT and bcrypt."""
    
    def __init__(self):
        # Initialize authentication components
        self.jwt_provider = JWTAuthProvider(
            secret_key="your-super-secret-jwt-key-at-least-32-characters-long",
            algorithm="HS256",
            token_expiry_minutes=60
        )
        
        self.credential_vault = BcryptCredentialVault(
            database_qualifier="auth",
            bcrypt_rounds=12
        )
        
        self.session_storage = OmmiSessionStorage(
            database_qualifier="auth",
            session_timeout_hours=24
        )
        
        self.rate_limiter = MemoryRateLimiter(
            default_limits={
                "login": "5/min",
                "api_request": "100/hour"
            }
        )
    
    async def register_user(self, username: str, password: str) -> bool:
        """Register a new user with secure password storage."""
        try:
            # Store password credential using bcrypt
            credential = await self.credential_vault.store_credential(
                user_id=username,
                credential_type="password",
                credential_data={"password": password}
            )
            
            print(f"User {username} registered successfully")
            return True
            
        except Exception as e:
            print(f"Registration failed: {e}")
            return False
    
    async def authenticate_user(self, username: str, password: str) -> dict | None:
        """Authenticate user and generate JWT token."""
        try:
            # Verify password
            validation_result = await self.credential_vault.verify_credential(
                user_id=username,
                credential_type="password",
                credential_data={"password": password}
            )
            
            if not validation_result.is_valid:
                print("Authentication failed: Invalid credentials")
                return None
            
            # Generate JWT token
            jwt_result = await self.jwt_provider.validate_credentials(
                credential_type="jwt",
                credential_data={
                    "user_id": username,
                    "role": "user",
                    "permissions": ["read", "write"]
                }
            )
            
            if jwt_result.is_valid:
                return {
                    "user_id": username,
                    "token": jwt_result.user_context["token"],
                    "expires_at": jwt_result.user_context["expires_at"]
                }
            
            return None
            
        except Exception as e:
            print(f"Authentication error: {e}")
            return None


# =============================================================================
# EXAMPLE 2: ROUTE PROTECTION WITH DECORATORS
# =============================================================================

class ProtectedRoutes(Route):
    """Example routes with various authentication requirements."""
    
    @handle.GET
    async def public_endpoint(
        self, request: GetRequest
    ) -> Annotated[dict, JsonResponse]:
        """Public endpoint - no authentication required."""
        return {"message": "This is a public endpoint", "timestamp": datetime.now().isoformat()}
    
    @auth_handle.authenticated()
    @handle.GET
    async def protected_endpoint(
        self, request: GetRequest
    ) -> Annotated[dict, JsonResponse]:
        """Protected endpoint - authentication required."""
        user_id = request.user_context.get("user_id", "unknown")
        return {
            "message": f"Hello, {user_id}! This is a protected endpoint.",
            "user_context": request.user_context
        }
    
    @auth_handle.with_permission("admin")
    @handle.GET
    async def admin_endpoint(
        self, request: GetRequest
    ) -> Annotated[dict, JsonResponse]:
        """Admin-only endpoint - requires 'admin' permission."""
        return {
            "message": "Admin access granted",
            "admin_data": {"users": 100, "active_sessions": 25}
        }
    
    @auth_handle.with_role("moderator")
    @handle.POST
    async def moderator_action(
        self, request: PostRequest
    ) -> Annotated[dict, JsonResponse]:
        """Moderator action - requires 'moderator' role."""
        data = await request.json()
        return {
            "message": "Moderator action completed",
            "action": data.get("action", "unknown"),
            "performed_by": request.user_context.get("user_id")
        }
    
    @auth_handle.with_permissions(["read", "write"])
    @handle.PUT
    async def multi_permission_endpoint(
        self, request: PostRequest
    ) -> Annotated[dict, JsonResponse]:
        """Endpoint requiring multiple permissions."""
        return {
            "message": "Multi-permission access granted",
            "permissions": ["read", "write"]
        }
    
    @auth_handle.optional_auth()
    @handle.GET
    async def optional_auth_endpoint(
        self, request: GetRequest
    ) -> Annotated[dict, JsonResponse]:
        """Endpoint with optional authentication - works for both authenticated and anonymous users."""
        if hasattr(request, 'user_context') and request.user_context:
            return {
                "message": f"Welcome back, {request.user_context.get('user_id')}!",
                "authenticated": True
            }
        else:
            return {
                "message": "Welcome, anonymous user!",
                "authenticated": False
            }


# =============================================================================
# EXAMPLE 3: LOGIN/LOGOUT IMPLEMENTATION
# =============================================================================

class AuthRoutes(Route):
    """Authentication-related routes."""
    
    @handle.POST
    async def login(
        self, 
        request: PostRequest,
        credential_vault: Inject[BcryptCredentialVault] = None,
        jwt_provider: Inject[JWTAuthProvider] = None,
        rate_limiter: Inject[MemoryRateLimiter] = None,
    ) -> Annotated[dict, JsonResponse]:
        """Login endpoint with rate limiting."""
        try:
            # Get client IP for rate limiting
            client_ip = getattr(request.client, "host", "unknown") if request.client else "unknown"
            
            # Check rate limit
            rate_result = await rate_limiter.check_rate_limit(client_ip, "login")
            if not rate_result.allowed:
                return {
                    "error": "Rate limit exceeded",
                    "retry_after": rate_result.retry_after
                }, 429
            
            # Get credentials from request
            data = await request.json()
            username = data.get("username")
            password = data.get("password")
            
            if not username or not password:
                return {"error": "Username and password required"}, 400
            
            # Verify credentials
            validation_result = await credential_vault.verify_credential(
                user_id=username,
                credential_type="password",
                credential_data={"password": password}
            )
            
            if not validation_result.is_valid:
                # Record failed login attempt
                await rate_limiter.check_rate_limit(client_ip, "failed_login")
                return {"error": "Invalid credentials"}, 401
            
            # Generate JWT token
            jwt_result = await jwt_provider.validate_credentials(
                credential_type="jwt",
                credential_data={
                    "user_id": username,
                    "role": "user",  # Could be fetched from user database
                    "permissions": ["read", "write"]  # Could be role-based
                }
            )
            
            if jwt_result.is_valid:
                return {
                    "message": "Login successful",
                    "token": jwt_result.user_context["token"],
                    "expires_at": jwt_result.user_context["expires_at"],
                    "user_id": username
                }
            
            return {"error": "Token generation failed"}, 500
            
        except Exception as e:
            return {"error": "Login service error"}, 500
    
    @handle.POST
    async def register(
        self,
        request: PostRequest,
        credential_vault: Inject[BcryptCredentialVault] = None,
    ) -> Annotated[dict, JsonResponse]:
        """Registration endpoint."""
        try:
            data = await request.json()
            username = data.get("username")
            password = data.get("password")
            
            if not username or not password:
                return {"error": "Username and password required"}, 400
            
            # Check if user already exists
            existing = await credential_vault.get_credential(username, "password")
            if existing:
                return {"error": "User already exists"}, 409
            
            # Store new user credentials
            await credential_vault.store_credential(
                user_id=username,
                credential_type="password",
                credential_data={"password": password}
            )
            
            return {"message": "Registration successful", "user_id": username}
            
        except Exception as e:
            return {"error": "Registration service error"}, 500
    
    @auth_handle.authenticated()
    @handle.POST
    async def logout(
        self,
        request: PostRequest,
        session_storage: Inject[OmmiSessionStorage] = None,
    ) -> Annotated[dict, JsonResponse]:
        """Logout endpoint - invalidates session."""
        try:
            # In a full implementation, you might want to blacklist the JWT token
            # For now, we'll just return success
            return {"message": "Logout successful"}
            
        except Exception as e:
            return {"error": "Logout service error"}, 500


# =============================================================================
# EXAMPLE 4: MIDDLEWARE CONFIGURATION
# =============================================================================

async def setup_auth_middleware(app: App) -> None:
    """Configure authentication middleware for the application."""
    
    # Create authentication components
    jwt_provider = JWTAuthProvider(
        secret_key="your-super-secret-jwt-key-at-least-32-characters-long",
        algorithm="HS256"
    )
    
    rate_limiter = MemoryRateLimiter(
        default_limits={
            "api_request": "100/min",
            "login": "5/min"
        }
    )
    
    # Add authentication middleware
    auth_middleware = AuthenticationMiddleware(
        providers={"jwt": jwt_provider},
        default_provider="jwt"
    )
    
    # Add authorization middleware
    authz_middleware = AuthorizationMiddleware(
        # Policy configuration would go here
    )
    
    # Add to app (order matters - auth before authz)
    app.add_middleware(auth_middleware)
    app.add_middleware(authz_middleware)


# =============================================================================
# EXAMPLE 5: COMPLETE APPLICATION SETUP
# =============================================================================

async def create_auth_app() -> App:
    """Create a complete Serv application with authentication."""
    
    # Create app
    app = App()
    
    # Setup authentication middleware
    await setup_auth_middleware(app)
    
    # Add routes
    app.router.add_route("/auth", AuthRoutes())
    app.router.add_route("/api", ProtectedRoutes())
    
    return app


# =============================================================================
# EXAMPLE 6: TESTING AUTHENTICATION
# =============================================================================

async def test_authentication_flow():
    """Example testing authentication flow."""
    
    auth_example = AuthenticationExample()
    
    # Test user registration
    print("Testing user registration...")
    success = await auth_example.register_user("testuser", "securepassword123")
    print(f"Registration successful: {success}")
    
    # Test authentication
    print("\\nTesting authentication...")
    auth_result = await auth_example.authenticate_user("testuser", "securepassword123")
    if auth_result:
        print(f"Authentication successful! Token: {auth_result['token'][:50]}...")
    else:
        print("Authentication failed!")
    
    # Test wrong password
    print("\\nTesting wrong password...")
    auth_result = await auth_example.authenticate_user("testuser", "wrongpassword")
    print(f"Wrong password result: {auth_result}")


# =============================================================================
# USAGE INSTRUCTIONS
# =============================================================================

"""
To use these examples in your Serv application:

1. Install the auth dependencies:
   uv add --extra auth

2. Configure your serv.config.yaml with authentication settings:
   ```yaml
   auth:
     providers:
       - type: jwt
         config:
           secret_key: "${JWT_SECRET}"
           algorithm: "HS256"
   ```

3. Set required environment variables:
   export JWT_SECRET="your-super-secret-jwt-key-at-least-32-characters-long"

4. Create your database tables (example SQL):
   ```sql
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

5. Use the route decorators and middleware as shown in the examples above.

For more advanced configurations, see the config_examples.yaml file.
"""

if __name__ == "__main__":
    # Run the test example
    asyncio.run(test_authentication_flow())