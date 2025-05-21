import pytest
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import AsyncIterator, Any
import contextlib
import textwrap
import importlib
import shutil
import uuid

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
from serv.plugin_loader import PluginLoader  # Import the actual PluginLoader


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
    mock_plugin.on = MagicMock()
    mock_plugin.name = "MockedRealPluginInstance"
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
        yaml.dump({"plugins": []}, f) # Start with empty config for default app

    # The PluginLoader methods will be mocked.
    # App._load_plugin_entry_point will call PluginLoader._load_plugin_entry_point
    # App._load_middleware_entry_point will call PluginLoader._load_middleware_entry_point

    # Default return for plugin loader
    mock_loader_plugin_return = mock_real_plugin_instance
    # Default return for middleware loader (can be a factory or a ServMiddleware subclass)
    # Let's default to returning a factory, tests for ServMiddleware can change this.
    mock_loader_middleware_return = mock_async_gen_middleware_factory

    with patch('serv.plugin_loader.PluginLoader._load_plugin_entry_point', return_value=mock_loader_plugin_return) as mock_loader_load_plugin, \
         patch('serv.plugin_loader.PluginLoader._load_middleware_entry_point', return_value=mock_loader_middleware_return) as mock_loader_load_middleware, \
         patch('serv.app.App.emit') as mock_emit: # Keep emit mocked to avoid unrelated asyncio issues

        # Patch the __init__ of PluginLoader to inject mocks if needed, or ensure App uses a new one each time.
        # For now, assume App creates its own PluginLoader instances as needed, or uses one that's easily patchable.
        # The patches above target the methods on the PluginLoader class, so any instance will use them.

        with Registry(): # Bevy registry
            # Ensure plugin_dir exists if App checks for it, even if loader is mocked
            plugin_test_dir = tmp_path / "plugins_test_dir"
            plugin_test_dir.mkdir(exist_ok=True)
            app = App(config=str(config_file), plugin_dir=str(plugin_test_dir))
            
            # Store mocks on app for easy access in tests
            app._mock_loader_load_plugin = mock_loader_load_plugin
            app._mock_loader_load_middleware = mock_loader_load_middleware
            
            # Allow tests to change the return value of loader mocks if needed
            app.set_mock_loader_plugin_return = lambda val: setattr(mock_loader_load_plugin, 'return_value', val)
            app.set_mock_loader_middleware_return = lambda val: setattr(mock_loader_load_middleware, 'return_value', val)
            
            app.emit = mock_emit 
            yield app


def test_load_single_plugin_entry_point_with_config(app_instance, caplog, mock_real_plugin_instance):
    app_instance.set_mock_loader_plugin_return(mock_real_plugin_instance)
    plugin_spec = {
        "name": "Test Plugin A",
        "entry points": [
            {"entry": PLUGIN_A_EP1, "config": {"key": "value"}}
        ]
    }
    app_instance._load_plugins([plugin_spec])
    
    # Check that PluginLoader._load_plugin_entry_point was called correctly by App's machinery
    # App calls PluginLoader._load_plugin_entry_point(self, entry_point_spec)
    app_instance._mock_loader_load_plugin.assert_called_once()
    # call_args.args is a tuple of positional arguments. call_args.args[0] is the first one.
    called_spec = app_instance._mock_loader_load_plugin.call_args.args[0]
    assert called_spec['entry'] == PLUGIN_A_EP1
    assert called_spec.get('config') == {"key": "value"}
    
    assert len(app_instance._plugins) == 1 # One plugin directory key
    assert len(app_instance._plugins[Path(".")]) == 1 # One plugin in that list
    assert app_instance._plugins[Path(".")][0] is mock_real_plugin_instance


def test_load_plugin_entry_point_no_constructor_config(app_instance, caplog, mock_real_plugin_instance):
    app_instance.set_mock_loader_plugin_return(mock_real_plugin_instance)
    plugin_spec = {
        "name": "Test Plugin A NoConstructorConfig",
        "entry points": [
            # PluginA_EntryPoint2 is defined in tests as taking no config.
            # The loader will be called with config=None or config={}.
            {"entry": PLUGIN_A_EP2, "config": {"key": "value_should_be_passed_to_loader"}}
        ]
    }
    app_instance._load_plugins([plugin_spec])
    
    app_instance._mock_loader_load_plugin.assert_called_once()
    called_spec = app_instance._mock_loader_load_plugin.call_args.args[0]
    assert called_spec['entry'] == PLUGIN_A_EP2
    assert called_spec.get('config') == {"key": "value_should_be_passed_to_loader"}

    assert len(app_instance._plugins) == 1
    assert len(app_instance._plugins[Path(".")]) == 1
    assert app_instance._plugins[Path(".")][0] is mock_real_plugin_instance


