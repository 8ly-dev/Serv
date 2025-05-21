import asyncio
import contextlib
import json
import logging
import traceback
import inspect
from asyncio import get_running_loop, Task
from collections import defaultdict
from itertools import chain
from typing import AsyncIterator, Awaitable, Callable, Any
from pathlib import Path
from bevy import dependency, get_registry, inject
from bevy.containers import Container
from bevy.registries import Registry
from jinja2 import Environment, FileSystemLoader, select_autoescape
from asgiref.typing import (
    Scope,
    ASGIReceiveCallable as Receive,
    ASGISendCallable as Send,
    LifespanShutdownCompleteEvent,
    LifespanStartupCompleteEvent,
)

from serv.config import load_raw_config
from serv.plugins import Plugin
from serv.loader import ServLoader
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.injectors import inject_request_object
from serv.routing import Router, HTTPNotFoundException
from serv.exceptions import HTTPMethodNotAllowedException
from serv.middleware import ServMiddleware

logger = logging.getLogger(__name__)

class EventEmitter:
    def __init__(self, plugins: dict[Path, list[Plugin]]):
        self.plugins = plugins

    def emit_sync(self, event: str, *, container: Container = dependency(), **kwargs) -> Task:
        return get_running_loop().create_task(self.emit(event, container=container, **kwargs))

    async def emit(self, event: str, *, container: Container = dependency(), **kwargs):
        async with asyncio.TaskGroup() as tg:
            for plugin in chain(*self.plugins.values()):
                tg.create_task(container.call(plugin.on, event, **kwargs))


