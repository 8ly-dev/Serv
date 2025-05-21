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
    
    def test_initialization(self, setup_test_dirs):
        """Test that the loader initializes correctly."""
        loader = setup_test_dirs["loader"]
        plugins_dir = setup_test_dirs["plugins_dir"]
        assert loader.get_search_path() == plugins_dir.resolve()
    
    def test_get_search_path(self, setup_test_dirs):
        """Test that search paths are resolved correctly."""
        loader = setup_test_dirs["loader"]
        plugins_dir = setup_test_dirs["plugins_dir"]
        assert loader.get_search_path().exists()
        assert loader.get_search_path() == plugins_dir.resolve()
    
    def test_list_available(self, setup_test_dirs):
        """Test listing available packages."""
        loader = setup_test_dirs["loader"]
        plugins_dir = setup_test_dirs["plugins_dir"]
        available = loader.list_available()
        expected_namespace = plugins_dir.name
        assert expected_namespace in available
        assert sorted(available[expected_namespace]) == sorted(["another_plugin", "test_plugin"])
    
    @mock.patch('importlib.util.module_from_spec')
    @mock.patch('importlib.util.spec_from_file_location')
    def test_load_package(self, mock_spec_from_file_location, mock_module_from_spec, setup_test_dirs):
        """Test loading a package."""
        loader = setup_test_dirs["loader"]
        plugins_dir = setup_test_dirs["plugins_dir"]
        plugin_pkg_dir = setup_test_dirs["plugin_pkg_dir"]
        namespace = plugins_dir.name

        mock_spec_test_plugin = mock.MagicMock(name=f"spec_for_{namespace}.test_plugin")
        mock_spec_test_plugin.loader = mock.MagicMock()
        mock_spec_test_plugin.name = f"{namespace}.test_plugin"
        mock_spec_test_plugin.submodule_search_locations = [str(plugin_pkg_dir)]

        mock_test_plugin_module = mock.MagicMock(name=f"module_{namespace}.test_plugin")
        mock_test_plugin_module.__name__ = f"{namespace}.test_plugin"
        mock_test_plugin_module.__path__ = [str(plugin_pkg_dir)] 

        def spec_side_effect(name, location, **kwargs):
            if name == f"{namespace}.test_plugin" and Path(location).parent.name == "test_plugin":
                return mock_spec_test_plugin
            elif name == f"{namespace}.nonexistent_plugin":
                return None 
            return None 
        mock_spec_from_file_location.side_effect = spec_side_effect

        def module_side_effect(spec):
            if spec and spec.name == f"{namespace}.test_plugin":
                return mock_test_plugin_module
            generic_mock = mock.MagicMock(name=f"module_for_spec_{getattr(spec, 'name', 'unknown')}")
            generic_mock.__name__ = getattr(spec, 'name', 'unknown_spec_module')
            return generic_mock
        mock_module_from_spec.side_effect = module_side_effect

        # Clean up sys.modules and loader cache for this specific test package to ensure a fresh load attempt
        # This is important if other tests using mocks might have populated these for the same name.
        module_full_name = f"{namespace}.test_plugin"
        if module_full_name in sys.modules: del sys.modules[module_full_name]
        if module_full_name in loader._module_cache: del loader._module_cache[module_full_name]
        # Clean up parent namespace too if it was created by loader and might hold outdated sub-pkg refs
        if namespace in sys.modules and hasattr(sys.modules[namespace], "test_plugin"):
            delattr(sys.modules[namespace], "test_plugin")

        loaded_module = loader.load_package(package_name="test_plugin", namespace=namespace)
        assert loaded_module is not None, "load_package should return the module for 'test_plugin'"
        assert loaded_module.__name__ == f"{namespace}.test_plugin"
        
        expected_init_path = plugin_pkg_dir / "__init__.py"
        mock_spec_from_file_location.assert_called_with(
            f"{namespace}.test_plugin", 
            expected_init_path, 
            submodule_search_locations=[str(plugin_pkg_dir)]
        )
        mock_module_from_spec.assert_called_with(mock_spec_test_plugin)
        mock_spec_test_plugin.loader.exec_module.assert_called_with(mock_test_plugin_module)

        mock_spec_from_file_location.reset_mock()
        mock_module_from_spec.reset_mock()
        # Clean sys.modules for non-existent as well, just in case though ServLoader should handle it
        module_full_name_nonexistent = f"{namespace}.nonexistent_plugin"
        if module_full_name_nonexistent in sys.modules: del sys.modules[module_full_name_nonexistent]
        if module_full_name_nonexistent in loader._module_cache: del loader._module_cache[module_full_name_nonexistent]

        assert loader.load_package(package_name="nonexistent_plugin", namespace=namespace) is None
    
    def test_import_path_object_load(self, setup_test_dirs):
        """Test importing a module by path."""
        loader = setup_test_dirs["loader"]
        plugins_dir = setup_test_dirs["plugins_dir"]
        namespace = plugins_dir.name

        # Ensure a clean slate in sys.modules for the packages this test loads for real
        # to avoid interference from mocks in other tests if loader shares sys.modules state.
        module_name_to_clean = f"{namespace}.test_plugin"
        submodule_name_to_clean = f"{module_name_to_clean}.module1"
        if submodule_name_to_clean in sys.modules: del sys.modules[submodule_name_to_clean]
        if module_name_to_clean in sys.modules: del sys.modules[module_name_to_clean]
        if module_name_to_clean in loader._module_cache: del loader._module_cache[module_name_to_clean]
        if submodule_name_to_clean in loader._module_cache: del loader._module_cache[submodule_name_to_clean]
        # Also clean parent namespace module from this specific package attribute
        if namespace in sys.modules and hasattr(sys.modules[namespace], "test_plugin"):
             delattr(sys.modules[namespace], "test_plugin")

        test_plugin_module = loader.load_package(package_name="test_plugin", namespace=namespace)
        assert test_plugin_module is not None, f"ServLoader failed to load package '{namespace}.test_plugin'"
        assert test_plugin_module.__name__ == f"{namespace}.test_plugin"
        assert hasattr(test_plugin_module, '__spec__'), "Loaded module should have __spec__ attribute"
        assert test_plugin_module.__spec__ is not None, "Module __spec__ should not be None"
        assert test_plugin_module.__spec__.name == f"{namespace}.test_plugin"

        # Verify submodule access and content after REAL load by ServLoader
        try:
            # Standard import should now work if ServLoader has set up paths correctly
            imported_submodule = importlib.import_module(f"{namespace}.test_plugin.module1")
            assert hasattr(imported_submodule, 'VALUE'), "Submodule 'module1' does not have VALUE attribute"
            assert imported_submodule.VALUE == 'plugin_module1_val', "Submodule 'module1' VALUE mismatch"
        except ImportError as e:
            pytest.fail(f"Could not import submodule '{namespace}.test_plugin.module1': {e}. sys.modules keys like: {{k for k in sys.modules if namespace in k}}")

        value = loader.import_path(f"{namespace}.test_plugin.module1:VALUE")
        assert value == 'plugin_module1_val'

        submodule_via_import_path = loader.import_path(f"{namespace}.test_plugin.module1")
        assert submodule_via_import_path is not None
        assert submodule_via_import_path.VALUE == 'plugin_module1_val'

        pkg_module_via_import_path = loader.import_path(f"{namespace}.test_plugin")
        assert pkg_module_via_import_path is not None
        assert hasattr(pkg_module_via_import_path, "module1"), "Package module should have submodule as attribute"
        assert pkg_module_via_import_path.module1.VALUE == 'plugin_module1_val'

        assert loader.import_path(f"{namespace}.test_plugin.nonexistent:FOO") is None
        assert loader.import_path(f"{namespace}.nonexistent_pkg:FOO") is None
    
    def test_cross_plugin_import(self, setup_test_dirs):
        """Test that one plugin can import another using the fully qualified import path."""
        loader = setup_test_dirs["loader"]
        plugins_dir = setup_test_dirs["plugins_dir"]
        namespace = plugins_dir.name

        base_pkg_name = "base_plugin_for_cross"
        dependent_pkg_name = "dependent_plugin_for_cross"

        # Clean sys.modules for these specific test packages
        for pkg_name in [base_pkg_name, dependent_pkg_name]:
            full_pkg_name = f"{namespace}.{pkg_name}"
            sub_main_name = f"{full_pkg_name}.main" # if main is a submodule
            sub_util_name = f"{full_pkg_name}.util" # if util is a submodule
            if sub_main_name in sys.modules: del sys.modules[sub_main_name]
            if sub_util_name in sys.modules: del sys.modules[sub_util_name]
            if full_pkg_name in sys.modules: del sys.modules[full_pkg_name]
            if full_pkg_name in loader._module_cache: del loader._module_cache[full_pkg_name]
            if sub_main_name in loader._module_cache: del loader._module_cache[sub_main_name]
            if sub_util_name in loader._module_cache: del loader._module_cache[sub_util_name]
            if namespace in sys.modules and hasattr(sys.modules[namespace], pkg_name):
                delattr(sys.modules[namespace], pkg_name)

        base_dir = plugins_dir / base_pkg_name
        base_dir.mkdir(exist_ok=True)
        (base_dir / "__init__.py").write_text(f"# {base_pkg_name} init")
        (base_dir / "util.py").write_text("""
class BaseUtility:
    def get_info(self):
        return \"Info from BaseUtility\"
""")

        dependent_dir = plugins_dir / dependent_pkg_name
        dependent_dir.mkdir(exist_ok=True)
        (dependent_dir / "__init__.py").write_text(f"# {dependent_pkg_name} init")
        dependent_main_content = f"""
from {namespace}.{base_pkg_name}.util import BaseUtility

class DependentService:
    def __init__(self):
        self.util = BaseUtility()
    def process(self):
        return f\"Processed: {{self.util.get_info()}}\"
"""
        (dependent_dir / "main.py").write_text(dependent_main_content)

        base_pkg_module = loader.load_package(package_name=base_pkg_name, namespace=namespace)
        assert base_pkg_module is not None, f"Failed to load {base_pkg_name}"
        assert base_pkg_module.__name__ == f"{namespace}.{base_pkg_name}"
        assert hasattr(base_pkg_module, '__spec__')

        dependent_pkg_module = loader.load_package(package_name=dependent_pkg_name, namespace=namespace)
        assert dependent_pkg_module is not None, f"Failed to load {dependent_pkg_name}"
        assert dependent_pkg_module.__name__ == f"{namespace}.{dependent_pkg_name}"
        assert hasattr(dependent_pkg_module, '__spec__')
        
        try:
            final_dependent_main_module = importlib.import_module(f"{namespace}.{dependent_pkg_name}.main")
            ServiceClass = final_dependent_main_module.DependentService
            instance = ServiceClass()
            result = instance.process()
            assert result == f"Processed: Info from BaseUtility"
        except ImportError as e:
            loaded_modules_in_namespace = {k:v for k,v in sys.modules.items() if k.startswith(namespace)}
            pytest.fail(f"ImportError during cross-import test: {e}. Namespace: {namespace}. sys.modules for namespace: {loaded_modules_in_namespace}. sys.path: {sys.path}")
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}") 