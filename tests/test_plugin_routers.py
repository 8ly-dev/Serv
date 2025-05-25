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
from serv.responses import ResponseBuilder
from serv.plugin_loader import PluginSpec


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
            async def handle_test(self, response: ResponseBuilder = dependency()):
                response.content_type("text/plain")
                response.body("test response")

            async def on_app_request_begin(self, router: Router = dependency()):
                router.add_route("/test", self.handle_test, methods=["GET"])
        
        plugin = TestPlugin()
        plugin._plugin_spec = PluginSpec(
            config={
                "name": plugin_yaml_content["name"],
                "description": plugin_yaml_content["description"],
                "version": plugin_yaml_content["version"],
                "author": "Test Author"
            },
            path=plugin_dir,
            override_settings={}
        )
    
    # Return the plugin and a reference to the temporary directory
    # to keep it alive during the test
    return plugin, temp_dir


@pytest.mark.asyncio
async def test_plugin_router_config_basic():
    """Test basic router configuration."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0"
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # Call the event handler to set up routes
    await plugin.on_app_request_begin(router)
    
    # Verify router was created and set up correctly
    assert len(router._routes) == 1
    
    # Check that the route was added correctly
    path, methods, handler, _ = router._routes[0]
    assert path == "/test"
    assert "GET" in methods
    assert handler is not None


@pytest.mark.asyncio
async def test_plugin_router_mounting():
    """Test router mounting configuration."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0"
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    main_router = Router()
    api_router = Router()
    container.instances[Router] = main_router
    
    # Mount the API router
    main_router.mount("/api", api_router)
    
    # Add routes to both routers
    await plugin.on_app_request_begin(main_router)
    await plugin.on_app_request_begin(api_router)
    
    # Verify routers were created
    assert len(main_router._routes) == 1
    assert len(api_router._routes) == 1
    
    # Check that the main router has the api router mounted
    assert len(main_router._mounted_routers) == 1
    
    # Verify the mount path
    mount_path, mounted_router = main_router._mounted_routers[0]
    assert mount_path == "/api"


@pytest.mark.asyncio
async def test_plugin_on_app_startup():
    """Test that routers are set up during app startup."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0"
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # Call the event handler to set up routes
    await plugin.on_app_request_begin(router)
    
    # Verify router was created and set up correctly
    assert len(router._routes) == 1
    
    # Check that the route was added correctly
    path, methods, handler, _ = router._routes[0]
    assert path == "/test"
    assert "GET" in methods
    assert handler is not None


def test_plugin_import_handler():
    """Test the handler import functionality."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0"
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    
    # Test simple colon-separated import (module.path:ClassName)
    with patch('importlib.import_module') as mock_import:
        mock_module = MagicMock()
        mock_handler_class = MagicMock()
        mock_module.TestHandler = mock_handler_class
        mock_import.return_value = mock_module
        
        # Test importing a handler
        from serv.config import import_from_string
        handler = import_from_string("some.module:TestHandler")
        
        # Verify the import was called correctly
        mock_import.assert_called_with("some.module")
        
        # Verify the handler was returned
        assert handler == mock_handler_class
    
    # Test nested colon-separated import (module.path:object.attribute.ClassName)
    with patch('importlib.import_module') as mock_import:
        # Setup nested structure
        nested_attr = MagicMock()
        nested_class = MagicMock()
        nested_attr.NestedClass = nested_class
        
        mock_module = MagicMock()
        mock_module.object = MagicMock()
        mock_module.object.attribute = nested_attr
        
        mock_import.return_value = mock_module
        
        # Test importing a handler with nested path
        handler = import_from_string("some.module:object.attribute.NestedClass")
        
        # Verify the import was called correctly
        mock_import.assert_called_with("some.module")
        
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
    
    # Attempt to use dot notation should raise ServConfigError
    from serv.config import import_from_string, ServConfigError
    with pytest.raises(ServConfigError) as excinfo:
        import_from_string("some.module.TestHandler")
    assert "Invalid import string format" in str(excinfo.value) 