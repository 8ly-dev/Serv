"""
Tests for the ServLoader class using pytest.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest import mock

from serv.loader import ServLoader


class TestServLoader:
    """Tests for the ServLoader class."""
    
    @pytest.fixture
    def setup_test_dirs(self, tmp_path):
        """Set up test fixtures with temporary directories."""
        # Create a test plugins directory
        plugins_dir = tmp_path / "test_plugins"
        plugins_dir.mkdir()
        
        # Create a test middleware directory
        middleware_dir = tmp_path / "test_middleware"
        middleware_dir.mkdir()
        
        # Create plugin package
        plugin_dir = plugins_dir / "test_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("# Test plugin package")
        
        # Create middleware package
        middleware_pkg_dir = middleware_dir / "test_middleware"
        middleware_pkg_dir.mkdir()
        (middleware_pkg_dir / "__init__.py").write_text("# Test middleware package")
        
        # Create the loader
        loader = ServLoader(
            plugin_dirs=[str(plugins_dir)],
            middleware_dirs=[str(middleware_dir)]
        )
        
        # Return a dictionary with all the test objects
        return {
            "plugins_dir": plugins_dir,
            "middleware_dir": middleware_dir,
            "plugin_dir": plugin_dir,
            "middleware_pkg_dir": middleware_pkg_dir,
            "loader": loader
        }
    
    def test_initialization(self, setup_test_dirs):
        """Test that the loader initializes correctly."""
        loader = setup_test_dirs["loader"]
        plugins_dir = setup_test_dirs["plugins_dir"]
        middleware_dir = setup_test_dirs["middleware_dir"]
        
        assert loader.plugin_dirs == [str(plugins_dir)]
        assert loader.middleware_dirs == [str(middleware_dir)]
        assert loader._module_cache == {}
    
    def test_get_search_paths(self, setup_test_dirs):
        """Test that search paths are resolved correctly."""
        loader = setup_test_dirs["loader"]
        
        plugin_paths = loader.get_search_paths("plugin")
        middleware_paths = loader.get_search_paths("middleware")
        
        assert len(plugin_paths) == 1
        assert len(middleware_paths) == 1
        assert plugin_paths[0].name == "test_plugins"
        assert middleware_paths[0].name == "test_middleware"
    
    def test_list_available(self, setup_test_dirs):
        """Test listing available packages."""
        loader = setup_test_dirs["loader"]
        
        packages = loader.list_available("plugin")
        assert packages == {"test_plugins": ["test_plugin"]}
        
        packages = loader.list_available("middleware")
        assert packages == {"test_middleware": ["test_middleware"]}
    
    @mock.patch('importlib.util.spec_from_file_location')
    @mock.patch('importlib.util.module_from_spec')
    def test_load_package(self, mock_module_from_spec, mock_spec_from_file_location, setup_test_dirs):
        """Test loading a package."""
        # Set up mocks for importlib
        mock_spec = mock.MagicMock()
        mock_spec.loader = mock.MagicMock()
        mock_spec_from_file_location.return_value = mock_spec
        
        mock_module = mock.MagicMock()
        mock_module_from_spec.return_value = mock_module
        
        # Get test objects
        loader = setup_test_dirs["loader"]
        plugin_dir = setup_test_dirs["plugin_dir"]
        
        # Create a simple plugin module
        plugin_module_path = plugin_dir / "main.py"
        plugin_module_path.write_text("""
class TestPlugin:
    def __init__(self):
        self.name = 'Test Plugin'
""")
        
        # Load the package
        loader.load_package("plugin", "test_plugin", "test_plugins")
        
        # Check that the module was loaded and cached
        assert mock_spec_from_file_location.call_count == 1
        assert mock_module_from_spec.call_count == 1
        
        # Check that the module was cached
        mock_spec.loader.exec_module.assert_called_once_with(mock_module)
    
    def test_import_path(self, setup_test_dirs):
        """Test importing a module by path."""
        # Get test objects
        loader = setup_test_dirs["loader"]
        plugins_dir = setup_test_dirs["plugins_dir"]
        
        # Create a module with a test class
        module_dir = plugins_dir / "my_plugin"
        module_dir.mkdir()
        
        init_file = module_dir / "__init__.py"
        init_file.write_text("# My plugin package")
        
        main_file = module_dir / "main.py"
        main_file.write_text("""
