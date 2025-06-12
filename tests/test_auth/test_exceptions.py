"""Test cases for auth exceptions."""

import pytest

from serv.auth.exceptions import (
    AuthError,
    AuthenticationError,
    AuthorizationError,
    AuthValidationError,
    SessionExpiredError,
    InvalidCredentialsError,
    PermissionDeniedError,
    AuditError,
    ConfigurationError,
    ProviderError,
)


class TestAuthExceptions:
    """Test auth exception hierarchy and functionality."""

    def test_base_auth_error(self):
        """Test base AuthError exception."""
        error = AuthError("Test error", {"code": 123})

        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {"code": 123}

    def test_auth_error_without_details(self):
        """Test AuthError without details."""
        error = AuthError("Test error")

        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {}

    def test_authentication_error(self):
        """Test AuthenticationError inheritance."""
        error = AuthenticationError("Auth failed")

        assert isinstance(error, AuthError)
        assert str(error) == "Auth failed"

    def test_authorization_error(self):
        """Test AuthorizationError inheritance."""
        error = AuthorizationError("Access denied")

        assert isinstance(error, AuthError)
        assert str(error) == "Access denied"

    def test_auth_validation_error(self):
        """Test AuthValidationError inheritance."""
        error = AuthValidationError("Invalid data")

        assert isinstance(error, AuthError)
        assert str(error) == "Invalid data"

    def test_session_expired_error(self):
        """Test SessionExpiredError inheritance."""
        error = SessionExpiredError("Session expired")

        assert isinstance(error, AuthenticationError)
        assert isinstance(error, AuthError)
        assert str(error) == "Session expired"

    def test_invalid_credentials_error(self):
        """Test InvalidCredentialsError inheritance."""
        error = InvalidCredentialsError("Bad credentials")

        assert isinstance(error, AuthenticationError)
        assert isinstance(error, AuthError)
        assert str(error) == "Bad credentials"

    def test_permission_denied_error_with_resource(self):
        """Test PermissionDeniedError with resource."""
        error = PermissionDeniedError("read:posts", "blog_post", {"user_id": "123"})

        assert isinstance(error, AuthorizationError)
        assert isinstance(error, AuthError)
        assert error.permission == "read:posts"
        assert error.resource == "blog_post"
        assert error.details == {"user_id": "123"}
        assert "read:posts" in str(error)
        assert "blog_post" in str(error)

    def test_permission_denied_error_without_resource(self):
        """Test PermissionDeniedError without resource."""
        error = PermissionDeniedError("admin")

        assert isinstance(error, AuthorizationError)
        assert error.permission == "admin"
        assert error.resource is None
        assert error.details == {}
        assert "admin" in str(error)
        assert "blog_post" not in str(error)

    def test_audit_error(self):
        """Test AuditError inheritance."""
        error = AuditError("Audit failed")

        assert isinstance(error, AuthError)
        assert str(error) == "Audit failed"

    def test_configuration_error(self):
        """Test ConfigurationError inheritance."""
        error = ConfigurationError("Bad config")

        assert isinstance(error, AuthError)
        assert str(error) == "Bad config"

    def test_provider_error(self):
        """Test ProviderError inheritance."""
        error = ProviderError("Provider failed")

        assert isinstance(error, AuthError)
        assert str(error) == "Provider failed"
