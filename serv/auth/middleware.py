"""
Authentication and authorization middleware for the Serv framework.

This module provides base middleware classes for integrating authentication
and authorization into the request processing pipeline.

Security considerations:
- Authentication checks must be performed before route handlers
- Authorization must be checked for every protected resource
- Security headers should be added to all responses
- Rate limiting must be enforced reliably
"""

from datetime import UTC
from typing import Any

from bevy import Inject

from serv.extensions.middleware import ServMiddleware
from serv.requests import Request
from serv.responses import ResponseBuilder

from .types import AuthResult, AuthStatus, PolicyDecision, RateLimitResult
from .utils import generate_device_fingerprint


class AuthenticationMiddleware(ServMiddleware):
    """
    Base authentication middleware.

    Handles user authentication by checking credentials, validating sessions,
    and establishing user context for downstream handlers.

    Security features:
    - Automatic session validation
    - Device fingerprint verification
    - Authentication state injection
    - Security header management
    """

    async def enter(
        self, request: Request = Inject, response: ResponseBuilder = Inject
    ):
        """
        Authenticate the user before request processing.

        Checks for authentication credentials and establishes user context.
        Sets authentication state in the request for downstream handlers.
        """
        # Generate device fingerprint for session security
        fingerprint = generate_device_fingerprint(request)

        # Check for existing session or authentication
        auth_result = await self._authenticate_request(request, fingerprint)

        # Set authentication state in request context
        request.auth = auth_result
        request.device_fingerprint = fingerprint

        # Add security headers
        await self._add_security_headers(response)

    async def _authenticate_request(
        self, request: Request, fingerprint: str
    ) -> AuthResult:
        """
        Authenticate the incoming request.

        Default implementation returns unauthenticated state.
        Subclasses should override to implement actual authentication.

        Args:
            request: The HTTP request
            fingerprint: Device fingerprint

        Returns:
            AuthResult with authentication status
        """
        return AuthResult(
            status=AuthStatus.INVALID_CREDENTIALS,
            error_message="No authentication provided",
        )

    async def _add_security_headers(self, response: ResponseBuilder):
        """
        Add security headers to the response.

        Args:
            response: Response builder to add headers to
        """
        # Security headers for auth-related responses
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

        for header, value in headers.items():
            response.header(header, value)


class AuthorizationMiddleware(ServMiddleware):
    """
    Base authorization middleware.

    Handles authorization checks by evaluating user permissions against
    requested resources and actions.

    Security features:
    - Permission-based access control
    - Policy evaluation
    - Resource protection
    - Authorization audit logging
    """

    async def enter(
        self, request: Request = Inject, response: ResponseBuilder = Inject
    ):
        """
        Check authorization before request processing.

        Evaluates user permissions for the requested resource.
        Blocks unauthorized access with appropriate error response.
        """
        # Skip authorization if not authenticated
        if not hasattr(request, "auth") or not request.auth.user_id:
            return  # Let authentication middleware handle this

        # Determine required permissions for this request
        required_action = await self._get_required_action(request)

        if required_action:
            # Check authorization
            auth_decision = await self._check_authorization(
                request.auth, required_action
            )

            if not auth_decision.allowed:
                # Return authorization error
                await self._handle_authorization_denied(
                    response, auth_decision, request
                )

    async def _get_required_action(self, request: Request) -> str | None:
        """
        Determine the required action for authorization.

        Default implementation returns None (no authorization required).
        Subclasses should override to implement action determination.

        Args:
            request: The HTTP request

        Returns:
            Action descriptor string or None
        """
        return None

    async def _check_authorization(
        self, auth_result: AuthResult, action: str
    ) -> PolicyDecision:
        """
        Check if user is authorized for the action.

        Default implementation allows all actions.
        Subclasses should override to implement actual authorization.

        Args:
            auth_result: Authentication result
            action: Action being requested

        Returns:
            PolicyDecision with authorization result
        """
        return PolicyDecision(allowed=True, reason="Default policy allows all actions")

    async def _handle_authorization_denied(
        self, response: ResponseBuilder, decision: PolicyDecision, request: Request
    ):
        """
        Handle authorization denial.

        Args:
            response: Response builder
            decision: Authorization decision
            request: The request being denied
        """
        # Log authorization failure (with sanitized data)
        # TODO: Implement audit logging with proper logger injection
        # request_info = mask_sensitive_data({
        #     "method": request.method,
        #     "path": str(request.url.path),
        #     "user_id": getattr(request.auth, "user_id", None),
        # })

        # Return 403 Forbidden
        error_data = {
            "error": "Authorization denied",
            "message": "Insufficient permissions for this resource",
        }

        response.status_code(403)
        response.json(error_data)


