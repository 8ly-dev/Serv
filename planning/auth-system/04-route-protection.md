# Route Protection System Design

## Overview

This document outlines the configuration-driven route and router protection system that integrates with the Serv framework's routing mechanism to enforce authentication and authorization policies. All protection is configured via `extension.yaml` files - no route decorators are used.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Request Flow                                │
├─────────────────────────────────────────────────────────────────┤
│  1. Request → Auth Middleware → Policy Engine → Route Handler  │
│                        ↓              ↓                        │
│                   Session Check   Permission Check             │
│                        ↓              ↓                        │
│                   Audit Log      Policy Decision               │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Authentication Middleware

```python
from bevy import Inject, injectable
from serv.middleware import Middleware
from serv.requests import Request
from serv.responses import Response, JsonResponse
from serv.auth import AuthProvider, Session, PolicyEngine

class AuthenticationMiddleware(Middleware):
    """Middleware that handles authentication for all requests."""
    
    @injectable
    async def __call__(
        self,
        request: Request,
        call_next: Callable,
        auth_provider: Inject[AuthProvider],
        policy_engine: Inject[PolicyEngine]
    ) -> Response:
        # Extract session information
        session = await self._extract_session(request, auth_provider)
        
        # Add session to request context for downstream handlers
        request.state.session = session
        request.state.user = await auth_provider.get_current_user(session.id) if session else None
        
        # Check if route requires authentication
        route_protection = await self._get_route_protection(request, policy_engine)
        
        if route_protection and not session:
            return await self._handle_unauthenticated(request, route_protection)
        
        # Check authorization if authenticated
        if session and route_protection:
            authorized = await self._check_authorization(request, session, route_protection, policy_engine)
            if not authorized:
                return await self._handle_unauthorized(request, route_protection)
        
        # Continue with request
        return await call_next(request)
    
    async def _extract_session(self, request: Request, auth_provider: AuthProvider) -> Optional[Session]:
        """Extract session from request (cookie, header, etc.)."""
        # Try session cookie first
        session_id = request.cookies.get('session_id')
        if not session_id:
            # Try Authorization header
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                session_id = auth_header[7:]
        
        if session_id:
            return await auth_provider.validate_session(session_id)
        
        return None
    
    async def _get_route_protection(self, request: Request, policy_engine: PolicyEngine) -> Optional[RouteProtection]:
        """Get protection requirements for current route."""
        return await policy_engine.get_route_protection(request.url.path, request.method)
    
    async def _check_authorization(
        self, 
        request: Request, 
        session: Session, 
        protection: RouteProtection,
        policy_engine: PolicyEngine
    ) -> bool:
        """Check if user is authorized for this route."""
        user = request.state.user
        context = {
            'request': request,
            'session': session,
            'path_params': getattr(request, 'path_params', {}),
            'query_params': dict(request.query_params),
        }
        
        return await policy_engine.evaluate_route_access(user, protection, context)
```

### 2. Policy Engine

```python
@dataclass
class RouteProtection:
    policy_name: str
    permissions: Set[Permission]
    roles: Set[str]
    custom_checks: List[Callable]
    require_fresh_auth: bool = False
    max_auth_age: Optional[timedelta] = None
    ip_restrictions: Optional[List[str]] = None
    time_restrictions: Optional[Dict[str, Any]] = None

class PolicyEngine:
    """Evaluates policies and manages route protection."""
    
    def __init__(
        self,
        policy_provider: PolicyProvider,
        auth_provider: AuthProvider,
        audit_provider: AuditProvider
    ):
        self.policy_provider = policy_provider
        self.auth_provider = auth_provider
        self.audit_provider = audit_provider
        self._route_cache = {}  # Cache compiled route patterns
        self._policy_cache = {}  # Cache policy evaluations
    
    async def get_route_protection(self, path: str, method: str) -> Optional[RouteProtection]:
        """Get protection requirements for a route."""
        cache_key = f"{method}:{path}"
        if cache_key in self._route_cache:
            return self._route_cache[cache_key]
        
        # Find matching route configuration
        protection = await self._find_route_protection(path, method)
        
        # Cache result
        self._route_cache[cache_key] = protection
        return protection
    
    async def evaluate_route_access(
        self, 
        user: User, 
        protection: RouteProtection,
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate if user can access protected route."""
        
        # Start audit trail
        audit_context = {
            'user_id': user.id if user else None,
            'route': context.get('request').url.path,
            'method': context.get('request').method,
            'policy': protection.policy_name
        }
        
        try:
            # Check fresh authentication requirement
            if protection.require_fresh_auth:
                if not await self._check_fresh_auth(user, protection.max_auth_age, context):
                    await self._audit_access_denied(audit_context, "stale_authentication")
                    return False
            
            # Check IP restrictions
            if protection.ip_restrictions:
                if not await self._check_ip_restrictions(protection.ip_restrictions, context):
                    await self._audit_access_denied(audit_context, "ip_restriction")
                    return False
            
            # Check time restrictions
            if protection.time_restrictions:
                if not await self._check_time_restrictions(protection.time_restrictions, user):
                    await self._audit_access_denied(audit_context, "time_restriction")
                    return False
            
            # Evaluate main policy
            policy_result = await self.policy_provider.evaluate_permission(
                user, protection.permissions, context
            )
            
            if policy_result.result == PolicyResult.ALLOW:
                await self._audit_access_granted(audit_context)
                return True
            else:
                await self._audit_access_denied(audit_context, policy_result.reason)
                return False
                
        except Exception as e:
            await self._audit_access_error(audit_context, str(e))
            # Fail secure - deny access on error
            return False
```

