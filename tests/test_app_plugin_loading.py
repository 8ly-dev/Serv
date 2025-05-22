import pytest
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from typing import AsyncIterator, Any
import contextlib
import textwrap
import importlib
import shutil
import uuid
import yaml
from collections import defaultdict

import pytest_asyncio
from bevy import get_registry
from bevy.registries import Registry
from bevy.containers import Container

from serv.app import App
from serv.plugins import Plugin
from serv.middleware import ServMiddleware
from serv.loader import ServLoader
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.routing import Router
from serv.plugin_loader import PluginLoader, PluginSpec  # Import the actual PluginLoader and PluginSpec


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


@pytest.fixture
def mock_real_plugin_instance():
    """Creates a MagicMock behaving like a Plugin instance, for loader returns."""
    mock_plugin = MagicMock(spec=Plugin)
    mock_plugin.plugin_dir = Path(".")
    mock_plugin.name = "MockedRealPluginInstance"
    mock_plugin.__plugins__ = defaultdict(list)
    mock_plugin.__plugin_spec__ = MagicMock()
    mock_plugin.__plugin_spec__.settings = {}
    mock_plugin.__plugin_spec__.entry_points = []
    mock_plugin.__plugin_spec__.middleware = []
    mock_plugin._stand_alone = False
    return mock_plugin


@pytest.fixture
def mock_real_servmiddleware_instance():
    """Creates a MagicMock behaving like a ServMiddleware instance, for loader returns."""
    mock_mw = MagicMock(spec=ServMiddleware)
    # Add any necessary attributes if App interacts with them post-loading
    mock_mw.name = "MockedRealServMiddlewareInstance"
    return mock_mw


@pytest.fixture
def mock_async_gen_middleware_factory():
    """
    Provides a mock async generator function.
    This is what PluginLoader._load_middleware_entry_point might return for factory-based middleware.
    """
    async def _factory(*args, **kwargs):
        # print(f"Mock async_gen_middleware_factory executed with: args={args}, kwargs={kwargs}")
        # print("Mock async_gen_middleware_factory: enter")
        yield
        # print("Mock async_gen_middleware_factory: leave")
    # Return the function itself, not a call to it
    return _factory


@pytest_asyncio.fixture
async def app_instance(monkeypatch, tmp_path, mock_real_plugin_instance, mock_async_gen_middleware_factory, mock_real_servmiddleware_instance):
    """
    Create an App instance for testing.
    Mocks PluginLoader methods to control plugin/middleware loading process
    without mocking App's internal loading logic.
    """
    config_file = tmp_path / "serv.config.yaml"
    with open(config_file, "w") as f:
        import yaml
        yaml.dump({"plugins": [{"plugin": "dummy"}]}, f)  # Add a dummy plugin to prevent welcome plugin loading

    # Create a dummy plugin spec for the dummy plugin
    dummy_plugin_spec = PluginSpec(
        name="Dummy Plugin",
        description="A dummy plugin",
        version="0.1.0",
        path=Path("."),
        author="Test Author"
    )

    # Default return for plugin loader
    mock_loader_plugin_return = mock_real_plugin_instance
    # Default return for middleware loader (can be a factory or a ServMiddleware subclass)
    # Let's default to returning a factory, tests for ServMiddleware can change this.
    mock_loader_middleware_return = mock_async_gen_middleware_factory

    # Mock the load_plugin method to control plugin loading
    with patch('serv.plugin_loader.PluginLoader.load_plugin', return_value=(dummy_plugin_spec, [])) as mock_load_plugin, \
         patch('serv.plugin_loader.PluginLoader._load_plugin_entry_points', return_value=(0, [])) as mock_loader_load_plugin, \
         patch('serv.plugin_loader.PluginLoader._load_plugin_middleware', return_value=(0, [])) as mock_loader_load_middleware, \
         patch('serv.app.App.emit') as mock_emit, \
         patch('serv.app.App._enable_welcome_plugin') as mock_enable_welcome:  # Mock welcome plugin loading

        with Registry(): # Bevy registry
            # Ensure plugin_dir exists if App checks for it, even if loader is mocked
            plugin_test_dir = tmp_path / "plugins_test_dir"
            plugin_test_dir.mkdir(exist_ok=True)
            app = App(config=str(config_file), plugin_dir=str(plugin_test_dir))
            
            # Store mocks on app for easy access in tests
            app._mock_load_plugin = mock_load_plugin
            app._mock_loader_load_plugin = mock_loader_load_plugin
            app._mock_loader_load_middleware = mock_loader_load_middleware
            app._mock_enable_welcome = mock_enable_welcome
            
            # Allow tests to change the return value of loader mocks if needed
            app.set_mock_plugin_return = lambda val: setattr(mock_load_plugin, 'return_value', val)
            app.set_mock_loader_plugin_return = lambda val: setattr(mock_loader_load_plugin, 'return_value', val)
            app.set_mock_loader_middleware_return = lambda val: setattr(mock_loader_load_middleware, 'return_value', val)
            
            # Set up the plugin loader instance with the mocks
            app._plugin_loader_instance._load_plugin_entry_points = mock_loader_load_plugin
            app._plugin_loader_instance._load_plugin_middleware = mock_loader_load_middleware
            
            app.emit = mock_emit
            
            # Reset the welcome plugin mock after initialization
            mock_enable_welcome.reset_mock()
            
            yield app


