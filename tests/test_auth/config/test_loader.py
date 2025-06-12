"""Test auth config parsing utilities."""

import pytest

from serv.auth.config.loader import (
    parse_auth_config,
    parse_extension_auth_config, 
    merge_extension_configs,
)
from serv.auth.config.schema import AuthConfig, ExtensionAuthConfig
from serv.auth.exceptions import ConfigurationError


class TestParseAuthConfig:
    """Test parse_auth_config function."""

    def test_parse_valid_auth_config(self):
        """Test parsing valid auth configuration."""
        app_config = {
            "auth": {
                "enabled": True,
                "providers": {
                    "credential": {"provider": "memory"},
                    "session": {"provider": "memory"},
                    "user": {"provider": "memory"},
                    "audit": {"provider": "memory"},
                    "policy": {"provider": "rbac"}
                }
            }
        }
        
        config = parse_auth_config(app_config)
        assert isinstance(config, AuthConfig)
        assert config.enabled is True
        assert config.providers.credential.provider == "memory"

    def test_parse_empty_app_config(self):
        """Test parsing empty app config raises error."""
        with pytest.raises(ConfigurationError, match="Application configuration is empty"):
            parse_auth_config({})

    def test_parse_missing_auth_section(self):
        """Test missing auth section raises error."""
        app_config = {"site_info": {"name": "Test"}}
        
        with pytest.raises(ConfigurationError, match="No 'auth' section found"):
            parse_auth_config(app_config)

    def test_parse_invalid_auth_config(self):
        """Test invalid auth config raises validation error."""
        app_config = {
            "auth": {
                "enabled": "not_a_boolean",  # Invalid type
                "providers": {}  # Missing required fields
            }
        }
        
        with pytest.raises(ConfigurationError, match="Invalid auth configuration"):
            parse_auth_config(app_config)


class TestParseExtensionAuthConfig:
    """Test parse_extension_auth_config function."""

    def test_parse_valid_extension_config(self):
        """Test parsing valid extension auth config."""
        extension_config = {
            "auth": {
                "permissions": [
                    {
                        "permission": "blog.create",
                        "description": "Create blog posts",
                        "resource": "blog",
                        "actions": ["create"]
                    }
                ]
            }
        }
        
        config = parse_extension_auth_config(extension_config)
        assert isinstance(config, ExtensionAuthConfig)
        assert len(config.permissions) == 1
        assert config.permissions[0].permission == "blog.create"

    def test_parse_empty_extension_config(self):
        """Test parsing empty extension config returns None."""
        config = parse_extension_auth_config({})
        assert config is None

    def test_parse_extension_config_no_auth_section(self):
        """Test extension config without auth section returns None."""
        extension_config = {"name": "blog", "version": "1.0.0"}
        
        config = parse_extension_auth_config(extension_config)
        assert config is None

    def test_parse_invalid_extension_config(self):
        """Test invalid extension auth config raises validation error."""
        extension_config = {
            "auth": {
                "permissions": [
                    {
                        # Missing required 'permission' field
                        "description": "Test",
                        "resource": "test",
                        "actions": []
                    }
                ]
            }
        }
        
        with pytest.raises(ConfigurationError, match="Invalid extension auth configuration"):
            parse_extension_auth_config(extension_config)


class TestMergeExtensionConfigs:
    """Test merge_extension_configs function."""

    def test_merge_configs_basic(self):
        """Test basic config merging (currently returns base config)."""
        base_config = AuthConfig(
            enabled=True,
            providers={
                "credential": {"provider": "memory"},
                "session": {"provider": "memory"}, 
                "user": {"provider": "memory"},
                "audit": {"provider": "memory"},
                "policy": {"provider": "rbac"}
            }
        )
        
        extension_configs = []
        
        merged = merge_extension_configs(base_config, extension_configs)
        assert merged == base_config

    def test_merge_with_extension_configs(self):
        """Test merging with extension configs (placeholder implementation)."""
        base_config = AuthConfig(
            enabled=True,
            providers={
                "credential": {"provider": "memory"},
                "session": {"provider": "memory"},
                "user": {"provider": "memory"}, 
                "audit": {"provider": "memory"},
                "policy": {"provider": "rbac"}
            }
        )
        
        extension_config = ExtensionAuthConfig(
            permissions=[
                {
                    "permission": "blog.create",
                    "description": "Create blog posts",
                    "resource": "blog",
                    "actions": ["create"]
                }
            ]
        )
        
        merged = merge_extension_configs(base_config, [extension_config])
        # Currently just returns base config - will be enhanced later
        assert merged == base_config