### 3. Router Protection

```python
class ProtectedRouter:
    """Router wrapper that enforces authentication before mounting."""
    
    def __init__(
        self,
        router: Router,
        protection_config: Dict[str, Any],
        policy_engine: PolicyEngine
    ):
        self.router = router
        self.protection_config = protection_config
        self.policy_engine = policy_engine
        self._compiled_protection = None
    
    async def should_mount(self, user: Optional[User], context: Dict[str, Any]) -> bool:
        """Determine if router should be mounted for this user."""
        if not self.protection_config:
            return True  # No protection configured
        
        if not user:
            # Check if any routes in this router are public
            return await self._has_public_routes()
        
        # Compile protection requirements
        if not self._compiled_protection:
            self._compiled_protection = await self._compile_protection()
        
        # Check if user meets any of the router's requirements
        for requirement in self._compiled_protection:
            if await self.policy_engine.evaluate_permission(user, requirement, context):
                return True
        
        return False
    
    async def _compile_protection(self) -> List[Permission]:
        """Compile router protection into permission requirements."""
        permissions = []
        
        # Default router policy
        if 'default' in self.protection_config:
            permissions.extend(await self._parse_policy(self.protection_config['default']))
        
        # Route-specific policies  
        if 'routes' in self.protection_config:
            for route_pattern, policy in self.protection_config['routes'].items():
                permissions.extend(await self._parse_policy(policy))
        
        return permissions
```

### 4. Configuration-Based Route Protection

All route protection is configured via `extension.yaml` files. No decorators are used on route methods. Routes are protected based on path patterns and HTTP methods defined in the extension configuration.

#### Route Protection Configuration Example

```yaml
# extension.yaml
auth:
  routes:
    # Public routes
    - path: "/api/health"
      methods: ["GET"]
      policy: "public"
    
    # Authenticated routes
    - path: "/api/posts"
      methods: ["GET"]
      policy: "authenticated"
    
    # Admin routes
    - path: "/api/admin/*"
      methods: ["*"]
      policy: "admin_only"
      require_fresh_auth: true
      max_auth_age: "30m"
    
    # Permission-based routes
    - path: "/api/posts"
      methods: ["POST", "PUT", "DELETE"]
      policy:
        type: "permission"
        permission: "write:posts"
```
```

### 5. Route Handler Integration

Route handlers have no authentication decorators. Protection is entirely handled through middleware based on `extension.yaml` configuration.

```python
class BlogRoute(Route):
    """Example route class - no auth decorators needed."""
    
    @handles.GET
    async def list_posts(
        self,
        request: GetRequest,
        current_user: Inject[Optional[User]] = None  # Injected if authenticated
    ) -> Annotated[list, JsonResponse]:
        # Protection configured in extension.yaml:
        # - path: "/blog/posts"
        #   methods: ["GET"]  
        #   policy: "public"
        return []
    
    @handles.POST
    async def create_post(
        self,
        request: PostRequest,
        current_user: Inject[User]  # Required user injection
    ) -> Annotated[dict, JsonResponse]:
        # Protection configured in extension.yaml:
        # - path: "/blog/posts"
        #   methods: ["POST"]
        #   policy:
        #     type: "permission"
        #     permission: "write:blog"
        return {"message": "Post created"}
    
    @handles.DELETE
    async def delete_post(
        self,
        request: DeleteRequest,
        current_user: Inject[User]
    ) -> Annotated[dict, JsonResponse]:
        # Protection configured in extension.yaml:
        # - path: "/blog/posts/{post_id}"
        #   methods: ["DELETE"]
        #   policy: "admin_only"
        return {"message": "Post deleted"}
