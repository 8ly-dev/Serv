from bevy import dependency
from bevy.containers import Container


class ServMiddleware:
    """
    Base class for Serv middleware, providing enter, leave, and on_error hooks.
    """

    def __init__(self, config: dict | None = None, container: Container = dependency()):
        self._container = container
        self._config = config

    def __aiter__(self):
        return self._create_iterator()

    async def _create_iterator(self):
        await self._container.call(self.enter)
        try:
            yield
        except Exception as e:
            await self._container.call(self.on_error, e)
        else:
            await self._container.call(self.leave)

    async def enter(self):
        """
        Called before the request is processed further.
        Override to inspect/modify the request or return an early response.
        """
        pass

    async def leave(self):
        """
        Called after the request has been processed and a response is available.
        Override to inspect/modify the response. This is not called if an exception occurred
        during request processing.
        """
        pass

    async def on_error(self, exc: Exception):
        """
        Called if an exception occurs during request processing after 'enter'.
        Override to handle errors and optionally return a custom error response.

        The base implementation raises the exception again.

        Args:
            exc: The exception that occurred.
        """
        raise exc
