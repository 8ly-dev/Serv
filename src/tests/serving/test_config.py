import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest
import yaml

from serving.config import Config


@dataclass
class DatabaseConfig:
    host: str
    port: int
    username: str
    password: str
    database: str


@dataclass
class ServerConfig:
    host: str
    port: int
    debug: bool = False
    workers: int = 1


@dataclass
class LoggingConfig:
    level: str
    format: str
    file: Optional[str] = None


@dataclass
class AppConfig:
    name: str
    version: str
    environment: str
    features: list[str]
    settings: dict[str, any]


class TestConfig:
    def test_init(self):
        config_dict = {"key": "value", "nested": {"key2": "value2"}}
        config = Config(config_dict)
        assert config.config == config_dict

    def test_get_simple_value(self):
        config_dict = {"key": "value", "number": 42}
        config = Config(config_dict)
        assert config.get("key") == "value"
        assert config.get("number") == 42

    def test_get_nested_dict(self):
        config_dict = {
            "database": {"host": "localhost", "port": 5432},
            "server": {"host": "0.0.0.0", "port": 8000},
        }
        config = Config(config_dict)
        assert config.get("database") == {"host": "localhost", "port": 5432}
        assert config.get("server") == {"host": "0.0.0.0", "port": 8000}

    def test_get_with_dataclass_model(self):
        config_dict = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "username": "admin",
                "password": "secret",
                "database": "mydb",
            }
        }
        config = Config(config_dict)
        db_config = config.get("database", DatabaseConfig)
        
        assert isinstance(db_config, DatabaseConfig)
        assert db_config.host == "localhost"
        assert db_config.port == 5432
        assert db_config.username == "admin"
        assert db_config.password == "secret"
        assert db_config.database == "mydb"

    def test_get_with_multiple_dataclass_models(self):
        config_dict = {
            "database": {
                "host": "db.example.com",
                "port": 3306,
                "username": "root",
                "password": "password123",
                "database": "production",
            },
            "server": {"host": "0.0.0.0", "port": 8080, "debug": True, "workers": 4},
            "logging": {"level": "INFO", "format": "json", "file": "/var/log/app.log"},
        }
        config = Config(config_dict)
        
        db_config = config.get("database", DatabaseConfig)
        assert db_config.host == "db.example.com"
        assert db_config.port == 3306
        
        server_config = config.get("server", ServerConfig)
        assert server_config.host == "0.0.0.0"
        assert server_config.port == 8080
        assert server_config.debug is True
        assert server_config.workers == 4
        
        log_config = config.get("logging", LoggingConfig)
        assert log_config.level == "INFO"
        assert log_config.format == "json"
        assert log_config.file == "/var/log/app.log"

    def test_get_with_dataclass_default_values(self):
        config_dict = {"server": {"host": "localhost", "port": 3000}}
        config = Config(config_dict)
        server_config = config.get("server", ServerConfig)
        
        assert server_config.host == "localhost"
        assert server_config.port == 3000
        assert server_config.debug is False
        assert server_config.workers == 1

    def test_get_with_complex_dataclass(self):
        config_dict = {
            "app": {
                "name": "MyApp",
                "version": "1.2.3",
                "environment": "production",
                "features": ["auth", "api", "websocket"],
                "settings": {"timeout": 30, "max_connections": 100},
            }
        }
        config = Config(config_dict)
        app_config = config.get("app", AppConfig)
        
        assert app_config.name == "MyApp"
        assert app_config.version == "1.2.3"
        assert app_config.environment == "production"
        assert app_config.features == ["auth", "api", "websocket"]
        assert app_config.settings == {"timeout": 30, "max_connections": 100}

    def test_get_missing_key(self):
        config = Config({"key": "value"})
        with pytest.raises(KeyError):
            config.get("nonexistent")

    def test_get_with_invalid_model_params(self):
        config_dict = {"database": {"host": "localhost"}}
        config = Config(config_dict)
        
        with pytest.raises(TypeError):
            config.get("database", DatabaseConfig)

    def test_load_config_from_yaml(self):
        yaml_content = """
database:
  host: localhost
  port: 5432
  username: testuser
  password: testpass
  database: testdb
server:
  host: 0.0.0.0
  port: 8000
  debug: false
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(yaml_content)
            
            config = Config.load_config("config.yaml", tmpdir)
            
            assert config.get("database")["host"] == "localhost"
            assert config.get("server")["port"] == 8000
            
            db_config = config.get("database", DatabaseConfig)
            assert db_config.username == "testuser"

    def test_load_config_current_directory(self):
        yaml_content = """
test:
  value: 123
  enabled: true
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test.yaml"
            config_file.write_text(yaml_content)
            
            original_cwd = Path.cwd()
            try:
                import os
                os.chdir(tmpdir)
                config = Config.load_config("test.yaml")
                assert config.get("test")["value"] == 123
                assert config.get("test")["enabled"] is True
            finally:
                os.chdir(original_cwd)

    def test_load_config_with_path_object(self):
        yaml_content = """
app:
  name: TestApp
  version: 0.1.0
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            config_file = tmppath / "app.yaml"
            config_file.write_text(yaml_content)
            
            config = Config.load_config("app.yaml", tmppath)
            assert config.get("app")["name"] == "TestApp"
            assert config.get("app")["version"] == "0.1.0"

    def test_load_config_invalid_directory(self):
        with pytest.raises(ValueError, match="Invalid directory"):
            Config.load_config("config.yaml", 123)

    def test_load_config_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError):
                Config.load_config("nonexistent.yaml", tmpdir)

    def test_load_config_with_complex_yaml(self):
        yaml_content = """
database:
  host: db.prod.example.com
  port: 5432
  username: admin
  password: supersecret
  database: production
  
server:
  host: 0.0.0.0
  port: 443
  debug: false
  workers: 8
  
logging:
  level: WARNING
  format: json
  
features:
  - authentication
  - api_v2
  - websockets
  - caching
  
environments:
  development:
    debug: true
    database: dev_db
  staging:
    debug: false
    database: staging_db
  production:
    debug: false
    database: prod_db
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "complex.yaml"
            config_file.write_text(yaml_content)
            
            config = Config.load_config("complex.yaml", tmpdir)
            
            db_config = config.get("database", DatabaseConfig)
            assert db_config.host == "db.prod.example.com"
            assert db_config.database == "production"
            
            server_config = config.get("server", ServerConfig)
            assert server_config.workers == 8
            assert server_config.port == 443
            
            features = config.get("features")
            assert "authentication" in features
            assert len(features) == 4
            
            environments = config.get("environments")
            assert environments["development"]["debug"] is True
            assert environments["production"]["database"] == "prod_db"

    def test_empty_yaml_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "empty.yaml"
            config_file.write_text("")
            
            config = Config.load_config("empty.yaml", tmpdir)
            assert config.config is None or config.config == {}

    def test_yaml_with_anchors_and_aliases(self):
        yaml_content = """
defaults: &defaults
  host: localhost
  port: 5432
  
development:
  <<: *defaults
  database: dev_db
  
production:
  <<: *defaults
  host: db.prod.com
  database: prod_db
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "anchors.yaml"
            config_file.write_text(yaml_content)
            
            config = Config.load_config("anchors.yaml", tmpdir)
            
            dev = config.get("development")
            assert dev["host"] == "localhost"
            assert dev["port"] == 5432
            assert dev["database"] == "dev_db"
            
            prod = config.get("production")
            assert prod["host"] == "db.prod.com"
            assert prod["port"] == 5432
            assert prod["database"] == "prod_db"