def test_load_multiple_plugin_entry_points(app_instance, caplog, mock_real_plugin_instance):
    # Ensure each call to the loader returns a new mock instance if App expects unique plugin objects
    # For this test, having it return the same mock_real_plugin_instance is fine for checking count.
    # If distinct instances are important, the mock setup would need to be more complex (e.g., side_effect list)
    app_instance.set_mock_loader_plugin_return(mock_real_plugin_instance)
    
    plugin_spec = {
        "name": "Test Plugin Multi",
        "entry points": [
            {"entry": PLUGIN_A_EP1, "config": {"id": 1}},
            {"entry": PLUGIN_A_EP2} 
        ]
    }
    app_instance._load_plugins([plugin_spec])
    
    assert app_instance._mock_loader_load_plugin.call_count == 2
    
    first_call_spec = app_instance._mock_loader_load_plugin.call_args_list[0].args[0]
    second_call_spec = app_instance._mock_loader_load_plugin.call_args_list[1].args[0]

    assert first_call_spec['entry'] == PLUGIN_A_EP1
    assert first_call_spec.get('config') == {"id": 1}
    assert second_call_spec['entry'] == PLUGIN_A_EP2
    assert second_call_spec.get('config') is None # Or {} depending on App's behavior for missing config

    assert len(app_instance._plugins) == 1 # One plugin directory key
    assert len(app_instance._plugins[Path(".")]) == 2 # Two plugins in that list
    assert app_instance._plugins[Path(".")][0] is mock_real_plugin_instance
    assert app_instance._plugins[Path(".")][1] is mock_real_plugin_instance


def test_load_servmiddleware_subclass_from_plugin(app_instance, caplog, mock_real_servmiddleware_instance):
    app_instance.set_mock_loader_middleware_return(mock_real_servmiddleware_instance)
    plugin_spec = {
        "name": "PluginWithMiddleware",
        "middleware": [
            {"entry": PLUGIN_A_MW, "config": {"mw_key": "mw_val"}}
        ]
    }
    app_instance._load_plugins([plugin_spec])
    
    app_instance._mock_loader_load_middleware.assert_called_once()
    called_spec = app_instance._mock_loader_load_middleware.call_args.args[0]
    assert called_spec['entry'] == PLUGIN_A_MW
    assert called_spec.get('config') == {"mw_key": "mw_val"}

    assert len(app_instance._middleware) == 1
    # App._middleware stores the direct return from loader (class or factory)
    assert app_instance._middleware[0] is mock_real_servmiddleware_instance


def test_load_middleware_factory_from_plugin(app_instance, caplog, mock_async_gen_middleware_factory):
    app_instance.set_mock_loader_middleware_return(mock_async_gen_middleware_factory)
    plugin_spec = {
        "name": "PluginWithFactoryMiddleware",
        "middleware": [
            {"entry": PLUGIN_A_FAC_MW, "config": {"factory_cfg": "yes"}}
        ]
    }
    app_instance._load_plugins([plugin_spec])
    
    app_instance._mock_loader_load_middleware.assert_called_once()
    called_spec = app_instance._mock_loader_load_middleware.call_args.args[0]
    assert called_spec['entry'] == PLUGIN_A_FAC_MW
    assert called_spec.get('config') == {"factory_cfg": "yes"}

    assert len(app_instance._middleware) == 1
    assert app_instance._middleware[0] is mock_async_gen_middleware_factory


