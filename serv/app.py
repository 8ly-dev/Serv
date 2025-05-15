import asyncio
import contextlib
import logging
import traceback
from typing import AsyncIterator, Awaitable, Callable
from bevy import dependency, get_registry, inject
from bevy.containers import Container
from bevy.registries import Registry
from starlette.types import Scope, Receive, Send

from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.injectors import inject_request_object

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
        self._error_handlers = {}

        self._init_container()

    def _init_container(self):
        inject_request_object.register_hook(self._registry)
        self._container.instances[App] = self
        self._container.instances[Container] = self._container
        self._container.instances[Registry] = self._registry

    def add_error_handler(self, error_type: type[Exception], handler: Callable[[Exception], Awaitable[None]]):
        self._error_handlers[error_type] = handler

    def add_middleware(self, middleware: Callable[[], AsyncIterator[None]]):
        self._middleware.append(middleware)

    async def emit(self, event: str, *, container: Container | None = None, **kwargs):
        async with asyncio.TaskGroup() as tg:
            for plugin in self._plugins:
                tg.create_task((container or self._container).call(plugin.on, event, **kwargs))
    
    async def handle_lifespan(self, scope: Scope, receive: Receive, send: Send):
        async for event in self._lifespan_iterator(receive):
            match event:
                case {"type": "lifespan.startup"}:
                    logger.debug("Lifespan startup event")
                    await self.emit("startup", scope=scope)
                    await send({"type": "lifespan.startup.complete"})

                case {"type": "lifespan.shutdown"}:
                    logger.debug("Lifespan shutdown event")
                    await self.emit("shutdown", scope=scope)
                    await self._async_exit_stack.aclose()
                    await send({"type": "lifespan.shutdown.complete"})

    @inject
    async def _default_error_handler(self, error: Exception, response: ResponseBuilder = dependency()):
        response.status_code = 500
        response.content_type("text/html")

        response.body(b"<html><body><h1>Internal Server Error</h1>")
        response.body(b"<p>Traceback:</p><pre>")
        response.body(traceback.format_exc().encode("utf-8"))
        response.body(b"</pre>")
        response.body(b"</body></html>")

    @inject
    async def _run_error_handler(self, error: Exception, container: Container = dependency()):
        handler = self._error_handlers.get(type(error), self._default_error_handler)
        try:
            await container.call(handler, error)
        except Exception as e:
            logger.exception("Error in error handler", exc_info=True)
            e.__context__ = error
            await container.call(self._default_error_handler, e)

    async def _lifespan_iterator(self, receive: Receive):
        event = {}
        while event.get("type") != "lifespan.shutdown":
            event = await receive()
            yield event

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        match scope:
            case {"type": "lifespan"}:
                await self.handle_lifespan(scope, receive, send)

            case _:
                await self._handle_request(scope, receive, send)

    async def _handle_request(self, scope: Scope, receive: Receive, send: Send):
        with self._container.branch() as container:
            container.instances[Request] = Request(scope, receive)
            container.instances[ResponseBuilder] = ResponseBuilder(send)
            container.instances[Container] = container
            try:
                await self._run_middleware_stack()
            except Exception as e:
                logger.exception("Error in middleware stack", exc_info=True)
                container.instances[ResponseBuilder].clear()
                await container.call(self._run_error_handler, e)
            finally:
                await container.instances[ResponseBuilder].send_response()

    async def _run_middleware_stack(self):
        stack = []
        error = None
        for middleware in self._middleware:
            try:
                middleware_iterator = await self._container.call(middleware)
                await anext(middleware_iterator)
            except Exception as e:
                logger.exception("Error in middleware", exc_info=True)
                error = e
                break
            else:
                stack.append(middleware_iterator)

        for middleware_iterator in reversed(stack):
            try:
                if error:
                    await middleware_iterator.athrow(error)
                    error = None # Only propagate the error once, let the middleware handle it
                else:
                    await anext(middleware_iterator)
            except StopAsyncIteration:
                pass
            except Exception as e:
                logger.exception("Error in middleware", exc_info=True)
                e.__context__ = error
                error = e
        
        if error:
            raise error
