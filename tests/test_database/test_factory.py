"""Tests for database factory loading system."""

import pytest

from serv.database.exceptions import DatabaseFactoryError
from serv.database.factory import FactoryLoader


class TestFactoryLoader:
    """Test factory loading functionality."""

    def test_load_factory_valid_provider(self):
        """Test loading a valid factory function."""
        # Use a built-in function for testing
        factory = FactoryLoader.load_factory("builtins:len")
        assert callable(factory)
        assert factory([1, 2, 3]) == 3

    def test_load_factory_invalid_format(self):
        """Test loading factory with invalid format."""
        with pytest.raises(DatabaseFactoryError, match="Invalid provider format"):
            FactoryLoader.load_factory("invalid_format")

    def test_load_factory_missing_module(self):
        """Test loading factory from missing module."""
        with pytest.raises(DatabaseFactoryError, match="Failed to load provider"):
            FactoryLoader.load_factory("non_existent_module:function")

    def test_load_factory_missing_function(self):
        """Test loading missing function from valid module."""
        with pytest.raises(DatabaseFactoryError, match="Failed to load provider"):
            FactoryLoader.load_factory("builtins:non_existent_function")

    def test_detect_config_style_nested(self):
        """Test detecting nested config style."""
        config = {"settings": {"key": "value"}}
        assert FactoryLoader.detect_config_style(config) == "nested"

    def test_detect_config_style_flat(self):
        """Test detecting flat config style."""
        config = {"key": "value", "another_key": "another_value"}
        assert FactoryLoader.detect_config_style(config) == "flat"

    def test_bind_flat_parameters(self):
        """Test binding flat parameters to function signature."""

        def test_func(name: str, param1: str, param2: int = 10):
            return f"{name}: {param1}, {param2}"

        config = {"param1": "test_value", "param2": 20}
        args, kwargs = FactoryLoader.bind_flat_parameters(test_func, config)

        assert args == ()
        assert kwargs == {"param1": "test_value", "param2": 20}

    def test_bind_flat_parameters_missing_required(self):
        """Test binding with missing required parameter."""

        def test_func(name: str, required_param: str):
            return f"{name}: {required_param}"

        config = {}  # Missing required_param

        with pytest.raises(DatabaseFactoryError, match="Required parameter"):
            FactoryLoader.bind_flat_parameters(test_func, config)

    @pytest.mark.asyncio
    async def test_invoke_factory_sync_nested(self):
        """Test invoking sync factory with nested config."""

        def sync_factory(name: str, settings: dict = None):
            settings = settings or {}
            return f"sync:{name}:{settings.get('key', 'default')}"

        config = {"settings": {"key": "test_value"}}
        result = await FactoryLoader.invoke_factory(sync_factory, "test_db", config)

        assert result == "sync:test_db:test_value"

    @pytest.mark.asyncio
    async def test_invoke_factory_async_nested(self):
        """Test invoking async factory with nested config."""

        async def async_factory(name: str, settings: dict = None):
            settings = settings or {}
            return f"async:{name}:{settings.get('key', 'default')}"

        config = {"settings": {"key": "test_value"}}
        result = await FactoryLoader.invoke_factory(async_factory, "test_db", config)

        assert result == "async:test_db:test_value"

    @pytest.mark.asyncio
    async def test_invoke_factory_sync_flat(self):
        """Test invoking sync factory with flat config."""

        def sync_factory(name: str, param1: str, param2: int = 10):
            return f"sync:{name}:{param1}:{param2}"

        config = {"param1": "test_value", "param2": 20}
        result = await FactoryLoader.invoke_factory(sync_factory, "test_db", config)

        assert result == "sync:test_db:test_value:20"

    @pytest.mark.asyncio
    async def test_invoke_factory_async_flat(self):
        """Test invoking async factory with flat config."""

        async def async_factory(name: str, param1: str, param2: int = 10):
            return f"async:{name}:{param1}:{param2}"

        config = {"param1": "test_value", "param2": 20}
        result = await FactoryLoader.invoke_factory(async_factory, "test_db", config)

        assert result == "async:test_db:test_value:20"
