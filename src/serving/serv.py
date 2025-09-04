import os
from pathlib import Path

from bevy.registries import Registry
from starlette.applications import Starlette

from serving.config import Config, handle_model_types


class ConfigurationError(Exception):
    """Raised when configuration cannot be loaded."""
    pass


class Serv:
    def __init__(
        self,
        config_path: str | Path | None = None,
        environment: str | None = None,
    ):
        """Initialize Serv application with configuration and dependency injection.
        
        Args:
            config_path: Path to config file. Can be:
                - str: Path to config file
                - Path: Path object to config file
                - None: Auto-detect based on environment (serv.{env}.yaml)
            environment: Environment name (e.g., 'dev', 'prod'). If not provided,
                        uses SERV_ENVIRONMENT env var, defaulting to 'prod'
        
        Raises:
            ConfigurationError: When config file cannot be found or loaded
        """
        self.app = Starlette()
        self.registry = Registry()
        
        # Register the config model handler
        handle_model_types.register_hook(self.registry)
        
        self.container = self.registry.create_container()
        
        # Determine environment
        if environment is None:
            environment = os.environ.get("SERV_ENVIRONMENT", "prod")
        self.environment = environment
        
        # Load configuration (will raise if not found)
        self._load_configuration(config_path)
    
    def _load_configuration(self, config_path: str | Path | None) -> None:
        """Load configuration from the specified path or auto-detect based on environment.
        
        Raises:
            ConfigurationError: When config file cannot be found or loaded
        """
        if config_path is None:
            # Auto-detect config file based on environment
            config_filename = f"serv.{self.environment}.yaml"
            config_path = Path.cwd() / config_filename
            
            if not config_path.exists():
                raise ConfigurationError(
                    f"Configuration file '{config_filename}' not found in {Path.cwd()}. "
                    f"Please create '{config_filename}' or specify an explicit config_path."
                )
        else:
            # Convert string to Path if necessary
            if isinstance(config_path, str):
                config_path = Path(config_path)
            
            # Check if file exists
            if not config_path.exists():
                raise ConfigurationError(
                    f"Configuration file '{config_path}' not found. "
                    f"Please ensure the file exists or provide a valid path."
                )
        
        # Load the configuration
        try:
            self.config = Config.load_config(config_path.name, str(config_path.parent))
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load configuration from '{config_path}': {e}"
            ) from e
        
        # Add Config to container for dependency injection
        self.container.add(self.config)