class App:
    """This is the main class for an ASGI application.

    It is responsible for handling the incoming requests and delegating them to the appropriate routes.
    """

    def __init__(
        self,
        *,
        config: str = "./serv.config.yaml",
        plugin_dir: str = "./plugins",
        dev_mode: bool = False,
    ):
        """Initialize a new Serv application.

        Args:
            config: configuration dictionary (usually from serv.config.yaml)
            plugin_dir: directory to search for plugins (default: './plugins')
            dev_mode: whether to run in development mode (default: False)
        """
        self._config = self._load_config(config)
        self._dev_mode = dev_mode
        self._registry = get_registry()
        self._container = self._registry.create_container()
        self._async_exit_stack = contextlib.AsyncExitStack()
        self._error_handlers: dict[type[Exception], Callable[[Exception], Awaitable[None]]] = {}
        self._middleware = []

        self._plugin_loader = ServLoader(plugin_dir)
        self._plugins: dict[Path, list[Plugin]] = defaultdict(list)
        self._emit = EventEmitter(self._plugins)

        self._init_container()
        self._register_default_error_handlers()
        self._load_plugins(self._config.get("plugins", []))

    def _load_config(self, config_path: str) -> dict[str, Any]:
        return load_raw_config(config_path)

    def _init_container(self):
        inject_request_object.register_hook(self._registry)
        self._container.instances[App] = self
        self._container.instances[Container] = self._container
        self._container.instances[Registry] = self._registry

    def _register_default_error_handlers(self):
        self.add_error_handler(HTTPNotFoundException, self._default_404_handler)
        self.add_error_handler(HTTPMethodNotAllowedException, self._default_405_handler)
        # Add more default handlers as needed

    def add_error_handler(self, error_type: type[Exception], handler: Callable[[Exception], Awaitable[None]]):
        self._error_handlers[error_type] = handler
        self.emit("error_handler.loaded", error_type=error_type, handler=handler, container=self._container)

    def add_middleware(self, middleware: Callable[[], AsyncIterator[None]]):
        self._middleware.append(middleware)
        self.emit("middleware.loaded", middleware=middleware, container=self._container)

    def add_plugin(self, plugin: Plugin):
        self._plugins[plugin.plugin_dir].append(plugin)
        self.emit("plugin.loaded", plugin=plugin, container=self._container)

    def get_plugin(self, path: Path) -> Plugin | None:
        return self._plugins.get(path)

    def _load_plugins(self, plugins_config: list[dict[str, Any]]):
        """Load plugins from a list of plugin configs and add them to the app.

        Args:
            plugins_config: List of plugin configs (usually from serv.config.yaml)
        """
        exceptions = []
        loaded_plugins_count = 0
        loaded_middleware_count = 0

        for plugin_spec in plugins_config:
            plugin_name = plugin_spec.get("name", "Unknown Plugin")
            # Load plugin entry points
            if "entry points" in plugin_spec:
                for entry_point_config in plugin_spec["entry points"]:
                    try:
                        plugin_instance = self._load_plugin_entry_point(entry_point_config)
                        self.add_plugin(plugin_instance)
                        loaded_plugins_count += 1
                        logger.info(f"Loaded plugin entry point for {plugin_name} from {entry_point_config.get('entry')}")
                    except Exception as e:
                        logger.warning(f"Failed to load plugin entry point for {plugin_name} from {entry_point_config.get('entry')}")
                        e.add_note(f" - Plugin: {plugin_name}")
                        e.add_note(f" - Entry point config: {entry_point_config}")
                        exceptions.append(e)

            # Load middleware from plugin
            if "middleware" in plugin_spec:
                for middleware_config_entry in plugin_spec["middleware"]:
                    try:
                        middleware_factory = self._load_middleware_entry_point(middleware_config_entry)
                        self.add_middleware(middleware_factory)
                        loaded_middleware_count += 1
                        logger.info(f"Loaded middleware for {plugin_name} from {middleware_config_entry.get('entry')}")
                    except Exception as e:
                        logger.warning(f"Failed to load middleware for {plugin_name} from {middleware_config_entry.get('entry')}")
                        e.add_note(f" - Plugin: {plugin_name}")
                        e.add_note(f" - Middleware config: {middleware_config_entry}")
                        exceptions.append(e)

        logger.info(f"Loaded {loaded_plugins_count} plugin entry points and {loaded_middleware_count} middleware entries.")
        if exceptions:
            logger.warning(f"Encountered {len(exceptions)} errors during plugin and middleware loading.")
            raise ExceptionGroup("Exceptions raised while loading plugins and middleware", exceptions)

    def _load_plugin_entry_point(self, entry_point_config: dict[str, Any]) -> Plugin:
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

    def _load_plugin_from_config(self, config: dict[str, Any]) -> Plugin:
        # This method is now primarily for backward compatibility if an old-style config is encountered.
        # The main loading path is via _load_plugins and _load_plugin_entry_point.
        if "entry" in config and ":" in config["entry"] and "entry points" not in config and "middleware" not in config:
            logger.warning(
                f"Plugin configuration for '{config['entry']}' is using the deprecated single 'entry' field. "
                f"Consider migrating to the new structure with 'name' and 'entry points'."
            )
            # Adapt to the new entry point structure for processing
            entry_point_config = {"entry": config["entry"], "config": config.get("config", {})}
            return self._load_plugin_entry_point(entry_point_config)

        # If it's not a simple, old-style config, it should be handled by the new _load_plugins logic.
        # This path indicates a malformed or unexpected configuration structure if reached directly with new format items.
        raise ValueError(
            f"_load_plugin_from_config was called with an unexpected configuration structure: {config}. "
            f"Ensure plugin configurations follow the documented format (either old style with single 'entry' "
            f"or new style with 'name', 'entry points', and/or 'middleware')."
        )
        
    def load_plugin(self, package_name: str, namespace: str = None) -> bool:
        """Load a plugin from the plugin directories.
        
        Args:
            package_name: Name of the plugin package to load
            namespace: Optional namespace to look in (defaults to first found)
            
        Returns:
            True if plugin was loaded successfully, False otherwise
        """
        plugin_module = self._plugin_loader.load_package("plugin", package_name, namespace)
        if not plugin_module:
            logger.warning(f"Failed to load plugin {package_name}")
            return False
            
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
                                self.add_plugin(plugin_instance)
                                logger.info(f"Loaded plugin {package_name} ({class_name})")
                                return True
            except Exception as e:
                logger.warning(f"Error loading plugin from plugin.yaml: {e}")
                
        logger.warning(f"Could not find Plugin subclass in {package_name}")
        return False
        
    def load_middleware(self, package_name: str, namespace: str = None) -> bool:
        """Load middleware from the middleware directories.
        
        Args:
            package_name: Name of the middleware package to load
            namespace: Optional namespace to look in (defaults to first found)
            
        Returns:
            True if middleware was loaded successfully, False otherwise
        """
        middleware_module = self._plugin_loader.load_package("middleware", package_name, namespace)
        if not middleware_module:
            logger.warning(f"Failed to load middleware {package_name}")
            return False
        
        # First try to find something that ends with _middleware
        for attr_name in dir(middleware_module):
            attr = getattr(middleware_module, attr_name)
            if callable(attr) and attr_name.endswith('_middleware'):
                self.add_middleware(attr)
                logger.info(f"Loaded middleware {package_name}.{attr_name}")
                return True
                
        # Try to find any callable that looks like a middleware factory
        for attr_name in dir(middleware_module):
            attr = getattr(middleware_module, attr_name)
            if callable(attr) and not attr_name.startswith('_'):
                try:
                    # Check if it's a function that might return an async iterator
                    sig = inspect.signature(attr)
                    if len(sig.parameters) <= 1:  # 0 or 1 parameter (config)
                        # It might be a middleware factory
                        self.add_middleware(attr)
                        logger.info(f"Loaded middleware {package_name}.{attr_name}")
                        return True
                except (ValueError, TypeError):
                    continue
                
        logger.warning(f"Could not find middleware factory in {package_name}")
        return False
        
    def load_plugins(self) -> int:
        """Load all available plugins.
        
        Returns:
            Number of plugins loaded
        """
        loaded_count = 0
        available = self._plugin_loader.list_available("plugin")
        
        for namespace, packages in available.items():
            for package_name in packages:
                if self.load_plugin(package_name, namespace):
                    loaded_count += 1
                    
        return loaded_count
        
    def load_middleware_packages(self) -> int:
        """Load all available middleware.
        
        Returns:
            Number of middleware loaded
        """
        loaded_count = 0
        available = self._plugin_loader.list_available("middleware")
        
        for namespace, packages in available.items():
            for package_name in packages:
                if self.load_middleware(package_name, namespace):
                    loaded_count += 1
                    
        return loaded_count

    def emit(self, event: str, *, container: Container = dependency(), **kwargs) -> Task:
        return container.call(self._emit.emit_sync, event, **kwargs)

    async def handle_lifespan(self, scope: Scope, receive: Receive, send: Send):
        async for event in self._lifespan_iterator(receive):
            match event:
                case {"type": "lifespan.startup"}:
                    logger.debug("Lifespan startup event")
                    await self.emit("app.startup", scope=scope, container=self._container)
                    await send(LifespanStartupCompleteEvent(type="lifespan.startup.complete"))

                case {"type": "lifespan.shutdown"}:
                    logger.debug("Lifespan shutdown event")
                    await self.emit("app.shutdown", scope=scope, container=self._container)
                    await self._async_exit_stack.aclose()
                    await send(LifespanShutdownCompleteEvent(type="lifespan.shutdown.complete"))

    def _get_template_locations(self) -> list[Path]:
        """Get a list of template locations to search for templates.

        The order of precedence is:
        1. Templates in the CWD/templates directory (if it exists)
        2. Templates in the serv/templates directory
        """
        template_locations = []

        # Check for templates in the current working directory
        cwd_templates = Path.cwd() / "templates"
        if cwd_templates.exists() and cwd_templates.is_dir():
            template_locations.append(cwd_templates)

        # Add the serv/templates directory
        serv_templates = Path(__file__).parent / "templates"
        if serv_templates.exists() and serv_templates.is_dir():
            template_locations.append(serv_templates)

        return template_locations

    def _render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template with the given context."""
        template_locations = self._get_template_locations()
        if not template_locations:
            # Fallback to simple HTML if no template locations are found
            return f"<html><body><h1>{context.get('error_title', 'Error')}</h1><p>{context.get('error_message', '')}</p></body></html>"

        env = Environment(
            loader=FileSystemLoader(template_locations),
            autoescape=select_autoescape(['html', 'xml'])
        )

        try:
            template = env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            # Fallback to simple HTML if template rendering fails
            return f"<html><body><h1>{context.get('error_title', 'Error')}</h1><p>{context.get('error_message', '')}</p></body></html>"

    @inject
    async def _default_error_handler(self, error: Exception, response: ResponseBuilder = dependency(), request: Request = dependency()):
        status_code = getattr(error, 'status_code', 500)
        response.set_status(status_code)
        
        # Check if the client accepts HTML
        accept_header = request.headers.get("accept", "")

        # Prepare error data for JSON response
        error_data = {
            "status_code": status_code,
            "error": type(error).__name__,
            "message": str(error),
            "path": request.path,
            "method": request.method
        }

        # For 500 errors, add stack trace information if appropriate
        if status_code == 500:
            error_chain = []
            current_exc = error.__context__ or error.__cause__
            chain_count = 0

            while current_exc and chain_count < 10:  # Limit depth to prevent infinite loops
                error_chain.append({
                    "type": type(current_exc).__name__,
                    "message": str(current_exc)
                })

                next_exc = current_exc.__context__ or current_exc.__cause__
                if next_exc is current_exc:  # Break if we're in a loop
                    break
                current_exc = next_exc
                chain_count += 1

            if error_chain:
                error_data["error_chain"] = error_chain

        if "text/html" in accept_header:
            # Use HTML response with templates
            response.content_type("text/html")
            
            # Prepare context for the template
            context = {
                "status_code": status_code,
                "error_title": f"Error {status_code}",
                "error_message": str(error) if self._dev_mode else "An error occurred while processing your request.",
                "error_type": type(error).__name__ if self._dev_mode else "Internal Server Error",
                "error_str": str(error) if self._dev_mode else "An error occurred while processing your request.",
                "request_path": request.path,
                "request_method": request.method,
                "show_details": status_code == 500  # Only show details for 500 errors
            }

            # Process error chain for 500 errors with full traceback
            if status_code == 500 and self._dev_mode:
                error_chain = []
                current_exc = error.__context__ or error.__cause__
                chain_count = 0

                while current_exc and chain_count < 10:
                    formatted_tb = "".join(traceback.format_exception(type(current_exc), current_exc, current_exc.__traceback__))
                    error_chain.append({
                        "type": type(current_exc).__name__,
                        "message": str(current_exc),
                        "traceback": formatted_tb
                    })

                    next_exc = current_exc.__context__ or current_exc.__cause__
                    if next_exc is current_exc:
                        break
                    current_exc = next_exc
                    chain_count += 1

                if error_chain:
                    context["error_chain"] = error_chain

                # Add traceback for the main error
                context["traceback"] = "".join(traceback.format_exception(type(error), error, error.__traceback__))

            # Try to use a specific template for this status code, fall back to generic_error.html
            template_name = f"error/{status_code}.html" if status_code in [404, 405, 500] else "error/generic_error.html"
            html_content = self._render_template(template_name, context)
            response.body(html_content)
        elif "application/json" in accept_header:
            # Use JSON response
            if not self._dev_mode:
                error_data.pop("error_chain", None)
                error_data.pop("traceback", None)

            response.content_type("application/json")
            response.body(json.dumps(error_data))
        else:
            # Use plaintext response
            message = f"{status_code} Error: "
            if self._dev_mode:
                message += f"{type(error).__name__}: {error}\n\n{traceback.format_exc()}"
            else:
                message += "An error occurred while processing your request."

            response.content_type("text/plain")
            response.body(message)

    @inject
    async def _default_404_handler(self, error: HTTPNotFoundException, response: ResponseBuilder = dependency(), request: Request = dependency()):
        response.set_status(HTTPNotFoundException.status_code)
        
        # Check if the client accepts HTML
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header:
            # Use HTML response
            response.content_type("text/html")
            context = {
                "status_code": HTTPNotFoundException.status_code,
                "error_title": "Not Found",
                "error_message": f"The requested resource was not found.",
                "error_type": type(error).__name__,
                "error_str": str(error),
                "request_path": request.path,
                "request_method": request.method,
                "show_details": False
            }
            
            html_content = self._render_template("error/404.html", context)
            response.body(html_content)
        elif "application/json" in accept_header:
            # Use JSON response
            response.content_type("application/json")
            error_data = {
                "status_code": HTTPNotFoundException.status_code,
                "error": "NotFound",
                "message": "The requested resource was not found.",
                "path": request.path,
                "method": request.method
            }
            response.body(json.dumps(error_data))
        else:
            # Use plaintext response
            response.content_type("text/plain")
            response.body(f"404 Not Found: The requested resource ({request.path}) was not found.")

    @inject
    async def _default_405_handler(self, error: HTTPMethodNotAllowedException, response: ResponseBuilder = dependency(), request: Request = dependency()):
        response.set_status(HTTPMethodNotAllowedException.status_code)
        
        allowed_methods_str = ", ".join(error.allowed_methods) if error.allowed_methods else ""
        if error.allowed_methods:
            response.add_header("Allow", allowed_methods_str)
        
        # Check if the client accepts HTML
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header:
            # Use HTML response
            response.content_type("text/html")
            context = {
                "status_code": HTTPMethodNotAllowedException.status_code,
                "error_title": "Method Not Allowed",
                "error_message": error.args[0] if error.args else "The method used is not allowed for the requested resource.",
                "error_type": type(error).__name__,
                "error_str": str(error),
                "request_path": request.path,
                "request_method": request.method,
                "allowed_methods": allowed_methods_str,
                "show_details": False
            }
            
            html_content = self._render_template("error/405.html", context)
            response.body(html_content)
        elif "application/json" in accept_header:
            # Use JSON response
            response.content_type("application/json")
            error_data = {
                "status_code": HTTPMethodNotAllowedException.status_code,
                "error": "MethodNotAllowed",
                "message": error.args[0] if error.args else "The method used is not allowed for the requested resource.",
                "path": request.path,
                "method": request.method,
                "allowed_methods": error.allowed_methods if error.allowed_methods else []
            }
            response.body(json.dumps(error_data))
        else:
            # Use plaintext response
            response.content_type("text/plain")
            message = error.args[0] if error.args else f"The method used is not allowed for the requested resource {request.path}."
            response.body(f"405 Method Not Allowed: {message}")

    @inject
    async def _run_error_handler(self, error: Exception, container: Container = dependency()):
        response_builder = container.get(ResponseBuilder)
        if not response_builder._headers_sent:
            response_builder.clear()

        handler_key = type(error)
        handler = self._error_handlers.get(handler_key)
        if not handler:
            for err_type, hnd in self._error_handlers.items():
                if isinstance(error, err_type):
                    handler = hnd
                    break
        handler = handler or self._default_error_handler

        try:
            await container.call(handler, error)
        except Exception as e:
            logger.exception("Critical error in error handling mechanism itself", exc_info=True)
            if handler is not self._default_error_handler:
                e.__context__ = error
                ultimate_response_builder = container.get(ResponseBuilder)
                if not ultimate_response_builder._headers_sent:
                    ultimate_response_builder.clear()
                await container.call(self._default_error_handler, e)

    async def _lifespan_iterator(self, receive: Receive):
        event = {}
        while event.get("type") != "lifespan.shutdown":
            event = await receive()
            yield event

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        match scope["type"]:
            case "lifespan":
                await self.handle_lifespan(scope, receive, send)
            case "http":
                await self._handle_request(scope, receive, send)
            case _:
                logger.warning(f"Unsupported ASGI scope type: {scope['type']}")

    async def _handle_request(self, scope: Scope, receive: Receive, send: Send):
        with self._container.branch() as container:
            request = Request(scope, receive)
            response_builder = ResponseBuilder(send)
            router_instance_for_request = Router()

            container.instances[Request] = request
            container.instances[ResponseBuilder] = response_builder
            container.instances[Container] = container
            container.instances[Router] = router_instance_for_request

            try:
                # Pass the newly created router_instance to the event
                await self.emit("app.request.begin", container=container)

                await self._run_middleware_stack(container=container, request_instance=request)

                await self.emit("app.request.end", error=None, container=container)
            except Exception as e:
                logger.exception("Unhandled exception during request processing", exc_info=e)
                await container.call(self._run_error_handler, e)
                await self.emit("app.request.end", error=e, container=container)
            finally:
                # Ensure response is sent. ResponseBuilder.send_response() should be robust
                # enough to handle being called if headers were already sent by an error handler,
                # or to send a default response if nothing was set.
                try:
                    await response_builder.send_response()
                except Exception as final_send_exc:
                    logger.error("Exception during final send_response", exc_info=final_send_exc)

    async def _run_middleware_stack(self, container: Container, request_instance: Request):
        stack = []
        error_to_propagate = None
        router_instance = container.get(Router)

        for middleware_factory in self._middleware:
            try:
                middleware_iterator = container.call(middleware_factory)
                await anext(middleware_iterator)
            except Exception as e:
                logger.exception(f"Error during setup of middleware {getattr(middleware_factory, '__name__', str(middleware_factory))}", exc_info=True)
                error_to_propagate = e
                break
            else:
                stack.append(middleware_iterator)

        if not error_to_propagate:
            await self.emit("app.request.before_router", container=container, request=request_instance, router_instance=router_instance)
            try:
                resolved_route_info = router_instance.resolve_route(request_instance.path, request_instance.method)
                if not resolved_route_info:
                    raise HTTPNotFoundException(f"No route found for {request_instance.method} {request_instance.path}")

            except Exception as e:
                logger.info(f"Router resolution resulted in exception: {type(e).__name__}: {e}")
                error_to_propagate = e

            else:
                handler_callable, path_params, route_settings = resolved_route_info
                
                # Create a branch of the container with route settings
                with container.branch() as route_container:
                    # Add route settings to the container
                    for setting_name, setting_value in route_settings.items():
                        route_container.instances[setting_name] = setting_value
                    
                    try:
                        await route_container.call(handler_callable, **path_params)
                    except Exception as e:
                        logger.info(f"Handler execution resulted in exception: {type(e).__name__}: {e}")
                        error_to_propagate = e

            await self.emit("app.request.after_router", container=container, request=request_instance, error=error_to_propagate, router_instance=router_instance)

        for middleware_iterator in reversed(stack):
            try:
                if error_to_propagate:
                    await middleware_iterator.athrow(error_to_propagate)
                    error_to_propagate = None
                else:
                    await anext(middleware_iterator)
            except StopAsyncIteration:
                pass
            except Exception as e:
                logger.exception("Error during unwinding of middleware", exc_info=True)
                if error_to_propagate:
                    e.__context__ = error_to_propagate
                error_to_propagate = e

        if error_to_propagate:
            raise error_to_propagate