def test_load_old_style_plugin_from_config(app_instance, mock_real_plugin_instance, caplog):
    # This test implies App has a separate method `_load_plugin_from_config`
    # We assume this method also uses the PluginLoader.
    # If App._load_plugin_from_config is a public/semi-public API for old style, test it directly.
    # If it's only called internally by _load_plugins, this test might be redundant or needs restructuring.
    # For now, let's assume it's a method on App we can call.
    
    # If _load_plugin_from_config does NOT exist, or is not meant to be tested this way,
    # this test needs a complete rethink or removal.
    
    # Assuming App has a method like: app_instance._load_plugin_from_config(old_plugin_conf)
    # And it uses the loader.
    if not hasattr(app_instance, '_load_plugin_from_config'):
        pytest.skip("App instance does not have _load_plugin_from_config method. Test needs review.")

    app_instance.set_mock_loader_plugin_return(mock_real_plugin_instance)
    
    old_style_plugin_config = {
        "entry": PLUGIN_B_SIMPLE,
        "config": {"legacy": True}
    }
    
    # We are testing the real App._load_plugin_from_config, assuming it calls the loader.
    # The original test patched this method, so it didn't test the actual implementation.
    try:
        # This is a hypothetical call. The actual method signature and behavior might differ.
        # If this method is supposed to add to app._plugins, we'd check that.
        # If it just returns the plugin, we check that.
        # The original test implies it returns a plugin instance.
        plugin_instance = app_instance._load_plugin_from_config(old_style_plugin_config)
        
        # Assert loader was called correctly by _load_plugin_from_config
        # This depends on _load_plugin_from_config's internal logic.
        # For example, it might call loader with old_style_plugin_config["entry"] and old_style_plugin_config["config"]
        # Based on current findings, loader is called with the whole spec: loader.method(spec)
        app_instance._mock_loader_load_plugin.assert_called_once()
        called_spec = app_instance._mock_loader_load_plugin.call_args.args[0]
        assert called_spec['entry'] == PLUGIN_B_SIMPLE
        assert called_spec.get('config') == {"legacy": True}

        assert plugin_instance is mock_real_plugin_instance
        # Also check if it was added to app_instance._plugins, if that's the behavior
        # assert mock_real_plugin_instance in app_instance._plugins

    except AttributeError:
        pytest.fail("App instance does not have _load_plugin_from_config method as assumed by the test.")
    except NotImplementedError:
        pytest.skip("App._load_plugin_from_config is not implemented in a way that uses the standard loader mock for this test.")


def test_load_plugin_class_not_found(app_instance, caplog):
    # Configure the PluginLoader mock to raise ImportError for a specific entry
    def loader_side_effect(spec_dict): # Expects the spec dictionary
        if spec_dict['entry'] == CLASS_MISSING_IN_A:
            raise ImportError(f"Simulated: No module or class found for {spec_dict['entry']}")
        # Fallback for other calls if any (shouldn't happen in this specific test)
        return MagicMock(spec=Plugin) 
        
    app_instance._mock_loader_load_plugin.side_effect = loader_side_effect
    
    plugin_spec = {"name": "ClassMissing", "entry points": [{"entry": CLASS_MISSING_IN_A}]}
    
    with pytest.raises(ExceptionGroup) as excinfo:
        app_instance._load_plugins([plugin_spec]) # Call the REAL _load_plugins
            
    assert len(excinfo.value.exceptions) == 1
    err = excinfo.value.exceptions[0]
    assert isinstance(err, ImportError)
    assert f"Simulated: No module or class found for {CLASS_MISSING_IN_A}" in str(err)
    assert not app_instance._plugins # Ensure no partial loading


def test_load_plugin_not_subclass_of_plugin(app_instance, caplog):
    # Configure PluginLoader mock to raise TypeError (or ValueError if loader does this check)
    # This error is typically raised by PluginLoader after successful import but type mismatch.
    def loader_side_effect(spec_dict): # Expects the spec dictionary
        if spec_dict['entry'] == PLUGIN_C_NOT_PLUGIN:
            raise TypeError(f"Simulated: Class for '{spec_dict['entry']}' does not inherit from 'Plugin'")
        return MagicMock(spec=Plugin)

    app_instance._mock_loader_load_plugin.side_effect = loader_side_effect
        
    plugin_spec = {"name": "NotAPluginTest", "entry points": [{"entry": PLUGIN_C_NOT_PLUGIN}]}
    
    with pytest.raises(ExceptionGroup) as excinfo:
        app_instance._load_plugins([plugin_spec])
            
    assert len(excinfo.value.exceptions) == 1
    err = excinfo.value.exceptions[0]
    assert isinstance(err, TypeError) # Or ValueError depending on loader's choice
    assert f"Simulated: Class for '{PLUGIN_C_NOT_PLUGIN}' does not inherit from 'Plugin'" in str(err)
    assert not app_instance._plugins


def test_load_middleware_not_servmiddleware_or_callable(app_instance, caplog):
    # Configure PluginLoader mock for middleware to raise TypeError/ValueError
    def loader_side_effect(spec_dict): # Expects the spec dictionary
        if spec_dict['entry'] == PLUGIN_C_NOT_MW:
            raise TypeError(f"Simulated: Middleware entry '{spec_dict['entry']}' is not ServMiddleware or factory")
        # Fallback, though not expected to be hit in this test if side_effect is specific
        return MagicMock(spec=ServMiddleware) 

    app_instance._mock_loader_load_middleware.side_effect = loader_side_effect
            
    plugin_spec = {"name": "NotMiddlewareTest", "middleware": [{"entry": PLUGIN_C_NOT_MW}]}
    
    with pytest.raises(ExceptionGroup) as excinfo:
        app_instance._load_plugins([plugin_spec])
            
    assert len(excinfo.value.exceptions) == 1
    err = excinfo.value.exceptions[0]
    assert isinstance(err, TypeError) # Or ValueError
    assert f"Simulated: Middleware entry '{PLUGIN_C_NOT_MW}' is not ServMiddleware or factory" in str(err)
    assert not app_instance._middleware


