"""
Tests for the auth configuration system and factory.

These tests verify that the auth configuration system can properly load
concrete implementations and register them in the DI container.
"""

from unittest.mock import Mock

import pytest
from bevy import get_registry

from serv.auth import (
    AuditLogger,
    AuthConfigError,
    AuthProvider,
    AuthSystemFactory,
    BackendLoader,
    CredentialVault,
    PolicyEngine,
    RateLimiter,
    RoleRegistry,
    SessionManager,
    TokenService,
    create_auth_system,
)


class TestBackendLoader:
    """Test the backend loading functionality."""

    def test_load_class_success(self):
        """Test loading a valid class."""
        loader = BackendLoader()
        cls = loader.load_class("builtins:dict")
        assert cls is dict

    def test_load_class_invalid_format(self):
        """Test loading with invalid module path format."""
        loader = BackendLoader()
        with pytest.raises(AuthConfigError, match="Invalid module path format"):
            loader.load_class("invalid_format")

    def test_load_class_missing_module(self):
        """Test loading from non-existent module."""
        loader = BackendLoader()
        with pytest.raises(AuthConfigError, match="Could not import module"):
            loader.load_class("nonexistent.module:Class")

    def test_load_class_missing_class(self):
        """Test loading non-existent class from valid module."""
        loader = BackendLoader()
        with pytest.raises(AuthConfigError, match="Class.*not found"):
            loader.load_class("builtins:NonExistentClass")


class MockAuthProvider(AuthProvider):
    """Mock auth provider for testing."""

    def _validate_config(self, config):
        pass

    async def authenticate(self, credentials, request_context=None):
        return Mock()

    async def refresh_authentication(self, refresh_token, request_context=None):
        return Mock()

    async def validate_session(self, session_token, request_context=None):
        return Mock()

    async def initiate_auth(self, request_context=None):
        return Mock()

    async def refresh_session(self, refresh_token, request_context=None):
        return Mock()

    async def validate_credential(self, credential_data, request_context=None):
        return Mock()

    async def cleanup(self):
        pass


class MockSessionManager(SessionManager):
    """Mock session manager for testing."""

    def _validate_config(self, config):
        pass

    async def create_session(self, user_data, request_context=None):
        return Mock()

    async def get_session(self, session_id, request_context=None):
        return Mock()

    async def update_session(self, session_id, data, request_context=None):
        return Mock()

    async def delete_session(self, session_id, request_context=None):
        return Mock()

    async def cleanup_expired_sessions(self):
        pass

    async def cleanup(self):
        pass

    async def extend_session(self, session_id, extension_time, request_context=None):
        return Mock()

    async def invalidate_session(self, session_id, request_context=None):
        return Mock()

    async def invalidate_user_sessions(
        self, user_id, exclude_session=None, request_context=None
    ):
        return Mock()

    async def validate_session(self, session_token, request_context=None):
        return Mock()


class MockCredentialVault(CredentialVault):
    """Mock credential vault for testing."""

    def _validate_config(self, config):
        pass

    async def store_credential(
        self, user_id, credential_type, data, metadata=None, expires_in=None
    ):
        return "mock_credential_id"

    async def verify_credential(self, credential_id, input_data):
        return True

    async def update_credential(self, credential_id, new_data, metadata=None):
        return True

    async def revoke_credential(self, credential_id):
        return True

    async def get_user_credentials(
        self, user_id, credential_type=None, active_only=True
    ):
        return []

    async def cleanup_expired_credentials(self):
        return 0

    async def _get_encryption_key(self):
        return b"mock_encryption_key"

    async def cleanup(self):
        pass


class MockRateLimiter(RateLimiter):
    """Mock rate limiter for testing."""

    def _validate_config(self, config):
        pass

    async def check_limit(self, identifier, action):
        from serv.auth.types import RateLimitResult

        return RateLimitResult(allowed=True, limit=100, remaining=99, reset_time=None)

    async def track_attempt(self, identifier, action):
        from serv.auth.types import RateLimitResult

        return RateLimitResult(allowed=True, limit=100, remaining=98, reset_time=None)

    async def reset_limits(self, identifier, action=None):
        pass

    async def get_limit_info(self, action):
        return {"limit": 100, "window": "hour"}

    async def get_top_offenders(self, action, limit=10):
        return []

    async def cleanup_expired_limits(self):
        return 0

    async def cleanup(self):
        pass


