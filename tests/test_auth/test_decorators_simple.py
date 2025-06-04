"""
Simplified tests for authentication decorators and route integration.

Tests the auth_handle decorators and their integration with Serv's routing system.
"""


import pytest

# Remove unnecessary imports
from serv.auth.decorators import (
    AuthenticatedHandleDecorator,
    AuthenticatedHandleRegistry,
    AuthRequirement,
    auth_handle,
)
from serv.requests import Request
from serv.routes import Route

# No specific response imports needed for basic tests


class TestAuthRequirement:
    """Test AuthRequirement class functionality."""

    def test_default_auth_requirement(self):
        """Test default AuthRequirement has no requirements."""
        req = AuthRequirement()

        assert req.require_auth is False
        assert req.auth_optional is False
        assert req.allow_anonymous is False
        assert not req.has_requirements()

    def test_require_auth(self):
        """Test AuthRequirement with authentication required."""
        req = AuthRequirement(require_auth=True)

        assert req.require_auth is True
        assert req.requires_authentication() is True
        assert req.has_requirements() is True

    def test_require_permission(self):
        """Test AuthRequirement with permission."""
        req = AuthRequirement(require_permission="users:read")

        assert req.require_auth is True  # Should auto-enable
        assert req.require_permission == "users:read"
        assert "users:read" in req.get_all_required_permissions()

    def test_require_permissions_list(self):
        """Test AuthRequirement with multiple permissions."""
        req = AuthRequirement(require_permissions=["users:read", "users:write"])

        assert req.require_auth is True
        assert req.require_permissions == ["users:read", "users:write"]
        assert req.get_all_required_permissions() == {"users:read", "users:write"}

    def test_require_role(self):
        """Test AuthRequirement with role."""
        req = AuthRequirement(require_role="admin")

        assert req.require_auth is True
        assert req.require_role == "admin"
        assert "admin" in req.get_required_roles()

    def test_validation_errors(self):
        """Test AuthRequirement validation."""
        # Contradictory settings
        with pytest.raises(
            ValueError, match="Cannot both require authentication and allow anonymous"
        ):
            AuthRequirement(require_auth=True, allow_anonymous=True)

        with pytest.raises(
            ValueError, match="Cannot both require authentication and make it optional"
        ):
            AuthRequirement(require_auth=True, auth_optional=True)

        # Invalid permission name (empty string after strip)
        with pytest.raises(ValueError, match="Invalid permission name"):
            AuthRequirement(require_permission="   ")

        # Invalid role name (empty string after strip)
        with pytest.raises(ValueError, match="Invalid role name"):
            AuthRequirement(require_role="   ")


class TestAuthenticatedHandleRegistry:
    """Test AuthenticatedHandleRegistry functionality."""

    def test_registry_creation(self):
        """Test that registry has expected methods."""
        registry = AuthenticatedHandleRegistry()

        # Standard HTTP methods
        assert hasattr(registry, "GET")
        assert hasattr(registry, "POST")
        assert hasattr(registry, "PUT")
        assert hasattr(registry, "DELETE")

        # Auth-specific methods
        assert hasattr(registry, "authenticated")
        assert hasattr(registry, "with_permission")
        assert hasattr(registry, "with_role")
        assert hasattr(registry, "optional_auth")

    def test_authenticated_method(self):
        """Test authenticated method creates proper decorator."""
        registry = AuthenticatedHandleRegistry()

        decorator = registry.authenticated(require_permission="users:read")

        assert isinstance(decorator, AuthenticatedHandleDecorator)
        assert decorator.auth_requirement.require_permission == "users:read"
        assert decorator.auth_requirement.require_auth is True

    def test_with_permission_method(self):
        """Test with_permission method."""
        registry = AuthenticatedHandleRegistry()

        decorator = registry.with_permission("users:write")

        assert isinstance(decorator, AuthenticatedHandleDecorator)
        assert decorator.auth_requirement.require_permission == "users:write"

    def test_with_role_method(self):
        """Test with_role method."""
        registry = AuthenticatedHandleRegistry()

        decorator = registry.with_role("admin")

        assert isinstance(decorator, AuthenticatedHandleDecorator)
        assert decorator.auth_requirement.require_role == "admin"

    def test_optional_auth_method(self):
        """Test optional_auth method."""
        registry = AuthenticatedHandleRegistry()

        decorator = registry.optional_auth()

        assert isinstance(decorator, AuthenticatedHandleDecorator)
        assert decorator.auth_requirement.auth_optional is True
        assert decorator.auth_requirement.require_auth is False


