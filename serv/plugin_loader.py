import logging
from typing import Any, Callable, AsyncIterator, List, Dict, Tuple, Optional
from pathlib import Path
import inspect
import os
import yaml

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
        loaded_plugins = {}
        middleware_list = []

        for plugin_spec in plugins_config:
            try:
                # Get the plugin identifier (dot notation or directory name)
                plugin_id = plugin_spec.get("plugin")
                if not plugin_id:
                    raise ValueError(f"Missing 'plugin' identifier in plugin spec: {plugin_spec}")
                
                # Get plugin settings override from the app config
                settings_override = plugin_spec.get("settings", {})
                
                # Load the plugin instance
                plugin_instance = self._load_plugin(plugin_id, settings_override)
                if not plugin_instance:
                    raise ValueError(f"Failed to load plugin: {plugin_id}")
                
                # Store the loaded plugin
                if plugin_instance.plugin_dir not in loaded_plugins:
                    loaded_plugins[plugin_instance.plugin_dir] = []
                loaded_plugins[plugin_instance.plugin_dir].append(plugin_instance)
                logger.info(f"Loaded plugin {plugin_instance.name} from {plugin_id}")
                
                # Load entry points from plugin.yaml
                entry_points = plugin_instance.get_entry_points()
                for entry_point_config in entry_points:
                    try:
                        entry_plugin = self._load_plugin_entry_point(
                            entry_point_config, 
                            plugin_dir=plugin_instance.plugin_dir
                        )
                        # Store the loaded plugin
                        if entry_plugin.plugin_dir not in loaded_plugins:
                            loaded_plugins[entry_plugin.plugin_dir] = []
                        loaded_plugins[entry_plugin.plugin_dir].append(entry_plugin)
                        entry_str = entry_point_config.get('entry', 'unknown')
                        logger.info(f"Loaded entry point {entry_str} from plugin {plugin_instance.name}")
                    except Exception as e:
                        entry_str = entry_point_config.get('entry', 'unknown')
                        logger.warning(f"Failed to load entry point {entry_str} from plugin {plugin_instance.name}: {e}")
                        e.add_note(f" - Plugin: {plugin_instance.name}")
                        e.add_note(f" - Entry point config: {entry_point_config}")
                        exceptions.append(e)
                
                # Load middleware from plugin.yaml
                middleware_configs = plugin_instance.get_middleware()
                for middleware_config in middleware_configs:
                    try:
                        middleware_factory = self._load_middleware_entry_point(
                            middleware_config,
                            plugin_dir=plugin_instance.plugin_dir
                        )
                        middleware_list.append(middleware_factory)
                        entry_str = middleware_config.get('entry', 'unknown')
                        logger.info(f"Loaded middleware {entry_str} from plugin {plugin_instance.name}")
                    except Exception as e:
                        entry_str = middleware_config.get('entry', 'unknown')
                        logger.warning(f"Failed to load middleware {entry_str} from plugin {plugin_instance.name}: {e}")
                        e.add_note(f" - Plugin: {plugin_instance.name}")
                        e.add_note(f" - Middleware config: {middleware_config}")
                        exceptions.append(e)
                        
            except Exception as e:
                logger.warning(f"Failed to load plugin: {plugin_spec}")
                e.add_note(f" - Plugin spec: {plugin_spec}")
                exceptions.append(e)

        if exceptions:
            logger.warning(f"Encountered {len(exceptions)} errors during plugin and middleware loading.")
            raise ExceptionGroup("Exceptions raised while loading plugins and middleware", exceptions)
            
        return loaded_plugins, middleware_list
        
    def _load_plugin(self, plugin_id: str, settings_override: dict[str, Any] = None) -> Optional[Plugin]:
        """Load a plugin by identifier (dot notation or directory name).
        
        Args:
            plugin_id: Plugin identifier (dot notation or directory name)
            settings_override: Optional settings to override plugin's default settings
            
        Returns:
            Plugin instance or None if loading failed
        """
        if "." in plugin_id:
            # Dot notation - try to load from a module
            namespace, package = plugin_id.rsplit(".", 1)
            success, plugin = self.load_plugin(package, namespace)
            if success and plugin:
                # Apply settings override if provided
                if settings_override:
                    plugin._settings.update(settings_override)
                return plugin
        else:
            # Directory name - try to load from plugin directory
            plugin_dir = Path(self._plugin_loader.directory) / plugin_id
            if plugin_dir.exists() and plugin_dir.is_dir():
                plugin_yaml_path = plugin_dir / "plugin.yaml"
                if plugin_yaml_path.exists():
                    try:
                        # Load the plugin.yaml file
                        with open(plugin_yaml_path, 'r') as f:
                            plugin_config = yaml.safe_load(f)
                        
                        # Get the main plugin entry point
                        entry = plugin_config.get("entry")
                        if not entry:
                            raise ValueError(f"Missing 'entry' in plugin.yaml for {plugin_id}")
                        
                        # Load the plugin class
                        if ":" in entry:
                            module_path, class_name = entry.split(":", 1)
                            # Build the module path relative to the plugin directory
                            module = self._load_module_from_plugin_dir(plugin_dir, module_path)
                            if not module:
                                raise ImportError(f"Failed to load module {module_path}")
                            
                            plugin_class = getattr(module, class_name, None)
                            if not plugin_class:
                                raise ImportError(f"Failed to find class {class_name} in module {module_path}")
                            
                            if not issubclass(plugin_class, Plugin):
                                raise ValueError(f"Class {class_name} is not a Plugin subclass")
                            
                            # Create plugin instance with settings
                            plugin_settings = plugin_config.get("settings", {})
                            if settings_override:
                                plugin_settings.update(settings_override)
                                
                            plugin = plugin_class(config=plugin_settings)
                            return plugin
                    except Exception as e:
                        logger.error(f"Error loading plugin from directory {plugin_id}: {e}")
        
        return None
    
    def _load_module_from_plugin_dir(self, plugin_dir: Path, module_path: str):
        """Load a module relative to a plugin directory.
        
        Args:
            plugin_dir: Path to the plugin directory
            module_path: Module path relative to plugin directory
            
        Returns:
            Loaded module or None if failed
        """
        try:
            # Convert module path format to directory path
            relative_path = module_path.replace(".", "/")
            
            # Add .py extension if needed
            if not relative_path.endswith(".py"):
                relative_path += ".py"
                
            # Get the full path to the module file
            module_file = plugin_dir / relative_path
            
            if not module_file.exists():
                # If direct file doesn't exist, try as a package with __init__.py
                package_init = plugin_dir / module_path.replace(".", "/") / "__init__.py"
                if package_init.exists():
                    module_file = package_init
                else:
                    raise ImportError(f"Module file not found: {relative_path}")
            
            # Import the module using the plugin loader
            # First get the module name - plugin dir name + module path
            full_module_name = f"{plugin_dir.name}.{module_path}"
            return self._plugin_loader.load_package(module_path, plugin_dir.name)
        except Exception as e:
            logger.error(f"Failed to import module {module_path} from {plugin_dir}: {e}")
            return None

    def _load_plugin_entry_point(self, entry_point_config: dict[str, Any], plugin_dir: Path = None) -> Plugin:
        """Load a plugin from an entry point configuration.
        
        Args:
            entry_point_config: Configuration dictionary for the entry point
            plugin_dir: Optional plugin directory for relative import paths
            
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

        # Get config for the entry point
        plugin_config = entry_point_config.get("config", {})
        
        # If plugin_dir is provided, handle relative paths
        if plugin_dir:
            # This is a path relative to the plugin directory
            module_path, class_name = entry.split(":", 1)
            
            # Load module relative to plugin directory
            plugin_module = self._load_module_from_plugin_dir(plugin_dir, module_path)
            if not plugin_module:
                raise ImportError(f"Failed to load plugin module: {module_path!r} relative to {plugin_dir}")
        else:
            # This is a fully qualified path
            module_path, class_name = entry.split(":", 1)
            plugin_module = self._plugin_loader.load_package(module_path)
        
        if not plugin_module:
            raise ImportError(f"Failed to load plugin module: {module_path!r}")

        plugin_class = getattr(plugin_module, class_name, None)
        if not plugin_class:
            raise ImportError(f"Failed to import plugin class {class_name!r} from {module_path!r}")

        if not issubclass(plugin_class, Plugin):
            raise ValueError(f"Plugin class {class_name!r} does not inherit from {Plugin.__name__!r}")
        
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

    def _load_middleware_entry_point(self, middleware_config: dict[str, Any], plugin_dir: Path = None) -> Callable[[], AsyncIterator[None]]:
        """Load middleware from an entry point configuration.
        
        Args:
            middleware_config: Configuration dictionary for the middleware
            plugin_dir: Optional plugin directory for relative import paths
            
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

        # Get middleware configuration
        mw_config = middleware_config.get("config", {})
        
        # If plugin_dir is provided, handle relative paths
        if plugin_dir:
            # This is a path relative to the plugin directory
            module_path, object_name = entry.split(":", 1)
            
            # Load module relative to plugin directory
            middleware_module = self._load_module_from_plugin_dir(plugin_dir, module_path)
            if not middleware_module:
                raise ImportError(f"Failed to load middleware module: {module_path!r} relative to {plugin_dir}")
        else:
            # This is a fully qualified path
            module_path, object_name = entry.split(":", 1)
            middleware_module = self._plugin_loader.load_package(module_path)
            
        if not middleware_module:
            raise ImportError(f"Failed to load middleware module: {module_path!r}")

        middleware_obj = getattr(middleware_module, object_name, None)
        if not middleware_obj:
            raise ImportError(f"Failed to import middleware {object_name!r} from {module_path!r}")

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
        # Handle namespaces with dots - to support bundled.plugins.welcome format
        if namespace and '.' in namespace:
            namespace_parts = namespace.split('.')
            # Build the full module path
            module_path = f"{namespace}.{package_name}" if namespace else package_name
            # Try to import the module directly
            try:
                import importlib
                plugin_module = importlib.import_module(module_path)
                # Try to find a Plugin subclass in the module
                for name in dir(plugin_module):
                    obj = getattr(plugin_module, name)
                    if isinstance(obj, type) and issubclass(obj, Plugin) and obj != Plugin:
                        plugin_instance = obj()
                        logger.info(f"Loaded plugin {package_name} ({name}) from {module_path}")
                        return True, plugin_instance
                
                # Also check __init__.py for imports
                if hasattr(plugin_module, "WelcomePlugin"):
                    plugin_class = plugin_module.WelcomePlugin
                    if issubclass(plugin_class, Plugin):
                        plugin_instance = plugin_class()
                        logger.info(f"Loaded plugin {package_name} (WelcomePlugin) from {module_path}")
                        return True, plugin_instance
                
                logger.warning(f"No Plugin subclass found in {module_path}")
                return False, None
            except ImportError as e:
                logger.warning(f"Failed to import {module_path}: {e}")
                return False, None
            
        # Try normal package loading
        plugin_module = self._plugin_loader.load_package(package_name, namespace)
        if not plugin_module:
            logger.warning(f"Failed to load plugin package {package_name}")
            return False, None
            
        # Find a Plugin subclass in the module
        plugin_class = None
        for name in dir(plugin_module):
            obj = getattr(plugin_module, name)
            if isinstance(obj, type) and issubclass(obj, Plugin) and obj != Plugin:
                plugin_class = obj
                break
                
        if not plugin_class:
            logger.warning(f"No Plugin subclass found in {package_name}")
            return False, None
            
        # Create an instance of the plugin
        try:
            plugin_instance = plugin_class()
            logger.info(f"Loaded plugin {package_name} ({plugin_class.__name__})")
            return True, plugin_instance
        except Exception as e:
            logger.error(f"Failed to instantiate plugin {plugin_class.__name__}: {e}")
            return False, None

    def load_middleware_from_package(self, package_name: str, namespace: str = None) -> tuple[bool, Callable[[], AsyncIterator[None]] | None]:
        """Load middleware from a package.
        
        Args:
            package_name: Name of the middleware package to load
            namespace: Optional namespace to look in (defaults to first found)
            
        Returns:
            Tuple of (success_bool, middleware_factory or None)
        """
        middleware_module = self._plugin_loader.load_package(package_name, namespace)
        if not middleware_module:
            logger.warning(f"Failed to load middleware package {package_name}")
            return False, None
            
        # Try to find a ServMiddleware subclass or callable
        middleware_obj = None
        for name in dir(middleware_module):
            obj = getattr(middleware_module, name)
            if inspect.isclass(obj) and issubclass(obj, ServMiddleware) and obj != ServMiddleware:
                middleware_obj = obj
                break
            elif callable(obj) and name.lower().endswith(('middleware', 'factory')):
                middleware_obj = obj
                break
                
        if not middleware_obj:
            logger.warning(f"No ServMiddleware subclass or callable found in {package_name}")
            return False, None
            
        # If it's a class, create a factory function
        if inspect.isclass(middleware_obj):
            def factory():
                return middleware_obj()
            return True, factory
        # If it's a callable, return it directly
        elif callable(middleware_obj):
            return True, middleware_obj
        
        return False, None 