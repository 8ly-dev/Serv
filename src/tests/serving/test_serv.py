import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from serving.config import Config, Model
from serving.serv import ConfigurationError, Serv


class DatabaseModel(Model):
    """Test model for database configuration."""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port


class TestServ:
    def test_init_fails_without_config(self):
        """Test that Serv initialization fails when no config file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                with pytest.raises(ConfigurationError, match="serv.prod.yaml.*not found"):
                    Serv()
            finally:
                os.chdir(original_cwd)

    def test_init_with_environment(self):
        """Test Serv initialization with explicit environment."""
        yaml_content = """
environment: dev
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serv.dev.yaml"
            config_file.write_text(yaml_content)
            
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                serv = Serv(environment="dev")
                assert serv.environment == "dev"
                assert serv.config.get("environment") == "dev"
            finally:
                os.chdir(original_cwd)

    def test_init_with_serv_environment_envvar(self):
        """Test Serv initialization using SERV_ENVIRONMENT env var."""
        yaml_content = """
environment: staging
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serv.staging.yaml"
            config_file.write_text(yaml_content)
            
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                with patch.dict(os.environ, {"SERV_ENVIRONMENT": "staging"}):
                    serv = Serv()
                    assert serv.environment == "staging"
            finally:
                os.chdir(original_cwd)

    def test_init_with_string_config_path(self):
        """Test Serv initialization with string config path."""
        yaml_content = """
database:
  host: localhost
  port: 5432
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(yaml_content)
            
            serv = Serv(config_path=str(config_file))
            
            assert serv.config.get("database")["host"] == "localhost"
            assert serv.config.get("database")["port"] == 5432

    def test_init_with_path_config_path(self):
        """Test Serv initialization with Path object config path."""
        yaml_content = """
app:
  name: TestApp
  version: 1.0.0
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "app.yaml"
            config_file.write_text(yaml_content)
            
            serv = Serv(config_path=config_file)
            
            assert serv.config.get("app")["name"] == "TestApp"
            assert serv.config.get("app")["version"] == "1.0.0"

    def test_auto_detect_environment_config(self):
        """Test auto-detection of environment-specific config file."""
        yaml_content = """
environment: development
database:
  host: dev.db.local
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serv.dev.yaml"
            config_file.write_text(yaml_content)
            
            # Change working directory temporarily
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                serv = Serv(environment="dev")
                
                assert serv.config.get("environment") == "development"
                assert serv.config.get("database")["host"] == "dev.db.local"
            finally:
                os.chdir(original_cwd)

    def test_fails_when_environment_config_missing(self):
        """Test that initialization fails when environment-specific config doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                with pytest.raises(ConfigurationError, match="serv.test.yaml.*not found"):
                    Serv(environment="test")
            finally:
                os.chdir(original_cwd)

    def test_nonexistent_explicit_config_path(self):
        """Test behavior when explicitly specified config doesn't exist."""
        with pytest.raises(ConfigurationError, match="not found"):
            Serv(config_path="/nonexistent/path/config.yaml")

    def test_invalid_yaml_fails(self):
        """Test that invalid YAML content causes initialization to fail."""
        invalid_yaml = """
test:
  - invalid
  : yaml
  : : content
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "invalid.yaml"
            config_file.write_text(invalid_yaml)
            
            with pytest.raises(ConfigurationError, match="Failed to load configuration"):
                Serv(config_path=config_file)

    def test_config_injection(self):
        """Test that Config is properly added to container for injection."""
        yaml_content = """
test:
  value: 123
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test.yaml"
            config_file.write_text(yaml_content)
            
            serv = Serv(config_path=config_file)
            
            # Get Config from container
            injected_config = serv.container.get(Config)
            assert injected_config is serv.config
            assert injected_config.get("test")["value"] == 123

    def test_model_injection(self):
        """Test that models can be injected using the config."""
        yaml_content = """
DatabaseModel:
  host: db.example.com
  port: 3306
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(yaml_content)
            
            serv = Serv(config_path=config_file)
            
            # Get model from container
            db_model = serv.container.get(DatabaseModel)
            assert isinstance(db_model, DatabaseModel)
            assert db_model.host == "db.example.com"
            assert db_model.port == 3306

    def test_environment_priority(self):
        """Test that explicit environment parameter takes priority over env var."""
        yaml_content = """
environment: production
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serv.production.yaml"
            config_file.write_text(yaml_content)
            
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                with patch.dict(os.environ, {"SERV_ENVIRONMENT": "staging"}):
                    serv = Serv(environment="production")
                    assert serv.environment == "production"
            finally:
                os.chdir(original_cwd)

    def test_config_path_priority(self):
        """Test that explicit config_path takes priority over auto-detection."""
        yaml_auto = """
source: auto
"""
        yaml_explicit = """
source: explicit
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create auto-detect file (won't be used)
            auto_file = Path(tmpdir) / "serv.test.yaml"
            auto_file.write_text(yaml_auto)
            
            # Create explicit file
            explicit_file = Path(tmpdir) / "explicit.yaml"
            explicit_file.write_text(yaml_explicit)
            
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                serv = Serv(config_path=explicit_file, environment="test")
                
                assert serv.config.get("source") == "explicit"
            finally:
                os.chdir(original_cwd)

    def test_multiple_serv_instances(self):
        """Test that multiple Serv instances can coexist with different configs."""
        yaml1 = """
instance: first
port: 8000
"""
        yaml2 = """
instance: second
port: 9000
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config1 = Path(tmpdir) / "config1.yaml"
            config1.write_text(yaml1)
            
            config2 = Path(tmpdir) / "config2.yaml"
            config2.write_text(yaml2)
            
            serv1 = Serv(config_path=config1)
            serv2 = Serv(config_path=config2)
            
            assert serv1.config.get("instance") == "first"
            assert serv1.config.get("port") == 8000
            
            assert serv2.config.get("instance") == "second"
            assert serv2.config.get("port") == 9000
            
            # Each should have its own container
            assert serv1.container is not serv2.container
            assert serv1.registry is not serv2.registry

    def test_error_message_includes_cwd(self):
        """Test that error message includes current working directory for context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                with pytest.raises(ConfigurationError) as exc_info:
                    Serv(environment="custom")
                
                error_msg = str(exc_info.value)
                assert "serv.custom.yaml" in error_msg
                assert str(tmpdir) in error_msg
            finally:
                os.chdir(original_cwd)

    def test_error_message_for_explicit_path(self):
        """Test that error message is clear when explicit path doesn't exist."""
        nonexistent_path = "/some/fake/path/config.yaml"
        with pytest.raises(ConfigurationError) as exc_info:
            Serv(config_path=nonexistent_path)
        
        error_msg = str(exc_info.value)
        assert nonexistent_path in error_msg
        assert "not found" in error_msg.lower()