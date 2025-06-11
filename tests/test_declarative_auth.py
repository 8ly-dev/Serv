"""
Tests for declarative authentication and authorization.

This module tests the declarative auth system including AuthRule parsing,
router/route-level auth enforcement, and middleware integration.
"""

import pytest
from typing import Annotated

from serv.app import App
from serv.auth import AuthRule, DeclarativeAuthProcessor
from serv.extensions.loader import AuthConfig
from serv.http import GetRequest, JsonResponse, ResponseBuilder
from serv.routing import Route, handle
from tests.e2e_test_helpers import create_test_client


class TestAuthRule:
    """Test AuthRule validation and evaluation."""

    def test_auth_rule_creation(self):
        """Test basic auth rule creation."""
        rule = AuthRule(require_auth=True)
        assert rule.require_auth is True
        assert rule.requires_authentication() is True

    def test_auth_rule_validation_contradictory(self):
        """Test validation of contradictory auth settings."""
        with pytest.raises(ValueError, match="Cannot both require authentication and allow anonymous"):
            AuthRule(require_auth=True, allow_anonymous=True)

        with pytest.raises(ValueError, match="Cannot both require authentication and make it optional"):
            AuthRule(require_auth=True, auth_optional=True)

    def test_auth_rule_auto_enable_auth(self):
        """Test that auth is auto-enabled when permissions/roles are specified."""
        rule = AuthRule(require_permission="admin")
        assert rule.require_auth is True

        rule = AuthRule(require_role="moderator")
        assert rule.require_auth is True

    def test_auth_rule_permission_evaluation(self):
        """Test permission evaluation logic."""
        rule = AuthRule(require_permissions=["read", "write"])
        
        # User has all required permissions
        assert rule.evaluate_permissions({"read", "write", "admin"}) is True
        
        # User missing a required permission
        assert rule.evaluate_permissions({"read"}) is False
        
        # Test any permission logic
        rule = AuthRule(require_any_permission=["admin", "moderator"])
        assert rule.evaluate_permissions({"admin"}) is True
        assert rule.evaluate_permissions({"moderator"}) is True
        assert rule.evaluate_permissions({"user"}) is False

    def test_auth_rule_role_evaluation(self):
        """Test role evaluation logic."""
        rule = AuthRule(require_roles=["admin", "moderator"])
        
        # User has one of the required roles
        assert rule.evaluate_roles({"admin"}) is True
        assert rule.evaluate_roles({"moderator"}) is True
        
        # User has neither required role
        assert rule.evaluate_roles({"user"}) is False

    def test_auth_rule_merging(self):
        """Test merging of auth rules."""
        router_rule = AuthRule(require_auth=True, require_permission="read")
        route_rule = AuthRule(require_permission="write")
        
        merged = router_rule.merge_with(route_rule)
        
        assert merged.require_auth is True
        assert "read" in merged.get_all_required_permissions()
        assert "write" in merged.get_all_required_permissions()


class TestDeclarativeAuthProcessor:
    """Test declarative auth configuration processing."""

    def test_parse_empty_config(self):
        """Test parsing empty or None config."""
        assert DeclarativeAuthProcessor.parse_auth_config(None) is None
        assert DeclarativeAuthProcessor.parse_auth_config({}) is None

    def test_parse_valid_config(self):
        """Test parsing valid auth configuration."""
        config = {
            "require_auth": True,
            "require_permission": "admin",
            "require_roles": ["moderator", "admin"]
        }
        
        rule = DeclarativeAuthProcessor.parse_auth_config(config)
        
        assert rule is not None
        assert rule.require_auth is True
        assert rule.require_permission == "admin"
        assert "moderator" in rule.get_required_roles()
        assert "admin" in rule.get_required_roles()

    def test_validate_invalid_config(self):
        """Test validation of invalid configurations."""
        # Invalid key
        with pytest.raises(ValueError, match="Unknown auth configuration keys"):
            DeclarativeAuthProcessor.validate_auth_config({"invalid_key": True})
        
        # Invalid type for permissions list
        with pytest.raises(ValueError, match="require_permissions must be a list"):
            DeclarativeAuthProcessor.validate_auth_config({"require_permissions": "not_a_list"})
        
        # Invalid permission type in list
        with pytest.raises(ValueError, match="All items in require_permissions must be strings"):
            DeclarativeAuthProcessor.validate_auth_config({"require_permissions": [123, "read"]})

    def test_merge_router_and_route_auth(self):
        """Test merging router and route auth rules."""
        router_config = {"require_auth": True, "require_permission": "read"}
        route_config = {"require_permission": "write"}
        
        router_rule = DeclarativeAuthProcessor.parse_auth_config(router_config)
        route_rule = DeclarativeAuthProcessor.parse_auth_config(route_config)
        
        merged = DeclarativeAuthProcessor.merge_router_and_route_auth(router_rule, route_rule)
        
        assert merged is not None
        assert merged.require_auth is True
        assert "read" in merged.get_all_required_permissions()
        assert "write" in merged.get_all_required_permissions()

    def test_evaluate_auth_rule(self):
        """Test auth rule evaluation."""
        rule = AuthRule(require_auth=True, require_permission="admin")
        
        # No user context, auth required -> deny
        is_allowed, reason = DeclarativeAuthProcessor.evaluate_auth_rule(rule, None)
        assert is_allowed is False
        assert "Authentication required" in reason
        
        # User context without required permission -> deny
        user_context = {"user_id": "user123", "permissions": ["read"]}
        is_allowed, reason = DeclarativeAuthProcessor.evaluate_auth_rule(rule, user_context)
        assert is_allowed is False
        assert "admin" in reason
        
        # User context with required permission -> allow
        user_context = {"user_id": "user123", "permissions": ["admin"]}
        is_allowed, reason = DeclarativeAuthProcessor.evaluate_auth_rule(rule, user_context)
        assert is_allowed is True