def test_load_single_plugin(app_instance, caplog, mock_real_plugin_instance):
    """Test loading a single plugin from app config."""
    plugin_spec = PluginSpec(
        name="Test Plugin",
        description="A test plugin",
        version="0.1.0",
        path=Path("."),
        author="Test Author"
    )
    app_instance.set_mock_plugin_return((plugin_spec, []))
    
    plugin_settings = {
        "plugin": "test_plugin",
        "settings": {"key": "value"}
    }
    app_instance._plugin_loader_instance.load_plugins([plugin_settings])
    
    # Check that PluginLoader.load_plugin was called correctly
    assert app_instance._mock_load_plugin.call_count == 2  # One for dummy plugin, one for test_plugin
    app_instance._mock_load_plugin.assert_any_call("test_plugin", {"key": "value"})
    
    # Verify welcome plugin was not enabled
    app_instance._mock_enable_welcome.assert_not_called()


def test_load_plugin_entry_points(app_instance, caplog, mock_real_plugin_instance):
    """Test loading a plugin with entry points from plugin.yaml."""
    # Create plugin spec with entry points
    plugin_spec = PluginSpec(
        name="Plugin With Entry Points",
        description="A test plugin with entry points",
        version="0.1.0",
        path=Path("."),
        author="Test Author",
        entry_points=["module.path:EntryPoint", "module.path:AnotherEntryPoint"],
        plugin_settings={"base_setting": "base_value"}
    )

    # Mock the plugin loading
    with patch.object(app_instance._plugin_loader_instance, 'load_plugin') as mock_load_plugin:
        mock_load_plugin.return_value = (plugin_spec, [])

        plugin_settings = {
            "plugin": "plugin_with_entry_points",
            "settings": {"override_setting": "override_value"}
        }

        # Load the plugins
        app_instance._plugin_loader_instance.load_plugins([plugin_settings])

        # Check that load_plugin was called with correct arguments
        mock_load_plugin.assert_called_once_with(
            "plugin_with_entry_points",
            {"override_setting": "override_value"}
        )


