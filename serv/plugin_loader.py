import logging
from typing import Any, Callable, AsyncIterator
from pathlib import Path
import inspect

from serv.loader import ServLoader
from serv.plugins import Plugin
from serv.middleware import ServMiddleware

logger = logging.getLogger(__name__)

class PluginLoader:
    """Handles loading and management of plugins and middleware."""
    
    def __init__(self, plugin_loader: ServLoader):
        """Initialize the PluginLoader.
        
        Args:
            plugin_loader: ServLoader instance for loading plugin packages
        """
        self._plugin_loader = plugin_loader
        
    def load_plugins(self, plugins_config: list[dict[str, Any]]) -> tuple[dict[Path, list[Plugin]], list[Callable[[], AsyncIterator[None]]]]:
        """Load plugins from a list of plugin configs.

        Args:
            plugins_config: List of plugin configs (usually from serv.config.yaml)
            
        Returns:
            Tuple of (loaded_plugins dict, middleware_list)
            
        Raises:
            ExceptionGroup: If any errors occurred during loading
        """
        exceptions = []
        loaded_plugins_count = 0
        loaded_middleware_count = 0
        loaded_plugins = {}
        middleware_list = []

        for plugin_spec in plugins_config:
            plugin_name = plugin_spec.get("name", "Unknown Plugin")
            # Load plugin entry points
            if "entry points" in plugin_spec:
                try:
                    if not isinstance(plugin_spec["entry points"], list):
                        raise TypeError(f"'entry points' must be a list for plugin '{plugin_name}', got {type(plugin_spec['entry points']).__name__}")
                    
                    for entry_point_config in plugin_spec["entry points"]:
                        try:
                            plugin_instance = self._load_plugin_entry_point(entry_point_config)
                            # Store the loaded plugin
                            if plugin_instance.plugin_dir not in loaded_plugins:
                                loaded_plugins[plugin_instance.plugin_dir] = []
                            loaded_plugins[plugin_instance.plugin_dir].append(plugin_instance)
                            loaded_plugins_count += 1
                            # Safely get entry string for logging
                            entry_str = entry_point_config.get('entry') if isinstance(entry_point_config, dict) else str(entry_point_config)
                            logger.info(f"Loaded plugin entry point for {plugin_name} from {entry_str}")
                        except Exception as e:
                            # Safely get entry string for error logging
                            entry_str = entry_point_config.get('entry') if isinstance(entry_point_config, dict) else str(entry_point_config)
                            logger.warning(f"Failed to load plugin entry point for {plugin_name} from {entry_str}")
                            e.add_note(f" - Plugin: {plugin_name}")
                            e.add_note(f" - Entry point config: {entry_point_config}")
                            exceptions.append(e)
                except TypeError as e:
                    logger.warning(f"Invalid entry points configuration for plugin {plugin_name}: {e}")
                    exceptions.append(e)

            # Load middleware from plugin
            if "middleware" in plugin_spec:
                try:
                    if not isinstance(plugin_spec["middleware"], list):
                        raise TypeError(f"'middleware' must be a list for plugin '{plugin_name}', got {type(plugin_spec['middleware']).__name__}")
                    
                    for middleware_config_entry in plugin_spec["middleware"]:
                        try:
                            middleware_factory = self._load_middleware_entry_point(middleware_config_entry)
                            middleware_list.append(middleware_factory)
                            loaded_middleware_count += 1
                            # Safely get entry string for logging
                            entry_str = middleware_config_entry.get('entry') if isinstance(middleware_config_entry, dict) else str(middleware_config_entry)
                            logger.info(f"Loaded middleware for {plugin_name} from {entry_str}")
                        except Exception as e:
                            # Safely get entry string for error logging
                            entry_str = middleware_config_entry.get('entry') if isinstance(middleware_config_entry, dict) else str(middleware_config_entry)
                            logger.warning(f"Failed to load middleware for {plugin_name} from {entry_str}")
                            e.add_note(f" - Plugin: {plugin_name}")
                            e.add_note(f" - Middleware config: {middleware_config_entry}")
                            exceptions.append(e)
                except TypeError as e:
                    logger.warning(f"Invalid middleware configuration for plugin {plugin_name}: {e}")
                    exceptions.append(e)

        # Log empty entry points and middleware cases
        for plugin_spec in plugins_config:
            plugin_name = plugin_spec.get("name", "Unknown Plugin")
            if "entry points" in plugin_spec and not plugin_spec["entry points"]:
                logger.info(f"Plugin {plugin_name} has empty 'entry points' list")
            if "middleware" in plugin_spec and not plugin_spec["middleware"]:
                logger.info(f"Plugin {plugin_name} has empty 'middleware' list")
            if "entry points" not in plugin_spec and "middleware" not in plugin_spec:
                logger.info(f"Plugin {plugin_name} has no 'entry points' or 'middleware' sections")

        logger.info(f"Loaded {loaded_plugins_count} plugin entry points and {loaded_middleware_count} middleware entries.")
        if exceptions:
            logger.warning(f"Encountered {len(exceptions)} errors during plugin and middleware loading.")
            raise ExceptionGroup("Exceptions raised while loading plugins and middleware", exceptions)
            
        return loaded_plugins, middleware_list

    def _load_plugin_entry_point(self, entry_point_config: dict[str, Any]) -> Plugin:
        """Load a plugin from an entry point configuration.
        
        Args:
            entry_point_config: Configuration dictionary for the entry point
            
        Returns:
            Instantiated Plugin object
            
        Raises:
            ValueError: If entry point config is invalid
            ImportError: If plugin module or class cannot be imported
        """
        if not isinstance(entry_point_config, dict):
            raise ValueError(f"Invalid plugin entry point config: {entry_point_config!r}")

        entry = entry_point_config.get("entry")
        if not entry:
            raise ValueError(f"Plugin entry point config missing 'entry': {entry_point_config!r}")

        if ":" not in entry:
            raise ValueError(f"Invalid plugin entry point, must use format 'module.path:ClassName': {entry!r}")

        module_path, class_name = entry.split(":", 1)
        plugin_module = self._plugin_loader.load_package(module_path)
        if not plugin_module:
            raise ImportError(f"Failed to load plugin module: {module_path!r}")

        plugin_class = getattr(plugin_module, class_name, None)
        if not plugin_class:
            raise ImportError(f"Failed to import plugin class {class_name!r} from {module_path!r}")

        if not issubclass(plugin_class, Plugin):
            raise ValueError(f"Plugin class {class_name!r} does not inherit from {Plugin.__name__!r}")
        
        plugin_config = entry_point_config.get("config", {})
        try:
            return plugin_class(config=plugin_config) if plugin_config else plugin_class()
        except TypeError as e:
            # Check if the error is due to an unexpected keyword argument 'config'
            # This is a bit fragile as it depends on the error message string.
            if "unexpected keyword argument 'config'" in str(e) or \
               (hasattr(e, "name") and e.name == "config" and "got an unexpected keyword argument" in str(e)): # More robust for some Python versions
                logger.debug(f"Plugin {class_name} constructor does not accept 'config'. Instantiating without it.")
                return plugin_class()
            raise # re-raise if it's a different TypeError

    def _load_middleware_entry_point(self, middleware_config: dict[str, Any]) -> Callable[[], AsyncIterator[None]]:
        """Load middleware from an entry point configuration.
        
        Args:
            middleware_config: Configuration dictionary for the middleware
            
        Returns:
            Middleware factory function
            
        Raises:
            ValueError: If middleware config is invalid
            ImportError: If middleware module or class cannot be imported
        """
        if not isinstance(middleware_config, dict):
            raise ValueError(f"Invalid middleware config: {middleware_config!r}")

        entry = middleware_config.get("entry")
        if not entry:
            raise ValueError(f"Middleware config missing 'entry': {middleware_config!r}")

        if ":" not in entry:
            raise ValueError(f"Invalid middleware entry, must use format 'module.path:ClassNameOrFactory': {entry!r}")

        module_path, object_name = entry.split(":", 1)
        middleware_module = self._plugin_loader.load_package(module_path)
        if not middleware_module:
            raise ImportError(f"Failed to load middleware module: {module_path!r}")

        middleware_obj = getattr(middleware_module, object_name, None)
        if not middleware_obj:
            raise ImportError(f"Failed to import middleware {object_name!r} from {module_path!r}")

        mw_config = middleware_config.get("config", {})

        if inspect.isclass(middleware_obj) and issubclass(middleware_obj, ServMiddleware):
            def factory(): # This factory will be stored and called by the app
                return middleware_obj(config=mw_config)
            return factory
        elif callable(middleware_obj):
            # For raw callables (like async generator functions or factories that don't take config directly via constructor)
            # we pass it as is. Config handling would need to be internal to the factory or through other means.
            if mw_config:
                logger.warning(
                    f"Middleware {object_name} from {module_path} is a direct callable/factory; "
                    f"'config' provided in plugin spec may not be automatically passed to its instantiation by Serv. "
                    f"Ensure the factory handles its own configuration if needed, or use a ServMiddleware subclass."
                )
            return middleware_obj 
        else:
            raise ValueError(f"Middleware entry {object_name!r} from {module_path!r} is not a ServMiddleware subclass or a callable factory.")

    def load_plugin(self, package_name: str, namespace: str = None) -> tuple[bool, Plugin | None]:
        """Load a plugin from the plugin directories.
        
        Args:
            package_name: Name of the plugin package to load
            namespace: Optional namespace to look in (defaults to first found)
            
        Returns:
            Tuple of (success_bool, plugin_instance or None)
        """
        plugin_module = self._plugin_loader.load_package("plugin", package_name, namespace)
        if not plugin_module:
            logger.warning(f"Failed to load plugin {package_name}")
            return False, None
            
        # First, try to find the class by looking for a name in plugin.yaml
        plugin_dir = None
        for search_path in self._plugin_loader.get_search_paths("plugin"):
            if namespace and search_path.name != namespace:
                continue
                
            potential_dir = search_path / package_name
            if potential_dir.exists() and (potential_dir / "plugin.yaml").exists():
                plugin_dir = potential_dir
                break
                
        if plugin_dir and (plugin_dir / "plugin.yaml").exists():
            try:
                import yaml
                with open(plugin_dir / "plugin.yaml", 'r') as f:
                    plugin_yaml = yaml.safe_load(f)
                    
                if plugin_yaml and "entry" in plugin_yaml:
                    entry = plugin_yaml["entry"]
                    if ":" in entry:
                        module_path, class_name = entry.split(":", 1)
                        # If this is a module.class format, extract just the class name
                        class_name = class_name.split(".")[-1]
                        
                        # Check if this class exists in the module we loaded
                        if hasattr(plugin_module, class_name):
                            plugin_class = getattr(plugin_module, class_name)
                            if isinstance(plugin_class, type) and issubclass(plugin_class, Plugin):
                                plugin_instance = plugin_class()
                                logger.info(f"Loaded plugin {package_name} ({class_name})")
                                return True, plugin_instance
            except Exception as e:
                logger.warning(f"Error loading plugin from plugin.yaml: {e}")
                
        logger.warning(f"Could not find Plugin subclass in {package_name}")
        return False, None
        
    def load_middleware_from_package(self, package_name: str, namespace: str = None) -> tuple[bool, Callable[[], AsyncIterator[None]] | None]:
        """Load middleware from the middleware directories.
        
        Args:
            package_name: Name of the middleware package to load
            namespace: Optional namespace to look in (defaults to first found)
            
        Returns:
            Tuple of (success_bool, middleware_factory or None)
        """
        middleware_module = self._plugin_loader.load_package("middleware", package_name, namespace)
        if not middleware_module:
            logger.warning(f"Failed to load middleware {package_name}")
            return False, None
        
        # First try to find something that ends with _middleware
        for attr_name in dir(middleware_module):
            attr = getattr(middleware_module, attr_name)
            if callable(attr) and attr_name.endswith('_middleware'):
                logger.info(f"Loaded middleware {package_name}.{attr_name}")
                return True, attr
                
        # Try to find any callable that looks like a middleware factory
        for attr_name in dir(middleware_module):
            attr = getattr(middleware_module, attr_name)
            if callable(attr) and not attr_name.startswith('_'):
                try:
                    # Check if it's a function that might return an async iterator
                    sig = inspect.signature(attr)
                    if len(sig.parameters) <= 1:  # 0 or 1 parameter (config)
                        # It might be a middleware factory
                        logger.info(f"Loaded middleware {package_name}.{attr_name}")
                        return True, attr
                except (ValueError, TypeError):
                    continue
                
        logger.warning(f"Could not find middleware factory in {package_name}")
        return False, None 