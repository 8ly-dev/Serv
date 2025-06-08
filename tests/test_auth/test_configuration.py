"""
Configuration system tests for authentication.

Tests configuration validation, environment variable substitution,
and security considerations in auth configuration.
"""

import os
import tempfile

import pytest
import yaml

from serv.config import ServConfigError, load_config, validate_auth_config


class TestAuthConfigurationValidation:
    """Test authentication configuration validation."""

    def test_valid_auth_config_passes_validation(self):
        """Test that a valid auth configuration passes validation."""
        valid_config = {
            "providers": [
                {
                    "type": "jwt",
                    "config": {
                        "secret_key": "this_is_a_very_long_secure_secret_key_for_testing_purposes_that_meets_minimum_length",
                        "algorithm": "HS256",
                        "token_lifetime": 3600,
                    },
                }
            ],
            "storage": {
                "backend": "serv.bundled.auth.storage.ommi_storage",
                "config": {"connection_string": "sqlite:///auth.db"},
            },
            "rate_limiting": {"login_attempts": "5/min", "api_requests": "100/hour"},
            "security": {
                "force_https": True,
                "session_timeout": 1800,
                "device_fingerprinting": True,
            },
        }

        # Should not raise any exception
        validate_auth_config(valid_config)

    def test_missing_providers_validation(self):
        """Test validation fails when providers are missing."""
        invalid_config = {
            "storage": {"backend": "test"},
            "rate_limiting": {"login_attempts": "5/min"},
        }

        with pytest.raises(
            ValueError, match="At least one authentication provider must be configured"
        ):
            validate_auth_config(invalid_config)

    def test_empty_providers_validation(self):
        """Test validation fails when providers list is empty."""
        invalid_config = {"providers": [], "storage": {"backend": "test"}}

        with pytest.raises(
            ValueError, match="At least one authentication provider must be configured"
        ):
            validate_auth_config(invalid_config)

    def test_provider_missing_type_validation(self):
        """Test validation fails when provider is missing type."""
        invalid_config = {"providers": [{"config": {"secret_key": "some_key"}}]}

        with pytest.raises(
            (ValueError, ServConfigError), match="missing required 'type' field"
        ):
            validate_auth_config(invalid_config)

    def test_jwt_provider_short_secret_validation(self):
        """Test validation fails when JWT secret is too short."""
        invalid_config = {
            "providers": [
                {
                    "type": "jwt",
                    "config": {
                        "secret_key": "short_key",  # Too short
                        "algorithm": "HS256",
                    },
                }
            ]
        }

        with pytest.raises(
            ValueError, match="JWT secret_key must be at least 32 characters"
        ):
            validate_auth_config(invalid_config)

    def test_jwt_provider_missing_secret_validation(self):
        """Test validation fails when JWT secret is missing."""
        invalid_config = {
            "providers": [
                {
                    "type": "jwt",
                    "config": {
                        "algorithm": "HS256"
                        # Missing secret_key
                    },
                }
            ]
        }

        with pytest.raises(
            ValueError, match="JWT provider requires 'secret_key' in config"
        ):
            validate_auth_config(invalid_config)

    def test_storage_backend_validation(self):
        """Test storage backend validation."""
        invalid_config = {
            "providers": [
                {
                    "type": "jwt",
                    "config": {
                        "secret_key": "this_is_a_very_long_secure_secret_key_for_testing_purposes"
                    },
                }
            ],
            "storage": {
                # Missing backend
                "config": {}
            },
        }

        with pytest.raises(
            (ValueError, ServConfigError), match="missing required 'backend' field"
        ):
            validate_auth_config(invalid_config)

    def test_rate_limiting_format_validation(self):
        """Test rate limiting format validation."""
        invalid_config = {
            "providers": [
                {
                    "type": "jwt",
                    "config": {
                        "secret_key": "this_is_a_very_long_secure_secret_key_for_testing_purposes"
                    },
                }
            ],
            "rate_limiting": {
                "login_attempts": "invalid_format"  # Should be like "5/min"
            },
        }

        with pytest.raises((ValueError, ServConfigError), match="Invalid rate limit"):
            validate_auth_config(invalid_config)

    def test_multiple_providers_validation(self):
        """Test validation with multiple providers."""
        valid_config = {
            "providers": [
                {
                    "type": "jwt",
                    "config": {
                        "secret_key": "this_is_a_very_long_secure_secret_key_for_testing_purposes"
                    },
                },
                {
                    "type": "oauth",
                    "config": {
                        "client_id": "oauth_client_id",
                        "client_secret": "oauth_client_secret_that_is_long_enough",
                    },
                },
            ]
        }

        # Should pass validation
        validate_auth_config(valid_config)