class TestDeclarativeAuthIntegration:
    """Test integration of declarative auth with routing system."""

    def test_extension_yaml_type_definitions(self):
        """Test that AuthConfig TypedDict accepts valid configurations."""
        # This tests the TypedDict at type-check time
        auth_config: AuthConfig = {
            "require_auth": True,
            "require_permission": "admin",
            "require_permissions": ["read", "write"],
            "require_any_permission": ["admin", "moderator"],
            "require_role": "admin",
            "require_roles": ["admin", "moderator"],
            "auth_optional": False,
            "allow_anonymous": False,
        }
        
        # Verify the config can be parsed
        rule = DeclarativeAuthProcessor.parse_auth_config(auth_config)
        assert rule is not None
        assert rule.require_auth is True

    @pytest.mark.asyncio
    async def test_route_auth_integration(self):
        """Test that route-level auth is enforced by the App class."""
        from serv.extensions import Listener, on
        from serv.routing import Router
        from bevy import Inject, injectable
        
        # Create a simple route class
        class TestRoute(Route):
            @handle.GET
            async def get_data(self, request: GetRequest) -> Annotated[dict, JsonResponse]:
                return {"message": "success"}

        class TestExtension(Listener):
            @on("app.request.begin")
            @injectable
            async def setup_routes(self, router: Inject[Router]) -> None:
                router.add_route("/test", TestRoute())

        # Create app (auth checking is now integrated into App class)
        app = App()
        app.add_extension(TestExtension(stand_alone=True))

        # Test client
        async with create_test_client(app_factory=lambda: app) as client:
            # Test without auth rule - should succeed
            response = await client.get("/test")
            assert response.status_code == 200

    # Note: Auth failure response testing is now covered by the e2e tests
    # since auth logic is integrated directly into the App class


class TestAuthRuleEdgeCases:
    """Test edge cases and error conditions for auth rules."""

    def test_empty_auth_rule(self):
        """Test auth rule with no requirements."""
        rule = AuthRule()
        assert rule.has_requirements() is False
        
        # Should allow access for any user context
        is_allowed, reason = DeclarativeAuthProcessor.evaluate_auth_rule(rule, None)
        assert is_allowed is True

    def test_optional_auth_with_no_user(self):
        """Test optional auth when no user context is provided."""
        rule = AuthRule(auth_optional=True)
        
        is_allowed, reason = DeclarativeAuthProcessor.evaluate_auth_rule(rule, None)
        assert is_allowed is True
        assert "Optional authentication" in reason

    def test_anonymous_only_access(self):
        """Test explicit anonymous-only access."""
        rule = AuthRule(allow_anonymous=True)
        
        # Should allow with no user context
        is_allowed, reason = DeclarativeAuthProcessor.evaluate_auth_rule(rule, None)
        assert is_allowed is True
        
        # Should also allow with user context (not exclusive)
        user_context = {"user_id": "user123"}
        is_allowed, reason = DeclarativeAuthProcessor.evaluate_auth_rule(rule, user_context)
        assert is_allowed is True

    def test_invalid_permission_names(self):
        """Test validation of invalid permission names."""
        with pytest.raises(ValueError, match="Invalid permission name"):
            AuthRule(require_permission="")
        
        with pytest.raises(ValueError, match="Invalid permission name"):
            AuthRule(require_permissions=["valid", ""])

    def test_invalid_role_names(self):
        """Test validation of invalid role names."""
        with pytest.raises(ValueError, match="Invalid role name"):
            AuthRule(require_role="")
        
        with pytest.raises(ValueError, match="Invalid role name"):
            AuthRule(require_roles=["valid", ""])