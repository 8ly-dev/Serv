"""
Functional tests for all auth interfaces and components.

Tests that all interfaces work correctly, can be implemented,
and handle various scenarios appropriately.
"""

from abc import ABC

import pytest

from serv.auth import (
    AuditEvent,
    AuditLogger,
    AuthProvider,
    AuthResult,
    AuthStatus,
    Credential,
    CredentialVault,
    PolicyEngine,
    RateLimiter,
    Role,
    RoleRegistry,
    Session,
    SessionManager,
    Token,
    TokenService,
)


class TestInterfaceDefinitions:
    """Test that all interfaces are properly defined as abstract base classes."""

    def test_all_interfaces_are_abstract(self):
        """Test that all auth interfaces are abstract base classes."""
        interfaces = [
            AuthProvider,
            SessionManager,
            PolicyEngine,
            TokenService,
            RateLimiter,
            AuditLogger,
            RoleRegistry,
            CredentialVault,
        ]

        for interface in interfaces:
            assert issubclass(interface, ABC), (
                f"{interface.__name__} should be abstract"
            )

    def test_interfaces_cannot_be_instantiated(self):
        """Test that abstract interfaces cannot be instantiated directly."""
        interfaces = [
            AuthProvider,
            SessionManager,
            PolicyEngine,
            TokenService,
            RateLimiter,
            AuditLogger,
            RoleRegistry,
            CredentialVault,
        ]

        for interface in interfaces:
            with pytest.raises(TypeError, match="Can't instantiate abstract class"):
                interface({})

    def test_all_interfaces_have_cleanup_method(self):
        """Test that all interfaces have an abstract cleanup method."""
        interfaces = [
            AuthProvider,
            SessionManager,
            PolicyEngine,
            TokenService,
            RateLimiter,
            AuditLogger,
            RoleRegistry,
            CredentialVault,
        ]

        for interface in interfaces:
            assert hasattr(interface, "cleanup"), (
                f"{interface.__name__} should have cleanup method"
            )
            # Check that cleanup is abstract
            assert "cleanup" in interface.__abstractmethods__, (
                f"{interface.__name__}.cleanup should be abstract"
            )


class TestAuthProvider:
    """Test AuthProvider interface functionality."""

    @pytest.mark.asyncio
    async def test_successful_authentication(self, mock_auth_provider):
        """Test successful authentication flow."""
        request_context = {"username": "valid_user", "password": "correct_password"}

        result = await mock_auth_provider.initiate_auth(request_context)

        assert result.status == AuthStatus.SUCCESS
        assert result.user_id == "user_123"
        assert result.user_context["username"] == "valid_user"
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_failed_authentication(self, mock_auth_provider):
        """Test failed authentication with invalid credentials."""
        request_context = {"username": "invalid_user", "password": "wrong_password"}

        result = await mock_auth_provider.initiate_auth(request_context)

        assert result.status == AuthStatus.INVALID_CREDENTIALS
        assert result.user_id is None
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_account_locked_authentication(self, mock_auth_provider):
        """Test authentication with locked account."""
        request_context = {"username": "locked_user", "password": "any_password"}

        result = await mock_auth_provider.initiate_auth(request_context)

        assert result.status == AuthStatus.ACCOUNT_LOCKED
        assert result.user_id is None
        assert "locked" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_valid_credential_validation(self, mock_auth_provider):
        """Test valid credential validation."""
        credential_payload = {"credential": "valid_token"}

        result = await mock_auth_provider.validate_credential(credential_payload)

        assert result.is_valid is True
        assert result.user_id == "user_123"
        assert result.user_context["username"] == "valid_user"

    @pytest.mark.asyncio
    async def test_invalid_credential_validation(self, mock_auth_provider):
        """Test invalid credential validation."""
        credential_payload = {"credential": "invalid_token"}

        result = await mock_auth_provider.validate_credential(credential_payload)

        assert result.is_valid is False
        assert result.user_id is None
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_successful_session_refresh(self, mock_auth_provider):
        """Test successful session refresh."""
        session_data = {"refresh_token": "valid_refresh"}

        result = await mock_auth_provider.refresh_session(session_data)

        assert result.success is True
        assert result.new_token == "new_access_token"
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_failed_session_refresh(self, mock_auth_provider):
        """Test failed session refresh."""
        session_data = {"refresh_token": "invalid_refresh"}

        result = await mock_auth_provider.refresh_session(session_data)

        assert result.success is False
        assert result.new_token is None
        assert result.error_message is not None

    def test_provider_metadata(self, mock_auth_provider):
        """Test provider metadata methods."""
        name = mock_auth_provider.get_provider_name()
        methods = mock_auth_provider.get_supported_methods()

        assert isinstance(name, str)
        assert len(name) > 0
        assert isinstance(methods, list)
        assert len(methods) > 0