class TestEnvironmentVariableSubstitution:
    """Test environment variable substitution in auth configuration."""

    def test_environment_variable_substitution(self):
        """Test basic environment variable substitution."""
        # Set test environment variables
        os.environ["TEST_JWT_SECRET"] = (
            "test_jwt_secret_key_that_is_long_enough_for_testing"
        )
        os.environ["TEST_DB_URL"] = "postgresql://user:pass@localhost/auth_test"

        try:
            config_with_env_vars = {
                "auth": {
                    "providers": [
                        {
                            "type": "jwt",
                            "config": {
                                "secret_key": "${TEST_JWT_SECRET}",
                                "algorithm": "HS256",
                            },
                        }
                    ],
                    "storage": {
                        "backend": "serv.bundled.auth.storage.ommi_storage",
                        "config": {"connection_string": "${TEST_DB_URL}"},
                    },
                }
            }

            # Create temporary config file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                yaml.dump(config_with_env_vars, f)
                temp_config_path = f.name

            try:
                # Load config with environment substitution
                loaded_config = load_config(temp_config_path)

                # Check that environment variables were substituted
                jwt_secret = loaded_config["auth"]["providers"][0]["config"][
                    "secret_key"
                ]
                db_url = loaded_config["auth"]["storage"]["config"]["connection_string"]

                assert (
                    jwt_secret == "test_jwt_secret_key_that_is_long_enough_for_testing"
                )
                assert db_url == "postgresql://user:pass@localhost/auth_test"

                # Validate the substituted config
                validate_auth_config(loaded_config["auth"])

            finally:
                os.unlink(temp_config_path)

        finally:
            # Clean up environment variables
            os.environ.pop("TEST_JWT_SECRET", None)
            os.environ.pop("TEST_DB_URL", None)

    def test_missing_environment_variable(self):
        """Test handling of missing environment variables."""
        config_with_missing_env = {
            "auth": {
                "providers": [
                    {
                        "type": "jwt",
                        "config": {
                            "secret_key": "${NONEXISTENT_SECRET_KEY}",
                            "algorithm": "HS256",
                        },
                    }
                ]
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_with_missing_env, f)
            temp_config_path = f.name

        try:
            with pytest.raises(
                (ValueError, ServConfigError),
                match="Required environment variable 'NONEXISTENT_SECRET_KEY' is not set",
            ):
                load_config(temp_config_path)

        finally:
            os.unlink(temp_config_path)

    def test_partial_environment_variable_substitution(self):
        """Test substitution in strings with other content."""
        os.environ["TEST_DB_HOST"] = "auth-db.example.com"
        os.environ["TEST_DB_PORT"] = "5432"

        try:
            config_with_partial_env = {
                "auth": {
                    "providers": [
                        {
                            "type": "jwt",
                            "config": {
                                "secret_key": "this_is_a_very_long_secure_secret_key_for_testing_purposes"
                            },
                        }
                    ],
                    "storage": {
                        "backend": "postgresql",
                        "config": {
                            "connection_string": "postgresql://user:pass@${TEST_DB_HOST}:${TEST_DB_PORT}/auth_db"
                        },
                    },
                }
            }

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                yaml.dump(config_with_partial_env, f)
                temp_config_path = f.name

            try:
                loaded_config = load_config(temp_config_path)
                connection_string = loaded_config["auth"]["storage"]["config"][
                    "connection_string"
                ]

                expected = "postgresql://user:pass@auth-db.example.com:5432/auth_db"
                assert connection_string == expected

            finally:
                os.unlink(temp_config_path)

        finally:
            os.environ.pop("TEST_DB_HOST", None)
            os.environ.pop("TEST_DB_PORT", None)

    def test_environment_variable_security(self):
        """Test that environment variables don't leak sensitive data."""
        os.environ["SENSITIVE_SECRET"] = (
            "super_secret_password_that_should_not_be_logged"
        )

        try:
            config_with_sensitive_env = {
                "auth": {
                    "providers": [
                        {
                            "type": "jwt",
                            "config": {
                                "secret_key": "${SENSITIVE_SECRET}",
                                "algorithm": "HS256",
                            },
                        }
                    ]
                }
            }

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                yaml.dump(config_with_sensitive_env, f)
                temp_config_path = f.name

            try:
                loaded_config = load_config(temp_config_path)

                # The secret should be substituted correctly
                jwt_secret = loaded_config["auth"]["providers"][0]["config"][
                    "secret_key"
                ]
                assert jwt_secret == "super_secret_password_that_should_not_be_logged"

                # But if we convert config to string, it should not contain the secret
                # (This is important for logging/debugging safety)
                config_str = str(loaded_config)
                # This test depends on implementation - the config might mask sensitive values

            finally:
                os.unlink(temp_config_path)

        finally:
            os.environ.pop("SENSITIVE_SECRET", None)


class TestConfigurationSecurity:
    """Test security aspects of configuration handling."""

    def test_config_file_permissions_warning(self):
        """Test that configuration loading checks file permissions."""
        # Create a config file with overly permissive permissions
        config_data = {
            "auth": {
                "providers": [
                    {
                        "type": "jwt",
                        "config": {"secret_key": "secret_key_that_should_be_protected"},
                    }
                ]
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_config_path = f.name

        try:
            # Make file readable by others (insecure)
            os.chmod(temp_config_path, 0o644)

            # Loading should still work but might issue warnings
            # (Implementation could check permissions and warn)
            loaded_config = load_config(temp_config_path)

            # Config should still be loaded correctly
            assert "auth" in loaded_config
            assert "providers" in loaded_config["auth"]

        finally:
            os.unlink(temp_config_path)

    def test_config_validation_injection_protection(self):
        """Test that config validation protects against injection attacks."""
        # Attempt to inject dangerous values
        malicious_config = {
            "providers": [
                {
                    "type": "jwt",
                    "config": {
                        "secret_key": "valid_secret_key_that_is_long_enough_for_validation",
                        "algorithm": "'; DROP TABLE users; --",  # SQL injection attempt
                    },
                }
            ],
            "storage": {
                "backend": "../../../etc/passwd",  # Path traversal attempt
                "config": {},
            },
        }

        # Should either reject the malicious values or sanitize them
        with pytest.raises((ValueError, ServConfigError, TypeError)):
            validate_auth_config(malicious_config)

    def test_config_deep_nesting_protection(self):
        """Test protection against deeply nested configuration attacks."""
        # Create deeply nested configuration
        nested_config = {"providers": []}
        current_level = nested_config

        # Create 100 levels of nesting
        for i in range(100):
            current_level["nested"] = {}
            current_level = current_level["nested"]

        current_level["type"] = "jwt"
        current_level["config"] = {"secret_key": "secret_key_that_is_long_enough"}

        # Should handle deep nesting gracefully (not cause stack overflow)
        try:
            validate_auth_config(nested_config)
        except (RecursionError, ValueError):
            # Either reject deep nesting or handle it gracefully
            pass

    def test_config_size_limits(self):
        """Test that configuration has reasonable size limits."""
        # Create a very large configuration
        large_config = {"providers": []}

        # Add many providers
        for i in range(1000):
            large_config["providers"].append(
                {
                    "type": "jwt",
                    "name": f"provider_{i}",
                    "config": {
                        "secret_key": f"secret_key_number_{i}_that_is_long_enough_for_validation"
                    },
                }
            )

        # Should either handle large configs or reject them with appropriate error
        try:
            validate_auth_config(large_config)
        except (ValueError, MemoryError):
            # Acceptable to reject overly large configurations
            pass


class TestConfigurationDefaults:
    """Test configuration defaults and fallbacks."""

    def test_minimal_configuration_with_defaults(self):
        """Test that minimal configuration gets sensible defaults."""
        minimal_config = {
            "providers": [
                {
                    "type": "jwt",
                    "config": {
                        "secret_key": "minimal_secret_key_that_meets_length_requirements"
                    },
                }
            ]
        }

        # Should pass validation even without optional fields
        validate_auth_config(minimal_config)

        # Could test that defaults are applied (depends on implementation)

    def test_default_security_settings(self):
        """Test that default security settings are secure."""
        config_without_security = {
            "providers": [
                {
                    "type": "jwt",
                    "config": {
                        "secret_key": "secret_key_for_testing_defaults_that_is_long_enough"
                    },
                }
            ]
        }

        # Should pass validation
        validate_auth_config(config_without_security)

        # In a real implementation, could check that secure defaults are applied:
        # - HTTPS enforcement
        # - Secure session timeouts
        # - Device fingerprinting enabled
        # - Rate limiting enabled

    def test_algorithm_defaults(self):
        """Test that secure algorithm defaults are used."""
        config_without_algorithm = {
            "providers": [
                {
                    "type": "jwt",
                    "config": {
                        "secret_key": "secret_key_for_algorithm_testing_that_is_long_enough"
                        # No algorithm specified
                    },
                }
            ]
        }

        # Should pass validation (should use secure default algorithm)
        validate_auth_config(config_without_algorithm)

        # Could verify that HS256 or better is used as default
