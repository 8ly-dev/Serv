"""Database manager for handling multiple database connections."""

from contextlib import AsyncExitStack
from typing import Any

from bevy import Container

from .exceptions import DatabaseConfigurationError, DatabaseConnectionError
from .factory import FactoryLoader
from .lifecycle import DatabaseLifecycle


class DatabaseManager:
    """
    Manages database connections defined in configuration.
    Handles factory loading, connection lifecycle, and DI registration.
    """

    def __init__(self, app_config: dict[str, Any], container: Container):
        """Initialize database manager.

        Args:
            app_config: Application configuration dictionary
            container: Bevy DI container for registering connections
        """
        self.config = app_config.get("databases", {})
        self.container = container
        self.connections: dict[str, Any] = {}
        self.exit_stack = AsyncExitStack()
        self.lifecycle = DatabaseLifecycle(self, self.exit_stack)

    async def initialize_databases(self) -> None:
        """Initialize all configured database connections.

        Raises:
            DatabaseConfigurationError: If configuration is invalid
            DatabaseConnectionError: If connection creation fails
        """
        if not self.config:
            return  # No databases configured

        for name, db_config in self.config.items():
            try:
                connection = await self.create_connection(name, db_config)
                self.connections[name] = connection

                # Register with DI container
                self.register_connection(name, connection)

                # Register cleanup
                self.lifecycle.register_cleanup(connection)

            except Exception as e:
                raise DatabaseConnectionError(
                    f"Failed to initialize database '{name}': {str(e)}"
                ) from e

    async def shutdown_databases(self) -> None:
        """Shutdown all database connections."""
        await self.exit_stack.aclose()
        self.connections.clear()

    def register_connection(self, name: str, connection: Any) -> None:
        """Register database connection with dependency injection using Bevy 3.1 qualifiers.

        Args:
            name: Database name
            connection: Database connection instance
        """
        # Register by factory return type with qualifier
        # This allows multiple instances of the same type (e.g., multiple Ommi instances)
        self.container.add(type(connection), connection, qualifier=name)

    async def create_connection(self, name: str, config: dict[str, Any]) -> Any:
        """Create single database connection from config with qualifier support.

        Args:
            name: Database name
            config: Database configuration

        Returns:
            Database connection instance

        Raises:
            DatabaseConfigurationError: If configuration is invalid
            DatabaseConnectionError: If connection creation fails
        """
        if "provider" not in config:
            raise DatabaseConfigurationError(
                f"Database '{name}' missing required 'provider' field"
            )

        provider = config["provider"]

        try:
            # Load factory function
            factory = FactoryLoader.load_factory(provider)

            # Create connection using factory
            connection = await FactoryLoader.invoke_factory(factory, name, config)

            return connection

        except Exception as e:
            raise DatabaseConnectionError(
                f"Failed to create connection for database '{name}': {str(e)}"
            ) from e
