"""
Request/response logging middleware for Serv demo.
"""

import logging
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

from bevy import dependency
from bevy.containers import Container

from serv.requests import Request
from serv.responses import ResponseBuilder

logger = logging.getLogger("serv.middleware.logging")


def request_logger_middleware(
    config: dict[str, Any] | None = None,
) -> Callable[[], AsyncIterator[None]]:
    """
    Middleware factory that logs request details.

    Args:
        config: Optional configuration dictionary

    Returns:
        A middleware factory function that returns an async iterator
    """
    if config is None:
        config = {}

    log_level = config.get("level", "INFO")
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # This function will be called by container.call() during middleware setup
    async def middleware_generator() -> AsyncIterator[None]:
        dependency(Container)
        request = dependency(Request)

        # Record the start time
        start_time = time.time()

        # Log the request
        logger.info(f"Request started: {request.method} {request.path}")

        if config.get("log_headers", False):
            for name, value in request.headers.items():
                logger.debug(f"Header: {name}: {value}")

        try:
            # Proceed with the middleware chain
            yield

            # Get response after the request has been processed
            response = dependency(ResponseBuilder)

            # Log the successful response
            duration = time.time() - start_time
            status = response.status or 200
            logger.info(
                f"Request completed: {request.method} {request.path} - {status} ({duration:.3f}s)"
            )

        except Exception as exc:
            # Log the error
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.path} - {type(exc).__name__}: {exc} ({duration:.3f}s)"
            )

            # Re-raise the exception
            raise

    return middleware_generator