class TestAuthenticatedHandleDecorator:
    """Test AuthenticatedHandleDecorator functionality."""

    def test_decorator_application(self):
        """Test that decorator properly applies to functions."""
        auth_req = AuthRequirement(require_auth=True)
        decorator = AuthenticatedHandleDecorator({"GET"}, auth_req)

        @decorator
        async def test_handler():
            return "test"

        # Should preserve function behavior
        assert test_handler.__name__ == "test_handler"

        # Should add metadata
        assert hasattr(test_handler, "__handle_methods__")
        assert hasattr(test_handler, "__auth_requirement__")
        assert test_handler.__handle_methods__ == {"GET"}
        assert test_handler.__auth_requirement__ == auth_req

    def test_decorator_or_combination(self):
        """Test combining decorators with | operator."""
        auth_req = AuthRequirement(require_auth=True)
        get_decorator = AuthenticatedHandleDecorator({"GET"}, auth_req)
        post_decorator = AuthenticatedHandleDecorator({"POST"}, auth_req)

        combined = get_decorator | post_decorator

        assert isinstance(combined, AuthenticatedHandleDecorator)
        assert combined.methods == {"GET", "POST"}
        assert combined.auth_requirement == auth_req

    def test_decorator_or_different_auth_fails(self):
        """Test that combining decorators with different auth fails."""
        auth_req1 = AuthRequirement(require_auth=True)
        auth_req2 = AuthRequirement(require_permission="users:read")

        get_decorator = AuthenticatedHandleDecorator({"GET"}, auth_req1)
        post_decorator = AuthenticatedHandleDecorator({"POST"}, auth_req2)

        with pytest.raises(
            ValueError, match="Cannot combine handlers with different auth requirements"
        ):
            get_decorator | post_decorator


class TestRouteIntegration:
    """Test integration with Route classes."""

    def test_simple_authenticated_route(self):
        """Test route with authenticated decorator."""

        class TestRoute(Route):
            @auth_handle.authenticated()
            async def handle_get(self, request: Request):
                return "Protected content"

        route = TestRoute()

        # Should have auth metadata
        assert hasattr(route.handle_get, "__auth_requirement__")
        assert route.handle_get.__auth_requirement__.require_auth is True

    def test_permission_based_route(self):
        """Test route with permission requirement."""

        class TestRoute(Route):
            @auth_handle.with_permission("users:read")
            async def handle_get(self, request: Request):
                return "User data"

        route = TestRoute()

        auth_req = route.handle_get.__auth_requirement__
        assert auth_req.require_permission == "users:read"
        assert auth_req.require_auth is True

    def test_role_based_route(self):
        """Test route with role requirement."""

        class TestRoute(Route):
            @auth_handle.with_role("admin")
            async def handle_delete(self, request: Request):
                return "Admin action"

        route = TestRoute()

        auth_req = route.handle_delete.__auth_requirement__
        assert auth_req.require_role == "admin"
        assert auth_req.require_auth is True

    def test_optional_auth_route(self):
        """Test route with optional authentication."""

        class TestRoute(Route):
            @auth_handle.optional_auth()
            async def handle_get(self, request: Request):
                return "Public or user content"

        route = TestRoute()

        auth_req = route.handle_get.__auth_requirement__
        assert auth_req.auth_optional is True
        assert auth_req.require_auth is False

    def test_complex_auth_requirements(self):
        """Test route with complex authentication requirements."""

        class TestRoute(Route):
            @auth_handle.authenticated(
                require_permissions=["users:read", "users:write"],
                require_role="manager",
            )
            async def handle_post(self, request: Request):
                return "Complex operation"

        route = TestRoute()

        auth_req = route.handle_post.__auth_requirement__
        assert auth_req.require_permissions == ["users:read", "users:write"]
        assert auth_req.require_role == "manager"
        assert auth_req.require_auth is True

    def test_mixed_auth_and_non_auth_methods(self):
        """Test route with both auth and non-auth methods."""

        class TestRoute(Route):
            async def public_method(self, request: Request):
                return "Public content"

            @auth_handle.authenticated()
            async def protected_method(self, request: Request):
                return "Protected content"

        route = TestRoute()

        # Public method should have no auth metadata
        assert not hasattr(route.public_method, "__auth_requirement__")

        # Protected method should have auth metadata
        assert hasattr(route.protected_method, "__auth_requirement__")
        assert route.protected_method.__auth_requirement__.require_auth is True


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_invalid_methods_parameter(self):
        """Test that invalid methods parameter raises error."""
        registry = AuthenticatedHandleRegistry()

        with pytest.raises(ValueError, match="Methods must be string, list, or set"):
            registry.authenticated(methods=123)

    def test_empty_methods_defaults_to_get(self):
        """Test that no methods parameter defaults to GET."""
        registry = AuthenticatedHandleRegistry()

        decorator = registry.authenticated()

        assert decorator.methods == {"GET"}

    def test_string_methods_converted_to_set(self):
        """Test that string methods are converted to uppercase set."""
        registry = AuthenticatedHandleRegistry()

        decorator = registry.authenticated(methods="post")

        assert decorator.methods == {"POST"}

    def test_list_methods_converted_to_set(self):
        """Test that list methods are converted to uppercase set."""
        registry = AuthenticatedHandleRegistry()

        decorator = registry.authenticated(methods=["get", "post"])

        assert decorator.methods == {"GET", "POST"}
