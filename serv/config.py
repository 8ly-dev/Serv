from types import ModuleType
import yaml
import importlib
import inspect
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar, Union, Type, TypedDict
import logging

from serv.app import App
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

def setup_app_from_config(app: Any, config: Dict[str, Any]) -> None:
    """
    Set up a Serv application from a configuration dictionary.
    
    Args:
        app: The Serv application instance to configure.
        config: Configuration dictionary.
        
    Raises:
        ServConfigError: If there was an error applying the configuration.
    """
    # Set site info
    if "site_info" in config and isinstance(config["site_info"], dict):
        app.site_info = config["site_info"]
    else:
        app.site_info = {}
        
    # Configure plugins
    if "plugins" in config and isinstance(config["plugins"], list):
        for i, plugin_entry in enumerate(config["plugins"]):
            if not isinstance(plugin_entry, dict) or "entry" not in plugin_entry:
                logger.warning(f"Invalid plugin entry at index {i}: {plugin_entry}")
                continue
                
            plugin_path = plugin_entry["entry"]
            plugin_config = plugin_entry.get("config", {})
            
            try:
                # Check if it's a namespace import (from our loader)
                if "." in plugin_path and ":" in plugin_path:
                    module_path, class_name = plugin_path.split(":", 1)
                    
                    # Extract namespace and package name
                    parts = module_path.split(".")
                    if len(parts) >= 2:
                        namespace = parts[0]
                        package_name = parts[1]
                        
                        # Try to load via loader first
                        if hasattr(app, "_loader"):
                            module = app._loader.load_package("plugin", package_name, namespace)
                            if module:
                                # Import the plugin class
                                if hasattr(module, class_name):
                                    plugin_class = getattr(module, class_name)
                                    plugin_instance = plugin_class()
                                    if plugin_config:
                                        if hasattr(plugin_instance, "configure"):
                                            plugin_instance.configure(plugin_config)
                                        # Also set as attributes for backward compatibility
                                        for k, v in plugin_config.items():
                                            setattr(plugin_instance, k, v)
                                    app.add_plugin(plugin_instance)
                                    logger.info(f"Loaded plugin {plugin_path}")
                                    continue
                
                # Fall back to regular import if loader didn't work
                plugin_class = import_from_string(plugin_path)
                if not isinstance(plugin_class, type):
                    # It's an instance, not a class
                    plugin_instance = plugin_class
                else:
                    # It's a class, instantiate it
                    plugin_instance = plugin_class()
                    
                # Apply configuration
                if plugin_config:
                    if hasattr(plugin_instance, "configure"):
                        plugin_instance.configure(plugin_config)
                    # Also set as attributes for backward compatibility
                    for k, v in plugin_config.items():
                        setattr(plugin_instance, k, v)
                        
                app.add_plugin(plugin_instance)
                logger.info(f"Loaded plugin {plugin_path}")
            except Exception as e:
                logger.error(f"Error loading plugin {plugin_path}: {e}")
                
    # Configure middleware
    if "middleware" in config and isinstance(config["middleware"], list):
        for i, mw_entry in enumerate(config["middleware"]):
            if not isinstance(mw_entry, dict) or "entry" not in mw_entry:
                logger.warning(f"Invalid middleware entry at index {i}: {mw_entry}")
                continue
                
            mw_path = mw_entry["entry"]
            mw_config = mw_entry.get("config", {})
            
            try:
                # Check if it's a namespace import (from our loader)
                if "." in mw_path and ":" in mw_path:
                    module_path, factory_name = mw_path.split(":", 1)
                    
                    # Extract namespace and package name
                    parts = module_path.split(".")
                    if len(parts) >= 2:
                        namespace = parts[0]
                        package_name = parts[1]
                        
                        # Try to load via loader first
                        if hasattr(app, "_loader"):
                            module = app._loader.load_package("middleware", package_name, namespace)
                            if module:
                                # Import the middleware factory function
                                if hasattr(module, factory_name):
                                    factory = getattr(module, factory_name)
                                    if mw_config:
                                        # If the factory accepts config, pass it
                                        # Otherwise set it as globals
                                        if callable(factory):
                                            import inspect
                                            sig = inspect.signature(factory)
                                            if "config" in sig.parameters:
                                                factory_with_config = lambda: factory(config=mw_config)
                                                app.add_middleware(factory_with_config)
                                                logger.info(f"Loaded middleware {mw_path} with config")
                                                continue
                                    # No config or factory doesn't accept config
                                    app.add_middleware(factory)
                                    logger.info(f"Loaded middleware {mw_path}")
                                    continue
                
                # Fall back to regular import if loader didn't work
                mw_factory = import_from_string(mw_path)
                if not callable(mw_factory):
                    logger.warning(f"Middleware {mw_path} is not callable")
                    continue
                    
                # Apply configuration
                if mw_config:
                    # If the factory accepts config, pass it
                    import inspect
                    sig = inspect.signature(mw_factory)
                    if "config" in sig.parameters:
                        factory_with_config = lambda: mw_factory(config=mw_config)
                        app.add_middleware(factory_with_config)
                        logger.info(f"Loaded middleware {mw_path} with config")
                        continue
                        
                app.add_middleware(mw_factory)
                logger.info(f"Loaded middleware {mw_path}")
            except Exception as e:
                logger.error(f"Error loading middleware {mw_path}: {e}") 