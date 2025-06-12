"""Test configuration loading functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from serv.auth.config.loader import AuthConfigLoader
from serv.auth.exceptions import ConfigurationError


class TestAuthConfigLoader:
    """Test AuthConfigLoader functionality."""

    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        config_data = {
            "auth": {
                "enabled": True,
                "providers": {
                    "credential": {"provider": "memory", "config": {}},
                    "session": {"provider": "memory", "config": {}},
                    "user": {"provider": "memory", "config": {}},
                    "audit": {"provider": "memory", "config": {}},
                    "policy": {"provider": "rbac", "config": {}},
                },
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = AuthConfigLoader.load_auth_config(config_path)

            assert config.enabled is True
            assert config.providers.credential.provider == "memory"
            assert config.providers.session.provider == "memory"
            assert config.providers.user.provider == "memory"
            assert config.providers.audit.provider == "memory"
            assert config.providers.policy.provider == "rbac"
        finally:
            config_path.unlink()

    def test_load_config_file_not_found(self):
        """Test loading non-existent configuration file."""
        non_existent_path = Path("/non/existent/config.yaml")

        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            AuthConfigLoader.load_auth_config(non_existent_path)

    def test_load_config_invalid_yaml(self):
        """Test loading configuration file with invalid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            config_path = Path(f.name)

        try:
            with pytest.raises(ConfigurationError, match="Invalid YAML"):
                AuthConfigLoader.load_auth_config(config_path)
        finally:
            config_path.unlink()

    def test_load_config_empty_file(self):
        """Test loading empty configuration file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            config_path = Path(f.name)

        try:
            with pytest.raises(ConfigurationError, match="Configuration file is empty"):
                AuthConfigLoader.load_auth_config(config_path)
        finally:
            config_path.unlink()

    def test_load_config_no_auth_section(self):
        """Test loading configuration file without auth section."""
        config_data = {"other": {"setting": "value"}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            with pytest.raises(ConfigurationError, match="No 'auth' section found"):
                AuthConfigLoader.load_auth_config(config_path)
        finally:
            config_path.unlink()

    def test_load_config_invalid_auth_config(self):
        """Test loading configuration file with invalid auth configuration."""
        config_data = {
            "auth": {
                "enabled": True,
                "providers": {
                    # Missing required providers
                    "credential": {"provider": "memory", "config": {}}
                },
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            with pytest.raises(ConfigurationError, match="Invalid auth configuration"):
                AuthConfigLoader.load_auth_config(config_path)
        finally:
            config_path.unlink()

    def test_load_extension_config_valid(self):
        """Test loading valid extension auth configuration."""
        config_data = {
            "name": "Test Extension",
            "auth": {
                "policies": {"default": "authenticated"},
                "permissions": [
                    {
                        "permission": "read:test",
                        "description": "Read test resources",
                        "resource": "test",
                        "actions": ["read"],
                    }
                ],
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = AuthConfigLoader.load_extension_auth_config(config_path)

            assert config is not None
            assert config.policies.default == "authenticated"
            assert len(config.permissions) == 1
            assert config.permissions[0].permission == "read:test"
        finally:
            config_path.unlink()

    def test_load_extension_config_no_auth_section(self):
        """Test loading extension configuration without auth section."""
        config_data = {"name": "Test Extension", "other": "data"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = AuthConfigLoader.load_extension_auth_config(config_path)
            assert config is None
        finally:
            config_path.unlink()

    def test_load_extension_config_file_not_found(self):
        """Test loading non-existent extension configuration file."""
        non_existent_path = Path("/non/existent/extension.yaml")

        config = AuthConfigLoader.load_extension_auth_config(non_existent_path)
        assert config is None


class TestEnvironmentVariableSubstitution:
    """Test environment variable substitution functionality."""

    def test_simple_env_var_substitution(self):
        """Test simple environment variable substitution."""
        config_data = {
            "auth": {
                "enabled": True,
                "providers": {
                    "credential": {
                        "provider": "database",
                        "config": {"database_url": "${DATABASE_URL}"},
                    },
                    "session": {"provider": "memory", "config": {}},
                    "user": {"provider": "memory", "config": {}},
                    "audit": {"provider": "memory", "config": {}},
                    "policy": {"provider": "rbac", "config": {}},
                },
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///test.db"}):
                config = AuthConfigLoader.load_auth_config(config_path)

                assert (
                    config.providers.credential.config["database_url"]
                    == "sqlite:///test.db"
                )
        finally:
            config_path.unlink()

    def test_env_var_with_default(self):
        """Test environment variable substitution with default value."""
        config_data = {
            "auth": {
                "enabled": True,
                "providers": {
                    "credential": {
                        "provider": "memory",
                        "config": {"timeout": "${CONNECTION_TIMEOUT:-30}"},
                    },
                    "session": {"provider": "memory", "config": {}},
                    "user": {"provider": "memory", "config": {}},
                    "audit": {"provider": "memory", "config": {}},
                    "policy": {"provider": "rbac", "config": {}},
                },
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            # Test with environment variable not set (should use default)
            with patch.dict(os.environ, {}, clear=True):
                config = AuthConfigLoader.load_auth_config(config_path)
                assert config.providers.credential.config["timeout"] == "30"

            # Test with environment variable set
            with patch.dict(os.environ, {"CONNECTION_TIMEOUT": "60"}):
                config = AuthConfigLoader.load_auth_config(config_path)
                assert config.providers.credential.config["timeout"] == "60"
        finally:
            config_path.unlink()

    def test_required_env_var_missing(self):
        """Test required environment variable that is missing."""
        config_data = {
            "auth": {
                "enabled": True,
                "providers": {
                    "credential": {
                        "provider": "database",
                        "config": {
                            "api_key": "${API_KEY:?API key is required for authentication}"
                        },
                    },
                    "session": {"provider": "memory", "config": {}},
                    "user": {"provider": "memory", "config": {}},
                    "audit": {"provider": "memory", "config": {}},
                    "policy": {"provider": "rbac", "config": {}},
                },
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(ConfigurationError, match="API key is required"):
                    AuthConfigLoader.load_auth_config(config_path)
        finally:
            config_path.unlink()

    def test_required_env_var_present(self):
        """Test required environment variable that is present."""
        config_data = {
            "auth": {
                "enabled": True,
                "providers": {
                    "credential": {
                        "provider": "database",
                        "config": {
                            "api_key": "${API_KEY:?API key is required for authentication}"
                        },
                    },
                    "session": {"provider": "memory", "config": {}},
                    "user": {"provider": "memory", "config": {}},
                    "audit": {"provider": "memory", "config": {}},
                    "policy": {"provider": "rbac", "config": {}},
                },
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            with patch.dict(os.environ, {"API_KEY": "secret_key_123"}):
                config = AuthConfigLoader.load_auth_config(config_path)
                assert config.providers.credential.config["api_key"] == "secret_key_123"
        finally:
            config_path.unlink()

    def test_env_var_missing_no_default(self):
        """Test environment variable that is missing without default."""
        config_data = {
            "auth": {
                "enabled": True,
                "providers": {
                    "credential": {
                        "provider": "memory",
                        "config": {"setting": "${MISSING_VAR}"},
                    },
                    "session": {"provider": "memory", "config": {}},
                    "user": {"provider": "memory", "config": {}},
                    "audit": {"provider": "memory", "config": {}},
                    "policy": {"provider": "rbac", "config": {}},
                },
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(
                    ConfigurationError,
                    match="Environment variable 'MISSING_VAR' not set",
                ):
                    AuthConfigLoader.load_auth_config(config_path)
        finally:
            config_path.unlink()

    def test_nested_env_var_substitution(self):
        """Test environment variable substitution in nested structures."""
        config_data = {
            "auth": {
                "enabled": True,
                "providers": {
                    "credential": {
                        "provider": "memory",
                        "config": {
                            "nested": {
                                "database_url": "${DATABASE_URL:-sqlite:///default.db}",
                                "timeout": "${TIMEOUT:-30}",
                            }
                        },
                    },
                    "session": {"provider": "memory", "config": {}},
                    "user": {"provider": "memory", "config": {}},
                    "audit": {"provider": "memory", "config": {}},
                    "policy": {"provider": "rbac", "config": {}},
                },
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            with patch.dict(
                os.environ, {"DATABASE_URL": "postgresql://localhost/test"}
            ):
                config = AuthConfigLoader.load_auth_config(config_path)

                nested = config.providers.credential.config["nested"]
                assert nested["database_url"] == "postgresql://localhost/test"
                assert nested["timeout"] == "30"  # Uses default
        finally:
            config_path.unlink()


class TestConfigurationUtilities:
    """Test configuration utility methods."""

    def test_get_default_config_path(self):
        """Test getting default configuration path."""
        path = AuthConfigLoader.get_default_config_path()
        assert path == Path.cwd() / "serv.config.yaml"

    def test_validate_config_exists_valid_path(self):
        """Test validating existing configuration file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("test: data")
            config_path = Path(f.name)

        try:
            validated_path = AuthConfigLoader.validate_config_exists(config_path)
            assert validated_path == config_path
        finally:
            config_path.unlink()

    def test_validate_config_exists_missing_file(self):
        """Test validating non-existent configuration file."""
        non_existent_path = Path("/non/existent/config.yaml")

        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            AuthConfigLoader.validate_config_exists(non_existent_path)

    def test_validate_config_exists_directory_not_file(self):
        """Test validating configuration path that is a directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)

            with pytest.raises(
                ConfigurationError, match="Configuration path is not a file"
            ):
                AuthConfigLoader.validate_config_exists(dir_path)