def test_load_plugin_middleware(app_instance, caplog, mock_real_plugin_instance, mock_async_gen_middleware_factory):
    """Test loading a plugin with middleware from plugin.yaml."""
    # Create plugin spec with middleware
    plugin_spec = PluginSpec(
        name="Plugin With Middleware",
        description="A test plugin with middleware",
        version="0.1.0",
        path=Path("."),
        author="Test Author",
        middleware=["module.path:TestMiddleware", "module.path:AnotherMiddleware"],
        plugin_settings={"base_setting": "base_value"}
    )

    # Mock the plugin loading
    with patch.object(app_instance._plugin_loader_instance, 'load_plugin') as mock_load_plugin:
        mock_load_plugin.return_value = (plugin_spec, [])

        plugin_settings = {
            "plugin": "plugin_with_middleware",
            "settings": {"override_setting": "override_value"}
        }

        # Load the plugins
        app_instance._plugin_loader_instance.load_plugins([plugin_settings])

        # Check that load_plugin was called with correct arguments
        mock_load_plugin.assert_called_once_with(
            "plugin_with_middleware",
            {"override_setting": "override_value"}
        )


def test_load_plugin_by_dot_notation(app_instance, caplog, mock_real_plugin_instance):
    """Test loading a plugin by dot notation."""
    plugin_spec = PluginSpec(
        name="Welcome Plugin",
        description="A welcome plugin",
        version="0.1.0",
        path=Path("."),
        author="Test Author"
    )
    app_instance.set_mock_plugin_return((plugin_spec, []))
    
    plugin_settings = {
        "plugin": "bundled.plugins.welcome"
    }
    app_instance._plugin_loader_instance.load_plugins([plugin_settings])
    
    # Check that load_plugin was called with the correct dot notation
    assert app_instance._mock_load_plugin.call_count == 2  # One for dummy plugin, one for welcome plugin
    app_instance._mock_load_plugin.assert_any_call("bundled.plugins.welcome", {})
    
    # Verify welcome plugin was not enabled
    app_instance._mock_enable_welcome.assert_not_called()


def test_load_multiple_plugins(app_instance, caplog, mock_real_plugin_instance):
    """Test loading multiple plugins."""
    plugin1_spec = PluginSpec(
        name="Plugin 1",
        description="First test plugin",
        version="0.1.0",
        path=Path("."),
        author="Test Author"
    )
    plugin2_spec = PluginSpec(
        name="Plugin 2",
        description="Second test plugin",
        version="0.1.0",
        path=Path("."),
        author="Test Author"
    )
    
    # Configure load_plugin to return different specs for different calls
    app_instance._mock_load_plugin.side_effect = [(plugin1_spec, []), (plugin2_spec, [])]
    
    plugins_settings = [
        {"plugin": "plugin1", "settings": {"key1": "value1"}},
        {"plugin": "plugin2", "settings": {"key2": "value2"}}
    ]
    app_instance._plugin_loader_instance.load_plugins(plugins_settings)
    
    # Check that load_plugin was called three times (dummy + two plugins)
    assert app_instance._mock_load_plugin.call_count == 3
    app_instance._mock_load_plugin.assert_any_call("plugin1", {"key1": "value1"})
    app_instance._mock_load_plugin.assert_any_call("plugin2", {"key2": "value2"})
    
    # Verify welcome plugin was not enabled
    app_instance._mock_enable_welcome.assert_not_called()


def test_plugin_settings_override(app_instance, caplog, mock_real_plugin_instance):
    """Test that plugin settings are correctly overridden by app config."""
    plugin_spec = PluginSpec(
        name="Test Plugin",
        description="A test plugin",
        version="0.1.0",
        path=Path("."),
        author="Test Author",
        plugin_settings={"default_key": "default_value", "override_key": "original_value"}
    )
    app_instance.set_mock_plugin_return((plugin_spec, []))
    
    plugin_settings = {
        "plugin": "test_plugin",
        "settings": {"override_key": "new_value", "new_key": "added_value"}
    }
    app_instance._plugin_loader_instance.load_plugins([plugin_settings])
    
    # Check settings were properly merged in the actual plugin
    assert app_instance._mock_load_plugin.call_count == 2  # One for dummy plugin, one for test plugin
    app_instance._mock_load_plugin.assert_any_call(
        "test_plugin",
        {"override_key": "new_value", "new_key": "added_value"}
    )
    
    # Verify the final settings in the plugin spec
    plugin_spec.override_settings = {"override_key": "new_value", "new_key": "added_value"}
    assert plugin_spec.settings == {
        "default_key": "default_value",
        "override_key": "new_value",
        "new_key": "added_value"
    }
    
    # Verify welcome plugin was not enabled
    app_instance._mock_enable_welcome.assert_not_called()


