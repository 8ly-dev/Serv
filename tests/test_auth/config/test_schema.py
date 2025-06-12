"""Test configuration schema validation."""

import pytest
from pydantic import ValidationError

from serv.auth.config.schema import (
    AuthConfig,
    ProviderConfig,
    ProvidersConfig,
    SecurityConfig,
    DevelopmentConfig,
    ExtensionAuthConfig,
    PolicyConfig,
    PolicyType,
    RouteConfig,
    RouterConfig,
    PermissionDef,
    RoleDef,
)


class TestProviderConfig:
    """Test ProviderConfig validation."""

    def test_simple_provider_spec(self):
        """Test simple provider specification."""
        config = ProviderConfig(provider="memory", config={"test": "value"})
        assert config.provider == "memory"
        assert config.config == {"test": "value"}

    def test_import_path_provider_spec(self):
        """Test import path provider specification."""
        config = ProviderConfig(provider="my.module:MyProvider", config={})
        assert config.provider == "my.module:MyProvider"

    def test_invalid_import_path_multiple_colons(self):
        """Test invalid import path with multiple colons."""
        with pytest.raises(ValidationError, match="exactly one ':' separator"):
            ProviderConfig(provider="my.module:class:extra", config={})

    def test_invalid_import_path_empty_parts(self):
        """Test invalid import path with empty parts."""
        with pytest.raises(
            ValidationError, match="Both module path and class name must be specified"
        ):
            ProviderConfig(provider=":ClassName", config={})

        with pytest.raises(
            ValidationError, match="Both module path and class name must be specified"
        ):
            ProviderConfig(provider="module.path:", config={})

    def test_empty_provider_spec(self):
        """Test empty provider specification."""
        with pytest.raises(
            ValidationError, match="Provider specification cannot be empty"
        ):
            ProviderConfig(provider="", config={})


class TestProvidersConfig:
    """Test ProvidersConfig validation."""

    def test_complete_providers_config(self):
        """Test complete valid providers configuration."""
        config = ProvidersConfig(
            credential=ProviderConfig(provider="memory", config={}),
            session=ProviderConfig(provider="memory", config={}),
            user=ProviderConfig(provider="memory", config={}),
            audit=ProviderConfig(provider="memory", config={}),
            policy=ProviderConfig(provider="rbac", config={}),
        )

        assert config.credential.provider == "memory"
        assert config.session.provider == "memory"
        assert config.user.provider == "memory"
        assert config.audit.provider == "memory"
        assert config.policy.provider == "rbac"


class TestAuthConfig:
    """Test AuthConfig validation."""

    def test_minimal_auth_config(self):
        """Test minimal valid auth configuration."""
        config = AuthConfig(
            providers=ProvidersConfig(
                credential=ProviderConfig(provider="memory", config={}),
                session=ProviderConfig(provider="memory", config={}),
                user=ProviderConfig(provider="memory", config={}),
                audit=ProviderConfig(provider="memory", config={}),
                policy=ProviderConfig(provider="rbac", config={}),
            )
        )

        assert config.enabled is True
        assert config.providers is not None
        assert config.security is not None
        assert config.development is not None

    def test_disabled_auth_config(self):
        """Test disabled auth configuration."""
        config = AuthConfig(
            enabled=False,
            providers=ProvidersConfig(
                credential=ProviderConfig(provider="memory", config={}),
                session=ProviderConfig(provider="memory", config={}),
                user=ProviderConfig(provider="memory", config={}),
                audit=ProviderConfig(provider="memory", config={}),
                policy=ProviderConfig(provider="rbac", config={}),
            ),
        )

        assert config.enabled is False


class TestPolicyConfig:
    """Test PolicyConfig validation."""

    def test_permission_policy_valid(self):
        """Test valid permission policy."""
        config = PolicyConfig(type=PolicyType.PERMISSION, permission="read:posts")
        assert config.type == PolicyType.PERMISSION
        assert config.permission == "read:posts"

    def test_permission_policy_missing_permission(self):
        """Test permission policy without permission specified."""
        with pytest.raises(
            ValidationError, match="Permission policy must specify a permission"
        ):
            PolicyConfig(type=PolicyType.PERMISSION)

    def test_role_policy_valid(self):
        """Test valid role policy."""
        config = PolicyConfig(type=PolicyType.ROLE, roles=["admin", "moderator"])
        assert config.type == PolicyType.ROLE
        assert config.roles == ["admin", "moderator"]

    def test_role_policy_missing_roles(self):
        """Test role policy without roles specified."""
        with pytest.raises(ValidationError, match="Role policy must specify roles"):
            PolicyConfig(type=PolicyType.ROLE)

    def test_attribute_policy_valid(self):
        """Test valid attribute policy."""
        config = PolicyConfig(
            type=PolicyType.ATTRIBUTE, attributes={"department": "engineering"}
        )
        assert config.type == PolicyType.ATTRIBUTE
        assert config.attributes == {"department": "engineering"}

    def test_attribute_policy_missing_attributes(self):
        """Test attribute policy without attributes specified."""
        with pytest.raises(
            ValidationError, match="Attribute policy must specify attributes"
        ):
            PolicyConfig(type=PolicyType.ATTRIBUTE)

    def test_complex_policy_valid(self):
        """Test valid complex policy."""
        from serv.auth.config.schema import PolicyCondition

        config = PolicyConfig(
            type=PolicyType.COMPLEX,
            conditions=[
                PolicyCondition(type=PolicyType.PERMISSION, permission="read:posts")
            ],
        )
        assert config.type == PolicyType.COMPLEX
        assert len(config.conditions) == 1

    def test_complex_policy_missing_conditions(self):
        """Test complex policy without conditions specified."""
        with pytest.raises(
            ValidationError, match="Complex policy must specify conditions"
        ):
            PolicyConfig(type=PolicyType.COMPLEX)


