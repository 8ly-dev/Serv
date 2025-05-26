"""
Tests for the declarative router functionality using RouterPlugin and plugin.yaml routers configuration.
"""
import tempfile
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
import yaml
import asyncio
from httpx import AsyncClient
import sys
import types

from bevy import dependency
from bevy.registries import Registry
from serv.plugins.router_plugin import RouterPlugin
from serv.routing import Router
from serv.responses import ResponseBuilder
from serv.plugins.loader import PluginSpec
from serv.app import App
from tests.helpers import create_mock_importer


def create_declarative_router_plugin(plugin_config):
    """Helper to create a RouterPlugin with specific configuration."""
    temp_dir = tempfile.TemporaryDirectory()
    plugin_dir = Path(temp_dir.name)
    
    # Create a temporary plugin.yaml file
    with open(plugin_dir / "plugin.yaml", "w") as f:
        yaml.dump(plugin_config, f)

    # Create a dummy __init__.py to make it a package
    (plugin_dir / "__init__.py").touch()

    # Create handler modules if needed
    routers_config = plugin_config.get("routers", [])
    for router_config in routers_config:
        routes = router_config.get("routes", [])
        for route in routes:
            handler_str = route.get("handler", "")
            if ":" in handler_str:
                module_name, class_name = handler_str.split(":")
                module_file = plugin_dir / f"{module_name}.py"
                if not module_file.exists():
                    module_file.write_text(f"""
from serv.responses import ResponseBuilder
from bevy import dependency

class {class_name}:
    async def __call__(self, response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body("Hello from {class_name}")
""")

    # Temporarily add the plugin directory to sys.path
    sys.path.insert(0, str(plugin_dir))

    try:
        # Create the plugin spec
        spec = PluginSpec(
            config=plugin_config, 
            path=plugin_dir, 
            override_settings={}, 
            importer=create_mock_importer(plugin_dir)
        )
        
        # Create the RouterPlugin instance
        plugin = RouterPlugin(plugin_spec=spec, stand_alone=True)
        
        return plugin, temp_dir
    finally:
        # Clean up sys.path
        if str(plugin_dir) in sys.path:
            sys.path.remove(str(plugin_dir))