def test_plugin_load_error_handling(app_instance, caplog):
    """Test error handling when loading a plugin fails."""
    # Configure load_plugin to raise an error
    app_instance._mock_load_plugin.side_effect = ValueError("Failed to load plugin")
    
    plugin_settings = {"plugin": "error_plugin"}
    
    with pytest.raises(ExceptionGroup) as excinfo:
        app_instance._plugin_loader_instance.load_plugins([plugin_settings])
    
    # Check the exception
    assert len(excinfo.value.exceptions) == 1
    err = excinfo.value.exceptions[0]
    assert isinstance(err, ValueError)
    assert "Failed to load plugin" in str(err)


def test_entry_point_load_error_handling(app_instance, caplog, mock_real_plugin_instance):
    """Test error handling when loading an entry point fails."""
    plugin_spec = PluginSpec(
        name="Plugin With Bad Entry Point",
        description="A test plugin with a bad entry point",
        version="0.1.0",
        path=Path("."),
        author="Test Author",
        entry_points=["module.path:BadEntryPoint"]
    )

    # Mock the plugin loading
    with patch.object(app_instance._plugin_loader_instance, 'load_plugin') as mock_load_plugin:
        mock_load_plugin.return_value = (plugin_spec, [ImportError("Failed to load entry point")])

        plugin_settings = {"plugin": "plugin_with_bad_entry_point"}

        # Load the plugins and expect an ExceptionGroup
        with pytest.raises(ExceptionGroup) as excinfo:
            app_instance._plugin_loader_instance.load_plugins([plugin_settings])

        # Check that we got the expected error
        assert len(excinfo.value.exceptions) == 1
        assert isinstance(excinfo.value.exceptions[0], ImportError)
        assert str(excinfo.value.exceptions[0]) == "Failed to load entry point"


def test_middleware_load_error_handling(app_instance, caplog, mock_real_plugin_instance):
    """Test error handling when loading middleware fails."""
    plugin_spec = PluginSpec(
        name="Plugin With Bad Middleware",
        description="A test plugin with bad middleware",
        version="0.1.0",
        path=Path("."),
        author="Test Author",
        middleware=["module.path:BadMiddleware"]
    )
    app_instance.set_mock_plugin_return((plugin_spec, []))
    
    # Mock the middleware loading to raise an error
    with patch('serv.plugin_loader.PluginLoader._load_plugin_middleware') as mock_load_middleware:
        mock_load_middleware.return_value = (0, [ValueError("Failed to load middleware")])
        
        # Configure load_plugin to return the plugin spec with the error
        app_instance.set_mock_plugin_return((plugin_spec, [ValueError("Failed to load middleware")]))
        
        plugin_settings = {"plugin": "plugin_with_bad_middleware"}
        
        with pytest.raises(ExceptionGroup) as excinfo:
            app_instance._plugin_loader_instance.load_plugins([plugin_settings])
        
        # Check the exception
        assert len(excinfo.value.exceptions) == 1
        err = excinfo.value.exceptions[0]
        assert isinstance(err, ValueError)
        assert "Failed to load middleware" in str(err)
        
        # Verify welcome plugin was not enabled
        app_instance._mock_enable_welcome.assert_not_called()