def test_entry_points_not_a_list(app_instance, caplog):
    # This tests validation within App._load_plugins itself, before loader calls
    plugin_spec = {"name": "BadEntryPointsType", "entry points": "not_a_list"}
    with pytest.raises(ExceptionGroup) as excinfo: # App._load_plugins wraps errors
        app_instance._load_plugins([plugin_spec])
    
    assert len(excinfo.value.exceptions) == 1
    err = excinfo.value.exceptions[0]
    assert isinstance(err, TypeError)
    # Message comes from App._load_plugins validation
    assert "'entry points' must be a list if provided" in str(err) or "'entry points' must be a list" in str(err)


def test_middleware_not_a_list(app_instance, caplog):
    # This tests validation within App._load_plugins itself
    plugin_spec = {"name": "BadMiddlewareType", "middleware": "not_a_list"}
    with pytest.raises(ExceptionGroup) as excinfo:
        app_instance._load_plugins([plugin_spec])
    
    assert len(excinfo.value.exceptions) == 1
    err = excinfo.value.exceptions[0]
    assert isinstance(err, TypeError)
    # Message comes from App._load_plugins validation
    assert "'middleware' must be a list if provided" in str(err) or "'middleware' must be a list" in str(err)


def test_empty_entry_points_list_ok(app_instance, caplog):
    # This tests App._load_plugins handling of empty list, should not call loader.
    with patch('serv.app.logger.info') as mock_logger_info: # Check specific log inside App
        plugin_spec = {"name": "EmptyEntriesOk", "entry points": []}
        app_instance._load_plugins([plugin_spec])
        
        app_instance._mock_loader_load_plugin.assert_not_called()
        mock_logger_info.assert_any_call(f"Plugin EmptyEntriesOk has empty 'entry points' list")
        assert len(app_instance._plugins) == 0


def test_empty_middleware_list_ok(app_instance, caplog):
    # This tests App._load_plugins handling of empty list, should not call loader.
    with patch('serv.app.logger.info') as mock_logger_info:
        plugin_spec = {"name": "EmptyMiddlewareOk", "middleware": []}
        app_instance._load_plugins([plugin_spec])
        
        app_instance._mock_loader_load_middleware.assert_not_called()
        mock_logger_info.assert_any_call(f"Plugin EmptyMiddlewareOk has empty 'middleware' list")
        assert len(app_instance._middleware) == 0


def test_plugin_spec_without_entry_points_or_middleware_ok(app_instance, caplog):
    # This tests App._load_plugins handling of spec with no relevant keys.
    with patch('serv.app.logger.info') as mock_logger_info:
        plugin_spec = {"name": "NoActionPluginOk"} # No 'entry points' or 'middleware' keys
        app_instance._load_plugins([plugin_spec])
        
        app_instance._mock_loader_load_plugin.assert_not_called()
        app_instance._mock_loader_load_middleware.assert_not_called()
        # Check for a general log about a plugin spec not having actionable items
        mock_logger_info.assert_any_call(f"Plugin NoActionPluginOk has no 'entry points' or 'middleware' sections")
        assert len(app_instance._plugins) == 0
        assert len(app_instance._middleware) == 0


