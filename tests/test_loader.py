"""
Tests for the ServLoader class using pytest.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest import mock
import importlib # Added for test_cross_plugin_import
import logging # Added for logger.debug in test_cross_plugin_import

from serv.loader import ServLoader

logger = logging.getLogger(__name__) # For test debugging

class TestServLoader:
    """Tests for the ServLoader class."""
    
    @pytest.fixture
    def setup_test_dirs(self, tmp_path):
        """Set up test fixtures with temporary directories."""
        plugins_dir_path = tmp_path / "test_plugins"
        plugins_dir_path.mkdir()
        
        middleware_dir_path = tmp_path / "test_middleware"
        middleware_dir_path.mkdir()
        
        plugin_pkg_dir_path = plugins_dir_path / "test_plugin"
        plugin_pkg_dir_path.mkdir()
        (plugin_pkg_dir_path / "__init__.py").write_text("# Test plugin package")
        (plugin_pkg_dir_path / "module1.py").write_text("VALUE = 'plugin_module1_val'")

        another_plugin_pkg_dir_path = plugins_dir_path / "another_plugin"
        another_plugin_pkg_dir_path.mkdir()
        (another_plugin_pkg_dir_path / "__init__.py").write_text("# Another test plugin package")
    
        middleware_pkg_dir_inner_path = middleware_dir_path / "test_mw_package"
        middleware_pkg_dir_inner_path.mkdir()
        (middleware_pkg_dir_inner_path / "__init__.py").write_text("# Test middleware package")
        (middleware_pkg_dir_inner_path / "module1.py").write_text("VALUE = 'mw_module1_val'")

        loader_instance = ServLoader(directory=str(plugins_dir_path))
    
        return {
            "plugins_dir": plugins_dir_path,
            "middleware_dir": middleware_dir_path,
            "plugin_pkg_dir": plugin_pkg_dir_path, # Actual package dir for "test_plugin"
            "another_plugin_pkg_dir": another_plugin_pkg_dir_path,
            "middleware_pkg_dir_inner": middleware_pkg_dir_inner_path,
            "loader": loader_instance
        }
        
    def test_load_module(self, setup_test_dirs):
        """Test loading a module from the plugins directory."""
        loader = setup_test_dirs["loader"]
        module = loader.load_module("test_plugin.module1")
        assert module.VALUE == 'plugin_module1_val'
        
    def test_load_package(self, setup_test_dirs):
        """Test loading a package from the plugins directory."""
        loader = setup_test_dirs["loader"]
        package = loader.load_module("test_plugin")
        assert hasattr(package, "__package__")
        assert package.__package__ == 'test_plugins.test_plugin'
        
    def test_module_not_found(self, setup_test_dirs):
        """Test that loading a non-existent module raises an appropriate exception."""
        loader = setup_test_dirs["loader"]
        with pytest.raises(ModuleNotFoundError):
            loader.load_module("test_plugin.non_existent_module")
            
    def test_package_not_found(self, setup_test_dirs):
        """Test that loading a non-existent package raises an appropriate exception."""
        loader = setup_test_dirs["loader"]
        with pytest.raises(ModuleNotFoundError):
            loader.load_module("non_existent_package")
            
    def test_cross_plugin_import(self, setup_test_dirs):
        """Test that one plugin can import another plugin's modules."""
        plugins_dir = setup_test_dirs["plugins_dir"]
        another_plugin_dir = setup_test_dirs["another_plugin_pkg_dir"]
        
        # Create a module in another_plugin that imports from test_plugin
        cross_import_code = """
from test_plugins.test_plugin.module1 import VALUE
IMPORTED_VALUE = VALUE
"""
        (another_plugin_dir / "cross_import.py").write_text(cross_import_code)
        
        loader = setup_test_dirs["loader"]
        module = loader.load_module("another_plugin.cross_import")
        assert module.IMPORTED_VALUE == 'plugin_module1_val'
        
    def test_nested_module(self, setup_test_dirs):
        """Test loading a nested module."""
        plugins_dir = setup_test_dirs["plugins_dir"]
        plugin_dir = setup_test_dirs["plugin_pkg_dir"]
        
        # Create a nested module structure
        nested_dir = plugin_dir / "nested"
        nested_dir.mkdir()
        (nested_dir / "__init__.py").write_text("# Nested package")
        (nested_dir / "deep_module.py").write_text("NESTED_VALUE = 'nested_value'")
        
        loader = setup_test_dirs["loader"]
        module = loader.load_module("test_plugin.nested.deep_module")
        assert module.NESTED_VALUE == 'nested_value'
        
    def test_package_without_init(self, setup_test_dirs):
        """Test loading a package that doesn't have an __init__.py file."""
        plugins_dir = setup_test_dirs["plugins_dir"]
        
        # Create a package without __init__.py
        no_init_dir = plugins_dir / "no_init_pkg"
        no_init_dir.mkdir()
        (no_init_dir / "some_module.py").write_text("NO_INIT_VALUE = 'no_init_value'")
        
        loader = setup_test_dirs["loader"]
        module = loader.load_module("no_init_pkg.some_module")
        assert module.NO_INIT_VALUE == 'no_init_value'
        
    def test_multiple_loaders(self, setup_test_dirs):
        """Test that multiple loader instances for different directories work correctly."""
        plugins_dir = setup_test_dirs["plugins_dir"]
        middleware_dir = setup_test_dirs["middleware_dir"]
        
        # Create a new loader for middleware directory
        middleware_loader = ServLoader(directory=str(middleware_dir))
        
        # Load modules from both loaders
        plugins_module = setup_test_dirs["loader"].load_module("test_plugin.module1")
        middleware_module = middleware_loader.load_module("test_mw_package.module1")
        
        assert plugins_module.VALUE == 'plugin_module1_val'
        assert middleware_module.VALUE == 'mw_module1_val'
        
    def test_loader_with_absolute_path(self, setup_test_dirs):
        """Test creating a loader with an absolute path."""
        plugins_dir = setup_test_dirs["plugins_dir"]
        absolute_path = plugins_dir.resolve()
        
        loader = ServLoader(directory=absolute_path)
        module = loader.load_module("test_plugin.module1")
        assert module.VALUE == 'plugin_module1_val'
