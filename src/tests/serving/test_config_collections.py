"""Tests for ConfigModel collection support."""

import tempfile
from pathlib import Path
from typing import List

import pytest
from bevy.registries import Registry

from serving.config import Config, ConfigModel, handle_model_types


class Server(ConfigModel, is_collection=True):
    """Test model representing servers as a collection."""
    
    def __init__(self, host: str, port: int, enabled: bool = True):
        self.host = host
        self.port = port
        self.enabled = enabled


class Database(ConfigModel):
    """Test model for a single database config."""
    
    def __init__(self, name: str, connection_string: str):
        self.name = name
        self.connection_string = connection_string


class Worker(ConfigModel, is_collection=True):
    """Test model for worker configurations."""
    
    def __init__(self, id: int, queue: str, concurrency: int = 1):
        self.id = id
        self.queue = queue
        self.concurrency = concurrency


class Feature(ConfigModel, is_collection=True):
    """Test model with from_dict class method."""
    
    def __init__(self, name: str, enabled: bool):
        self.name = name
        self.enabled = enabled
    
    @classmethod
    def from_dict(cls, data: dict):
        """Custom factory method for creating instances from dict."""
        return cls(
            name=data.get("name", "unknown"),
            enabled=data.get("enabled", False)
        )


class TestConfigCollections:
    """Test collection support in Config class."""
    
    def test_get_collection_of_models(self):
        """Test getting a collection of models from config."""
        config_data = {
            "Server": [
                {"host": "server1.example.com", "port": 8080},
                {"host": "server2.example.com", "port": 8081, "enabled": False},
                {"host": "server3.example.com", "port": 8082},
            ]
        }
        config = Config(config_data)
        
        servers = config.get("Server", Server, is_collection=True)
        
        assert len(servers) == 3
        assert all(isinstance(s, Server) for s in servers)
        assert servers[0].host == "server1.example.com"
        assert servers[0].port == 8080
        assert servers[0].enabled is True  # default value
        assert servers[1].host == "server2.example.com"
        assert servers[1].enabled is False
        assert servers[2].port == 8082
    
    def test_get_single_model_not_collection(self):
        """Test getting a single model (not a collection)."""
        config_data = {
            "Database": {
                "name": "main_db",
                "connection_string": "postgresql://localhost/mydb"
            }
        }
        config = Config(config_data)
        
        db = config.get("Database", Database, is_collection=False)
        
        assert isinstance(db, Database)
        assert db.name == "main_db"
        assert db.connection_string == "postgresql://localhost/mydb"
    
    def test_empty_collection(self):
        """Test handling of empty collections."""
        config_data = {"Server": []}
        config = Config(config_data)
        
        servers = config.get("Server", Server, is_collection=True)
        
        assert servers == []
        assert isinstance(servers, list)
    
    def test_collection_with_from_dict_method(self):
        """Test collection models that have custom from_dict method."""
        config_data = {
            "Feature": [
                {"name": "feature1", "enabled": True},
                {"name": "feature2"},  # Missing enabled, should use default
                {"enabled": False},  # Missing name, should use default
            ]
        }
        config = Config(config_data)
        
        features = config.get("Feature", Feature, is_collection=True)
        
        assert len(features) == 3
        assert features[0].name == "feature1"
        assert features[0].enabled is True
        assert features[1].name == "feature2"
        assert features[1].enabled is False  # from_dict default
        assert features[2].name == "unknown"  # from_dict default
        assert features[2].enabled is False


