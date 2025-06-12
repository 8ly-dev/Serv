"""Exception classes for the authentication system."""


class AuthError(Exception):
    """Base exception for all authentication-related errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthenticationError(AuthError):
    """Raised when authentication fails."""

    pass


class AuthorizationError(AuthError):
    """Raised when authorization fails (user lacks required permissions)."""

    pass


class AuthValidationError(AuthError):
    """Raised when auth data validation fails."""

    pass


class SessionExpiredError(AuthenticationError):
    """Raised when a session has expired."""

    pass


class InvalidCredentialsError(AuthenticationError):
    """Raised when provided credentials are invalid."""

    pass


class PermissionDeniedError(AuthorizationError):
    """Raised when a user lacks required permissions for an action."""

    def __init__(
        self, permission: str, resource: str | None = None, details: dict | None = None
    ):
        self.permission = permission
        self.resource = resource

        if resource:
            message = f"Permission denied: '{permission}' for resource '{resource}'"
        else:
            message = f"Permission denied: '{permission}'"

        super().__init__(message, details)


class AuditError(AuthError):
    """Raised when audit operations fail."""

    pass


class ConfigurationError(AuthError):
    """Raised when auth configuration is invalid."""

    pass


class ProviderError(AuthError):
    """Raised when auth provider operations fail."""

    pass


class ProviderNotFoundError(ProviderError):
    """Raised when a required auth provider is not found."""

    pass


class ProviderInitializationError(ProviderError):
    """Raised when auth provider initialization fails."""

    pass