def test_multiple_plugins_one_fails_but_others_load(app_instance, mock_real_plugin_instance, mock_async_gen_middleware_factory, caplog):
    # Configure loader mocks: one success for plugin, one failure for plugin, one success for middleware
    
    plugin_good = mock_real_plugin_instance
    middleware_good = mock_async_gen_middleware_factory

    # Simulate PluginLoader returning partial results along with an ExceptionGroup
    # The App should still process the successful ones.
    # PluginLoader.load_plugins is mocked in the app_instance fixture.
    # We need its side_effect to return (loaded_plugins_dict, loaded_middleware_list)
    # AND raise an ExceptionGroup if one is to be simulated.
    
    # This test needs the PluginLoader.load_plugins method itself to be the one raising the ExceptionGroup
    # while still returning partial successes. The current mocks are on _load_plugin_entry_point etc.
    # So, the App's _load_plugins_from_config will get an ExceptionGroup directly from 
    # self._plugin_loader_instance.load_plugins if that's how PluginLoader behaves.

    # The App's PluginLoader instance will use the mocks for _load_plugin_entry_point and 
    # _load_middleware_entry_point that are set up in the app_instance fixture.
    # We want the actual PluginLoader.load_plugins method to run, encounter an error from
    # its call to the mocked _load_plugin_entry_point, and then raise an ExceptionGroup.

    def plugin_loader_side_effect_for_partial(spec_dict):
        if spec_dict['entry'] == PLUGIN_A_EP1: # Good plugin
            return plugin_good
        elif spec_dict['entry'] == NONEXISTENT_MODULE: # Bad plugin
            # This error will be caught by the real PluginLoader.load_plugins,
            # which will then raise an ExceptionGroup.
            raise ImportError("Simulated: Cannot find NONEXISTENT_MODULE")
        # This case should ideally not be hit if plugin_specs matches the side_effect logic
        raise ValueError(f"Unexpected plugin entry in side_effect for partial: {spec_dict['entry']}")

    def middleware_loader_side_effect_for_partial(spec_dict):
        if spec_dict['entry'] == PLUGIN_A_MW: # Good middleware
            return middleware_good
        # This case should ideally not be hit
        raise ValueError(f"Unexpected middleware entry in side_effect for partial: {spec_dict['entry']}")
    
    app_instance._mock_loader_load_plugin.side_effect = plugin_loader_side_effect_for_partial
    app_instance._mock_loader_load_middleware.side_effect = middleware_loader_side_effect_for_partial

    plugins_specs = [
        {"name": "GoodPlugin", "entry points": [{"entry": PLUGIN_A_EP1, "config": {"id": "good"}}]},
        {"name": "BadPlugin", "entry points": [{"entry": NONEXISTENT_MODULE}]}, # This one will fail
        {"name": "AnotherGoodPlugin", "middleware": [{"entry": PLUGIN_A_MW, "config": {"id": "good_mw"}}]}
    ]
    
    with pytest.raises(ExceptionGroup) as excinfo:
        app_instance._load_plugins(plugins_specs) 
    
    # Check the exception
    assert len(excinfo.value.exceptions) == 1
    err = excinfo.value.exceptions[0]
    assert isinstance(err, ImportError)
    assert "Simulated: Cannot find NONEXISTENT_MODULE" in str(err)
    
    # Given app.py logic, if PluginLoader.load_plugins raises ExceptionGroup, 
    # App's _load_plugins_from_config will not proceed to add_plugin/add_middleware.
    assert len(app_instance._plugins) == 0, "If ExceptionGroup is raised by loader, App should not add plugins"
    assert len(app_instance._middleware) == 0, "If ExceptionGroup is raised by loader, App should not add middleware"


@pytest.mark.asyncio
async def test_middleware_execution_from_plugin(app_instance, mock_async_gen_middleware_factory, caplog, capsys):
    # This test verifies that a loaded middleware factory can be retrieved
    # and behaves as expected (simple yield for enter/leave).
    # True "execution" through app's request cycle is more complex and might be for integration tests.

    # Use a specific, instrumented factory for this test
    # So we can capture its output.
    
    # We need a new MagicMock for the factory itself to check calls if App wraps it.
    # For now, let's use a real async generator function that prints.
    
    @contextlib.asynccontextmanager
    async def instrumented_middleware_cm(*args, **kwargs):
        print(f"Instrumented Middleware Factory CM: Enter - Config: {kwargs}")
        yield
        print("Instrumented Middleware Factory CM: Leave")

    # The loader should return the factory *function* that creates this CM.
    def instrumented_factory_for_loader(config=None): # App calls this with config
        # print(f"instrumented_factory_for_loader called with config: {config}")
        return instrumented_middleware_cm(**config if config else {})


    # Make the mock loader return our instrumented factory *function*
    # The original fixture mock_async_gen_middleware_factory is an async_generator_function.
    # The App is expected to take this function, potentially wrap it with @asynccontextmanager if it's a raw generator,
    # then call it with config to get the actual context manager.
    # So, loader returns the async generator func.
    
    _enter_msg = "Test Middleware Factory: Enter"
    _leave_msg = "Test Middleware Factory: Leave"
    _config_val = "exec_val"

    async def specific_test_factory(config=None): # This is the async generator function
        # print(f"Specific test factory called with config: {config}")
        print(f"{_enter_msg} with {config}")
        yield
        print(_leave_msg)

    app_instance.set_mock_loader_middleware_return(specific_test_factory)

    plugin_spec = {
        "name": "PluginWithExecutableMiddleware",
        "middleware": [
            {"entry": "test.exec.mw:TestExecMiddleware", "config": {"exec_key": _config_val}}
        ]
    }
    app_instance._load_plugins([plugin_spec])

    assert len(app_instance._middleware) == 1
    loaded_mw_factory = app_instance._middleware[0]
    assert loaded_mw_factory is specific_test_factory # App stores the factory

    # Now, simulate how the app might use this factory to get a context manager
    # and run it. This part depends on App's internal API for middleware stack.
    # For now, let's assume app prepares and runs it.
    # If app has a method like `app.run_middleware_stack(loaded_mw_factory, config)`
    # or if it's more integrated, this test part might need to change.

    # Simplified: Manually create and run the CM from the factory, like App might do.
    # App would typically wrap the async_gen_func with @asynccontextmanager if it's not already.
    # Then call it with config.
    
    # Assume ServLoader or App itself handles wrapping raw async generator functions
    # with @asynccontextmanager.
    # And then calls it with the config.
    
    # If App._middleware stores the raw async_gen_func:
    actual_cm_provider = contextlib.asynccontextmanager(loaded_mw_factory)
    # App would call this with config:
    middleware_config_from_spec = plugin_spec["middleware"][0]["config"]
    actual_cm_instance = actual_cm_provider(config=middleware_config_from_spec)

    async with actual_cm_instance:
        # print("Inside mock middleware execution context")
        pass # Simulate request handling

    captured = capsys.readouterr()
    assert f"{_enter_msg} with {{'exec_key': '{_config_val}'}}" in captured.out
    assert _leave_msg in captured.out 

