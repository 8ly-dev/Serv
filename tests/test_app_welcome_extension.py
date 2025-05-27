from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from bevy.registries import Registry

from serv.app import App
from serv.extensions import Extension
from serv.extensions.loader import ExtensionSpec


@pytest.fixture
def app_with_empty_config(tmp_path):
    """Create an App instance with an empty config file."""
    config_file = tmp_path / "empty_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump({"extensions": []}, f)

    return str(config_file)


def test_welcome_plugin_auto_enabled(app_with_empty_config):
    """Test that the welcome plugin is auto-enabled when no extensions/middleware are registered."""
    with patch("serv.app.App._enable_welcome_extension") as mock_enable_welcome:
        with Registry():  # Bevy registry
            App(config=app_with_empty_config)

            # Check that _enable_welcome_extension was called
            mock_enable_welcome.assert_called_once()


@pytest.mark.parametrize(
    "has_plugins,has_middleware,should_enable",
    [
        (True, True, False),  # Has both plugins and middleware
        (True, False, False),  # Has plugins but no middleware
        (False, True, False),  # Has middleware but no plugins
        (False, False, True),  # Has neither plugins nor middleware
    ],
)
def test_welcome_plugin_conditional_enabling(
    has_plugins, has_middleware, should_enable, tmp_path
):
    """Test that the welcome plugin is only enabled when no plugins and no middleware are registered."""
    # Create an empty config file
    config_file = tmp_path / "empty_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump({"extensions": []}, f)

    # Create mocks for plugins and middleware
    from tests.helpers import create_mock_importer

    ExtensionSpec(
        config={
            "name": "Mock Extension",
            "description": "A mock plugin",
            "version": "0.1.0",
            "author": "Test Author",
        },
        path=Path("."),
        override_settings={},
        importer=create_mock_importer(),
    )

    with (
        patch("serv.app.App._enable_welcome_extension") as mock_enable_welcome,
        patch(
            "serv.extensions.loader.ExtensionLoader.load_extensions"
        ) as mock_load_extensions,
    ):
        # Set up mock behavior for plugin loading
        mock_load_extensions.return_value = (
            {Path("."): [MagicMock(spec=Extension)]} if has_plugins else {},
            [MagicMock()] if has_middleware else [],
        )

        with Registry():  # Bevy registry
            App(config=str(config_file))

            # Check if _enable_welcome_extension was called as expected
            if should_enable:
                mock_enable_welcome.assert_called_once()
            else:
                mock_enable_welcome.assert_not_called()


def test_welcome_plugin_loading():
    """Test that the welcome plugin can be loaded from the bundled directory."""
    # This test verifies that the welcome plugin exists and can be imported
    from pathlib import Path

    # Get the path to the welcome plugin module
    welcome_extension_path = (
        Path(__file__).parent.parent
        / "serv"
        / "bundled"
        / "extensions"
        / "welcome"
        / "welcome.py"
    )

    # Verify the welcome plugin file exists
    assert welcome_extension_path.exists(), "Welcome plugin file should exist"

    # Verify the extension.yaml exists
    welcome_yaml_path = (
        Path(__file__).parent.parent
        / "serv"
        / "bundled"
        / "extensions"
        / "welcome"
        / "extension.yaml"
    )
    assert welcome_yaml_path.exists(), "Welcome extension.yaml should exist"