class MyPlugin:
    def hello(self):
        return "Hello from MyPlugin"
""")
        
        # Create a mock for the module with our test class
        mock_module = mock.MagicMock()
        mock_class = mock.MagicMock()
        mock_class.hello = lambda: "Hello from MyPlugin"
        mock_module.MyPlugin = mock_class
        
        # Patch the import_module function
        with mock.patch("serv.loader.import_module") as mock_import:
            # Set up the mock to return our mock module
            mock_import.return_value = mock_module
            
            # Call the function being tested
            result = loader.import_path("test_plugins.my_plugin.main:MyPlugin")
            
            # Verify the import was called with the correct module path
            mock_import.assert_called_once_with("test_plugins.my_plugin.main")
            
            # Verify we got the right class back
            assert result == mock_class
            
    def test_cross_plugin_import(self, setup_test_dirs):
        """Test that one plugin can import another using the fully qualified import path."""
        # Get test objects
        loader = setup_test_dirs["loader"]
        plugins_dir = setup_test_dirs["plugins_dir"]
        
        # Create two plugin packages: base_plugin and dependent_plugin
        base_dir = plugins_dir / "base_plugin"
        base_dir.mkdir()
        (base_dir / "__init__.py").write_text("# Base plugin package")
        
        dependent_dir = plugins_dir / "dependent_plugin"
        dependent_dir.mkdir()
        (dependent_dir / "__init__.py").write_text("# Dependent plugin package")
        
        # Create implementation files
        base_main_file = base_dir / "main.py"
        base_main_file.write_text("""
class BasePlugin:
    def get_version(self):
        return "1.0.0"
""")
        
        dependent_main_file = dependent_dir / "main.py"
        dependent_main_file.write_text("""
import sys
from test_plugins.base_plugin.main import BasePlugin

class DependentPlugin:
    def __init__(self):
        self.base = BasePlugin()
        
    def get_base_version(self):
        return self.base.get_version()
""")
        
        # Set up mocks for the modules
        base_module = mock.MagicMock()
        base_class = mock.MagicMock()
        base_class.get_version = lambda: "1.0.0"
        base_module.BasePlugin = base_class
        
        dependent_module = mock.MagicMock()
        dependent_class = mock.MagicMock()
        dependent_class.get_base_version = lambda: "1.0.0"
        dependent_module.DependentPlugin = dependent_class
        dependent_module.BasePlugin = base_class  # Simulate the import
        
        # Use a side effect function to handle different import paths
        def side_effect(module_path):
            if module_path == "test_plugins.base_plugin.main":
                return base_module
            elif module_path == "test_plugins.dependent_plugin.main":
                return dependent_module
            else:
                raise ImportError(f"No module named '{module_path}'")
        
        # Test loading packages and cross-plugin importing
        with mock.patch("serv.loader.import_module", side_effect=side_effect), \
             mock.patch("importlib.util.spec_from_file_location") as mock_spec_location, \
             mock.patch("importlib.util.module_from_spec") as mock_module_from_spec:
            
            # Mock spec and module for base plugin
            base_spec = mock.MagicMock()
            base_spec.loader = mock.MagicMock()
            mock_spec_location.return_value = base_spec
            mock_module_from_spec.return_value = base_module
            
            # Load the base plugin first
            base_result = loader.load_package("plugin", "base_plugin", "test_plugins")
            assert base_result is not None
            
            # Now mock for dependent plugin
            dependent_spec = mock.MagicMock()
            dependent_spec.loader = mock.MagicMock()
            mock_spec_location.return_value = dependent_spec
            mock_module_from_spec.return_value = dependent_module
            
            # Load the dependent plugin
            dependent_result = loader.load_package("plugin", "dependent_plugin", "test_plugins")
            assert dependent_result is not None
            
            # Verify the dependent plugin can use the base plugin
            result_class = loader.import_path("test_plugins.dependent_plugin.main:DependentPlugin")
            assert result_class is dependent_class
            assert result_class.get_base_version() == "1.0.0" 