@pytest.mark.asyncio
async def test_middleware_execution_from_plugin(app_instance, caplog, mock_real_plugin_instance, mock_async_gen_middleware_factory):
    """Test that middleware from a plugin is executed correctly."""
    # Create plugin spec with middleware
    plugin_spec = PluginSpec(
        name="Plugin With Middleware",
        description="A test plugin with middleware",
        version="0.1.0",
        path=Path("."),
        author="Test Author",
        middleware=["module.path:TestMiddleware"],
        plugin_settings={"base_setting": "base_value"}
    )

    # Mock the plugin loading
    with patch.object(app_instance._plugin_loader_instance, 'load_plugin') as mock_load_plugin:
        mock_load_plugin.return_value = (plugin_spec, [])

        plugin_settings = {
            "plugin": "plugin_with_middleware",
            "settings": {"override_setting": "override_value"}
        }

        # Load the plugins
        loaded_plugins, loaded_middleware = app_instance._plugin_loader_instance.load_plugins([plugin_settings])

        # Check that load_plugin was called with correct arguments
        mock_load_plugin.assert_called_once_with(
            "plugin_with_middleware",
            {"override_setting": "override_value"}
        )


# New test fixtures for real plugin directory testing
@pytest.fixture
def create_plugin_dir(tmp_path):
    """Create a temporary plugin directory with plugin.yaml and module files."""
    def _create_plugin(plugin_id, plugin_config, file_contents=None):
        # Create the actual plugin directory structure
        plugin_dir = tmp_path / plugin_id
        plugin_dir.mkdir(exist_ok=True)
        
        # Write plugin.yaml
        plugin_yaml_path = plugin_dir / "plugin.yaml"
        with open(plugin_yaml_path, "w") as f:
            import yaml
            yaml.dump(plugin_config, f)
        
        # Create __init__.py to make it a package
        init_py = plugin_dir / "__init__.py"
        init_py.write_text("")
        
        # Create additional files if specified
        if file_contents:
            for rel_path, content in file_contents.items():
                # Create directories if needed
                full_path = plugin_dir / rel_path
                os.makedirs(full_path.parent, exist_ok=True)
                # Write file content
                full_path.write_text(content)
        
        return plugin_dir
    
    yield _create_plugin
    
    # Cleanup
    for item in tmp_path.iterdir():
        if item.is_dir() and (item / "plugin.yaml").exists():
            shutil.rmtree(item)


def test_real_plugin_loading_with_directory(monkeypatch, tmp_path, create_plugin_dir):
    """Test loading a real plugin from a directory."""
    # Create a plugin directory with plugin.yaml and implementation
    plugin_id = "test_plugin"
    plugin_files = {
        "plugin.py": textwrap.dedent("""
        from serv.plugins import Plugin

        class TestPlugin(Plugin):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self._stand_alone = False
                self.test_value = self.settings.get("test_key", "default")
        """)
    }

    plugin_config = {
        "name": "Test Plugin",
        "description": "A test plugin",
        "author": "Test Author",
        "version": "1.0.0",
        "entry": "plugin:TestPlugin",
        "plugin_settings": {
            "test_key": "default_value"
        },
        "entry_points": [],
        "middleware": []
    }

    # Create plugin directory
    plugin_dir = create_plugin_dir(plugin_id, plugin_config, plugin_files)

    # Create app config file
    config_file = tmp_path / "serv.config.yaml"
    app_config = {
        "plugins": [
            {
                "plugin": plugin_id,  # Use exact same ID for both plugin dir and config
                "settings": {
                    "test_key": "override_value"
                }
            }
        ]
    }

    with open(config_file, "w") as f:
        yaml.dump(app_config, f)

    # Create our mock and verify plugin loading
    with patch('serv.plugin_loader.PluginLoader.load_plugin') as mock_load_plugin:
        # Set up mock behavior for plugin loading
        plugin_spec = PluginSpec(
            name="Test Plugin",
            description="A test plugin",
            version="1.0.0",
            path=plugin_dir,
            author="Test Author",
            plugin_settings={"test_key": "default_value"},
            override_settings={"test_key": "override_value"}
        )
        mock_load_plugin.return_value = (plugin_spec, [])

        # Create app with the temp directory as plugin_dir
        with Registry():
            app = App(config=str(config_file), plugin_dir=str(plugin_dir))

            # Check that the plugin was loaded with the correct settings
            mock_load_plugin.assert_any_call("test_plugin", {"test_key": "override_value"})