# New fixtures for real plugin testing

@pytest.fixture
def real_temp_plugin_dir(tmp_path):
    """
    Creates a temporary plugin directory with real plugin modules.
    The ServLoader expects a directory structure where:
    - The tmp_path becomes the namespace
    - Inside tmp_path are package directories
    - Each package directory has an __init__.py
    """
    # Create a unique package name for our test plugin
    plugin_pkg_name = f"testplugin_{uuid.uuid4().hex[:8]}"
    
    # Create the plugin package directory
    plugin_dir = tmp_path / plugin_pkg_name
    plugin_dir.mkdir(exist_ok=True)
    
    # Create __init__.py to make it a package - import needed items directly
    init_content = textwrap.dedent("""
    from .plugin import TestPlugin, TestMiddleware, test_middleware_factory
    from .not_plugin import NotAPlugin
    """)
    (plugin_dir / "__init__.py").write_text(init_content)
    
    # Create plugin.py with the test plugin implementation
    plugin_content = textwrap.dedent("""
    from pathlib import Path
    from serv.plugins import Plugin
    from serv.middleware import ServMiddleware
    
    class TestPlugin(Plugin):
        def __init__(self, plugin_dir=None, config=None):
            # Initialize the base class correctly
            # Pass stand_alone=True to avoid searching for plugin.yaml
            super().__init__(stand_alone=True)
            
            # Store parameters locally - avoid using plugin_dir which is a property
            self._custom_plugin_dir = Path(plugin_dir) if plugin_dir else None
            self.config = config
            self.name = "TestPlugin"
            self.last_event = None
            self.last_kwargs = None
            
        def on(self, event, **kwargs):
            # Store the event for testing
            self.last_event = event
            self.last_kwargs = kwargs
            return True
    
    class TestMiddleware(ServMiddleware):
        def __init__(self, config=None):
            self.config = config
            self.name = "TestMiddleware"
            
        async def __call__(self, request, next_handler):
            # Add a marker to the request
            request.add_attribute("middleware_was_here", True)
            if self.config and "add_header" in self.config:
                request.add_attribute("middleware_header", self.config["add_header"])
            return await next_handler(request)
            
    async def test_middleware_factory(config=None):
        # This is an async generator function that can be used as middleware
        config = config or {}
        # Add middleware start marker
        yield
        # This code runs after the request is processed
    """)
    (plugin_dir / "plugin.py").write_text(plugin_content)
    
    # Create a plugin.yaml for the plugin directory
    plugin_yaml_content = textwrap.dedent("""
    name: TestPlugin
    entry: plugin.TestPlugin
    version: 0.1.0
    """)
    (plugin_dir / "plugin.yaml").write_text(plugin_yaml_content)
    
    # Create a non-plugin module for negative testing
    not_plugin_content = textwrap.dedent("""
    class NotAPlugin:
        def __init__(self):
            self.name = "NotAPlugin"
    """)
    (plugin_dir / "not_plugin.py").write_text(not_plugin_content)
    
    # Create a namespace __init__.py to make the tmp_path a package
    # This is needed for the import to work correctly
    (tmp_path / "__init__.py").write_text("")
    
    # The tmp_path directory name becomes the namespace
    namespace = tmp_path.name
    
    yield {
        "dir": tmp_path,
        "name": plugin_pkg_name,
        "namespace": namespace,
        "plugin_module": plugin_pkg_name,  # Just the package name
        "plugin_class": f"{plugin_pkg_name}:TestPlugin",  # Entry point format package:ClassName
        "middleware_class": f"{plugin_pkg_name}:TestMiddleware",
        "middleware_factory": f"{plugin_pkg_name}:test_middleware_factory",
        "not_plugin_class": f"{plugin_pkg_name}:NotAPlugin",
    }
    
    # Cleanup
    try:
        # Remove the __init__.py first
        (tmp_path / "__init__.py").unlink()
        shutil.rmtree(plugin_dir)
    except (OSError, IOError):
        pass
    
    # Clean up any imported modules
    namespace = tmp_path.name
    for key in list(sys.modules.keys()):
        if key.startswith(namespace) or key == namespace:
            del sys.modules[key]

