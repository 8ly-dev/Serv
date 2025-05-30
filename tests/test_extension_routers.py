import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from bevy import dependency
from bevy.registries import Registry

from serv.extensions import Extension, on
from serv.extensions.loader import ExtensionSpec
from serv.responses import ResponseBuilder
from serv.routing import Router


def create_plugin_with_config(extension_config):
    """Helper to create a plugin with specific configuration."""
    temp_dir = tempfile.TemporaryDirectory()
    extension_dir = Path(temp_dir.name)

    # Create a temporary extension.yaml file
    with open(extension_dir / "extension.yaml", "w") as f:
        yaml.dump(extension_config, f)

    # Create a dummy __init__.py to make it a package
    (extension_dir / "__init__.py").touch()

    # Create a dummy handlers.py if extension_config implies it needs one for its routes
    router_config_from_plugin = extension_config.get("router", {})
    if isinstance(router_config_from_plugin, dict) and any(
        str(route.get("handler", "")).startswith("handlers.")
        for route in router_config_from_plugin.get("routes", [])
    ):
        handlers_file = extension_dir / "handlers.py"
        handlers_file.write_text(
            """from serv.responses import ResponseBuilder
async def sample_handler(response: ResponseBuilder):
    response.body('Hello from plugin')
"""
        )

    # Temporarily add the parent of the temp_dir to sys.path
    # so that the plugin can be imported
    sys.path.insert(0, str(temp_dir))

    class TestExtension(Extension):
        @on("app.request.begin")
        async def setup_routes(self, router: Router = dependency()):
            # Setup routes from extension_config if they exist
            if not hasattr(self, "__extension_spec__") or not self.__extension_spec__:
                return

            router_config = self.__extension_spec__._config.get("router", {})
            if not isinstance(router_config, dict):  # Check if router_config is a dict
                return

            routes = router_config.get("routes", [])
            for route_def in routes:
                path = route_def.get("path")
                handler_str = route_def.get("handler")
                methods = route_def.get("methods")
                route_def.get("name")
                settings = route_def.get("settings")

                if not path or not handler_str:
                    continue  # Skip incomplete route definitions

                # For these dynamically created test plugins, handlers are often
                # simple functions or need to be mocked. A real plugin might import them.
                # For now, let's assume a dummy handler if not found, or allow specific
                # tests to mock/patch this part.
                async def dummy_handler(
                    response: ResponseBuilder = dependency(), current_path: str = path
                ):
                    response.body(f"Handler for {current_path}")

                actual_handler = dummy_handler  # Placeholder

                # Try to import handler if it's a string
                if isinstance(handler_str, str) and ":" in handler_str:
                    try:
                        from serv.config import import_from_string

                        actual_handler = import_from_string(handler_str)
                    except ImportError as e:
                        print(f"Warning: Could not import handler {handler_str}: {e}")
                        # Fallback to dummy_handler if import fails
                        pass  # Keep actual_handler as dummy_handler
                elif callable(handler_str):  # if handler_str is already a callable
                    actual_handler = handler_str

                router.add_route(
                    path, actual_handler, methods=methods, settings=settings
                )

    # Get the actual module where TestExtension is defined for patching
    test_extension_module = sys.modules[TestExtension.__module__]

    # Store original spec if it exists, to restore later
    original_spec = getattr(test_extension_module, "__extension_spec__", None)

    # Patch the actual module with the plugin spec before instantiation
    from tests.helpers import create_mock_importer

    spec = ExtensionSpec(
        config=extension_config,
        path=extension_dir,
        override_settings={},
        importer=create_mock_importer(extension_dir),
    )
    test_extension_module.__extension_spec__ = spec

    # Instantiate the plugin. With the module patched, stand_alone=True is not strictly necessary
    # for this specific problem, but harmless.
    plugin = TestExtension(stand_alone=True)
    plugin.__extension_spec__ = (
        spec  # Also set on instance for tests that might look for it there.
    )

    # Clean up: restore original spec and remove temp module from sys.path
    if original_spec is not None:
        test_extension_module.__extension_spec__ = original_spec
    elif hasattr(test_extension_module, "__extension_spec__"):
        del test_extension_module.__extension_spec__

    sys.path.pop(0)
    # No need to del sys.modules[plugin_module_name] as we are patching the existing module

    return plugin, temp_dir


