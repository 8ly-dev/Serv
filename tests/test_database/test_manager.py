"""Tests for database manager."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bevy import get_registry

from serv.database.exceptions import DatabaseConfigurationError
from serv.database.manager import DatabaseManager


class TestDatabaseManager:
    """Test DatabaseManager functionality."""

    def test_init_no_databases(self):
        """Test initialization with no database configuration."""
        config = {}
        registry = get_registry()
        container = registry.create_container()
        manager = DatabaseManager(config, container)

        assert manager.config == {}
        assert manager.connections == {}

    def test_init_with_databases(self):
        """Test initialization with database configuration."""
        config = {
            "databases": {
                "test_db": {"provider": "test.provider:factory", "qualifier": "test"}
            }
        }
        registry = get_registry()
        container = registry.create_container()
        manager = DatabaseManager(config, container)

        assert "test_db" in manager.config

    @pytest.mark.asyncio
    async def test_initialize_databases_empty_config(self):
        """Test initializing with empty database config."""
        config = {}
        registry = get_registry()
        container = registry.create_container()
        manager = DatabaseManager(config, container)

        # Should not raise any errors
        await manager.initialize_databases()
        assert manager.connections == {}

    @pytest.mark.asyncio
    async def test_create_connection_missing_provider(self):
        """Test creating connection with missing provider."""
        config = {}
        registry = get_registry()
        container = registry.create_container()
        manager = DatabaseManager(config, container)

        db_config = {"qualifier": "test"}  # Missing provider

        with pytest.raises(
            DatabaseConfigurationError, match="missing required 'provider' field"
        ):
            await manager.create_connection("test_db", db_config)

    @pytest.mark.asyncio
    async def test_create_connection_success(self):
        """Test successful connection creation."""
        config = {}
        registry = get_registry()
        container = registry.create_container()
        manager = DatabaseManager(config, container)

        # Mock the factory loading
        original_load_factory = None
        original_invoke_factory = None

        try:
            from serv.database.factory import FactoryLoader

            original_load_factory = FactoryLoader.load_factory
            original_invoke_factory = FactoryLoader.invoke_factory

            # Mock factory function
            mock_connection = MagicMock()
            mock_factory = AsyncMock(return_value=mock_connection)

            FactoryLoader.load_factory = MagicMock(return_value=mock_factory)
            FactoryLoader.invoke_factory = AsyncMock(return_value=mock_connection)

            db_config = {"provider": "test.provider:factory"}
            result = await manager.create_connection("test_db", db_config)

            assert result == mock_connection
            FactoryLoader.load_factory.assert_called_once_with("test.provider:factory")
            FactoryLoader.invoke_factory.assert_called_once_with(
                mock_factory, "test_db", db_config
            )

        finally:
            # Restore original methods
            if original_load_factory:
                FactoryLoader.load_factory = original_load_factory
            if original_invoke_factory:
                FactoryLoader.invoke_factory = original_invoke_factory

    def test_register_with_di(self):
        """Test registering connection with DI container."""
        config = {}
        registry = get_registry()
        container = registry.create_container()
        manager = DatabaseManager(config, container)

        # Mock connection
        mock_connection = MagicMock()
        mock_connection.__class__ = type("MockDB", (), {})

        # Register with DI
        manager.register_with_di("test_db", mock_connection)

        # Verify registration (this tests that the method runs without error)
        # The actual DI testing would require a more complex setup

    @pytest.mark.asyncio
    async def test_shutdown_databases(self):
        """Test shutting down databases."""
        config = {}
        registry = get_registry()
        container = registry.create_container()
        manager = DatabaseManager(config, container)

        # Add a mock connection
        manager.connections["test_db"] = MagicMock()

        # Should not raise errors
        await manager.shutdown_databases()
        assert manager.connections == {}
