import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest_asyncio
from bevy import get_registry
from bevy.registries import Registry

from serv.app import App


@pytest.fixture
def app_with_empty_config(tmp_path):
    """Create an App instance with an empty config file."""
    config_file = tmp_path / "empty_config.yaml"
    with open(config_file, "w") as f:
        import yaml
        yaml.dump({}, f)  # Empty config
    
    return str(config_file)


def test_welcome_plugin_auto_enabled(app_with_empty_config):
    """Test that the welcome plugin is auto-enabled when no plugins/middleware are registered."""
    with patch('serv.app.App._enable_welcome_plugin') as mock_enable_welcome:
        with Registry():  # Bevy registry
            App(config=app_with_empty_config)
            
            # Check that _enable_welcome_plugin was called
            mock_enable_welcome.assert_called_once()


@pytest.mark.parametrize("has_plugins,has_middleware,should_enable", [
    (True, True, False),   # Has both plugins and middleware
    (True, False, False),  # Has plugins but no middleware
    (False, True, False),  # Has middleware but no plugins
    (False, False, True),  # Has neither plugins nor middleware
])
def test_welcome_plugin_conditional_enabling(has_plugins, has_middleware, should_enable, app_with_empty_config):
    """Test that the welcome plugin is only enabled when no plugins and no middleware are registered."""
    
    # Create mocks for plugins and middleware
    mock_plugin = MagicMock()
    mock_middleware = MagicMock()
    
    with patch('serv.app.App._enable_welcome_plugin') as mock_enable_welcome:
        with Registry():  # Bevy registry
            app = App(config=app_with_empty_config)
            
            # Manually set plugins and middleware based on test parameters
            if has_plugins:
                app._plugins[Path(".")] = [mock_plugin]
            
            if has_middleware:
                app._middleware = [mock_middleware]
            
            # Reset the mock to clear the initial call during construction
            mock_enable_welcome.reset_mock()
            
            # Manually call _load_plugins_from_config to test the condition
            app._load_plugins_from_config([])
            
            # Check if _enable_welcome_plugin was called as expected
            if should_enable:
                mock_enable_welcome.assert_called_once()
            else:
                mock_enable_welcome.assert_not_called()


def test_welcome_plugin_loading():
    """Test that the welcome plugin can be loaded from the bundled directory."""
    # Direct import test
    try:
        from serv.bundled.plugins.welcome import WelcomePlugin
        
        # Check it's a valid Plugin class
        assert hasattr(WelcomePlugin, 'on_app_request_begin')
    except ImportError:
        pytest.fail("Failed to import WelcomePlugin from serv.bundled.plugins.welcome")
    
    # Test creating a WelcomePlugin instance
    plugin = WelcomePlugin()
    assert plugin is not None
    assert plugin.__class__.__name__ == "WelcomePlugin" 