@pytest.mark.asyncio
async def test_declarative_router_basic():
    """Test basic declarative router configuration."""
    plugin_config = {
        "name": "Declarative Router Test Plugin",
        "description": "A test plugin with declarative routers",
        "version": "0.1.0",
        "routers": [
            {
                "name": "main_router",
                "routes": [
                    {
                        "path": "/test",
                        "handler": "handlers:TestHandler"
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_declarative_router_plugin(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # Call the event handler to set up routes
    await plugin.on_app_request_begin(router)
    
    # Verify a sub-router was added
    assert len(router._sub_routers) == 1
    
    # Check that the route was added to the sub-router
    sub_router = router._sub_routers[0]
    assert len(sub_router._routes) == 1
    path, methods, handler, _ = sub_router._routes[0]
    assert path == "/test"
    assert handler is not None


@pytest.mark.asyncio
async def test_declarative_router_multiple_routes():
    """Test declarative router with multiple routes."""
    plugin_config = {
        "name": "Multi-Route Test Plugin",
        "description": "A test plugin with multiple declarative routes",
        "version": "0.1.0",
        "routers": [
            {
                "name": "api_router",
                "routes": [
                    {
                        "path": "/users",
                        "handler": "api:UsersHandler"
                    },
                    {
                        "path": "/posts",
                        "handler": "api:PostsHandler"
                    },
                    {
                        "path": "/comments",
                        "handler": "api:CommentsHandler"
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_declarative_router_plugin(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # Call the event handler to set up routes
    await plugin.on_app_request_begin(router)
    
    # Verify a sub-router was added
    assert len(router._sub_routers) == 1
    
    # Check that all routes were added to the sub-router
    sub_router = router._sub_routers[0]
    assert len(sub_router._routes) == 3
    paths = [route[0] for route in sub_router._routes]
    assert "/users" in paths
    assert "/posts" in paths
    assert "/comments" in paths


@pytest.mark.asyncio
async def test_declarative_router_multiple_routers():
    """Test declarative configuration with multiple routers."""
    plugin_config = {
        "name": "Multi-Router Test Plugin",
        "description": "A test plugin with multiple declarative routers",
        "version": "0.1.0",
        "routers": [
            {
                "name": "main_router",
                "routes": [
                    {
                        "path": "/",
                        "handler": "main:HomeHandler"
                    }
                ]
            },
            {
                "name": "api_router",
                "routes": [
                    {
                        "path": "/api/users",
                        "handler": "api:UsersHandler"
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_declarative_router_plugin(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # Call the event handler to set up routes
    await plugin.on_app_request_begin(router)
    
    # Verify two sub-routers were added (one for each router config)
    assert len(router._sub_routers) == 2
    
    # Check that routes from both routers were added
    all_paths = []
    for sub_router in router._sub_routers:
        paths = [route[0] for route in sub_router._routes]
        all_paths.extend(paths)
    assert "/" in all_paths
    assert "/api/users" in all_paths


@pytest.mark.asyncio
async def test_declarative_router_with_mount():
    """Test declarative router with mount configuration."""
    plugin_config = {
        "name": "Mounted Router Test Plugin",
        "description": "A test plugin with mounted declarative router",
        "version": "0.1.0",
        "routers": [
            {
                "name": "api_router",
                "mount": "/api",
                "routes": [
                    {
                        "path": "/users",
                        "handler": "api:UsersHandler"
                    },
                    {
                        "path": "/posts",
                        "handler": "api:PostsHandler"
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_declarative_router_plugin(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    main_router = Router()
    container.instances[Router] = main_router
    
    # Call the event handler to set up routes
    await plugin.on_app_request_begin(main_router)
    
    # Verify that a router was mounted
    assert len(main_router._mounted_routers) == 1
    
    # Check the mount path
    mount_path, mounted_router = main_router._mounted_routers[0]
    assert mount_path == "/api"
    
    # Verify the mounted router has the correct routes
    assert len(mounted_router._routes) == 2
    paths = [route[0] for route in mounted_router._routes]
    assert "/users" in paths
    assert "/posts" in paths


@pytest.mark.asyncio
async def test_declarative_router_with_config():
    """Test declarative router with router-level configuration."""
    plugin_config = {
        "name": "Configured Router Test Plugin",
        "description": "A test plugin with router configuration",
        "version": "0.1.0",
        "routers": [
            {
                "name": "configured_router",
                "config": {
                    "auth_required": True,
                    "rate_limit": 100
                },
                "routes": [
                    {
                        "path": "/protected",
                        "handler": "auth:ProtectedHandler",
                        "config": {
                            "require_admin": True
                        }
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_declarative_router_plugin(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # Call the event handler to set up routes
    await plugin.on_app_request_begin(router)
    
    # Verify a sub-router was added
    assert len(router._sub_routers) == 1
    
    # Check that the route has the correct configuration
    sub_router = router._sub_routers[0]
    assert len(sub_router._routes) == 1
    path, methods, handler, settings = sub_router._routes[0]
    assert path == "/protected"
    assert settings == {"require_admin": True}


@pytest.mark.asyncio
async def test_declarative_router_empty_config():
    """Test declarative router with empty routers configuration."""
    plugin_config = {
        "name": "Empty Router Test Plugin",
        "description": "A test plugin with no routers",
        "version": "0.1.0",
        "routers": []
    }
    
    plugin, temp_dir = create_declarative_router_plugin(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # Call the event handler to set up routes
    await plugin.on_app_request_begin(router)
    
    # Verify no routes or sub-routers were added
    assert len(router._routes) == 0
    assert len(router._sub_routers) == 0
    assert len(router._mounted_routers) == 0


@pytest.mark.asyncio
async def test_declarative_router_no_routers_config():
    """Test declarative router with no routers configuration at all."""
    plugin_config = {
        "name": "No Routers Test Plugin",
        "description": "A test plugin with no routers configuration",
        "version": "0.1.0"
    }
    
    plugin, temp_dir = create_declarative_router_plugin(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # Call the event handler to set up routes
    await plugin.on_app_request_begin(router)
    
    # Verify no routes or sub-routers were added
    assert len(router._routes) == 0
    assert len(router._sub_routers) == 0
    assert len(router._mounted_routers) == 0








def test_router_builder_with_mount():
    """Test RouterBuilder with mount path."""
    from serv.plugins.router_plugin import RouterBuilder
    
    # Create a mock importer
    mock_importer = create_mock_importer()
    
    # Mock the load_module method
    mock_module = MagicMock()
    mock_handler = MagicMock()
    mock_module.ApiHandler = mock_handler
    mock_importer.load_module.return_value = mock_module
    
    # Create route configurations
    routes = [
        {
            "path": "/users",
            "handler": "api:ApiHandler"
        }
    ]
    
    # Create RouterBuilder with mount path
    builder = RouterBuilder(
        mount_path="/api",
        settings={},
        routes=routes,
        importer=mock_importer
    )
    
    # Create main router
    main_router = Router()
    
    # Build the router
    builder.build(main_router)
    
    # Verify a router was mounted
    assert len(main_router._mounted_routers) == 1
    
    # Check the mount path
    mount_path, mounted_router = main_router._mounted_routers[0]
    assert mount_path == "/api"


@pytest.mark.asyncio
async def test_declarative_router_with_methods():
    """Test declarative router with specific HTTP methods."""
    plugin_config = {
        "name": "Methods Test Plugin",
        "description": "A test plugin with method-specific routes",
        "version": "0.1.0",
        "routers": [
            {
                "name": "api_router",
                "routes": [
                    {
                        "path": "/users",
                        "handler": "api:UsersHandler",
                        "methods": ["GET", "POST"]
                    },
                    {
                        "path": "/users/{id}",
                        "handler": "api:UserHandler",
                        "methods": ["GET", "PUT", "DELETE"]
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_declarative_router_plugin(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # Call the event handler to set up routes
    await plugin.on_app_request_begin(router)
    
    # Verify a sub-router was added
    assert len(router._sub_routers) == 1
    
    # Check that routes were added with correct methods
    sub_router = router._sub_routers[0]
    assert len(sub_router._routes) == 2
    
    # Check first route
    path1, methods1, handler1, _ = sub_router._routes[0]
    assert path1 == "/users"
    assert methods1 == frozenset(["GET", "POST"])
    
    # Check second route
    path2, methods2, handler2, _ = sub_router._routes[1]
    assert path2 == "/users/{id}"
    assert methods2 == frozenset(["GET", "PUT", "DELETE"])


@pytest.mark.asyncio
async def test_declarative_router_complex_configuration():
    """Test declarative router with complex nested configuration."""
    plugin_config = {
        "name": "Complex Router Test Plugin",
        "description": "A test plugin with complex router configuration",
        "version": "0.1.0",
        "routers": [
            {
                "name": "main_router",
                "config": {
                    "middleware": ["auth", "logging"],
                    "default_headers": {"X-API-Version": "1.0"}
                },
                "routes": [
                    {
                        "path": "/",
                        "handler": "main:HomeHandler",
                        "config": {
                            "cache_ttl": 3600,
                            "public": True
                        }
                    }
                ]
            },
            {
                "name": "api_router",
                "mount": "/api/v1",
                "config": {
                    "rate_limit": 1000,
                    "auth_required": True
                },
                "routes": [
                    {
                        "path": "/users",
                        "handler": "api:UsersHandler",
                        "methods": ["GET", "POST"],
                        "config": {
                            "db_table": "users",
                            "cache_ttl": 300
                        }
                    },
                    {
                        "path": "/users/{id}",
                        "handler": "api:UserHandler",
                        "methods": ["GET", "PUT", "DELETE"],
                        "config": {
                            "db_table": "users",
                            "require_ownership": True
                        }
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_declarative_router_plugin(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    main_router = Router()
    container.instances[Router] = main_router
    
    # Call the event handler to set up routes
    await plugin.on_app_request_begin(main_router)
    
    # Verify one sub-router and one mounted router were added
    assert len(main_router._sub_routers) == 1  # main_router
    assert len(main_router._mounted_routers) == 1  # api_router mounted at /api/v1
    
    # Check the mounted router
    mount_path, mounted_router = main_router._mounted_routers[0]
    assert mount_path == "/api/v1"
    assert len(mounted_router._routes) == 2
    
    # Check the sub-router
    sub_router = main_router._sub_routers[0]
    assert len(sub_router._routes) == 1
    
    # Verify route configurations
    path, methods, handler, settings = sub_router._routes[0]
    assert path == "/"
    assert settings == {"cache_ttl": 3600, "public": True}
    
    # Verify mounted router routes
    api_routes = mounted_router._routes
    users_route = next(r for r in api_routes if r[0] == "/users")
    user_route = next(r for r in api_routes if r[0] == "/users/{id}")
    
    assert users_route[3] == {"db_table": "users", "cache_ttl": 300}
    assert user_route[3] == {"db_table": "users", "require_ownership": True}


@pytest.mark.asyncio
async def test_declarative_router_error_handling():
    """Test declarative router error handling for invalid configurations."""
    # Test with invalid handler format
    plugin_config = {
        "name": "Error Test Plugin",
        "description": "A test plugin with invalid handler",
        "version": "0.1.0",
        "routers": [
            {
                "name": "error_router",
                "routes": [
                    {
                        "path": "/invalid",
                        "handler": "invalid_handler_format"  # Missing colon
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_declarative_router_plugin(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # This should raise an error due to invalid handler format
    with pytest.raises(ValueError):
        await plugin.on_app_request_begin(router)


def test_declarative_router_integration_with_app():
    """Test declarative router integration with the App class."""
    plugin_config = {
        "name": "Integration Test Plugin",
        "description": "A test plugin for app integration",
        "version": "0.1.0",
        "routers": [
            {
                "name": "integration_router",
                "routes": [
                    {
                        "path": "/integration",
                        "handler": "handlers:IntegrationHandler"
                    }
                ]
            }
        ]
    }
    
    # Create the plugin
    temp_dir = tempfile.TemporaryDirectory()
    plugin_dir = Path(temp_dir.name)
    
    # Create plugin.yaml
    with open(plugin_dir / "plugin.yaml", "w") as f:
        yaml.dump(plugin_config, f)
    
    # Create __init__.py
    (plugin_dir / "__init__.py").touch()
    
    # Create handlers module
    handlers_file = plugin_dir / "handlers.py"
    handlers_file.write_text("""
from serv.responses import ResponseBuilder
from bevy import dependency

class IntegrationHandler:
    async def __call__(self, response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body("Integration test successful")
""")
    
    # Create the plugin spec and plugin
    spec = PluginSpec(
        config=plugin_config, 
        path=plugin_dir, 
        override_settings={}, 
        importer=create_mock_importer(plugin_dir)
    )
    
    plugin = RouterPlugin(plugin_spec=spec, stand_alone=True)
    
    # Verify the plugin was created successfully
    assert len(plugin._routers) == 1
    assert "integration_router" in plugin._routers


@pytest.mark.asyncio
async def test_declarative_router_route_resolution():
    """Test that declarative routes can be resolved correctly."""
    plugin_config = {
        "name": "Resolution Test Plugin",
        "description": "A test plugin for route resolution",
        "version": "0.1.0",
        "routers": [
            {
                "name": "resolution_router",
                "routes": [
                    {
                        "path": "/users/{id}",
                        "handler": "handlers:UserHandler",
                        "methods": ["GET"]
                    }
                ]
            }
        ]
    }
    
    plugin, temp_dir = create_declarative_router_plugin(plugin_config)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # Call the event handler to set up routes
    await plugin.on_app_request_begin(router)
    
    # Test route resolution
    result = router.resolve_route("/users/123", "GET")
    assert result is not None
    
    handler, params, settings = result
    assert params == {"id": "123"}
    assert handler is not None
    
    # Test non-existent route
    result = router.resolve_route("/nonexistent", "GET")
    assert result is None


@pytest.mark.asyncio
async def test_declarative_router_multiple_plugins():
    """Test multiple RouterPlugins working together."""
    # First plugin
    plugin_config1 = {
        "name": "Plugin One",
        "description": "First test plugin",
        "version": "0.1.0",
        "routers": [
            {
                "name": "plugin1_router",
                "routes": [
                    {
                        "path": "/plugin1",
                        "handler": "handlers:Plugin1Handler"
                    }
                ]
            }
        ]
    }
    
    # Second plugin
    plugin_config2 = {
        "name": "Plugin Two",
        "description": "Second test plugin",
        "version": "0.1.0",
        "routers": [
            {
                "name": "plugin2_router",
                "mount": "/api",
                "routes": [
                    {
                        "path": "/plugin2",
                        "handler": "handlers:Plugin2Handler"
                    }
                ]
            }
        ]
    }
    
    plugin1, temp_dir1 = create_declarative_router_plugin(plugin_config1)
    plugin2, temp_dir2 = create_declarative_router_plugin(plugin_config2)
    
    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router
    
    # Set up routes from both plugins
    await plugin1.on_app_request_begin(router)
    await plugin2.on_app_request_begin(router)
    
    # Verify both plugins added their routes
    assert len(router._sub_routers) == 1  # plugin1
    assert len(router._mounted_routers) == 1  # plugin2
    
    # Test route resolution for both plugins
    result1 = router.resolve_route("/plugin1", "GET")
    assert result1 is not None
    
    result2 = router.resolve_route("/api/plugin2", "GET")
    assert result2 is not None 