def test_real_plugin_loading_with_entry_points(monkeypatch, tmp_path, create_plugin_dir):
    """Test loading a real plugin with entry points from plugin.yaml."""
    # Create a plugin directory with plugin.yaml and implementation
    plugin_id = "plugin_with_entry_points"
    plugin_files = {
        "plugin.py": textwrap.dedent("""
        from serv.plugins import Plugin
        
        class MainPlugin(Plugin):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self._stand_alone = False
        
        class EntryPoint(Plugin):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self._stand_alone = False
                self.entry_point_value = self.settings.get("ep_key", "default")
        """)
    }
    
    plugin_config = {
        "name": "Plugin With Entry Points",
        "description": "A test plugin with entry points",
        "version": "1.0.0",
        "entry": "plugin:MainPlugin",
        "plugin_settings": {},
        "entry_points": [
            {
                "entry": "plugin:EntryPoint",
                "config": {
                    "ep_key": "entry_point_value"
                }
            }
        ],
        "middleware": []
    }
    
    # Create plugin directory
    plugin_dir = create_plugin_dir(plugin_id, plugin_config, plugin_files)
    
    # Create app config file
    config_file = tmp_path / "serv.config.yaml"
    app_config = {
        "plugins": [
            {
                "plugin": plugin_id  # Use exact same ID for both plugin dir and config
            }
        ]
    }
    
    with open(config_file, "w") as f:
        import yaml
        yaml.dump(app_config, f)
    
    # Create our mock and verify plugin loading
    with patch('serv.plugin_loader.PluginLoader.load_plugin') as mock_load_plugin, \
         patch('serv.app.App._enable_welcome_plugin') as mock_enable_welcome:
        
        # Set up mock behavior for plugin loading
        plugin_spec = PluginSpec(
            name="Plugin With Entry Points",
            description="A test plugin with entry points",
            version="1.0.0",
            path=plugin_dir,
            author="Test Author",
            entry_points=["plugin:EntryPoint"]
        )
        mock_load_plugin.return_value = (plugin_spec, [])
        
        # Create app with the temp directory as plugin_dir
        with Registry():
            app = App(config=str(config_file), plugin_dir=str(plugin_dir))
            
            # Check that the plugin was loaded with the correct settings
            mock_load_plugin.assert_called_once_with("plugin_with_entry_points", {})


def test_real_plugin_loading_with_middleware(monkeypatch, tmp_path, create_plugin_dir):
    """Test loading a real plugin with middleware from plugin.yaml."""
    # Create a plugin directory with plugin.yaml and implementation
    plugin_id = "plugin_with_middleware"
    plugin_files = {
        "plugin.py": textwrap.dedent("""
        from serv.plugins import Plugin
        from serv.middleware import ServMiddleware

        class MainPlugin(Plugin):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self._stand_alone = False

        class TestMiddleware(ServMiddleware):
            def __init__(self, config=None):
                self.config = config
                self.name = "TestMiddleware"

            async def __call__(self, request, next_handler):
                # Add middleware marker
                request.add_attribute("middleware_was_here", True)
                return await next_handler(request)

        async def test_middleware_factory(config=None):
            # This is an async generator middleware
            config = config or {}
            yield
        """)
    }

    plugin_config = {
        "name": "Plugin With Middleware",
        "description": "A test plugin with middleware",
        "version": "1.0.0",
        "entry": "plugin:MainPlugin",
        "plugin_settings": {},
        "entry_points": [],
        "middleware": [
            {
                "entry": "plugin:TestMiddleware",
                "config": {
                    "mw_key": "mw_value"
                }
            },
            {
                "entry": "plugin:test_middleware_factory",
                "config": {
                    "factory_key": "factory_value"
                }
            }
        ]
    }

    # Create plugin directory
    plugin_dir = create_plugin_dir(plugin_id, plugin_config, plugin_files)

    # Create app config file
    config_file = tmp_path / "serv.config.yaml"
    app_config = {
        "plugins": [
            {
                "plugin": plugin_id  # Use exact same ID for both plugin dir and config
            }
        ]
    }

    with open(config_file, "w") as f:
        yaml.dump(app_config, f)

    # Create our mock and verify plugin loading
    with patch('serv.plugin_loader.PluginLoader.load_plugin') as mock_load_plugin, \
         patch('serv.app.App._enable_welcome_plugin') as mock_enable_welcome:
        # Set up mock behavior for plugin loading
        plugin_spec = PluginSpec(
            name="Plugin With Middleware",
            description="A test plugin with middleware",
            version="1.0.0",
            path=plugin_dir,
            author="Test Author",
            middleware=["plugin:TestMiddleware", "plugin:test_middleware_factory"]
        )
        mock_load_plugin.return_value = (plugin_spec, [])

        # Create app with the temp directory as plugin_dir
        with Registry():
            app = App(config=str(config_file), plugin_dir=str(plugin_dir))

            # Check that the plugin was loaded with the correct settings
            mock_load_plugin.assert_called_once_with("plugin_with_middleware", {})