class TestConfigModelInjection:
    """Test dependency injection with collection models."""
    
    def test_inject_collection_model(self):
        """Test injecting a collection of models."""
        config_data = {
            "Worker": [
                {"id": 1, "queue": "default"},
                {"id": 2, "queue": "priority", "concurrency": 5},
                {"id": 3, "queue": "background", "concurrency": 2},
            ]
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        
        config = Config(config_data)
        container.add(config)
        
        # Test direct injection
        workers = container.get(list[Worker])
        
        assert len(workers) == 3
        assert all(isinstance(w, Worker) for w in workers)
        assert workers[0].id == 1
        assert workers[0].queue == "default"
        assert workers[0].concurrency == 1  # default
        assert workers[1].concurrency == 5
        assert workers[2].queue == "background"
    
    def test_inject_single_non_collection_model(self):
        """Test that single models still work correctly."""
        config_data = {
            "Database": {
                "name": "test_db",
                "connection_string": "sqlite:///test.db"
            }
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        
        config = Config(config_data)
        container.add(config)
        
        # Test direct injection of single model
        db = container.get(Database)
        
        assert isinstance(db, Database)
        assert db.name == "test_db"
        assert db.connection_string == "sqlite:///test.db"
    
    def test_collection_mismatch_error_expects_list_gets_single(self):
        """Test error when expecting list but model is not a collection."""
        config_data = {
            "Database": {
                "name": "test_db",
                "connection_string": "sqlite:///test.db"
            }
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        
        config = Config(config_data)
        container.add(config)
        
        # Try to inject as list when it's not a collection
        with pytest.raises(ValueError, match="expects a collection"):
            container.get(list[Database])
    
    def test_collection_mismatch_error_expects_single_gets_list(self):
        """Test error when expecting single but model is a collection."""
        config_data = {
            "Server": [
                {"host": "server1.example.com", "port": 8080},
            ]
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        
        config = Config(config_data)
        container.add(config)
        
        # Try to inject as single when it's a collection
        with pytest.raises(ValueError, match="is a collection.*expects a singular"):
            container.get(Server)
    
    def test_collection_model_with_custom_key(self):
        """Test collection model with custom model_key."""
        class Service(ConfigModel, model_key="services", is_collection=True):
            def __init__(self, name: str, url: str):
                self.name = name
                self.url = url
        
        config_data = {
            "services": [
                {"name": "api", "url": "http://api.example.com"},
                {"name": "web", "url": "http://web.example.com"},
            ]
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        
        config = Config(config_data)
        container.add(config)
        
        services = container.get(list[Service])
        
        assert len(services) == 2
        assert services[0].name == "api"
        assert services[1].url == "http://web.example.com"
    
    def test_multiple_collections_in_config(self):
        """Test handling multiple different collections in the same config."""
        config_data = {
            "Server": [
                {"host": "server1.example.com", "port": 8080},
                {"host": "server2.example.com", "port": 8081},
            ],
            "Worker": [
                {"id": 1, "queue": "default"},
                {"id": 2, "queue": "priority"},
            ],
            "Database": {
                "name": "main",
                "connection_string": "postgresql://localhost/db"
            }
        }
        
        registry = Registry()
        handle_model_types.register_hook(registry)
        container = registry.create_container()
        
        config = Config(config_data)
        container.add(config)
        
        # Get all different types
        servers = container.get(list[Server])
        workers = container.get(list[Worker])
        db = container.get(Database)
        
        assert len(servers) == 2
        assert len(workers) == 2
        assert isinstance(db, Database)
        assert servers[0].host == "server1.example.com"
        assert workers[1].queue == "priority"
        assert db.name == "main"


class TestConfigCollectionIntegration:
    """Integration tests for collection support."""
    
    def test_load_collection_from_yaml(self):
        """Test loading collections from YAML files."""
        yaml_content = """
Server:
  - host: prod1.example.com
    port: 443
    enabled: true
  - host: prod2.example.com
    port: 443
    enabled: true
  - host: staging.example.com
    port: 8443
    enabled: false

Worker:
  - id: 1
    queue: emails
    concurrency: 10
  - id: 2
    queue: reports
    concurrency: 3
  - id: 3
    queue: background

Database:
  name: production
  connection_string: postgresql://prod.db.example.com/app
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(yaml_content)
            
            config = Config.load_config("config.yaml", tmpdir)
            
            # Test getting collections
            servers = config.get("Server", Server, is_collection=True)
            workers = config.get("Worker", Worker, is_collection=True)
            db = config.get("Database", Database, is_collection=False)
            
            assert len(servers) == 3
            assert servers[0].port == 443
            assert servers[2].enabled is False
            
            assert len(workers) == 3
            assert workers[0].queue == "emails"
            assert workers[2].concurrency == 1  # default
            
            assert db.name == "production"
    
    def test_complex_nested_collections(self):
        """Test complex nested structures with collections."""
        yaml_content = """
Feature:
  - name: authentication
    enabled: true
  - name: notifications
    enabled: true
  - name: beta_features
    enabled: false

Server:
  - host: lb1.example.com
    port: 80
  - host: lb2.example.com
    port: 80
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "complex.yaml"
            config_file.write_text(yaml_content)
            
            config = Config.load_config("complex.yaml", tmpdir)
            
            features = config.get("Feature", Feature, is_collection=True)
            servers = config.get("Server", Server, is_collection=True)
            
            assert len(features) == 3
            assert sum(f.enabled for f in features) == 2  # 2 enabled features
            
            assert len(servers) == 2
            assert all(s.port == 80 for s in servers)