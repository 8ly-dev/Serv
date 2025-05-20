import os
import tempfile
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
import yaml

from bevy import dependency, get_registry
from bevy.containers import Container
from bevy.registries import Registry
from serv.plugins import Plugin
from serv.routing import Router


def create_plugin_with_config(plugin_yaml_content):
    """Helper to create a plugin with specific configuration."""
    temp_dir = tempfile.TemporaryDirectory()
    plugin_dir = Path(temp_dir.name)
    
    # Create plugin.yaml file
    with open(plugin_dir / "plugin.yaml", "w") as f:
        yaml.dump(plugin_yaml_content, f)

    # Create temporary plugin class
    with patch('serv.plugins.search_for_plugin_directory') as mock_search:
        mock_search.return_value = plugin_dir
        
        class TestPlugin(Plugin):
            # Test handler method
            async def handle_test(self, **kwargs):
                return "test response"
        
        plugin = TestPlugin()
    
    # Return the plugin and a reference to the temporary directory
    # to keep it alive during the test
    return plugin, temp_dir


def test_plugin_router_config_basic():
    """Test basic router configuration."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0",
        "routers": [
            {
                "name": "test_router",
                "routes": [
                    {
                        "path": "/test",
                        "handler_method": "handle_test"
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    
    # Set up routers from config
    routers = plugin.setup_routers(container)
    
    # Verify router was created and set up correctly
    assert len(routers) == 1
    assert len(routers[0]._routes) == 1
    
    # Check that the route was added correctly
    path, methods, handler, _ = routers[0]._routes[0]
    assert path == "/test"
    assert handler is not None


def test_plugin_router_mounting():
    """Test router mounting configuration."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0",
        "routers": [
            {
                "name": "main_router",
                "routes": [
                    {
                        "path": "/",
                        "handler_method": "handle_test"
                    }
                ]
            },
            {
                "name": "api_router",
                "routes": [
                    {
                        "path": "/test",
                        "handler_method": "handle_test"
                    }
                ],
                "mount_at": "/api",
                "mount_to": "main_router"
            }
        ]
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    
    # Set up routers from config
    routers = plugin.setup_routers(container)
    
    # Verify routers were created
    assert len(routers) == 2
    
    # Check that the main router has the api router mounted
    main_router = next(r for i, r in enumerate(routers) if i == 0)
    assert len(main_router._mounted_routers) == 1
    
    # Verify the mount path
    mount_path, mounted_router = main_router._mounted_routers[0]
    assert mount_path == "/api"


def test_plugin_on_app_startup():
    """Test that routers are set up during app startup."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0",
        "routers": [
            {
                "name": "test_router",
                "routes": [
                    {
                        "path": "/test",
                        "handler_method": "handle_test"
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    
    # Create a mocked container for the test
    mock_container = MagicMock()
    mock_container.instances = {}
    
    # Mock Router for the test
    mock_router = Router()
    
    # Call the on_app_startup method with our mocked objects
    with patch.object(plugin, 'setup_routers', return_value=[mock_router]):
        # We need to inject the real Router class
        from serv.routing import Router as RealRouter
        plugin.on_app_startup(MagicMock(), mock_container)
        
        # After the method executes, the Router should be in the container instances
        assert RealRouter in mock_container.instances
        assert mock_container.instances[RealRouter] == mock_router


def test_plugin_import_handler():
    """Test the handler import functionality."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0"
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    
    # Test simple colon-separated import (module.path:ClassName)
    with patch('builtins.__import__') as mock_import:
        mock_module = MagicMock()
        mock_handler_class = MagicMock()
        mock_module.TestHandler = mock_handler_class
        mock_import.return_value = mock_module
        
        # Test importing a handler
        handler = plugin._import_handler("some.module:TestHandler")
        
        # Verify the import was called correctly
        mock_import.assert_called_with("some.module", fromlist=["__name__"])
        
        # Verify the handler was returned
        assert handler == mock_handler_class
    
    # Test nested colon-separated import (module.path:object.attribute.ClassName)
    with patch('builtins.__import__') as mock_import:
        # Setup nested structure
        nested_attr = MagicMock()
        nested_class = MagicMock()
        nested_attr.NestedClass = nested_class
        
        mock_module = MagicMock()
        mock_module.object = MagicMock()
        mock_module.object.attribute = nested_attr
        
        mock_import.return_value = mock_module
        
        # Test importing a handler with nested path
        handler = plugin._import_handler("some.module:object.attribute.NestedClass")
        
        # Verify the import was called correctly
        mock_import.assert_called_with("some.module", fromlist=["__name__"])
        
        # Verify we got the nested object
        assert handler == nested_class

def test_plugin_import_handler_rejects_dot_notation():
    """Test that dot notation for handlers is rejected."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0"
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    
    # Attempt to use dot notation should return None after logging error
    with patch('logging.Logger.error') as mock_error:
        handler = plugin._import_handler("some.module.TestHandler")
        assert handler is None
        mock_error.assert_called_once() 