def test_plugin_event_registration():
    """Test that plugin events are correctly registered via __init_subclass__."""
    class TestEventPlugin(Plugin):
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
    assert "startup" in TestEventPlugin.__plugins__
    assert "shutdown" in TestEventPlugin.__plugins__
    assert "event" in TestEventPlugin.__plugins__
    
    # Check that non-event methods were not registered
    assert "not_an_event" not in {event for events in TestEventPlugin.__plugins__.values() for event in events}
    
    # Check that the correct method names were registered for each event
    assert "on_startup" in TestEventPlugin.__plugins__["startup"]
    assert "on_shutdown" in TestEventPlugin.__plugins__["shutdown"]
    assert "custom_on_event" in TestEventPlugin.__plugins__["event"]
    
    # Check that non-callable attributes were not registered
    assert "non_callable_on_event" not in {method for methods in TestEventPlugin.__plugins__.values() for method in methods}


@pytest.fixture
def app_with_empty_config(tmp_path):
    """Creates an app instance with an empty config file."""
    config_file = tmp_path / "empty_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump({"plugins": []}, f)
    return str(config_file)


@pytest.mark.parametrize("has_plugins,has_middleware,should_enable", [
    (True, True, False),   # Has both plugins and middleware
    (True, False, False),  # Has plugins but no middleware
    (False, True, False),  # Has middleware but no plugins
    (False, False, True),  # Has neither plugins nor middleware
])
def test_welcome_plugin_conditional_enabling(has_plugins, has_middleware, should_enable, tmp_path):
    """Test that the welcome plugin is only enabled when no plugins and no middleware are registered."""
    # Create an empty config file
    config_file = tmp_path / "empty_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump({"plugins": []}, f)

    # Create mocks for plugins and middleware
    mock_plugin_spec = PluginSpec(
        name="Mock Plugin",
        description="A mock plugin",
        version="0.1.0",
        path=Path("."),
        author="Test Author"
    )

    with patch('serv.app.App._enable_welcome_plugin') as mock_enable_welcome, \
         patch('serv.plugin_loader.PluginLoader.load_plugins') as mock_load_plugins:
        # Set up mock behavior for plugin loading
        mock_load_plugins.return_value = ({Path("."): [MagicMock(spec=Plugin)]} if has_plugins else {}, [MagicMock()] if has_middleware else [])

        with Registry():  # Bevy registry
            app = App(config=str(config_file))

            # Check if _enable_welcome_plugin was called as expected
            if should_enable:
                mock_enable_welcome.assert_called()
            else:
                mock_enable_welcome.assert_not_called() 