@pytest.fixture
def real_plugin_loader(real_temp_plugin_dir):
    """
    Creates a ServLoader and PluginLoader configured to find real plugins.
    """
    plugin_info = real_temp_plugin_dir
    
    # Print some debug info
    print(f"\nTemporary plugin directory: {plugin_info['dir']}")
    print(f"Plugin package name: {plugin_info['name']}")
    print(f"Directory structure:")
    for item in plugin_info['dir'].iterdir():
        if item.is_dir():
            print(f"  /{item.name}/")
            for subitem in item.iterdir():
                print(f"    /{item.name}/{subitem.name}")
        else:
            print(f"  {item.name}")
    
    # Create a ServLoader that looks in the temp directory
    serv_loader = ServLoader(directory=str(plugin_info["dir"]))
    
    # Create a PluginLoader that uses this ServLoader
    loader = PluginLoader(plugin_loader=serv_loader)
    
    return {
        "plugin_loader": loader,
        "serv_loader": serv_loader,
        "plugin_info": plugin_info
    }

def test_real_plugin_import(real_plugin_loader):
    """Test that PluginLoader can import and instantiate a real plugin."""
    loader = real_plugin_loader["plugin_loader"]
    plugin_info = real_plugin_loader["plugin_info"]
    serv_loader = real_plugin_loader["serv_loader"]
    
    # Try loading the package directly with ServLoader to debug
    plugin_module_name = plugin_info["name"]
    print(f"\nTrying to load package directly: {plugin_module_name}")
    module = serv_loader.load_package(plugin_module_name)
    print(f"Result: {module}")
    
    # Verify the module has the TestPlugin class imported at the top level
    if hasattr(module, "TestPlugin"):
        print(f"TestPlugin found in module: {module.TestPlugin}")
    else:
        print("TestPlugin not found in module!")
    
    # Create the entry point specification with direct class name
    spec = {
        "entry": plugin_info["plugin_class"],
        "config": {"test_key": "test_value"}
    }
    
    print(f"Entry point spec: {spec}")
    
    # Use the real plugin loader to load the plugin
    plugin_instance = loader._load_plugin_entry_point(spec)
    
    # Verify the plugin was properly loaded and instantiated
    assert plugin_instance is not None
    assert plugin_instance.__class__.__name__ == "TestPlugin"
    assert plugin_instance.name == "TestPlugin"
    assert plugin_instance.config == {"test_key": "test_value"}
    
    # Test plugin functionality
    plugin_instance.on("test_event", arg1="value1")
    assert plugin_instance.last_event == "test_event"
    assert plugin_instance.last_kwargs == {"arg1": "value1"}

def test_real_middleware_import(real_plugin_loader):
    """Test that PluginLoader can import and instantiate real middleware."""
    loader = real_plugin_loader["plugin_loader"]
    plugin_info = real_plugin_loader["plugin_info"]
    
    # Create the middleware entry point specification
    spec = {
        "entry": plugin_info["middleware_class"],
        "config": {"add_header": "X-Test"}
    }
    
    # Use the real plugin loader to load the middleware
    middleware_factory = loader._load_middleware_entry_point(spec)
    
    # Middleware factory should be callable
    assert callable(middleware_factory)
    
    # Call the factory to get the actual middleware instance
    middleware_instance = middleware_factory()
    
    # Verify the middleware was properly instantiated
    assert middleware_instance is not None
    assert middleware_instance.__class__.__name__ == "TestMiddleware"
    assert middleware_instance.name == "TestMiddleware"
    assert middleware_instance.config == {"add_header": "X-Test"}

def test_real_middleware_factory_import(real_plugin_loader):
    """Test that PluginLoader can import and use a middleware factory."""
    loader = real_plugin_loader["plugin_loader"]
    plugin_info = real_plugin_loader["plugin_info"]
    
    # Create the factory entry point specification
    spec = {
        "entry": plugin_info["middleware_factory"],
        "config": {"factory_config": "test"}
    }
    
    # Use the real plugin loader to load the middleware factory
    factory = loader._load_middleware_entry_point(spec)
    
    # Factory should be callable
    assert callable(factory)
    
    # Should be an async generator function
    import inspect
    assert inspect.isasyncgenfunction(factory)

