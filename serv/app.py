import asyncio
import contextlib
import json
import logging
import sys
import traceback
from asyncio import get_running_loop, Task
from collections import defaultdict
from itertools import chain
from typing import AsyncIterator, Awaitable, Callable, Any
from pathlib import Path
from bevy import dependency, get_registry, inject
from bevy.containers import Container
from bevy.registries import Registry
from jinja2 import Environment, FileSystemLoader
from asgiref.typing import (
    Scope,
    ASGIReceiveCallable as Receive,
    ASGISendCallable as Send,
    LifespanShutdownCompleteEvent,
    LifespanStartupCompleteEvent,
)

from serv.config import load_raw_config
from serv.plugins import Plugin
from serv.plugins.importer import Importer
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.injectors import inject_request_object
from serv.routing import Router, HTTPNotFoundException
from serv.exceptions import HTTPMethodNotAllowedException, ServException
from serv.plugins.loader import PluginLoader

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

        self._plugin_loader = Importer(plugin_dir)
        self._plugins: dict[Path, list[Plugin]] = defaultdict(list)
        
        # Initialize the plugin loader
        self._plugin_loader_instance = PluginLoader(self, self._plugin_loader)
        
        self._emit = EventEmitter(self._plugins)

        self._init_container()
        self._register_default_error_handlers()
        self._init_plugins(self._config.get("plugins", []))
        
    def _load_config(self, config_path: str) -> dict[str, Any]:
        return load_raw_config(config_path)

    def _init_plugins(self, plugins_config: list[dict[str, Any]]):
        loaded_plugins, loaded_middleware = self._plugin_loader_instance.load_plugins(plugins_config)
        if not loaded_plugins and not loaded_middleware:
            self._enable_welcome_plugin()

    def _init_container(self):
        # Register hooks for injection
        inject_request_object.register_hook(self._registry)
        
        # Set up container instances
        self._container.instances[App] = self
        self._container.instances[Container] = self._container
        self._container.instances[Registry] = self._registry

    def _register_default_error_handlers(self):
        self.add_error_handler(HTTPNotFoundException, self._default_404_handler)
        self.add_error_handler(HTTPMethodNotAllowedException, self._default_405_handler)

    def add_error_handler(self, error_type: type[Exception], handler: Callable[[Exception], Awaitable[None]]):
        self._error_handlers[error_type] = handler

    def add_middleware(self, middleware: Callable[[], AsyncIterator[None]]):
        self._middleware.append(middleware)

    def add_plugin(self, plugin: Plugin):
        if plugin.__plugin_spec__:
            spec = plugin.__plugin_spec__
        else:
            module = sys.modules[plugin.__module__]
            spec = module.__plugin_spec__

        self._plugins[spec.path].append(plugin)

    def get_plugin(self, path: Path) -> Plugin | None:
        return self._plugins.get(path, [None])[0]

    def _load_plugins(self, plugins_config: list[dict[str, Any]]):
        """Legacy method, delegates to _load_plugins_from_config."""
        return self._load_plugins_from_config(plugins_config)

    def _enable_welcome_plugin(self):
        """Enable the bundled welcome plugin if no other plugins are registered."""
        plugin_spec, exceptions = self._plugin_loader_instance.load_plugin("serv.bundled.plugins.welcome")
        if exceptions:
            raise ExceptionGroup("Exceptions raised while loading welcome plugin", exceptions)

        return True

    # Backward compatibility methods
    def _load_plugin_entry_point(self, entry_point_config: dict[str, Any]) -> Plugin:
        """Backward compatibility method that delegates to PluginLoader."""
        return self._plugin_loader_instance._load_plugin_entry_point(entry_point_config)

    def _load_middleware_entry_point(self, middleware_config: dict[str, Any]) -> Callable[[], AsyncIterator[None]]:
        """Backward compatibility method that delegates to PluginLoader."""
        return self._plugin_loader_instance._load_middleware_entry_point(middleware_config)

    def _load_plugin_from_config(self, config: dict[str, Any]) -> Plugin:
        # This method is now primarily for backward compatibility if an old-style config is encountered.
        # The main loading path is via _load_plugins_from_config and PluginLoader.
        if not isinstance(config, dict):
            raise ValueError(f"Invalid plugin config: {config!r}")

        entry = config.get("entry")
        if not entry:
            raise ValueError(f"Plugin config missing 'entry': {config!r}")

        plugin_config = config.get("config", {})
        return self._load_plugin_entry_point({"entry": entry, "config": plugin_config})

    def load_plugin(self, package_name: str, namespace: str = None) -> bool:
        """Load a plugin from a package name.

        Args:
            package_name: The name of the package to load
            namespace: Optional namespace to restrict search

        Returns:
            True if the plugin was loaded successfully
        """
        success, plugin = self._plugin_loader_instance.load_plugin(package_name, namespace)
        if success and plugin:
            self.add_plugin(plugin)
            return True
        return False

    def load_middleware(self, package_name: str, namespace: str = None) -> bool:
        """Load middleware from a package name.

        Args:
            package_name: The name of the package to load
            namespace: Optional namespace to restrict search

        Returns:
            True if the middleware was loaded successfully
        """
        success, middleware_factory = self._plugin_loader_instance.load_middleware_from_package(package_name, namespace)
        if success and middleware_factory:
            self.add_middleware(middleware_factory)
            return True
        return False

    def load_plugins(self) -> int:
        """Load all plugins from the plugin directories.

        Returns:
            Number of plugins loaded
        """
        plugins_count = 0
        plugins_dir = Path(self._plugin_loader.plugin_dir)
        
        if not plugins_dir.exists():
            logger.warning(f"Plugin directory {plugins_dir} does not exist.")
            return 0
            
        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith("_"):
                if self.load_plugin(plugin_dir.name):
                    plugins_count += 1
                    
        return plugins_count

    def load_middleware_packages(self) -> int:
        """Load all middleware packages from the plugin directories.

        Returns:
            Number of middleware packages loaded
        """
        middleware_count = 0
        plugins_dir = Path(self._plugin_loader.plugin_dir)
        
        if not plugins_dir.exists():
            logger.warning(f"Plugin directory {plugins_dir} does not exist.")
            return 0
            
        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith("_"):
                if self.load_middleware(plugin_dir.name):
                    middleware_count += 1
                    
        return middleware_count

    def emit(self, event: str, *, container: Container = dependency(), **kwargs) -> Task:
        return self._emit.emit_sync(event, container=container, **kwargs)

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
        """Get the template locations for this app.

        Returns a list of paths to search for templates.
        """
        return [Path.cwd() / "templates", Path(__file__).parent / "templates"]

    def _render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template with the given context.

        Args:
            template_name: Name of the template to render
            context: Context to render the template with

        Returns:
            Rendered template as a string
        """
        template_locations = self._get_template_locations()
        env = Environment(loader=FileSystemLoader(template_locations))
        
        # Try to load the template
        try:
            template = env.get_template(template_name)
        except Exception as e:
            logger.exception(f"Failed to load template {template_name}")
            # Special case for error templates - provide a fallback
            if template_name.startswith("error/"):
                status_code = context.get("status_code", 500)
                error_title = context.get("error_title", "Error")
                error_message = context.get("error_message", "An error occurred")
                
                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{status_code} {error_title}</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; padding: 20px; }}
                        h1 {{ color: #d00; }}
                        pre {{ background: #f4f4f4; padding: 10px; border-radius: 5px; }}
                    </style>
                </head>
                <body>
                    <h1>{status_code} {error_title}</h1>
                    <p>{error_message}</p>
                </body>
                </html>
                """
            raise
            
        # Render the template
        return template.render(**context)

    @inject
    async def _default_error_handler(self, error: Exception, response: ResponseBuilder = dependency(), request: Request = dependency()):
        logger.exception("Unhandled exception", exc_info=error)
        
        # Check if the error is a ServException subclass and use its status code
        status_code = getattr(error, "status_code", 500) if isinstance(error, ServException) else 500
        response.set_status(status_code)
        
        # Check if the client accepts HTML
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header:
            # Use HTML response
            response.content_type("text/html")
            context = {
                "status_code": status_code,
                "error_title": "Error",
                "error_message": "An unexpected error occurred.",
                "error_type": type(error).__name__,
                "error_str": str(error),
                "traceback": "".join(traceback.format_exception(error)),
                "request_path": request.path,
                "request_method": request.method,
                "show_details": self._dev_mode
            }
            
            html_content = self._render_template("error/500.html", context)
            response.body(html_content)
        elif "application/json" in accept_header:
            # Use JSON response
            response.content_type("application/json")
            error_data = {
                "status_code": status_code,
                "error": type(error).__name__,
                "message": str(error) if self._dev_mode else "An unexpected error occurred.",
                "path": request.path,
                "method": request.method
            }
            
            if self._dev_mode:
                error_data["traceback"] = traceback.format_exception(error)
                
            response.body(json.dumps(error_data))
        else:
            # Use plaintext response
            response.content_type("text/plain")
            error_message = f"{status_code} Error: {type(error).__name__}: {error}" if self._dev_mode else f"{status_code} Error: An unexpected error occurred."
            response.body(error_message)

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
                "error_message": error.args[0] if error.args else "The requested resource was not found.",
                "error_type": "NotFound",
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

            error_to_propagate = None
            try:
                # Pass the newly created router_instance to the event
                await self.emit("app.request.begin", container=container)

                # Run middleware stack
                try:
                    await self._run_middleware_stack(container=container, request_instance=request)
                except Exception as e:
                    error_to_propagate = e

                # Handle any errors that occurred
                if error_to_propagate:
                    await container.call(self._run_error_handler, error_to_propagate)

                await self.emit("app.request.end", error=error_to_propagate, container=container)

            except Exception as e:
                logger.exception("Unhandled exception during request processing", exc_info=e)
                await container.call(self._run_error_handler, e)
                await self.emit("app.request.end", error=e, container=container)

            finally:
                # Ensure response is sent. ResponseBuilder.send_response() should be robust
                # enough to handle being called if headers were already sent by an error handler,
                # or to send a default response if nothing was set.
                # Ensure response is sent
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
                # For middleware functions, use container.call to properly inject dependencies
                # Don't await the result since it's an async generator
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
                    # Add route settings to the container using RouteSettings
                    from serv.routing import RouteSettings
                    route_container.instances[RouteSettings] = RouteSettings(**route_settings)
                    
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
