import asyncio
import contextlib
import logging
import traceback
from typing import AsyncIterator, Awaitable, Callable
from bevy import dependency, get_registry, inject
from bevy.containers import Container
from bevy.registries import Registry
from starlette.types import Scope, Receive, Send

from serv.observers import Observer
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.injectors import inject_request_object
from serv.routing import Router, HTTPNotFoundException
from serv.exceptions import HTTPMethodNotAllowedException

logger = logging.getLogger(__name__)


class App:
    """This is the main class for an ASGI application.
    
    It is responsible for handling the incoming requests and delegating them to the appropriate routes.
    """

    def __init__(self):
        self._registry = get_registry()
        self._container = self._registry.create_container()
        self._plugins = []
        self._async_exit_stack = contextlib.AsyncExitStack()
        self._middleware = []
        self._error_handlers: dict[type[Exception], Callable[[Exception], Awaitable[None]]] = {}

        self._init_container()
        self._register_default_error_handlers()

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

    def add_middleware(self, middleware: Callable[[], AsyncIterator[None]]):
        self._middleware.append(middleware)

    def add_plugin(self, plugin: Observer):
        self._plugins.append(plugin)
    async def emit(self, event: str, *, container: Container | None = None, **kwargs):
        container = container or self._container
        async with asyncio.TaskGroup() as tg:
            for plugin in self._plugins:
                tg.create_task(container.call(plugin.on, event, **kwargs))
    
    async def handle_lifespan(self, scope: Scope, receive: Receive, send: Send):
        async for event in self._lifespan_iterator(receive):
            match event:
                case {"type": "lifespan.startup"}:
                    logger.debug("Lifespan startup event")
                    await self.emit("app.lifespan.startup", scope=scope, container=self._container)
                    await send({"type": "lifespan.startup.complete"})

                case {"type": "lifespan.shutdown"}:
                    logger.debug("Lifespan shutdown event")
                    await self.emit("app.lifespan.shutdown", scope=scope, container=self._container)
                    await self._async_exit_stack.aclose()
                    await send({"type": "lifespan.shutdown.complete"})

    @inject
    async def _default_error_handler(self, error: Exception, response: ResponseBuilder = dependency(), request: Request = dependency()):
        status_code = getattr(error, 'status_code', 500)
        response.set_status(status_code)
        response.content_type("text/html")

        response.body(f"<html><body><h1>Error {status_code}</h1>")
        response.body(f"<p>{type(error).__name__}: {str(error)}</p>")
        if status_code == 500:
            response.body(b"<p>Traceback:</p><pre>")
            response.body(traceback.format_exc().encode(response._default_encoding))
            response.body(b"</pre>")
        response.body(b"</body></html>")

    @inject
    async def _default_404_handler(self, error: HTTPNotFoundException, response: ResponseBuilder = dependency(), request: Request = dependency()):
        response.set_status(HTTPNotFoundException.status_code)
        response.content_type("text/plain")
        response.body(f"Not Found: The requested resource {request.path} was not found.")

    @inject
    async def _default_405_handler(self, error: HTTPMethodNotAllowedException, response: ResponseBuilder = dependency(), request: Request = dependency()):
        response.set_status(HTTPMethodNotAllowedException.status_code)
        response.content_type("text/plain")
        response.body(f"Method Not Allowed: {error.args[0] if error.args else 'Unknown reason'}")
        if error.allowed_methods:
            response.add_header("Allow", ", ".join(error.allowed_methods))

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
            container.instances[Request] = request
            response_builder = ResponseBuilder(send)
            container.instances[ResponseBuilder] = response_builder
            container.instances[Container] = container
            container.instances[Router] = Router()

            error_occurred_in_stack = False
            try:
                await self.emit("app.request.begin", container=container, scope=scope, request=request)
                await self._run_middleware_stack(container=container, request_instance=request)
                await self.emit("app.request.end", container=container, scope=scope, request=request, error=None)
            except Exception as e:
                error_occurred_in_stack = True
                logger.exception("Unhandled exception during request processing", exc_info=e)
                await container.call(self._run_error_handler, e)
                await self.emit("app.request.end", container=container, scope=scope, request=request, error=e)
            finally:
                # Ensure response is sent. ResponseBuilder.send_response() should be robust
                # enough to handle being called if headers were already sent by an error handler,
                # or to send a default response if nothing was set.
                try:
                    await response_builder.send_response()
                except Exception as final_send_exc:
                    logger.error("Exception during final send_response", exc_info=final_send_exc)

    @inject
    async def _run_middleware_stack(self, container: Container, request_instance: Request):
        stack = []
        error_to_propagate = None

        for middleware_factory in self._middleware:
            try:
                middleware_iterator = await container.call(middleware_factory)
                await anext(middleware_iterator)
            except Exception as e:
                logger.exception(f"Error during setup of middleware {getattr(middleware_factory, '__name__', str(middleware_factory))}", exc_info=True)
                error_to_propagate = e
                break 
            else:
                stack.append(middleware_iterator)

        if not error_to_propagate:
            await self.emit("app.request.before_router", container=container, request=request_instance)
            try:
                router = container.get(Router)
                resolved_route_info = router.resolve_route(request_instance.path, request_instance.method)
                if not resolved_route_info:
                    raise HTTPNotFoundException(f"No route found for {request_instance.method} {request_instance.path}")
                
            except Exception as e: 
                logger.info(f"Router resolution resulted in exception: {type(e).__name__}: {e}")
                error_to_propagate = e

            else:
                handler_callable, path_params = resolved_route_info
                try:
                    await container.call(handler_callable, request_instance, **path_params)
                except Exception as e:
                    logger.info(f"Handler execution resulted in exception: {type(e).__name__}: {e}")
                    error_to_propagate = e

            await self.emit("app.request.after_router", container=container, request=request_instance, error=error_to_propagate)

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