```

### 6. Extension Integration

```python
class BlogExtension(Extension):
    """Extension with built-in route protection."""
    
    @on("app.router.setup")
    async def setup_routes(
        self, 
        router: Inject[Router],
        policy_engine: Inject[PolicyEngine]
    ):
        # Load protection configuration from extension.yaml
        auth_config = self.get_auth_config()
        
        # Create protected router
        blog_router = ProtectedRouter(
            Router(),
            auth_config.get('routers', [{}])[0],  # First router config
            policy_engine
        )
        
        # Add routes to protected router
        blog_router.router.add_route("/posts", BlogRoute)
        blog_router.router.add_route("/admin", AdminBlogRoute)
        
        # Mount with protection check
        if await blog_router.should_mount(None, {}):  # Check for public routes
            router.mount("/blog", blog_router.router)
    
    def get_auth_config(self) -> Dict[str, Any]:
        """Load auth configuration from extension.yaml."""
        return self.extension_spec.config.get('auth', {})
```

## Error Handling

### 1. Authentication Errors

```python
class AuthenticationError(Exception):
    """Base authentication error."""
    
    def __init__(self, message: str, redirect_to: Optional[str] = None):
        super().__init__(message)
        self.redirect_to = redirect_to

class UnauthenticatedError(AuthenticationError):
    """User is not authenticated."""
    
    def __init__(self, redirect_to: str = "/login"):
        super().__init__("Authentication required", redirect_to)

class SessionExpiredError(AuthenticationError):
    """User session has expired."""
    
    def __init__(self, redirect_to: str = "/login"):
        super().__init__("Session expired", redirect_to)

class AuthorizationError(Exception):
    """Base authorization error."""
    pass

class InsufficientPermissionsError(AuthorizationError):
    """User lacks required permissions."""
    
    def __init__(self, required_permissions: Set[Permission]):
        self.required_permissions = required_permissions
        super().__init__(f"Insufficient permissions: {required_permissions}")

class ForbiddenError(AuthorizationError):
    """User is forbidden from accessing resource."""
    pass
```

### 2. Error Response Handling

```python
async def handle_auth_error(request: Request, exc: AuthenticationError) -> Response:
    """Handle authentication errors."""
    if request.headers.get('Accept') == 'application/json':
        return JsonResponse(
            {"error": "authentication_required", "message": str(exc)},
            status_code=401
        )
    
    # Redirect to login for HTML requests
    if exc.redirect_to:
        return RedirectResponse(exc.redirect_to, status_code=302)
    
    return Response("Unauthorized", status_code=401)

async def handle_authz_error(request: Request, exc: AuthorizationError) -> Response:
    """Handle authorization errors."""
    if request.headers.get('Accept') == 'application/json':
        return JsonResponse(
            {"error": "insufficient_permissions", "message": str(exc)},
            status_code=403
        )
    
    return Response("Forbidden", status_code=403)
```

## Testing

### 1. Unit Tests

```python
class TestPolicyEngine:
    async def test_route_protection_compilation(self):
        """Test that route protection is compiled correctly."""
        engine = PolicyEngine(mock_policy_provider, mock_auth_provider, mock_audit_provider)
        
        protection = await engine.get_route_protection("/admin/users", "GET")
        
        assert protection.policy_name == "admin_only"
        assert "admin" in protection.roles

    async def test_access_evaluation(self):
        """Test policy evaluation for route access."""
        user = User(id="123", username="admin", roles=["admin"])
        protection = RouteProtection(policy_name="admin_only", roles={"admin"})
        
        result = await engine.evaluate_route_access(user, protection, {})
        
        assert result is True
```

### 2. Integration Tests

```python
class TestRouteProtection:
    async def test_protected_route_access(self, client):
        """Test that protected routes require authentication."""
        response = await client.get("/admin/users")
        assert response.status_code == 401
        
        # Login and try again
        await client.post("/login", data={"username": "admin", "password": "password"})
        response = await client.get("/admin/users")
        assert response.status_code == 200
```

This route protection system provides:
- **Comprehensive Security**: Authentication and authorization at multiple levels
- **Flexible Policies**: Support for complex policy expressions
- **Performance**: Caching and efficient evaluation
- **Audit Trail**: Complete logging of all access decisions
- **Integration**: Seamless integration with Serv routing system
- **Testability**: Clear separation of concerns for testing