class MockTokenService(TokenService):
    """Mock token service for testing."""

    def _validate_config(self, config):
        pass

    async def generate_token(self, payload, token_type="access", expires_in=None):
        from serv.auth.types import Token

        return Token(
            token_id="mock_token_id",
            token_value="mock_token_value",
            token_type=token_type,
            user_id=payload.get("user_id", "mock_user"),
            payload=payload,
            created_at=None,
            expires_at=None,
            is_active=True,
        )

    async def validate_token(self, token_str):
        from serv.auth.types import Token

        return Token(
            token_id="mock_token_id",
            token_value=token_str,
            token_type="access",
            user_id="mock_user",
            payload={"user_id": "mock_user"},
            created_at=None,
            expires_at=None,
            is_active=True,
        )

    async def refresh_token(self, refresh_token):
        from serv.auth.types import Token

        return Token(
            token_id="mock_new_token_id",
            token_value="mock_new_token_value",
            token_type="access",
            user_id="mock_user",
            payload={"user_id": "mock_user"},
            created_at=None,
            expires_at=None,
            is_active=True,
        )

    async def revoke_token(self, token_str):
        return True

    async def revoke_user_tokens(self, user_id, token_type=None):
        return 1

    async def cleanup_expired_tokens(self):
        return 0

    async def _get_user_tokens(self, user_id, token_type=None):
        return []

    async def cleanup(self):
        pass


class MockAuditLogger(AuditLogger):
    """Mock audit logger for testing."""

    def _validate_config(self, config):
        pass

    async def log_event(self, event):
        return "mock_event_id"

    async def query_events(
        self, start_time=None, end_time=None, user_id=None, event_type=None, limit=100
    ):
        from serv.auth.types import AuditEvent
        
        return [
            AuditEvent(
                event_id="mock_event_id",
                event_type="mock_type",
                user_id="mock_user",
                timestamp=None,
                result="success",
            )
        ]

    async def get_event_statistics(self, start_time=None, end_time=None):
        return {"total_events": 10, "event_types": {"test": 5}}

    async def verify_log_integrity(self):
        return True

    async def cleanup_old_events(self):
        return 5

    async def cleanup(self):
        pass


class MockPolicyEngine(PolicyEngine):
    """Mock policy engine for testing."""

    def _validate_config(self, config):
        pass

    async def evaluate(self, resource, action, user_context):
        from serv.auth.types import PolicyDecision
        
        return PolicyDecision(
            allowed=True,
            reason="Mock policy allows",
            policy_id="mock_policy",
            applied_policies=[],
        )

    async def register_policy(self, policy):
        return "mock_policy_id"

    async def bulk_evaluate(self, requests):
        from serv.auth.types import PolicyDecision
        
        return [
            PolicyDecision(
                allowed=True,
                reason="Mock bulk evaluation",
                policy_id="mock_policy",
                applied_policies=[],
            )
            for _ in requests
        ]

    async def get_user_permissions(self, user_context):
        return {"read", "write"}

    async def cleanup(self):
        pass


class MockRoleRegistry(RoleRegistry):
    """Mock role registry for testing."""

    def _validate_config(self, config):
        pass

    async def define_role(self, name, description="", permissions=None):
        from serv.auth.types import Role
        
        return Role(
            role_id="mock_role_id",
            name=name,
            description=description,
            permissions=permissions or [],
            metadata={},
            created_at=None,
            is_active=True,
        )

    async def define_permission(self, name, description="", resource=None):
        from serv.auth.types import Permission
        
        return Permission(
            permission_id="mock_permission_id",
            name=name,
            description=description,
            resource=resource,
            created_at=None,
            is_active=True,
        )

    async def assign_role(self, user_id, role_name):
        return True

    async def revoke_role(self, user_id, role_name):
        return True

    async def check_permission(self, user_id, permission_name):
        return True

    async def get_user_roles(self, user_id):
        return ["mock_role"]

    async def get_user_permissions(self, user_id):
        return ["mock_permission"]

    async def cleanup(self):
        pass


