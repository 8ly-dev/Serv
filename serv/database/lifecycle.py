"""Database connection lifecycle management."""

import inspect
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Any

from .exceptions import DatabaseLifecycleError

if TYPE_CHECKING:
    from .manager import DatabaseManager


class DatabaseLifecycle:
    """
    Manages database connection lifecycle within app context.
    Integrates with app startup/shutdown and exit stack management.
    """

    def __init__(self, manager: "DatabaseManager", exit_stack: AsyncExitStack):
        """Initialize lifecycle manager.

        Args:
            manager: DatabaseManager instance
            exit_stack: Async exit stack for cleanup registration
        """
        self.manager = manager
        self.exit_stack = exit_stack

    async def startup_databases(self) -> None:
        """Initialize databases during app startup.

        Raises:
            DatabaseLifecycleError: If database startup fails
        """
        try:
            await self.manager.initialize_databases()
        except Exception as e:
            raise DatabaseLifecycleError(
                f"Failed to startup databases: {str(e)}"
            ) from e

    async def shutdown_databases(self) -> None:
        """Cleanup databases during app shutdown.

        Raises:
            DatabaseLifecycleError: If database shutdown fails
        """
        try:
            await self.manager.shutdown_databases()
        except Exception as e:
            raise DatabaseLifecycleError(
                f"Failed to shutdown databases: {str(e)}"
            ) from e

    def register_cleanup(self, connection: Any) -> None:
        """Register connection cleanup with exit stack.

        Args:
            connection: Database connection to register for cleanup
        """
        if hasattr(connection, "_cleanup"):
            self.exit_stack.push_async_callback(connection._cleanup)
        elif hasattr(connection, "close"):
            if inspect.iscoroutinefunction(connection.close):
                self.exit_stack.push_async_callback(connection.close)
            else:
                self.exit_stack.callback(connection.close)
        elif hasattr(connection, "__aexit__"):
            self.exit_stack.push_async_exit(connection)
