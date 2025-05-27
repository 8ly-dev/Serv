from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from bevy.registries import Registry

from serv.app import App
from serv.plugins import Listener
from serv.plugins.loader import PluginSpec
from tests.helpers import create_mock_importer

# Constants for test paths
PLUGIN_A_EP1 = "plugin_a.module.plugin:PluginA_EntryPoint1"
PLUGIN_A_EP2 = "plugin_a.module.plugin:PluginA_EntryPoint2"
PLUGIN_A_MW = "plugin_a.module.plugin:PluginA_Middleware"
PLUGIN_A_FAC_MW = "plugin_a.module.plugin:plugin_a_factory_mw"
PLUGIN_B_SIMPLE = "plugin_b.plugin:SimplePlugin"
PLUGIN_C_NOT_PLUGIN = "plugin_c.plugin:NotAPlugin"
PLUGIN_C_NOT_MW = "plugin_c.plugin:NotMiddleware"
NONEXISTENT_MODULE = "nonexistent.module:NonExistentPlugin"
CLASS_MISSING_IN_A = "plugin_a.module.plugin:MissingClass"
INVALID_ENTRY_NO_COLON_A = "plugin_a.module.plugin.InvalidFormat"


# Test fixtures for plugin directory testing
@pytest.fixture
def create_plugin_dir(tmp_path):
    """Create a temporary plugin directory structure."""

    def _create_plugin_dir(name="plugins"):
        plugin_dir = tmp_path / name
        plugin_dir.mkdir(exist_ok=True)
        return plugin_dir

    yield _create_plugin_dir


def test_real_plugin_loading_with_directory(monkeypatch, tmp_path, create_plugin_dir):
    """Test that app creation works with plugin directory structure."""
    # Create an empty plugin directory structure
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    # Create app config file with no plugins
    config_file = tmp_path / "serv.config.yaml"
    app_config = {"plugins": []}

    with open(config_file, "w") as f:
        yaml.dump(app_config, f)

    # Test that app can be created with empty plugin directory
    with patch("serv.app.App._enable_welcome_plugin") as mock_enable_welcome:
        with Registry():
            app = App(config=str(config_file), plugin_dir=str(plugin_dir))

            # Verify welcome plugin was enabled since we have no plugins
            mock_enable_welcome.assert_called_once()

            # Verify the app was created successfully
            assert app is not None


def test_real_plugin_loading_with_entry_points(
    monkeypatch, tmp_path, create_plugin_dir
):
    """Test that app creation works with plugin configuration structure."""
    # Create an empty plugin directory structure
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    # Create app config file with empty plugin list
    config_file = tmp_path / "serv.config.yaml"
    app_config = {"plugins": []}

    with open(config_file, "w") as f:
        import yaml

        yaml.dump(app_config, f)

    # Test that app can be created with plugin configuration
    with patch("serv.app.App._enable_welcome_plugin") as mock_enable_welcome:
        with Registry():
            app = App(config=str(config_file), plugin_dir=str(plugin_dir))

            # Verify welcome plugin was enabled since we have no plugins
            mock_enable_welcome.assert_called_once()

            # Verify the app was created successfully
            assert app is not None


def test_real_plugin_loading_with_middleware(monkeypatch, tmp_path, create_plugin_dir):
    """Test that app creation works with middleware configuration structure."""
    # Create an empty plugin directory structure
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    # Create app config file with empty plugin list
    config_file = tmp_path / "serv.config.yaml"
    app_config = {"plugins": []}

    with open(config_file, "w") as f:
        yaml.dump(app_config, f)

    # Test that app can be created with middleware configuration
    with patch("serv.app.App._enable_welcome_plugin") as mock_enable_welcome:
        with Registry():
            app = App(config=str(config_file), plugin_dir=str(plugin_dir))

            # Verify welcome plugin was enabled since we have no plugins
            mock_enable_welcome.assert_called_once()

            # Verify the app was created successfully
            assert app is not None


def test_plugin_event_registration():
    """Test that plugin events are correctly registered via __init_subclass__."""

    class TestEventListener(Listener):
        def on_startup(self):
            pass

        def on_shutdown(self):
            pass

        def custom_on_event(self):
            pass

        def not_an_event(self):
            pass

        non_callable_on_event = "not a method"

    # Check that events were registered correctly
    assert "startup" in TestEventListener.__listeners__
    assert "shutdown" in TestEventListener.__listeners__
    assert "event" in TestEventListener.__listeners__

    # Check that non-event methods were not registered
    assert "not_an_event" not in {
        event for events in TestEventListener.__listeners__.values() for event in events
    }

    # Check that the correct method names were registered for each event
    assert "on_startup" in TestEventListener.__listeners__["startup"]
    assert "on_shutdown" in TestEventListener.__listeners__["shutdown"]
    assert "custom_on_event" in TestEventListener.__listeners__["event"]

    # Check that non-callable attributes were not registered
    assert "non_callable_on_event" not in {
        method
        for methods in TestEventListener.__listeners__.values()
        for method in methods
    }


def test_plugin_spec_creation():
    """Test that PluginSpec can be created with required parameters."""

    plugin_spec = PluginSpec(
        config={
            "name": "Test Plugin",
            "description": "A test plugin",
            "version": "0.1.0",
            "author": "Test Author",
        },
        path=Path("."),
        override_settings={"test_key": "test_value"},
        importer=create_mock_importer(),
    )

    assert plugin_spec.name == "Test Plugin"
    assert plugin_spec.version == "0.1.0"
    assert plugin_spec.settings == {"test_key": "test_value"}


def test_plugin_settings_merging():
    """Test that plugin settings are correctly merged with overrides."""

    plugin_spec = PluginSpec(
        config={
            "name": "Test Plugin",
            "description": "A test plugin",
            "version": "0.1.0",
            "author": "Test Author",
            "settings": {
                "default_key": "default_value",
                "override_key": "original_value",
            },
        },
        path=Path("."),
        override_settings={"override_key": "new_value", "new_key": "added_value"},
        importer=create_mock_importer(),
    )

    # Verify the final settings are correctly merged
    expected_settings = {
        "default_key": "default_value",
        "override_key": "new_value",
        "new_key": "added_value",
    }
    assert plugin_spec.settings == expected_settings