class TestAuthSystemFactory:
    """Test the auth system factory."""

    def setup_method(self):
        """Set up test container."""
        registry = get_registry()
        self.container = registry.create_container()
        self.factory = AuthSystemFactory(self.container)

    def test_create_auth_provider_jwt(self):
        """Test creating JWT auth provider."""
        config = {
            "type": "jwt",
            "config": {"secret_key": "test-secret", "algorithm": "HS256"},
        }

        # Mock the loader to return our mock class for the JWT provider path
        def mock_load_class(path):
            if path == "serv.bundled.auth.providers.jwt_provider:JwtAuthProvider":
                return MockAuthProvider
            raise ValueError(f"Unexpected path: {path}")

        self.factory._loader.load_class = mock_load_class

        provider = self.factory.create_auth_provider(config)
        assert isinstance(provider, MockAuthProvider)
        assert provider.config == config["config"]

    def test_create_auth_provider_missing_type(self):
        """Test creating auth provider without type."""
        config = {"config": {"secret": "test"}}

        with pytest.raises(AuthConfigError, match="missing 'type' field"):
            self.factory.create_auth_provider(config)

    def test_create_auth_provider_unknown_type(self):
        """Test creating auth provider with unknown type."""
        config = {"type": "unknown", "config": {}}

        with pytest.raises(AuthConfigError, match="Unknown auth provider type"):
            self.factory.create_auth_provider(config)

    def test_create_session_storage(self):
        """Test creating session storage."""
        config = {
            "backend": "test.module:MockSessionManager",
            "database_qualifier": "auth",
            "session_timeout": 3600,
        }

        # Mock the loader
        self.factory._loader.load_class = lambda path: MockSessionManager

        storage = self.factory.create_session_storage(config)
        assert isinstance(storage, MockSessionManager)
        assert storage.config["database_qualifier"] == "auth"
        assert "backend" not in storage.config  # Should be excluded

    def test_create_session_storage_missing_backend(self):
        """Test creating session storage without backend."""
        config = {"database_qualifier": "auth"}

        with pytest.raises(AuthConfigError, match="missing 'backend' field"):
            self.factory.create_session_storage(config)

    def test_create_credential_vault(self):
        """Test creating credential vault."""
        config = {"backend": "test.module:MockCredentialVault", "bcrypt_rounds": 12}

        # Mock the loader
        self.factory._loader.load_class = lambda path: MockCredentialVault

        vault = self.factory.create_credential_vault(config)
        assert isinstance(vault, MockCredentialVault)
        assert vault.config["bcrypt_rounds"] == 12

    def test_create_rate_limiter(self):
        """Test creating rate limiter."""
        config = {
            "backend": "test.module:MockRateLimiter",
            "default_limits": {"login": "5/min"},
        }

        # Mock the loader
        self.factory._loader.load_class = lambda path: MockRateLimiter

        limiter = self.factory.create_rate_limiter(config)
        assert isinstance(limiter, MockRateLimiter)
        assert limiter.config["default_limits"] == {"login": "5/min"}

    def test_create_audit_logger(self):
        """Test creating audit logger."""
        config = {
            "backend": "test.module:MockAuditLogger",
            "retention_days": 365,
        }

        # Mock the loader
        self.factory._loader.load_class = lambda path: MockAuditLogger

        logger = self.factory.create_audit_logger(config)
        assert isinstance(logger, MockAuditLogger)
        assert logger.config["retention_days"] == 365

    def test_create_audit_logger_missing_backend(self):
        """Test creating audit logger without backend."""
        config = {"retention_days": 365}

        with pytest.raises(AuthConfigError, match="missing 'backend' field"):
            self.factory.create_audit_logger(config)

    def test_create_policy_engine(self):
        """Test creating policy engine."""
        config = {
            "backend": "test.module:MockPolicyEngine",
            "default_decision": "deny",
        }

        # Mock the loader
        self.factory._loader.load_class = lambda path: MockPolicyEngine

        engine = self.factory.create_policy_engine(config)
        assert isinstance(engine, MockPolicyEngine)
        assert engine.config["default_decision"] == "deny"

    def test_create_policy_engine_missing_backend(self):
        """Test creating policy engine without backend."""
        config = {"default_decision": "deny"}

        with pytest.raises(AuthConfigError, match="missing 'backend' field"):
            self.factory.create_policy_engine(config)

    def test_create_role_registry(self):
        """Test creating role registry."""
        config = {
            "backend": "test.module:MockRoleRegistry",
            "cache_expiry": 300,
        }

        # Mock the loader
        self.factory._loader.load_class = lambda path: MockRoleRegistry

        registry = self.factory.create_role_registry(config)
        assert isinstance(registry, MockRoleRegistry)
        assert registry.config["cache_expiry"] == 300

    def test_create_role_registry_missing_backend(self):
        """Test creating role registry without backend."""
        config = {"cache_expiry": 300}

        with pytest.raises(AuthConfigError, match="missing 'backend' field"):
            self.factory.create_role_registry(config)

    def test_configure_auth_system_full(self):
        """Test configuring a complete auth system."""
        auth_config = {
            "providers": [{"type": "jwt", "config": {"secret_key": "test"}}],
            "storage": {
                "backend": "test.module:MockSessionManager",
                "database_qualifier": "auth",
            },
            "credential_vault": {
                "backend": "test.module:MockCredentialVault",
                "bcrypt_rounds": 12,
            },
            "rate_limiting": {
                "backend": "test.module:MockRateLimiter",
                "default_limits": {"login": "5/min"},
            },
            "token_service": {
                "backend": "test.module:MockTokenService",
                "expiry_time": 3600,
            },
            "audit_logger": {
                "backend": "test.module:MockAuditLogger",
                "retention_days": 365,
            },
            "policy_engine": {
                "backend": "test.module:MockPolicyEngine",
                "default_decision": "deny",
            },
            "role_registry": {
                "backend": "test.module:MockRoleRegistry",
                "cache_expiry": 300,
            },
        }

        # Mock all loaders
        def mock_loader(path):
            if "jwt_provider:JwtAuthProvider" in path:
                return MockAuthProvider
            elif "MockSessionManager" in path:
                return MockSessionManager
            elif "MockCredentialVault" in path:
                return MockCredentialVault
            elif "MockRateLimiter" in path:
                return MockRateLimiter
            elif "MockTokenService" in path:
                return MockTokenService
            elif "MockAuditLogger" in path:
                return MockAuditLogger
            elif "MockPolicyEngine" in path:
                return MockPolicyEngine
            elif "MockRoleRegistry" in path:
                return MockRoleRegistry
            else:
                raise ValueError(f"Unknown path: {path}")

        self.factory._loader.load_class = mock_loader

        components = self.factory.configure_auth_system(auth_config)

        # Verify all components were created
        assert "providers" in components
        assert "storage" in components
        assert "credential_vault" in components
        assert "rate_limiter" in components
        assert "token_service" in components
        assert "audit_logger" in components
        assert "policy_engine" in components
        assert "role_registry" in components

        # Verify types are registered in DI container using abstract base classes
        assert self.container.get(AuthProvider) is not None
        assert self.container.get(SessionManager) is not None
        assert self.container.get(CredentialVault) is not None
        assert self.container.get(RateLimiter) is not None
        assert self.container.get(TokenService) is not None
        assert self.container.get(AuditLogger) is not None
        assert self.container.get(PolicyEngine) is not None
        assert self.container.get(RoleRegistry) is not None

    def test_configure_auth_system_partial(self):
        """Test configuring auth system with only some components."""
        auth_config = {
            "providers": [{"type": "jwt", "config": {"secret_key": "test"}}],
            "storage": {
                "backend": "test.module:MockSessionManager",
                "database_qualifier": "auth",
            },
        }

        # Mock loaders
        def mock_loader(path):
            if "jwt_provider:JwtAuthProvider" in path:
                return MockAuthProvider
            elif "MockSessionManager" in path:
                return MockSessionManager
            else:
                raise ValueError(f"Unknown path: {path}")

        self.factory._loader.load_class = mock_loader

        components = self.factory.configure_auth_system(auth_config)

        # Verify only configured components exist
        assert "providers" in components
        assert "storage" in components
        assert "credential_vault" not in components
        assert "rate_limiter" not in components
        assert "token_service" not in components
        assert "audit_logger" not in components
        assert "policy_engine" not in components
        assert "role_registry" not in components

        # Verify only configured types are in DI container
        assert self.container.get(AuthProvider) is not None
        assert self.container.get(SessionManager) is not None

        # These should not be available
        with pytest.raises(Exception):  # noqa: B017
            self.container.get(CredentialVault)
        with pytest.raises(Exception):  # noqa: B017
            self.container.get(RateLimiter)
        with pytest.raises(Exception):  # noqa: B017
            self.container.get(TokenService)
        with pytest.raises(Exception):  # noqa: B017
            self.container.get(AuditLogger)
        with pytest.raises(Exception):  # noqa: B017
            self.container.get(PolicyEngine)
        with pytest.raises(Exception):  # noqa: B017
            self.container.get(RoleRegistry)

    def test_configure_auth_system_empty(self):
        """Test configuring auth system with empty config."""
        components = self.factory.configure_auth_system({})

        assert components == {}

        # No types should be registered
        with pytest.raises(Exception):  # noqa: B017
            self.container.get(AuthProvider)


class TestCreateAuthSystem:
    """Test the convenience create_auth_system function."""

    def test_create_auth_system_with_new_container(self):
        """Test creating auth system with new container."""
        auth_config = {"providers": [{"type": "jwt", "config": {"secret_key": "test"}}]}

        # This would normally fail without mocking, but we test the interface
        with pytest.raises(AuthConfigError):
            create_auth_system(auth_config)

    def test_create_auth_system_with_existing_container(self):
        """Test creating auth system with existing container."""
        registry = get_registry()
        container = registry.create_container()

        auth_config = {"providers": [{"type": "jwt", "config": {"secret_key": "test"}}]}

        # This would normally fail without mocking, but we test the interface
        with pytest.raises(AuthConfigError):
            create_auth_system(auth_config, container)
