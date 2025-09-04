import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import pytest
import yaml
from bevy.containers import Container
from bevy.registries import Registry

from serving.config import Config, Model, handle_model_types


class DatabaseModel(Model):
    """Model for database configuration."""
    
    def __init__(self, host: str, port: int, username: str, password: str, database: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database


class ServerModel(Model):
    """Model for server configuration."""
    
    def __init__(self, host: str, port: int, debug: bool = False, workers: int = 1):
        self.host = host
        self.port = port
        self.debug = debug
        self.workers = workers


class CustomKeyModel(Model, model_key="CustomConfig"):
    """Model with custom model key."""
    
    def __init__(self, value: str, enabled: bool = True):
        self.value = value
        self.enabled = enabled


class AppSettingsModel(Model):
    """Model for application settings."""
    
    def __init__(self, name: str, version: str, features: list[str], settings: dict):
        self.name = name
        self.version = version
        self.features = features
        self.settings = settings


class TestModelInjection:
    def test_basic_model_injection(self):
        """Test basic model injection with a simple configuration."""
        config_dict = {
            "DatabaseModel": {
                "host": "localhost",
                "port": 5432,
                "username": "admin",
                "password": "secret",
                "database": "testdb"
            }
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        container.add(Config(config_dict))
        
        db_model = container.get(DatabaseModel)
        
        assert isinstance(db_model, DatabaseModel)
        assert db_model.host == "localhost"
        assert db_model.port == 5432
        assert db_model.username == "admin"
        assert db_model.password == "secret"
        assert db_model.database == "testdb"

    def test_multiple_model_injection(self):
        """Test injecting multiple different models."""
        config_dict = {
            "DatabaseModel": {
                "host": "db.example.com",
                "port": 3306,
                "username": "root",
                "password": "password123",
                "database": "production"
            },
            "ServerModel": {
                "host": "0.0.0.0",
                "port": 8080,
                "debug": True,
                "workers": 4
            }
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        container.add(Config(config_dict))
        
        db_model = container.get(DatabaseModel)
        server_model = container.get(ServerModel)
        
        assert db_model.host == "db.example.com"
        assert db_model.port == 3306
        
        assert server_model.host == "0.0.0.0"
        assert server_model.port == 8080
        assert server_model.debug is True
        assert server_model.workers == 4

    def test_model_with_default_values(self):
        """Test model injection with default values."""
        config_dict = {
            "ServerModel": {
                "host": "localhost",
                "port": 3000
            }
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        container.add(Config(config_dict))
        
        server_model = container.get(ServerModel)
        
        assert server_model.host == "localhost"
        assert server_model.port == 3000
        assert server_model.debug is False  # default value
        assert server_model.workers == 1  # default value

    def test_model_keys(self):
        """Test that model keys are correctly set."""
        assert DatabaseModel.__model_key__ == "DatabaseModel"
        assert ServerModel.__model_key__ == "ServerModel"
        assert CustomKeyModel.__model_key__ == "CustomConfig"
        assert AppSettingsModel.__model_key__ == "AppSettingsModel"

    def test_custom_model_key_injection(self):
        """Test injection with custom model_key parameter."""
        config_dict = {
            "CustomConfig": {  # Using the custom key instead of class name
                "value": "test_value",
                "enabled": False
            }
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        container.add(Config(config_dict))
        
        custom_model = container.get(CustomKeyModel)
        
        assert isinstance(custom_model, CustomKeyModel)
        assert custom_model.value == "test_value"
        assert custom_model.enabled is False

    def test_complex_model_injection(self):
        """Test injection with complex nested data structures."""
        config_dict = {
            "AppSettingsModel": {
                "name": "MyApplication",
                "version": "2.1.0",
                "features": ["auth", "api", "websocket", "caching"],
                "settings": {
                    "timeout": 30,
                    "max_connections": 100,
                    "cache_ttl": 3600,
                    "retry_attempts": 3
                }
            }
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        container.add(Config(config_dict))
        
        app_model = container.get(AppSettingsModel)
        
        assert app_model.name == "MyApplication"
        assert app_model.version == "2.1.0"
        assert len(app_model.features) == 4
        assert "auth" in app_model.features
        assert "websocket" in app_model.features
        assert app_model.settings["timeout"] == 30
        assert app_model.settings["max_connections"] == 100

    def test_missing_model_config(self):
        """Test that appropriate error is raised when model config is missing."""
        config_dict = {
            "SomeOtherModel": {
                "key": "value"
            }
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        container.add(Config(config_dict))
        
        with pytest.raises(KeyError):
            container.get(DatabaseModel)

    def test_invalid_model_parameters(self):
        """Test that error is raised with invalid model parameters."""
        config_dict = {
            "DatabaseModel": {
                "host": "localhost",
                "port": 5432
                # Missing required parameters: username, password, database
            }
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        container.add(Config(config_dict))
        
        with pytest.raises(TypeError):
            container.get(DatabaseModel)

    def test_non_model_dependency(self):
        """Test that non-Model types raise appropriate error."""
        from bevy.injection_types import DependencyResolutionError
        
        class NotAModel:
            pass
        
        config_dict = {}
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        container.add(Config(config_dict))
        
        with pytest.raises(DependencyResolutionError, match="No handler found"):
            container.get(NotAModel)

    def test_container_reuse(self):
        """Test that the same container can be used for multiple injections."""
        config_dict = {
            "DatabaseModel": {
                "host": "localhost",
                "port": 5432,
                "username": "user",
                "password": "pass",
                "database": "db"
            },
            "ServerModel": {
                "host": "0.0.0.0",
                "port": 8000,
                "debug": False,
                "workers": 2
            }
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        container.add(Config(config_dict))
        
        # Get models multiple times
        db1 = container.get(DatabaseModel)
        db2 = container.get(DatabaseModel)
        server1 = container.get(ServerModel)
        server2 = container.get(ServerModel)
        
        # Each call should return a new instance
        assert db1 is not db2
        assert server1 is not server2
        
        # But with same values
        assert db1.host == db2.host
        assert server1.port == server2.port

    def test_config_update(self):
        """Test updating config and getting updated models."""
        initial_config = {
            "DatabaseModel": {
                "host": "localhost",
                "port": 5432,
                "username": "user1",
                "password": "pass1",
                "database": "db1"
            }
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        container.add(Config(initial_config))
        
        db_model1 = container.get(DatabaseModel)
        assert db_model1.username == "user1"
        
        # Update config
        updated_config = {
            "DatabaseModel": {
                "host": "newhost",
                "port": 3306,
                "username": "user2",
                "password": "pass2",
                "database": "db2"
            }
        }
        
        # Remove old config and add new one
        container.add(Config(updated_config))
        
        db_model2 = container.get(DatabaseModel)
        assert db_model2.username == "user2"
        assert db_model2.host == "newhost"

    def test_integration_with_yaml_loading(self):
        """Test the full integration with loading config from YAML file."""
        yaml_content = """
DatabaseModel:
  host: db.integration.test
  port: 5432
  username: integration_user
  password: integration_pass
  database: integration_db
  
ServerModel:
  host: 127.0.0.1
  port: 9000
  debug: true
  workers: 8
"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "integration.yaml"
            config_file.write_text(yaml_content)
            
            config = Config.load_config("integration.yaml", tmpdir)
            
            registry = Registry()
            handle_model_types.register_hook(registry)
            container = registry.create_container()
            container.add(config)
            
            db_model = container.get(DatabaseModel)
            server_model = container.get(ServerModel)
            
            assert db_model.host == "db.integration.test"
            assert db_model.username == "integration_user"
            
            assert server_model.host == "127.0.0.1"
            assert server_model.port == 9000
            assert server_model.debug is True
            assert server_model.workers == 8

    def test_model_inheritance(self):
        """Test that subclassed models work correctly."""
        class ExtendedDatabaseModel(DatabaseModel):
            def __init__(self, host: str, port: int, username: str, password: str, 
                         database: str, pool_size: int = 10):
                super().__init__(host, port, username, password, database)
                self.pool_size = pool_size
        
        config_dict = {
            "ExtendedDatabaseModel": {
                "host": "localhost",
                "port": 5432,
                "username": "admin",
                "password": "secret",
                "database": "testdb",
                "pool_size": 20
            }
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        container.add(Config(config_dict))
        
        extended_db = container.get(ExtendedDatabaseModel)
        
        assert isinstance(extended_db, ExtendedDatabaseModel)
        assert extended_db.host == "localhost"
        assert extended_db.pool_size == 20
        assert extended_db.__model_key__ == "ExtendedDatabaseModel"