"""Test provider registry functionality."""

import pytest

from serv.auth.factory.registry import ProviderRegistry


class TestProviderRegistry:
    """Test ProviderRegistry functionality."""

    def test_initialization(self):
        """Test registry initialization with bundled providers."""
        registry = ProviderRegistry()

        # Check that bundled providers are registered
        credential_providers = registry.get_bundled_implementations("credential")
        assert "memory" in credential_providers
        assert "database" in credential_providers

        session_providers = registry.get_bundled_implementations("session")
        assert "memory" in session_providers
        assert "database" in session_providers

        user_providers = registry.get_bundled_implementations("user")
        assert "memory" in user_providers
        assert "database" in user_providers

        audit_providers = registry.get_bundled_implementations("audit")
        assert "memory" in audit_providers
        assert "database" in audit_providers
        assert "file" in audit_providers

        policy_providers = registry.get_bundled_implementations("policy")
        assert "rbac" in policy_providers
        assert "abac" in policy_providers

    def test_resolve_bundled_provider(self):
        """Test resolving bundled provider specifications."""
        registry = ProviderRegistry()

        # Test resolving bundled providers
        import_string = registry.resolve_provider_import("credential", "memory")
        assert (
            import_string
            == "serv.bundled.auth.memory.credential:MemoryCredentialProvider"
        )

        import_string = registry.resolve_provider_import("session", "database")
        assert (
            import_string
            == "serv.bundled.auth.database.session:DatabaseSessionProvider"
        )

        import_string = registry.resolve_provider_import("audit", "file")
        assert import_string == "serv.bundled.auth.file.audit:FileAuditProvider"

    def test_resolve_import_string_passthrough(self):
        """Test that import strings are passed through unchanged."""
        registry = ProviderRegistry()

        import_string = "my.custom.provider:CustomProvider"
        resolved = registry.resolve_provider_import("credential", import_string)
        assert resolved == import_string

    def test_resolve_unknown_provider(self):
        """Test resolving unknown provider specifications."""
        registry = ProviderRegistry()

        # Test unknown bundled provider
        import_string = registry.resolve_provider_import("credential", "unknown")
        assert import_string is None

        # Test unknown provider type
        import_string = registry.resolve_provider_import("unknown_type", "memory")
        assert import_string is None

    def test_register_external_provider(self):
        """Test registering external providers."""
        registry = ProviderRegistry()

        # Register external provider
        registry.register_external_provider(
            "credential", "custom", "my.auth.providers:CustomCredentialProvider"
        )

        # Test resolution
        import_string = registry.resolve_provider_import("credential", "custom")
        assert import_string == "my.auth.providers:CustomCredentialProvider"

        # Test it appears in external implementations
        external = registry.get_external_implementations("credential")
        assert "custom" in external
        assert external["custom"] == "my.auth.providers:CustomCredentialProvider"

    def test_unregister_external_provider(self):
        """Test unregistering external providers."""
        registry = ProviderRegistry()

        # Register and then unregister
        registry.register_external_provider(
            "session", "redis", "redis.auth:RedisSessionProvider"
        )

        # Verify it's registered
        assert registry.resolve_provider_import("session", "redis") is not None

        # Unregister
        result = registry.unregister_external_provider("session", "redis")
        assert result is True

        # Verify it's gone
        assert registry.resolve_provider_import("session", "redis") is None

        # Test unregistering non-existent provider
        result = registry.unregister_external_provider("session", "nonexistent")
        assert result is False

    def test_is_bundled_provider(self):
        """Test checking if provider is bundled."""
        registry = ProviderRegistry()

        # Test bundled providers
        assert registry.is_bundled_provider("credential", "memory") is True
        assert registry.is_bundled_provider("credential", "database") is True

        # Test non-bundled providers
        assert registry.is_bundled_provider("credential", "unknown") is False

        # Register external and test
        registry.register_external_provider(
            "credential", "external", "ext.provider:Provider"
        )
        assert registry.is_bundled_provider("credential", "external") is False

    def test_list_available_providers(self):
        """Test listing available providers."""
        registry = ProviderRegistry()

        # Test listing bundled providers
        providers = registry.list_available_providers("credential")
        assert "memory" in providers
        assert "database" in providers
        assert providers["memory"] == "bundled"
        assert providers["database"] == "bundled"

        # Add external provider and test
        registry.register_external_provider(
            "credential", "custom", "custom.provider:Provider"
        )

        providers = registry.list_available_providers("credential")
        assert "custom" in providers
        assert providers["custom"] == "external"

    def test_get_supported_provider_types(self):
        """Test getting supported provider types."""
        registry = ProviderRegistry()

        types = registry.get_supported_provider_types()
        assert "credential" in types
        assert "session" in types
        assert "user" in types
        assert "audit" in types
        assert "policy" in types

    def test_get_implementations_returns_copy(self):
        """Test that get_*_implementations returns copies."""
        registry = ProviderRegistry()

        # Get bundled implementations
        bundled = registry.get_bundled_implementations("credential")
        original_count = len(bundled)

        # Modify the returned dict
        bundled["test"] = "test:Provider"

        # Get again and verify original is unchanged
        bundled_again = registry.get_bundled_implementations("credential")
        assert len(bundled_again) == original_count
        assert "test" not in bundled_again

        # Same test for external
        external = registry.get_external_implementations("credential")
        external["test"] = "test:Provider"

        external_again = registry.get_external_implementations("credential")
        assert "test" not in external_again
