import yaml
import importlib
import inspect
import os
from pathlib import Path
from typing import Any, Callable

from serv.app import App
from bevy import dependency # For potential use in middleware factories

# Default config file name
DEFAULT_CONFIG_FILE = "serv.config.yaml"

class ServConfigError(Exception):
    """Custom exception for configuration errors."""
    pass

def import_from_string(import_string: str) -> Callable[..., Any]:
    """
    Imports a callable (class or function) from an import string like "module.path:ObjectName".
    """
    try:
        module_path, object_name = import_string.rsplit(":", 1)
    except ValueError:
        raise ServConfigError(
            f"Invalid import string format '{import_string}'. Expected 'module.path:ObjectName'."
        )
    
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise ServConfigError(f"Could not import module '{module_path}' from '{import_string}'. Error: {e}")
    
    try:
        obj = getattr(module, object_name)
        if not callable(obj):
            raise ServConfigError(f"Imported object '{object_name}' from '{import_string}' is not callable.")
        return obj
    except AttributeError:
        raise ServConfigError(f"Object '{object_name}' not found in module '{module_path}' from '{import_string}'.")

def load_raw_config(config_path_str: str | Path | None = None) -> dict:
    """
    Loads the raw configuration from a YAML file.
    Tries SERV_CONFIG_PATH env var, then provided path, then default path relative to CWD.
    """
    config_to_try = config_path_str or os.getenv("SERV_CONFIG_PATH") or DEFAULT_CONFIG_FILE
    config_file_path = Path(config_to_try).resolve()

    if not config_file_path.exists():
        if str(config_file_path).endswith(DEFAULT_CONFIG_FILE) and config_to_try == DEFAULT_CONFIG_FILE:
             print(f"INFO: Default config file {DEFAULT_CONFIG_FILE!r} not found. Proceeding without it.")
             return {}
        raise ServConfigError(f"Configuration file not found: {config_file_path}")

    try:
        with open(config_file_path, 'r') as f:
            raw_config_data = yaml.safe_load(f)
        if not isinstance(raw_config_data, dict):
            raise ServConfigError(f"Configuration file '{config_file_path}' content is not a valid YAML mapping (dictionary).")
        print(f"INFO: Loaded configuration from '{config_file_path}'")
        return raw_config_data
    except yaml.YAMLError as e:
        raise ServConfigError(f"Error parsing YAML configuration file '{config_file_path}': {e}")
    except Exception as e:
        raise ServConfigError(f"Error loading configuration file '{config_file_path}': {e}")


def setup_app_from_config(app: App, raw_config: dict):
    """
    Configures the given App instance with plugins and middleware from the loaded config.
    """
    for plugin_entry in raw_config.get("plugins", []):
        if not isinstance(plugin_entry, dict) or "import" not in plugin_entry:
            raise ServConfigError(f"Invalid plugin entry: {plugin_entry}. Must be a dict with an 'import' key.")
        
        import_str = plugin_entry["import"]
        config_params = plugin_entry.get("config", {})
        if not isinstance(config_params, dict):
            raise ServConfigError(f"Plugin '{import_str}' config must be a dictionary.")

        plugin_callable = import_from_string(import_str)
        
        try:
            if inspect.isclass(plugin_callable):
                plugin_instance = plugin_callable(**config_params)
            else:
                plugin_instance = plugin_callable(**config_params)
            
            app.add_plugin(plugin_instance)
            print(f"INFO: Loaded plugin '{import_str}' with config {config_params}")
        except Exception as e:
            # Using str() for e and config_params to avoid complex f-string issues with repr.
            raise ServConfigError(f"Error loading plugin {import_str!r}: {str(e)!r}. Parameters: {str(config_params)}")

    for middleware_entry in raw_config.get("middleware", []):
        if not isinstance(middleware_entry, dict) or "import" not in middleware_entry:
            raise ServConfigError(f"Invalid middleware entry: {middleware_entry}. Must be a dict with an 'import' key.")

        import_str = middleware_entry["import"]
        config_params = middleware_entry.get("config", {})
        if not isinstance(config_params, dict):
            raise ServConfigError(f"Middleware {import_str!r} config must be a dictionary.")
            
        middleware_meta_factory = import_from_string(import_str)
        
        try:
            actual_middleware_factory = middleware_meta_factory(**config_params)
            app.add_middleware(actual_middleware_factory)
            print(f"INFO: Loaded middleware '{import_str}' with config {config_params}")
        except Exception as e:
            raise ServConfigError(f"Error loading middleware {import_str!r}: {str(e)!r}. Parameters: {str(config_params)}")

    site_info = raw_config.get("site_info", {})
    if site_info:
        print(f"INFO: Site info loaded: {str(site_info)}")

    return app 