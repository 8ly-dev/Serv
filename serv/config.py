from types import ModuleType
import yaml
import importlib
import inspect
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar, Union, Type, TypedDict
import logging

from bevy import dependency # For potential use in middleware factories

logger = logging.getLogger(__name__)

# Default config file name
DEFAULT_CONFIG_FILE = "serv.config.yaml"

T = TypeVar('T')
ImportCallable = Callable[..., Any]

class PluginConfig(TypedDict, total=False):
    entry: str
    config: Dict[str, Any]

class MiddlewareConfig(TypedDict, total=False):
    entry: str
    config: Dict[str, Any]

class ServConfig(TypedDict, total=False):
    site_info: Dict[str, Any]
    plugins: list[PluginConfig]
    middleware: list[MiddlewareConfig]
    
class ServConfigError(Exception):
    """Custom exception for configuration errors."""
    pass

def import_from_string(import_str: str) -> Any:
    """
    Import a class, function, or variable from a module by string.
    
    Args:
        import_str: String in the format "module.path:symbol"
        
    Returns:
        The imported object
        
    Raises:
        ServConfigError: If the import failed.
    """
    if ":" not in import_str:
        raise ServConfigError(f"Invalid import string format '{import_str}'. Expected 'module.path:symbol'.")
        
    module_path, object_path = import_str.split(":", 1)
    
    try:
        module = importlib.import_module(module_path)
        
        # Handle nested attributes
        target = module
        for part in object_path.split('.'):
            target = getattr(target, part)
            
        return target
    except (ImportError, AttributeError) as e:
        raise ServConfigError(f"Failed to import '{import_str}': {str(e)}") from e

def import_module_from_string(module_path: str) -> Any:
    """
    Import a module by string.
    
    Args:
        module_path: String representing the module path (e.g., "serv.app")
        
    Returns:
        The imported module
        
    Raises:
        ServConfigError: If the import failed.
    """
    try:
        return importlib.import_module(module_path)
    except ImportError as e:
        raise ServConfigError(f"Failed to import module '{module_path}': {str(e)}") from e

def load_raw_config(config_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load a configuration file.
    
    Args:
        config_path: Path to the configuration file.
        
    Returns:
        Dictionary containing the configuration.
        
    Raises:
        ServConfigError: If the configuration file could not be loaded.
    """
    try:
        config_path_obj = Path(config_path)
        if not config_path_obj.exists():
            return {}
            
        with open(config_path_obj, 'r') as f:
            config = yaml.safe_load(f)
            
        if config is None:  # Empty file
            config = {}
            
        if not isinstance(config, dict):
            raise ServConfigError(f"Invalid configuration format in {config_path}. Expected a dictionary.")
            
        return config
    except Exception as e:
        if isinstance(e, ServConfigError):
            raise
        raise ServConfigError(f"Error loading configuration from {config_path}: {str(e)}") from e
