import sys
import tempfile
from pathlib import Path

import pytest
import yaml
from bevy import dependency
from bevy.registries import Registry

from serv.extensions import Extension, on
from serv.extensions.loader import ExtensionSpec
from serv.responses import ResponseBuilder
from serv.routing import Router
from tests.helpers import create_mock_importer


def create_plugin_with_config(extension_yaml_content):
    """Helper to create a plugin with specific configuration."""
    temp_dir = tempfile.TemporaryDirectory()
    extension_dir = Path(temp_dir.name)

    # Create extension.yaml file
    with open(extension_dir / "extension.yaml", "w") as f:
        yaml.dump(extension_yaml_content, f)

    # Create a dummy __init__.py to make it a package for potential handler imports
    (extension_dir / "__init__.py").touch()
    sys.path.insert(0, str(temp_dir.name))  # Add temp_dir to path for imports

    class TestExtension(Extension):
        # Test handler method
        async def handle_test(self, response: ResponseBuilder = dependency()):
            response.content_type("text/plain")
            response.body("test response")

        # Handler with dependency injection
        async def handle_with_settings(
            self,
            response: ResponseBuilder = dependency(),
            test_setting: str = dependency(),
        ):
            response.content_type("text/plain")
            response.body(f"Setting value: {test_setting}")

        @on("app.request.begin")
        async def setup_routes(self, router: Router = dependency()):
            # Use settings from self.__extension_spec__ if available, otherwise default
            route_settings_from_spec = (
                getattr(self.__extension_spec__, "_config", {})
                .get("router", {})
                .get("default_route_settings", {"route_setting": "route_value"})
            )
            test_setting_from_spec = (
                getattr(self.__extension_spec__, "_config", {})
                .get("router", {})
                .get("default_test_settings", {"test_setting": "injected_value"})
            )

            router.add_route(
                "/test",
                self.handle_test,
                methods=["GET"],
                settings=route_settings_from_spec,
            )
            router.add_route(
                "/test_with_settings",
                self.handle_with_settings,
                methods=["GET"],
                settings=test_setting_from_spec,
            )

    # Patch the module of TestExtension before instantiation
    test_extension_module = sys.modules[TestExtension.__module__]
    original_spec = getattr(test_extension_module, "__extension_spec__", None)

    spec_config = {
        "name": extension_yaml_content.get("name", "Test Extension Default Name"),
        "description": extension_yaml_content.get(
            "description", "Test Extension Default Desc"
        ),
        "version": extension_yaml_content.get("version", "0.0.0"),
        "author": "Test Author",
    }
    # Include router settings from extension_yaml_content if they exist, for on_app_request_begin
    if "router" in extension_yaml_content:
        spec_config["router"] = extension_yaml_content["router"]

    current_spec = ExtensionSpec(
        config=spec_config,
        path=extension_dir,
        override_settings=extension_yaml_content.get("override_settings", {}),
        importer=create_mock_importer(extension_dir),
    )
    test_extension_module.__extension_spec__ = current_spec

    plugin = TestExtension(stand_alone=True)
    plugin.__extension_spec__ = current_spec  # Also set on instance

    # Clean up module patch and sys.path
    if original_spec is not None:
        test_extension_module.__extension_spec__ = original_spec
    elif hasattr(test_extension_module, "__extension_spec__"):
        del test_extension_module.__extension_spec__
    sys.path.pop(0)

    return plugin, temp_dir


@pytest.mark.asyncio
async def test_route_settings():
    """Test route-level settings."""
    extension_config = {
        "name": "Test Extension",
        "description": "A test plugin",
        "version": "0.1.0",
    }

    plugin, temp_dir = create_plugin_with_config(extension_config)
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router

    # Set up routes via event emission
    await plugin.on("app.request.begin", container=container, router=router)

    # Resolve a route and check settings
    resolved = router.resolve_route("/test", "GET")
    assert resolved is not None

    handler, params, settings = resolved
    assert settings == {"route_setting": "route_value"}


@pytest.mark.asyncio
async def test_settings_injection():
    """Test that settings are properly injected into handlers."""
    extension_config = {
        "name": "Test Extension",
        "description": "A test plugin",
        "version": "0.1.0",
    }

    plugin, temp_dir = create_plugin_with_config(extension_config)
    registry = Registry()
    container = registry.create_container()
    router = Router()
    container.instances[Router] = router

    # Set up routes via event emission
    await plugin.on("app.request.begin", container=container, router=router)

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
    extension_config = {
        "name": "Test Extension",
        "description": "A test plugin",
        "version": "0.1.0",
    }

    plugin, temp_dir = create_plugin_with_config(extension_config)
    registry = Registry()
    container = registry.create_container()
    main_router = Router(
        settings={"main_setting": "main_value", "shared_setting": "main_level"}
    )
    api_router = Router(
        settings={"api_setting": "api_value", "shared_setting": "api_level"}
    )
    container.instances[Router] = main_router

    # Mount the API router
    main_router.mount("/api", api_router)

    # Set up routes on both routers via event emission
    await plugin.on("app.request.begin", container=container, router=main_router)
    await plugin.on("app.request.begin", container=container, router=api_router)

    # Resolve a route on the mounted router
    resolved = main_router.resolve_route("/api/test", "GET")
    assert resolved is not None

    handler, params, settings = resolved

    # Check settings inheritance and overriding
    assert settings["main_setting"] == "main_value"
    assert settings["api_setting"] == "api_value"
    assert settings["route_setting"] == "route_value"
    assert settings["shared_setting"] == "api_level"  # Most specific wins