class TestRouteConfig:
    """Test RouteConfig validation."""

    def test_simple_route_config(self):
        """Test simple route configuration."""
        config = RouteConfig(
            path="/api/posts", methods=["GET", "POST"], policy="authenticated"
        )

        assert config.path == "/api/posts"
        assert config.methods == ["GET", "POST"]
        assert config.policy == "authenticated"

    def test_route_config_with_policy_object(self):
        """Test route configuration with policy object."""
        policy = PolicyConfig(type=PolicyType.PERMISSION, permission="read:posts")

        config = RouteConfig(path="/api/posts", policy=policy)

        assert config.path == "/api/posts"
        assert config.policy == policy


class TestExtensionAuthConfig:
    """Test ExtensionAuthConfig validation."""

    def test_empty_extension_config(self):
        """Test empty extension auth configuration."""
        config = ExtensionAuthConfig()

        assert config.policies is None
        assert config.routes is None
        assert config.routers is None
        assert config.permissions is None
        assert config.roles is None
        assert config.audit is None

    def test_extension_config_with_permissions(self):
        """Test extension config with permissions."""
        config = ExtensionAuthConfig(
            permissions=[
                PermissionDef(
                    permission="read:blog",
                    description="Read blog posts",
                    resource="blog",
                    actions=["read"],
                )
            ]
        )

        assert len(config.permissions) == 1
        assert config.permissions[0].permission == "read:blog"

    def test_extension_config_with_roles(self):
        """Test extension config with roles."""
        config = ExtensionAuthConfig(
            roles=[
                RoleDef(
                    name="blog_reader",
                    description="Can read blog content",
                    permissions=["read:blog"],
                )
            ]
        )

        assert len(config.roles) == 1
        assert config.roles[0].name == "blog_reader"

    def test_extension_config_with_routes(self):
        """Test extension config with routes."""
        config = ExtensionAuthConfig(
            routes=[RouteConfig(path="/blog/posts", methods=["GET"], policy="public")]
        )

        assert len(config.routes) == 1
        assert config.routes[0].path == "/blog/posts"


class TestSecurityConfig:
    """Test SecurityConfig validation."""

    def test_default_security_config(self):
        """Test default security configuration."""
        config = SecurityConfig()

        assert config.headers.strict_transport_security is True
        assert config.headers.x_frame_options == "DENY"
        assert config.password_security.breach_checking is True
        assert config.session_security.ip_validation is True

    def test_custom_security_config(self):
        """Test custom security configuration."""
        from serv.auth.config.schema import (
            SecurityHeadersConfig,
            PasswordSecurityConfig,
            SessionSecurityConfig,
        )

        config = SecurityConfig(
            headers=SecurityHeadersConfig(
                strict_transport_security=False, x_frame_options="SAMEORIGIN"
            ),
            password_security=PasswordSecurityConfig(
                breach_checking=False, similarity_threshold=0.9
            ),
            session_security=SessionSecurityConfig(concurrent_login_limit=5),
        )

        assert config.headers.strict_transport_security is False
        assert config.headers.x_frame_options == "SAMEORIGIN"
        assert config.password_security.breach_checking is False
        assert config.password_security.similarity_threshold == 0.9
        assert config.session_security.concurrent_login_limit == 5


class TestDevelopmentConfig:
    """Test DevelopmentConfig validation."""

    def test_default_development_config(self):
        """Test default development configuration."""
        config = DevelopmentConfig()

        assert config.mock_providers is False
        assert config.bypass_mfa is False
        assert config.debug_audit is False
        assert config.test_users == []

    def test_development_config_with_test_users(self):
        """Test development config with test users."""
        from serv.auth.config.schema import DevelopmentUserConfig

        config = DevelopmentConfig(
            test_users=[
                DevelopmentUserConfig(
                    username="admin", password="admin123", roles=["admin"]
                ),
                DevelopmentUserConfig(
                    username="user", password="user123", roles=["user"]
                ),
            ]
        )

        assert len(config.test_users) == 2
        assert config.test_users[0].username == "admin"
        assert config.test_users[1].username == "user"
