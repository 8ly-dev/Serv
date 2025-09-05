import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from serving.config import Config, ConfigModel
from serving.serv import ConfigurationError, Serv


class DatabaseModel(ConfigModel):
    """Test model for database configuration."""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port


@pytest.fixture(autouse=True)
def disable_auth():
    """Disable authentication for all tests."""
    with patch('serving.serv.Serv._configure_auth', MagicMock()):
        yield


class TestServ:
    def test_init_fails_without_config(self):
        """Test that Serv initialization fails when no config file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                with pytest.raises(ConfigurationError, match="serving.prod.yaml.*not found"):
                    Serv()
            finally:
                os.chdir(original_cwd)

    def test_init_with_environment(self):
        """Test Serv initialization with explicit environment."""
        yaml_content = """
environment: dev
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serving.dev.yaml"
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
            config_file = Path(tmpdir) / "serving.staging.yaml"
            config_file.write_text(yaml_content)
            
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                with patch.dict(os.environ, {"SERV_ENVIRONMENT": "staging"}):
                    serv = Serv()
                    assert serv.environment == "staging"
            finally:
                os.chdir(original_cwd)

    def test_init_with_string_working_directory(self):
        """Test Serv initialization with string working directory."""
        yaml_content = """
database:
  host: localhost
  port: 5432
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serving.prod.yaml"
            config_file.write_text(yaml_content)
            
            serv = Serv(working_directory=str(tmpdir))
            
            assert serv.config.get("database")["host"] == "localhost"
            assert serv.config.get("database")["port"] == 5432

    def test_init_with_path_working_directory(self):
        """Test Serv initialization with Path object working directory."""
        yaml_content = """
app:
  name: TestApp
  version: 1.0.0
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serving.prod.yaml"
            config_file.write_text(yaml_content)
            
            serv = Serv(working_directory=Path(tmpdir))
            
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
            config_file = Path(tmpdir) / "serving.dev.yaml"
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
                with pytest.raises(ConfigurationError, match="serving.test.yaml.*not found"):
                    Serv(environment="test")
            finally:
                os.chdir(original_cwd)

    def test_nonexistent_working_directory(self):
        """Test behavior when explicitly specified working directory doesn't exist."""
        with pytest.raises(ConfigurationError, match="does not exist"):
            Serv(working_directory="/nonexistent/path")

    def test_invalid_yaml_fails(self):
        """Test that invalid YAML content causes initialization to fail."""
        invalid_yaml = """
test:
  - invalid
  : yaml
  : : content
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serving.prod.yaml"
            config_file.write_text(invalid_yaml)
            
            with pytest.raises(ConfigurationError, match="Failed to load configuration"):
                Serv(working_directory=tmpdir)

    def test_config_injection(self):
        """Test that Config is properly added to container for injection."""
        yaml_content = """
test:
  value: 123
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serving.prod.yaml"
            config_file.write_text(yaml_content)
            
            serv = Serv(working_directory=tmpdir)
            
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
            config_file = Path(tmpdir) / "serving.prod.yaml"
            config_file.write_text(yaml_content)
            
            serv = Serv(working_directory=tmpdir)
            
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
            config_file = Path(tmpdir) / "serving.production.yaml"
            config_file.write_text(yaml_content)
            
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                with patch.dict(os.environ, {"SERV_ENVIRONMENT": "staging"}):
                    serv = Serv(environment="production")
                    assert serv.environment == "production"
            finally:
                os.chdir(original_cwd)

    def test_working_directory_priority(self):
        """Test that explicit working_directory takes priority over current directory."""
        yaml_auto = """
source: auto
"""
        yaml_explicit = """
source: explicit
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create auto-detect file in main directory
            auto_file = Path(tmpdir) / "serving.test.yaml"
            auto_file.write_text(yaml_auto)
            
            # Create explicit file in subdirectory
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            explicit_file = Path(subdir) / "serving.test.yaml"
            explicit_file.write_text(yaml_explicit)
            
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                serv = Serv(working_directory=subdir, environment="test")
                
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
            # Create two subdirectories with their own configs
            dir1 = Path(tmpdir) / "dir1"
            dir1.mkdir()
            config1 = dir1 / "serving.prod.yaml"
            config1.write_text(yaml1)
            
            dir2 = Path(tmpdir) / "dir2"
            dir2.mkdir()
            config2 = dir2 / "serving.prod.yaml"
            config2.write_text(yaml2)
            
            serv1 = Serv(working_directory=dir1)
            serv2 = Serv(working_directory=dir2)
            
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
                assert "serving.custom.yaml" in error_msg
                assert str(tmpdir) in error_msg
            finally:
                os.chdir(original_cwd)

    def test_error_message_for_explicit_path(self):
        """Test that error message is clear when explicit path doesn't exist."""
        nonexistent_path = "/some/fake/path"
        with pytest.raises(ConfigurationError) as exc_info:
            Serv(working_directory=nonexistent_path)
        
        error_msg = str(exc_info.value)
        assert nonexistent_path in error_msg
        assert "does not exist" in error_msg.lower()