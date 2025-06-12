"""
Integration tests for auth system implementations.

These tests verify that all auth implementations work together correctly
and integrate properly with the dependency injection system.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bevy import get_registry

from serv.auth import (
    AuditLogger,
    AuthProvider,
    AuthSystemFactory,
    CredentialVault,
    PolicyEngine,
    RateLimiter,
    RoleRegistry,
    SessionManager,
    TokenService,
)
from serv.auth.types import AuditEvent, PolicyDecision
from serv.bundled.auth import (
    JwtTokenService,
    OmmiAuditLogger,
    OmmiRoleRegistry,
    SimplePolicyEngine,
)


class TestAuthSystemIntegration:
    """Test integration between different auth system components."""

    def setup_method(self):
        """Set up test fixtures."""
        registry = get_registry()
        self.container = registry.create_container()
        self.factory = AuthSystemFactory(self.container)

    @pytest.mark.asyncio
    async def test_token_service_and_policy_engine_integration(self):
        """Test JWT token service integration with policy engine."""
        # Configure JWT token service
        token_config = {
            "secret_key": "test-secret-key-for-integration-test",
            "algorithm": "HS256",
            "access_token_expiry": 3600,
        }
        token_service = JwtTokenService(token_config)

        # Configure policy engine
        policy_config = {
            "default_decision": "deny",
            "policies": [
                {
                    "effect": "allow",
                    "description": "Admin access",
                    "roles": ["admin"],
                    "resources": ["*"],
                    "actions": ["*"],
                },
                {
                    "effect": "allow",
                    "description": "User self-access",
                    "permissions": ["user:self"],
                    "resources": ["/api/user/*"],
                    "actions": ["GET", "PUT"],
                },
            ],
        }
        policy_engine = SimplePolicyEngine(policy_config)

        # Generate token with user context
        user_payload = {
            "user_id": "test-user",
            "roles": ["admin"],
            "permissions": ["user:self"],
        }
        token = await token_service.generate_token(user_payload)

        # Validate token and extract user context
        validated_token = await token_service.validate_token(token.token_value)
        user_context = {
            "user_id": validated_token.user_id,
            "roles": validated_token.payload.get("roles", []),
            "permissions": validated_token.payload.get("permissions", []),
        }

        # Test policy evaluation with token-derived context
        decision = await policy_engine.evaluate("/admin/users", "DELETE", user_context)
        assert decision.allowed is True
        assert "admin" in decision.reason.lower()

        # Test user self-access
        decision = await policy_engine.evaluate("/api/user/profile", "GET", user_context)
        assert decision.allowed is True

    @pytest.mark.asyncio
    async def test_role_registry_and_policy_engine_integration(self):
        """Test role registry integration with policy engine."""
        # Mock database for role registry
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi

        # Configure role registry
        role_config = {"database_qualifier": "test_auth", "case_sensitive": False}
        role_registry = OmmiRoleRegistry(role_config)

        # Mock role registry methods to return expected data
        async def mock_get_user_roles(user_id, database=None):
            return ["admin", "user"]

        async def mock_get_user_permissions(user_id, database=None):
            return ["user:read", "user:write", "admin:all"]

        role_registry.get_user_roles = mock_get_user_roles
        role_registry.get_user_permissions = mock_get_user_permissions

        # Configure policy engine
        policy_config = {
            "default_decision": "deny",
            "policies": [
                {
                    "effect": "allow",
                    "description": "Admin role access",
                    "roles": ["admin"],
                    "resources": ["/admin/*"],
                    "actions": ["*"],
                },
                {
                    "effect": "allow",
                    "description": "User permission access",
                    "permissions": ["user:read"],
                    "resources": ["/api/users"],
                    "actions": ["GET"],
                },
            ],
        }
        policy_engine = SimplePolicyEngine(policy_config)

        # Get user context from role registry
        user_roles = await role_registry.get_user_roles("test-user")
        user_permissions = await role_registry.get_user_permissions("test-user")

        user_context = {
            "user_id": "test-user",
            "roles": user_roles,
            "permissions": user_permissions,
        }

        # Test policy evaluation with role-derived context
        decision = await policy_engine.evaluate("/admin/dashboard", "GET", user_context)
        assert decision.allowed is True

        decision = await policy_engine.evaluate("/api/users", "GET", user_context)
        assert decision.allowed is True

    @pytest.mark.asyncio
    async def test_audit_logger_with_auth_events(self):
        """Test audit logger with authentication events."""
        # Mock database for audit logger
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi

        # Mock successful audit logging
        mock_result = AsyncMock()
        mock_saved_model = MagicMock()
        mock_saved_model.event_id = "test-event-id"
        mock_result.or_raise.return_value = [mock_saved_model]
        mock_ommi.add.return_value = mock_result

        # Configure audit logger
        audit_config = {"database_qualifier": "test_audit", "retention_days": 30}
        audit_logger = OmmiAuditLogger(audit_config)

        # Create authentication event
        auth_event = AuditEvent(
            event_type="authentication",
            user_id="test-user",
            session_id="test-session",
            source_ip="192.168.1.1",
            user_agent="Test Browser",
            resource="/api/login",
            action="POST",
            result="success",
            event_data={
                "username": "testuser",
                "method": "password",
                "multi_factor": False,
            },
            metadata={"client_type": "web", "device_id": "browser-123"},
        )

        # Test audit logging
        event_id = await audit_logger.log_event(auth_event, database=mock_database)
        assert event_id == "test-event-id"

        # Verify that the event was stored with proper serialization
        mock_ommi.add.assert_called_once()
        stored_model = mock_ommi.add.call_args[0][0]
        assert stored_model.event_type == "authentication"
        assert stored_model.user_id == "test-user"

        # Verify JSON serialization
        import json
        event_data = json.loads(stored_model.event_data)
        assert event_data["username"] == "testuser"
        assert event_data["method"] == "password"

    @pytest.mark.asyncio
    async def test_complete_auth_flow_integration(self):
        """Test complete authentication flow with multiple components."""
        # Setup components
        token_service = JwtTokenService({
            "secret_key": "test-secret-key-for-complete-flow",
            "algorithm": "HS256",
        })

        policy_engine = SimplePolicyEngine({
            "default_decision": "deny",
            "policies": [{
                "effect": "allow",
                "roles": ["authenticated"],
                "resources": ["/api/*"],
                "actions": ["GET", "POST"],
            }],
        })

        # Mock audit logger
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        mock_result = AsyncMock()
        mock_saved_model = MagicMock()
        mock_saved_model.event_id = "flow-event-id"
        mock_result.or_raise.return_value = [mock_saved_model]
        mock_ommi.add.return_value = mock_result

        audit_logger = OmmiAuditLogger({"database_qualifier": "test_audit"})

        # Step 1: User authenticates and gets token
        user_payload = {
            "user_id": "flow-test-user",
            "roles": ["authenticated"],
            "email": "user@example.com",
        }
        token = await token_service.generate_token(user_payload)

        # Log authentication event
        auth_event = AuditEvent(
            event_type="authentication",
            user_id="flow-test-user",
            result="success",
            event_data={"method": "token_generation"},
        )
        await audit_logger.log_event(auth_event, database=mock_database)

        # Step 2: Validate token for API request
        validated_token = await token_service.validate_token(token.token_value)
        assert validated_token.user_id == "flow-test-user"

        # Step 3: Check authorization for API access
        user_context = {
            "user_id": validated_token.user_id,
            "roles": validated_token.payload.get("roles", []),
            "email": validated_token.payload.get("email"),
        }

        decision = await policy_engine.evaluate("/api/data", "GET", user_context)
        assert decision.allowed is True

        # Log authorization event
        authz_event = AuditEvent(
            event_type="authorization",
            user_id="flow-test-user",
            resource="/api/data",
            action="GET",
            result="allowed",
            event_data={"policy_id": decision.policy_id},
        )
        await audit_logger.log_event(authz_event, database=mock_database)

        # Step 4: Verify all events were logged
        assert mock_ommi.add.call_count == 2  # Auth and authz events

    @pytest.mark.asyncio
    async def test_factory_integration_with_di_container(self):
        """Test factory integration with dependency injection container."""
        # Configure complete auth system via factory
        auth_config = {
            "providers": [{"type": "jwt", "config": {"secret_key": "test-secret"}}],
            "token_service": {
                "backend": "serv.bundled.auth.tokens.jwt_token_service:JwtTokenService",
                "secret_key": "test-secret",
                "algorithm": "HS256",
            },
            "policy_engine": {
                "backend": "serv.bundled.auth.policies.simple_policy_engine:SimplePolicyEngine",
                "default_decision": "allow",
                "policies": [],
            },
        }

        # Mock the loader for providers (JWT needs special handling in factory)
        def mock_loader(path):
            if "jwt_provider" in path:
                from tests.test_auth_config_system import MockAuthProvider
                return MockAuthProvider
            elif "JwtTokenService" in path:
                return JwtTokenService
            elif "SimplePolicyEngine" in path:
                return SimplePolicyEngine
            else:
                raise ValueError(f"Unknown path: {path}")

        self.factory._loader.load_class = mock_loader

        # Configure the system
        components = self.factory.configure_auth_system(auth_config)

        # Verify components were created and registered
        assert "providers" in components
        assert "token_service" in components
        assert "policy_engine" in components

        # Verify DI container has the services
        token_service = self.container.get(TokenService)
        policy_engine = self.container.get(PolicyEngine)

        assert isinstance(token_service, JwtTokenService)
        assert isinstance(policy_engine, SimplePolicyEngine)

        # Test that the services work together via DI
        user_payload = {"user_id": "di-test-user", "roles": ["user"]}
        token = await token_service.generate_token(user_payload)
        validated_token = await token_service.validate_token(token.token_value)

        user_context = {
            "user_id": validated_token.user_id,
            "roles": validated_token.payload.get("roles", []),
        }

        decision = await policy_engine.evaluate("/test", "GET", user_context)
        assert decision.allowed is True  # Default policy is allow

    def test_service_interface_compliance(self):
        """Test that all implementations properly implement their interfaces."""
        # Test JWT Token Service
        token_service = JwtTokenService({"secret_key": "test-key"})
        assert isinstance(token_service, TokenService)

        # Test Simple Policy Engine
        policy_engine = SimplePolicyEngine({"default_decision": "deny"})
        assert isinstance(policy_engine, PolicyEngine)

        # Test Ommi Audit Logger
        audit_logger = OmmiAuditLogger({"database_qualifier": "test"})
        assert isinstance(audit_logger, AuditLogger)

        # Test Ommi Role Registry
        role_registry = OmmiRoleRegistry({"database_qualifier": "test"})
        assert isinstance(role_registry, RoleRegistry)

        # Verify all have required methods
        assert hasattr(token_service, 'generate_token')
        assert hasattr(token_service, 'validate_token')
        assert hasattr(policy_engine, 'evaluate')
        assert hasattr(audit_logger, 'log_event')
        assert hasattr(role_registry, 'define_role')

    @pytest.mark.asyncio
    async def test_error_handling_integration(self):
        """Test error handling across integrated components."""
        # Test invalid token with policy engine
        token_service = JwtTokenService({"secret_key": "test-secret"})
        policy_engine = SimplePolicyEngine({"default_decision": "deny"})

        # Try to validate invalid token
        with pytest.raises(ValueError, match="Invalid token"):
            await token_service.validate_token("invalid.token.format")

        # Test policy engine with missing user context
        decision = await policy_engine.evaluate("/test", "GET", {})
        assert decision.allowed is False  # Should deny by default

        # Test policy engine with malformed policies
        with pytest.raises(ValueError):
            SimplePolicyEngine({
                "default_decision": "deny",
                "policies": [{"effect": "invalid"}],  # Missing conditions
            })

    @pytest.mark.asyncio
    async def test_performance_with_multiple_operations(self):
        """Test performance with multiple concurrent operations."""
        import asyncio

        token_service = JwtTokenService({"secret_key": "perf-test-secret"})
        policy_engine = SimplePolicyEngine({
            "default_decision": "allow",
            "policies": [],
        })

        # Generate multiple tokens concurrently
        async def generate_and_validate_token(user_id):
            payload = {"user_id": f"user-{user_id}", "roles": ["user"]}
            token = await token_service.generate_token(payload)
            validated = await token_service.validate_token(token.token_value)
            return validated

        # Test concurrent token operations
        tasks = [generate_and_validate_token(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        for i, result in enumerate(results):
            assert result.user_id == f"user-{i}"

        # Test concurrent policy evaluations
        async def evaluate_policy(resource):
            user_context = {"user_id": "test", "roles": ["user"]}
            return await policy_engine.evaluate(f"/api/{resource}", "GET", user_context)

        policy_tasks = [evaluate_policy(f"resource-{i}") for i in range(10)]
        policy_results = await asyncio.gather(*policy_tasks)

        assert len(policy_results) == 10
        for result in policy_results:
            assert isinstance(result, PolicyDecision)
            assert result.allowed is True  # Default allow policy