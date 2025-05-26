"""
Regression tests for declarative router functionality.

These tests ensure that the declarative router feature continues to work
correctly after changes to the PluginSpec class and related infrastructure.
"""
import tempfile
from pathlib import Path
import pytest
import yaml
from unittest.mock import MagicMock

from serv.plugins.router_plugin import RouterPlugin, RouterBuilder
from serv.plugins.loader import PluginSpec
from serv.routing import Router
from tests.helpers import create_mock_importer


def test_router_plugin_with_plugin_spec():
    """Test that RouterPlugin works correctly with PluginSpec that has an importer."""
    # Create a plugin config with routers
    plugin_config = {
        "name": "Test Router Plugin",
        "description": "A test plugin with declarative routers",
        "version": "1.0.0",
        "routers": [
            {
                "name": "test_router",
                "routes": [
                    {
                        "path": "/test",
                        "handler": "handlers:TestHandler"
                    }
                ]
            }
        ]
    }
    
    # Create a mock importer
    mock_importer = create_mock_importer()
    
    # Mock the load_module method to return a module with our handler
    mock_module = MagicMock()
    mock_handler = MagicMock()
    mock_module.TestHandler = mock_handler
    mock_importer.load_module.return_value = mock_module
    
    # Create a PluginSpec with the importer
    plugin_spec = PluginSpec(
        config=plugin_config,
        path=Path("."),
        override_settings={},
        importer=mock_importer
    )
    
    # Create the RouterPlugin
    router_plugin = RouterPlugin(plugin_spec=plugin_spec)
    
    # Verify the plugin was initialized correctly
    assert len(router_plugin._routers) == 1
    assert "test_router" in router_plugin._routers
    
    # Verify the router builder was created correctly
    router_builder = router_plugin._routers["test_router"]
    assert isinstance(router_builder, RouterBuilder)
    assert router_builder._importer == mock_importer


def test_router_builder_with_importer():
    """Test that RouterBuilder correctly uses the importer to load handlers."""
    # Create a mock importer
    mock_importer = create_mock_importer()
    
    # Mock the load_module method
    mock_module = MagicMock()
    mock_handler = MagicMock()
    mock_module.TestHandler = mock_handler
    mock_importer.load_module.return_value = mock_module
    
    # Create route configurations
    routes = [
        {
            "path": "/test",
            "handler": "handlers:TestHandler"
        }
    ]
    
    # Create RouterBuilder
    builder = RouterBuilder(
        mount_path=None,
        settings={},
        routes=routes,
        importer=mock_importer
    )
    
    # Create main router
    main_router = Router()
    
    # Build the router
    builder.build(main_router)
    
    # Verify the importer was called correctly
    mock_importer.load_module.assert_called_once_with("handlers")
    
    # Verify the router was added to the main router
    assert len(main_router._sub_routers) == 1


def test_plugin_spec_requires_importer():
    """Test that PluginSpec requires an importer parameter."""
    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "version": "1.0.0"
    }
    
    # This should raise a TypeError because importer is required
    with pytest.raises(TypeError, match="missing 1 required positional argument: 'importer'"):
        PluginSpec(
            config=plugin_config,
            path=Path("."),
            override_settings={}
            # Missing importer parameter
        )


def test_plugin_spec_from_path_requires_importer():
    """Test that PluginSpec.from_path requires an importer parameter."""
    # Create a temporary plugin directory
    with tempfile.TemporaryDirectory() as temp_dir:
        plugin_dir = Path(temp_dir)
        
        # Create plugin.yaml
        plugin_config = {
            "name": "Test Plugin",
            "description": "A test plugin",
            "version": "1.0.0"
        }
        
        with open(plugin_dir / "plugin.yaml", "w") as f:
            yaml.dump(plugin_config, f)
        
        # This should raise a TypeError because importer is required
        with pytest.raises(TypeError, match="missing 1 required positional argument: 'importer'"):
            PluginSpec.from_path(
                path=plugin_dir,
                override_settings={}
                # Missing importer parameter
            )


def test_router_plugin_handles_empty_routers():
    """Test that RouterPlugin handles plugins with no routers configuration."""
    plugin_config = {
        "name": "Empty Router Plugin",
        "description": "A plugin with no routers",
        "version": "1.0.0"
        # No routers key
    }
    
    mock_importer = create_mock_importer()
    
    plugin_spec = PluginSpec(
        config=plugin_config,
        path=Path("."),
        override_settings={},
        importer=mock_importer
    )
    
    # This should not raise an error
    router_plugin = RouterPlugin(plugin_spec=plugin_spec)
    
    # Should have no routers
    assert len(router_plugin._routers) == 0


def test_router_builder_error_handling():
    """Test that RouterBuilder properly handles errors when loading handlers."""
    # Create a mock importer that raises an error
    mock_importer = create_mock_importer()
    mock_importer.load_module.side_effect = ModuleNotFoundError("Module not found")
    
    # Create route configurations
    routes = [
        {
            "path": "/test",
            "handler": "nonexistent:TestHandler"
        }
    ]
    
    # Create RouterBuilder
    builder = RouterBuilder(
        mount_path=None,
        settings={},
        routes=routes,
        importer=mock_importer
    )
    
    # Create main router
    main_router = Router()
    
    # Building the router should raise an error when trying to load the handler
    with pytest.raises(ModuleNotFoundError):
        builder.build(main_router) 