class RateLimitMiddleware(ServMiddleware):
    """
    Rate limiting middleware.

    Protects against abuse by limiting request rates from specific
    identifiers (IP addresses, user accounts, etc.).

    Security features:
    - Configurable rate limits per action
    - Multiple identifier strategies
    - Rate limit headers
    - Automatic blocking of excessive requests
    """

    def __init__(self, container, config: dict[str, Any] | None = None):
        super().__init__(container, config)
        self.rate_limits = config.get("rate_limits", {}) if config else {}

    async def enter(
        self, request: Request = Inject, response: ResponseBuilder = Inject
    ):
        """
        Check rate limits before request processing.

        Blocks requests that exceed configured rate limits.
        Adds rate limit headers to response.
        """
        # Determine rate limit identifier
        identifier = await self._get_rate_limit_identifier(request)

        # Determine action for rate limiting
        action = await self._get_rate_limit_action(request)

        # Check rate limit
        limit_result = await self._check_rate_limit(identifier, action)

        # Add rate limit headers
        await self._add_rate_limit_headers(response, limit_result)

        # Block if rate limited
        if not limit_result.allowed:
            await self._handle_rate_limit_exceeded(response, limit_result)

    async def _get_rate_limit_identifier(self, request: Request) -> str:
        """
        Get identifier for rate limiting.

        Default implementation uses IP address.
        Subclasses can override for user-based or other strategies.

        Args:
            request: The HTTP request

        Returns:
            Rate limit identifier string
        """
        # Use IP address as default identifier
        client_ip = (
            getattr(request.client, "host", "unknown") if request.client else "unknown"
        )
        return f"ip:{client_ip}"

    async def _get_rate_limit_action(self, request: Request) -> str:
        """
        Get action for rate limiting.

        Default implementation uses HTTP method.
        Subclasses can override for more specific actions.

        Args:
            request: The HTTP request

        Returns:
            Rate limit action string
        """
        return request.method.lower()

    async def _check_rate_limit(self, identifier: str, action: str) -> RateLimitResult:
        """
        Check rate limit for identifier/action.

        Default implementation allows all requests.
        Subclasses should override to implement actual rate limiting.

        Args:
            identifier: Rate limit identifier
            action: Action being rate limited

        Returns:
            RateLimitResult with limit status
        """
        from datetime import datetime

        return RateLimitResult(
            allowed=True, limit=1000, remaining=999, reset_time=datetime.now(UTC)
        )

    async def _add_rate_limit_headers(
        self, response: ResponseBuilder, limit_result: RateLimitResult
    ):
        """
        Add rate limit headers to response.

        Args:
            response: Response builder
            limit_result: Rate limit result
        """
        headers = {
            "X-RateLimit-Limit": str(limit_result.limit),
            "X-RateLimit-Remaining": str(limit_result.remaining),
            "X-RateLimit-Reset": str(int(limit_result.reset_time.timestamp())),
        }

        if limit_result.retry_after:
            headers["Retry-After"] = str(limit_result.retry_after)

        for header, value in headers.items():
            response.header(header, value)

    async def _handle_rate_limit_exceeded(
        self, response: ResponseBuilder, limit_result: RateLimitResult
    ):
        """
        Handle rate limit exceeded.

        Args:
            response: Response builder
            limit_result: Rate limit result
        """
        error_data = {
            "error": "Rate limit exceeded",
            "message": f"Too many requests. Try again in {limit_result.retry_after} seconds.",
            "retry_after": limit_result.retry_after,
        }

        response.status_code(429)
        response.json(error_data)


class SecurityHeadersMiddleware(ServMiddleware):
    """
    Security headers middleware.

    Adds comprehensive security headers to all responses to protect
    against common web vulnerabilities.

    Security features:
    - Content Security Policy
    - HSTS headers
    - Anti-clickjacking protection
    - XSS protection
    - Content type validation
    """

    def __init__(self, container, config: dict[str, Any] | None = None):
        super().__init__(container, config)
        self.security_config = config.get("security", {}) if config else {}

    async def leave(self, response: ResponseBuilder = Inject):
        """
        Add security headers after request processing.
        """
        # Core security headers
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "X-Permitted-Cross-Domain-Policies": "none",
        }

        # HSTS header for HTTPS
        if self.security_config.get("force_https", False):
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content Security Policy
        csp = self.security_config.get("content_security_policy")
        if csp:
            headers["Content-Security-Policy"] = csp

        # Permissions Policy
        permissions_policy = self.security_config.get("permissions_policy")
        if permissions_policy:
            headers["Permissions-Policy"] = permissions_policy

        for header, value in headers.items():
            response.header(header, value)