class TestSessionManager:
    """Test SessionManager interface functionality."""

    @pytest.mark.asyncio
    async def test_create_session(
        self, mock_session_manager, sample_user_context, sample_device_fingerprint
    ):
        """Test session creation."""
        session = await mock_session_manager.create_session(
            sample_user_context, sample_device_fingerprint
        )

        assert isinstance(session, Session)
        assert session.user_id == sample_user_context["user_id"]
        assert session.device_fingerprint == sample_device_fingerprint
        assert not session.is_expired()
        assert len(session.session_id) > 30  # Should be cryptographically secure

    @pytest.mark.asyncio
    async def test_validate_existing_session(
        self, mock_session_manager, sample_user_context, sample_device_fingerprint
    ):
        """Test validation of existing session."""
        # Create session first
        created_session = await mock_session_manager.create_session(
            sample_user_context, sample_device_fingerprint
        )

        # Validate the session
        validated_session = await mock_session_manager.validate_session(
            created_session.session_id, sample_device_fingerprint
        )

        assert validated_session is not None
        assert validated_session.session_id == created_session.session_id
        assert validated_session.user_id == sample_user_context["user_id"]

    @pytest.mark.asyncio
    async def test_validate_nonexistent_session(
        self, mock_session_manager, sample_device_fingerprint
    ):
        """Test validation of non-existent session."""
        result = await mock_session_manager.validate_session(
            "nonexistent_session_id", sample_device_fingerprint
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_session_wrong_fingerprint(
        self, mock_session_manager, sample_user_context, sample_device_fingerprint
    ):
        """Test validation with wrong device fingerprint."""
        # Create session
        created_session = await mock_session_manager.create_session(
            sample_user_context, sample_device_fingerprint
        )

        # Try to validate with wrong fingerprint
        result = await mock_session_manager.validate_session(
            created_session.session_id, "wrong_fingerprint"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_session(
        self, mock_session_manager, sample_user_context, sample_device_fingerprint
    ):
        """Test session invalidation."""
        # Create session
        created_session = await mock_session_manager.create_session(
            sample_user_context, sample_device_fingerprint
        )

        # Invalidate session
        success = await mock_session_manager.invalidate_session(
            created_session.session_id
        )
        assert success is True

        # Verify session is invalidated
        result = await mock_session_manager.validate_session(
            created_session.session_id, sample_device_fingerprint
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_user_sessions(
        self, mock_session_manager, sample_user_context, sample_device_fingerprint
    ):
        """Test invalidation of all user sessions."""
        # Create multiple sessions for the same user
        session1 = await mock_session_manager.create_session(
            sample_user_context, sample_device_fingerprint
        )
        session2 = await mock_session_manager.create_session(
            sample_user_context, "different_fingerprint"
        )

        # Invalidate all user sessions
        count = await mock_session_manager.invalidate_user_sessions(
            sample_user_context["user_id"]
        )
        assert count == 2

        # Verify sessions are invalidated
        result1 = await mock_session_manager.validate_session(
            session1.session_id, sample_device_fingerprint
        )
        result2 = await mock_session_manager.validate_session(
            session2.session_id, "different_fingerprint"
        )
        assert result1 is None
        assert result2 is None


class TestDataTypes:
    """Test data type functionality and security features."""

    def test_session_creation(self, sample_user_context, sample_device_fingerprint):
        """Test session creation with secure defaults."""
        session = Session.create(
            user_id=sample_user_context["user_id"],
            user_context=sample_user_context,
            device_fingerprint=sample_device_fingerprint,
        )

        assert session.user_id == sample_user_context["user_id"]
        assert session.device_fingerprint == sample_device_fingerprint
        assert not session.is_expired()
        assert len(session.session_id) > 30  # Cryptographically secure
        assert session.created_at <= session.expires_at

    def test_token_creation_and_security(self):
        """Test token creation and security features."""
        token = Token.create(
            token_value="secret_token_value",
            token_type="access",
            user_id="user_123",
            payload={"sub": "user_123"},
            expires_in=3600,
        )

        assert token.token_value == "secret_token_value"
        assert token.user_id == "user_123"
        assert not token.is_expired()

        # Security test: token value should not appear in repr
        token_repr = repr(token)
        assert "secret_token_value" not in token_repr
        assert "user_123" in token_repr  # User ID is safe to show

    def test_auth_result_validation(self):
        """Test AuthResult validation rules."""
        # Success result must have user_id
        with pytest.raises(
            ValueError, match="Successful authentication must include user_id"
        ):
            AuthResult(status=AuthStatus.SUCCESS, user_id=None)

        # Valid success result
        result = AuthResult(status=AuthStatus.SUCCESS, user_id="user_123")
        assert result.status == AuthStatus.SUCCESS
        assert result.user_id == "user_123"

    def test_audit_event_security_validation(self):
        """Test audit event security validation."""
        # Should reject sensitive data in actor_info
        with pytest.raises(ValueError, match="Sensitive data not allowed"):
            AuditEvent.create(
                event_type="test",
                actor_info={"password": "secret"},  # Should be rejected
                resource_info={},
                outcome="success",
            )

        # Should accept safe data
        event = AuditEvent.create(
            event_type="authentication",
            actor_info={"actor_id": "user_123", "actor_type": "user"},
            resource_info={"resource_type": "session"},
            outcome="success",
        )
        assert event.event_type == "authentication"
        assert event.outcome == "success"

    def test_role_permissions(self):
        """Test role and permission functionality."""
        role = Role(
            name="admin",
            permissions={"read", "write", "delete"},
            description="Administrator role",
        )

        assert role.has_permission("read")
        assert role.has_permission("write")
        assert not role.has_permission("execute")

        # Test permission management
        role.add_permission("execute")
        assert role.has_permission("execute")

        role.remove_permission("delete")
        assert not role.has_permission("delete")

    def test_credential_security(self):
        """Test credential security features."""
        credential = Credential.create(user_id="user_123", credential_type="password")

        assert credential.user_id == "user_123"
        assert credential.credential_type == "password"
        assert credential.is_active
        assert not credential.is_expired()

        # Security test: credential details should not appear in repr
        cred_repr = repr(credential)
        assert "user_123" in cred_repr
        assert "password" in cred_repr
        # No actual credential data should be exposed