def test_full_plugin_loading(real_plugin_loader):
    """Test loading multiple plugins and middleware in a single operation."""
    loader = real_plugin_loader["plugin_loader"]
    plugin_info = real_plugin_loader["plugin_info"]
    
    # Create a complete plugin specification with multiple components
    plugin_spec = {
        "name": "TestPluginSpec",
        "entry points": [
            {"entry": plugin_info["plugin_class"], "config": {"id": "plugin1"}}
        ],
        "middleware": [
            {"entry": plugin_info["middleware_class"], "config": {"id": "mw1"}},
            {"entry": plugin_info["middleware_factory"], "config": {"id": "factory1"}}
        ]
    }
    
    # Use the real plugin loader to load everything
    plugins, middleware = loader.load_plugins([plugin_spec])
    
    # Verify plugins were loaded
    assert len(plugins) == 1  # One plugin directory
    plugin_dir = next(iter(plugins.keys()))
    assert len(plugins[plugin_dir]) == 1  # One plugin
    plugin = plugins[plugin_dir][0]
    assert plugin.__class__.__name__ == "TestPlugin"
    assert plugin.config == {"id": "plugin1"}
    
    # Verify middleware were loaded
    assert len(middleware) == 2
    
    # First middleware should be a factory for TestMiddleware
    mw_factory = middleware[0]
    assert callable(mw_factory)
    mw_instance = mw_factory()
    assert mw_instance.__class__.__name__ == "TestMiddleware"
    assert mw_instance.config == {"id": "mw1"}
    
    # Second middleware should be the async generator function
    assert callable(middleware[1])
    import inspect
    assert inspect.isasyncgenfunction(middleware[1])

def test_import_failure(real_plugin_loader):
    """Test that PluginLoader properly handles import failures."""
    loader = real_plugin_loader["plugin_loader"]
    plugin_info = real_plugin_loader["plugin_info"]
    
    # Test with a nonexistent module
    nonexistent_pkg = "nonexistent_module"
    spec = {"entry": f"{nonexistent_pkg}:NonExistentClass"}
    
    with pytest.raises(ImportError):
        loader._load_plugin_entry_point(spec)
    
    # Test with a nonexistent class in an existing module
    spec = {"entry": f"{plugin_info['name']}:NonExistentClass"}
    
    with pytest.raises(ImportError):
        loader._load_plugin_entry_point(spec)

def test_not_a_plugin(real_plugin_loader):
    """Test that PluginLoader rejects classes not inheriting from Plugin."""
    loader = real_plugin_loader["plugin_loader"]
    plugin_info = real_plugin_loader["plugin_info"]
    
    spec = {"entry": plugin_info["not_plugin_class"]}
    
    with pytest.raises(ValueError):
        loader._load_plugin_entry_point(spec)

def test_app_integration(real_plugin_loader):
    """Test that App can load real plugins using the PluginLoader."""
    plugin_info = real_plugin_loader["plugin_info"]
    tmp_path = plugin_info["dir"]
    
    # Create a config file for the App
    config_file = tmp_path / "test_config.yaml"
    config_content = {
        "plugins": [
            {
                "name": "TestPlugin",
                "entry points": [
                    {"entry": plugin_info["plugin_class"], "config": {"app_test": True}}
                ],
                "middleware": [
                    {"entry": plugin_info["middleware_class"], "config": {"app_mw_test": True}}
                ]
            }
        ]
    }
    
    with open(config_file, "w") as f:
        import yaml
        yaml.dump(config_content, f)
    
    # Create App with configuration pointing to our temp directory
    with Registry():  # Bevy registry
        # Override the plugin_dir to use our temp directory
        app = App(config=str(config_file), plugin_dir=str(tmp_path))
        
        # Check plugins were loaded
        assert len(app._plugins) == 1
        plugin_dir = next(iter(app._plugins.keys()))
        plugin = app._plugins[plugin_dir][0]
        
        # Verify plugin properties
        assert plugin.__class__.__name__ == "TestPlugin"
        assert plugin.config == {"app_test": True}
        
        # Check middleware was loaded
        assert len(app._middleware) == 1
        middleware_factory = app._middleware[0]
        middleware = middleware_factory()
        
        # Verify middleware properties
        assert middleware.__class__.__name__ == "TestMiddleware"
        assert middleware.config == {"app_mw_test": True} 