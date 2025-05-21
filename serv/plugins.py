"""Defines a base type that can observe events happening in the Serv app. Handlers are defined as methods on the class
with names following the format '[optional_]on_{event_name}'. This gives the author the ability to make readable 
function names like 'set_role_on_user_create' or 'create_annotations_on_form_submit'."""


from collections import defaultdict
from inspect import isawaitable
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Callable, Type, Optional, TYPE_CHECKING

from bevy import dependency, get_container
from bevy.containers import Container
import yaml

# Avoid circular imports by only importing Router for type checking
if TYPE_CHECKING:
    from serv.routing import Router


type PluginMapping = dict[str, list[str]]


def search_for_plugin_directory(path: Path) -> Path | None:
    while path.name:
        if (path / "plugin.yaml").exists():
            return path

        path = path.parent

    raise Exception("Plugin directory not found")


class Plugin:
    __plugins__: PluginMapping

    def __init_subclass__(cls, **kwargs) -> None:
        cls.__plugins__ = defaultdict(list)

        for name in dir(cls):
            if name.startswith("_"):
                continue
            
            event = re.match(r"^(?:.+_)?on_(.*)$", name)
            if not event:
                continue

            callback = getattr(cls, name)
            if not callable(callback):
                continue
            
            event_name = event.group(1)
            cls.__plugins__[event_name].append(name)
    
    def __init__(self, *, stand_alone: bool = False):
        """Initialize the plugin.
        
        Loads plugin configuration and sets up any defined routers and routes
        if they are configured in the plugin.yaml file.
        """
        self._config = {} if stand_alone else self.config()
        self._router_configs = self._config.get("routers", [])

    def config(self) -> dict[str, Any]:
        """
        Returns a dictionary of configuration options for the plugin.
        """
        module_path = sys.modules[self.__module__].__file__
        plugin_path = search_for_plugin_directory(Path(module_path).parent)
        config_file_path = plugin_path / "plugin.yaml"
        if not config_file_path.exists():
            return {}

        with open(config_file_path, 'r') as f:
            raw_config_data = yaml.safe_load(f)

        return raw_config_data
    
    def setup_routers(self, container: Container = dependency()) -> List["Router"]:
        """
        Sets up routers defined in the plugin configuration.
        Returns a list of created Router instances.
        
        Router configuration format in plugin.yaml:
        ```yaml
        routers:
          - name: api_router  # Optional, used for reference
            settings:  # Optional settings for this router
              auth_required: true
              rate_limit: 100
            routes:
              - path: /users
                handler: users:UserRoute  # Import path to Route class
                settings:  # Optional settings for this route
                  db_table: users
                  cache_ttl: 300
              - path: /posts
                handler_method: handle_posts  # Method on this plugin
                methods: [GET, POST]  # Optional, only used with handler_method
                settings:
                  db_table: posts
            mount_at: /api  # Optional, path to mount this router
            mount_to: main_router  # Optional, name of router to mount to
        ```
        """
        # Import Router here to avoid circular import
        from serv.routing import Router
        
        created_routers = []
        router_instances = {}
        
        # First pass: create all routers
        for router_config in self._router_configs:
            router_name = router_config.get("name", f"router_{len(router_instances)}")
            router_settings = router_config.get("settings", {})
            router = Router(settings=router_settings)
            router_instances[router_name] = router
            created_routers.append(router)
            
            # Add routes to this router
            if "routes" in router_config:
                for route_config in router_config["routes"]:
                    self._add_route_from_config(router, route_config, container)
        
        # Second pass: handle mounting
        for router_config in self._router_configs:
            if "mount_at" in router_config and "mount_to" in router_config:
                router_name = router_config.get("name", f"router_{len(router_instances)}")
                router = router_instances.get(router_name)
                
                mount_to_name = router_config["mount_to"]
                mount_to_router = router_instances.get(mount_to_name)
                
                if router and mount_to_router:
                    mount_path = router_config["mount_at"]
                    mount_to_router.mount(mount_path, router)
        
        return created_routers
    
    def _add_route_from_config(self, router: Any, route_config: Dict[str, Any], container: Container) -> None:
        """Add a route to a router based on route configuration."""
        path = route_config.get("path")
        if not path:
            return
            
        # Extract route settings if any
        settings = route_config.get("settings", {})
            
        # Handle route defined as an importable class
        if "handler" in route_config:
            handler_path = route_config["handler"]
            handler_class = self._import_handler(handler_path)
            if handler_class:
                router.add_route(path, handler_class, settings=settings)
        
        # Handle route defined as a method on this plugin
        elif "handler_method" in route_config:
            method_name = route_config["handler_method"]
            if hasattr(self, method_name):
                handler_method = getattr(self, method_name)
                methods = route_config.get("methods")
                router.add_route(path, handler_method, methods=methods, settings=settings)
    
    def _import_handler(self, handler_path: str) -> Optional[Type]:
        """Import a handler class from a string path.
        
        Format required:
        - "module.path:ClassName" - Import a class directly
        - "module.path:object.attribute.ClassName" - Access a nested object/attribute
        
        Note: The colon separator is required to distinguish between the module path
        and the object path.
        """
        try:
            if ":" not in handler_path:
                raise ValueError(f"Handler path must use colon notation (module.path:ClassName): {handler_path}")
                
            # Split on colon to separate module path from object access path
            module_path, object_path = handler_path.split(":", 1)
            
            # Import the module
            module = __import__(module_path, fromlist=["__name__"])
            
            # Navigate through the object access path
            obj = module
            for attr in object_path.split("."):
                obj = getattr(obj, attr)
            
            return obj
        except (ImportError, AttributeError, ValueError) as e:
            # Log error but don't crash
            import logging
            logging.getLogger(__name__).error(f"Failed to import handler {handler_path}: {e}")
            return None

    async def on(self, event_name: str, container: Container | None = None, *args: Any, **kwargs: Any) -> None:
        """Receives event notifications.
        
        This method will be called by the application when an event this plugin
        is registered for occurs. Subclasses should implement this method to handle
        specific events.

        Args:
            event_name: The name of the event that occurred.
            **kwargs: Arbitrary keyword arguments associated with the event.
        """
        event_name = re.sub(r"[^a-z0-9]+", "_", event_name.lower())
        for plugin_handler_name in self.__plugins__[event_name]:
            callback = getattr(self, plugin_handler_name)
            result = get_container(container).call(callback, *args, **kwargs)
            if isawaitable(result):
                await result
                
    def on_app_startup(self, app: Any = None, container: Container = dependency()) -> None:
        """Called when the app starts up.
        
        This is a good place to set up routers defined in the plugin configuration.
        
        Args:
            app: The Serv application instance.
            container: The dependency injection container.
        """
        # Import Router here to avoid circular import
        from serv.routing import Router
        
        # Set up routers from config if any are defined
        if self._router_configs:
            routers = self.setup_routers(container)
            
            # If there's only one router and it's not mounted to another router,
            # register it as the main router in the container
            if len(routers) == 1 and not any(
                "mount_to" in config for config in self._router_configs
            ):
                # Container.set is not available, use instances attribute directly
                container.instances[Router] = routers[0]
