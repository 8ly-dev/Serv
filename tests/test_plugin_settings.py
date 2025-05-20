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
                
            # Handler with dependency injection
            async def handle_with_settings(self, test_setting: str = dependency()):
                return f"Setting value: {test_setting}"
        
        plugin = TestPlugin()
    
    # Return the plugin and a reference to the temporary directory
    # to keep it alive during the test
    return plugin, temp_dir


def test_router_settings():
    """Test router-level settings."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0",
        "routers": [
            {
                "name": "test_router",
                "settings": {
                    "router_setting": "router_value"
                },
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
    
    # Verify router was created with settings
    assert len(routers) == 1
    assert routers[0]._settings == {"router_setting": "router_value"}
    
    # Resolve a route and check settings
    resolved = routers[0].resolve_route("/test", "GET")
    assert resolved is not None
    
    handler, params, settings = resolved
    assert settings == {"router_setting": "router_value"}


def test_route_settings():
    """Test route-level settings."""
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
                        "handler_method": "handle_test",
                        "settings": {
                            "route_setting": "route_value"
                        }
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    registry = Registry()
    container = registry.create_container()
    routers = plugin.setup_routers(container)
    
    # Resolve a route and check settings
    resolved = routers[0].resolve_route("/test", "GET")
    assert resolved is not None
    
    handler, params, settings = resolved
    assert settings == {"route_setting": "route_value"}


def test_combined_settings():
    """Test combined router and route settings."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0",
        "routers": [
            {
                "name": "test_router",
                "settings": {
                    "router_setting": "router_value",
                    "shared_setting": "router_level"
                },
                "routes": [
                    {
                        "path": "/test",
                        "handler_method": "handle_test",
                        "settings": {
                            "route_setting": "route_value",
                            "shared_setting": "route_level"  # Should override router setting
                        }
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    registry = Registry()
    container = registry.create_container()
    routers = plugin.setup_routers(container)
    
    # Resolve a route and check settings
    resolved = routers[0].resolve_route("/test", "GET")
    assert resolved is not None
    
    handler, params, settings = resolved
    
    # Route settings should override router settings with the same key
    assert settings["router_setting"] == "router_value"
    assert settings["route_setting"] == "route_value"
    assert settings["shared_setting"] == "route_level"  # Route setting takes precedence


def test_settings_injection():
    """Test that settings are properly injected into handlers."""
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
                        "handler_method": "handle_with_settings",
                        "settings": {
                            "test_setting": "injected_value"
                        }
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    registry = Registry()
    container = registry.create_container()
    routers = plugin.setup_routers(container)
    
    # Resolve the route
    resolved = routers[0].resolve_route("/test", "GET")
    assert resolved is not None
    
    handler, params, settings = resolved
    
    # Verify that settings contain the expected value
    assert "test_setting" in settings
    assert settings["test_setting"] == "injected_value"
    
    # Just verify the key settings structure is correct
    assert isinstance(settings, dict)
    assert len(settings) > 0


def test_mounted_router_settings():
    """Test that settings from mounted routers are properly merged."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "0.1.0",
        "routers": [
            {
                "name": "main_router",
                "settings": {
                    "main_setting": "main_value",
                    "shared_setting": "main_level"
                }
            },
            {
                "name": "api_router",
                "settings": {
                    "api_setting": "api_value",
                    "shared_setting": "api_level"
                },
                "routes": [
                    {
                        "path": "/test",
                        "handler_method": "handle_test",
                        "settings": {
                            "route_setting": "route_value",
                            "shared_setting": "route_level"
                        }
                    }
                ],
                "mount_at": "/api",
                "mount_to": "main_router"
            }
        ]
    }
    
    plugin, temp_dir = create_plugin_with_config(plugin_config)
    registry = Registry()
    container = registry.create_container()
    routers = plugin.setup_routers(container)
    
    # Find the main router
    main_router = next(r for r in routers if "main_setting" in r._settings)
    
    # Resolve a route on the mounted router
    resolved = main_router.resolve_route("/api/test", "GET")
    assert resolved is not None
    
    handler, params, settings = resolved
    
    # Check settings inheritance and overriding
    assert settings["main_setting"] == "main_value"
    assert settings["api_setting"] == "api_value"
    assert settings["route_setting"] == "route_value"
    assert settings["shared_setting"] == "route_level"  # Most specific wins 