@pytest.mark.asyncio
async def test_extension_router_config_basic():
    """Test basic router configuration."""
    extension_config = {
        "name": "Test Extension",
        "description": "A test plugin",
        "version": "0.1.0",
        "router": {  # Add a basic router configuration
            "routes": [
                {
                    "path": "/test_basic",
                    "handler": "handlers.sample_handler",  # Ensure period for startswith check
                    "methods": ["GET"],
                }
            ]
        },
    }

    plugin, temp_dir = create_plugin_with_config(extension_config)

    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router

    # Call the event handler to set up routes
    await plugin.on("app.request.begin", container=container, router=router)

    # Verify router was created and set up correctly
    assert len(router._routes) == 1

    # Check that the route was added correctly
    path, methods, handler, _ = router._routes[0]
    assert path == "/test_basic"
    assert "GET" in methods
    assert handler is not None


@pytest.mark.asyncio
async def test_extension_router_mounting():
    """Test router mounting configuration."""
    extension_config = {
        "name": "Test Extension",
        "description": "A test plugin",
        "version": "0.1.0",
        "router": {  # Add a basic router configuration for the test
            "routes": [
                {
                    "path": "/mounted_test",
                    "handler": "handlers.sample_handler",
                    "methods": ["GET"],
                }
            ]
        },
    }

    plugin, temp_dir = create_plugin_with_config(extension_config)

    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    main_router = Router()
    api_router = Router()
    container.instances[Router] = main_router

    # Mount the API router
    main_router.mount("/api", api_router)

    # Add routes to both routers
    await plugin.on("app.request.begin", container=container, router=main_router)
    await plugin.on("app.request.begin", container=container, router=api_router)

    # Verify routers were created
    assert len(main_router._routes) == 1
    assert len(api_router._routes) == 1

    # Check that the main router has the api router mounted
    assert len(main_router._mounted_routers) == 1

    # Verify the mount path
    mount_path, mounted_router = main_router._mounted_routers[0]
    assert mount_path == "/api"


@pytest.mark.asyncio
async def test_extension_on_app_startup():
    """Test that routers are set up during app startup."""
    extension_config = {
        "name": "Test Extension",
        "description": "A test plugin",
        "version": "0.1.0",
        "router": {  # Add a basic router configuration for the test
            "routes": [
                {
                    "path": "/startup_test",
                    "handler": "handlers.sample_handler",
                    "methods": ["GET"],
                }
            ]
        },
    }

    plugin, temp_dir = create_plugin_with_config(extension_config)

    # Create a container for dependency injection
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router

    # Call the event handler to set up routes
    await plugin.on("app.request.begin", container=container, router=router)

    # Verify router was created and set up correctly
    assert len(router._routes) == 1

    # Check that the route was added correctly
    path, methods, handler, _ = router._routes[0]
    assert path == "/startup_test"
    assert "GET" in methods
    assert handler is not None


def test_extension_import_handler():
    """Test the handler import functionality."""
    extension_config = {
        "name": "Test Extension",
        "description": "A test plugin",
        "version": "0.1.0",
    }

    plugin, temp_dir = create_plugin_with_config(extension_config)

    # Test simple colon-separated import (module.path:ClassName)
    with patch("importlib.import_module") as mock_import:
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
    with patch("importlib.import_module") as mock_import:
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


def test_extension_import_handler_rejects_dot_notation():
    """Test that dot notation for handlers is rejected."""
    extension_config = {
        "name": "Test Extension",
        "description": "A test plugin",
        "version": "0.1.0",
    }

    plugin, temp_dir = create_plugin_with_config(extension_config)

    # Attempt to use dot notation should raise ServConfigError
    from serv.config import ServConfigError, import_from_string

    with pytest.raises(ServConfigError) as excinfo:
        import_from_string("some.module.TestHandler")
    assert "Invalid import string format" in str(excinfo.value)
