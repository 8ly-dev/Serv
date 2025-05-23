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
