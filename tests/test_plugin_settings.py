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
from serv.plugin_loader import PluginSpec
from serv.responses import ResponseBuilder


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
                
            # Handler with dependency injection
            async def handle_with_settings(self, response: ResponseBuilder = dependency(), test_setting: str = dependency()):
                response.content_type("text/plain")
                response.body(f"Setting value: {test_setting}")

            async def on_app_request_begin(self, router: Router = dependency()):
                router.add_route("/test", self.handle_test, methods=["GET"], settings={"route_setting": "route_value"})
                router.add_route("/test_with_settings", self.handle_with_settings, methods=["GET"], settings={"test_setting": "injected_value"})
        
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
async def test_route_settings():
    """Test route-level settings."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0"
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # Set up routes
    await plugin.on_app_request_begin(router)
    
    # Resolve a route and check settings
    resolved = router.resolve_route("/test", "GET")
    assert resolved is not None
    
    handler, params, settings = resolved
    assert settings == {"route_setting": "route_value"}


@pytest.mark.asyncio
async def test_settings_injection():
    """Test that settings are properly injected into handlers."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0"
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # Set up routes
    await plugin.on_app_request_begin(router)
    
    # Resolve the route
    resolved = router.resolve_route("/test_with_settings", "GET")
    assert resolved is not None
    
    handler, params, settings = resolved
    
    # Verify that settings contain the expected value
    assert "test_setting" in settings
    assert settings["test_setting"] == "injected_value"
    
    # Just verify the key settings structure is correct
    assert isinstance(settings, dict)
    assert len(settings) > 0


@pytest.mark.asyncio
async def test_mounted_router_settings():
    """Test that settings from mounted routers are properly merged."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0"
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    registry = Registry()
    container = registry.create_container()
    main_router = Router(settings={"main_setting": "main_value", "shared_setting": "main_level"})
    api_router = Router(settings={"api_setting": "api_value", "shared_setting": "api_level"})
    container.instances[Router] = main_router
    
    # Mount the API router
    main_router.mount("/api", api_router)
    
    # Set up routes on both routers
    await plugin.on_app_request_begin(main_router)
    await plugin.on_app_request_begin(api_router)
    
    # Resolve a route on the mounted router
    resolved = main_router.resolve_route("/api/test", "GET")
    assert resolved is not None
    
    handler, params, settings = resolved
    
    # Check settings inheritance and overriding
    assert settings["main_setting"] == "main_value"
    assert settings["api_setting"] == "api_value"
    assert settings["route_setting"] == "route_value"
    assert settings["shared_setting"] == "api_level"  # Most specific wins 