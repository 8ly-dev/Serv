"""
Tests for the Importer class using pytest.
"""

import logging  # Added for logger.debug in test_cross_plugin_import
import sys

import pytest

from serv.extensions.importer import Importer, ImporterMetaPathFinder

logger = logging.getLogger(__name__)  # For test debugging


@pytest.fixture(scope="function", autouse=True)
def isolate_loader_tests():
    """Isolate loader tests from other tests by managing sys.meta_path properly."""
    # Store the original meta_path state
    original_meta_path = sys.meta_path.copy()

    # Remove any existing ImporterMetaPathFinder instances that might have been
    # left by other tests before we start
    sys.meta_path[:] = [
        finder
        for finder in sys.meta_path
        if not isinstance(finder, ImporterMetaPathFinder)
    ]

    # Store original modules to restore later (only for our test modules)
    test_module_prefixes = ["test_extensions", "test_middleware"]
    original_modules = {}
    modules_to_remove = []

    for module_name in list(sys.modules.keys()):
        if any(module_name.startswith(prefix) for prefix in test_module_prefixes):
            original_modules[module_name] = sys.modules[module_name]
            modules_to_remove.append(module_name)

    # Remove our test modules from sys.modules
    for module_name in modules_to_remove:
        del sys.modules[module_name]

    yield

    # Clean up: restore the original meta_path and remove any ImporterMetaPathFinder
    # instances that were added during this test
    sys.meta_path[:] = [
        finder
        for finder in original_meta_path
        if not isinstance(finder, ImporterMetaPathFinder)
    ]

    # Remove any test modules that were loaded during this test
    modules_to_clean = []
    for module_name in list(sys.modules.keys()):
        if any(module_name.startswith(prefix) for prefix in test_module_prefixes):
            modules_to_clean.append(module_name)

    for module_name in modules_to_clean:
        del sys.modules[module_name]

    # Restore original modules if they existed
    for module_name, module in original_modules.items():
        sys.modules[module_name] = module


class TestServLoader:
    """Tests for the Importer class."""

    @pytest.fixture
    def setup_test_dirs(self, tmp_path):
        """Set up test fixtures with temporary directories."""
        plugins_dir_path = tmp_path / "test_extensions"
        plugins_dir_path.mkdir()

        middleware_dir_path = tmp_path / "test_middleware"
        middleware_dir_path.mkdir()

        plugin_pkg_dir_path = plugins_dir_path / "test_extension"
        plugin_pkg_dir_path.mkdir()
        (plugin_pkg_dir_path / "__init__.py").write_text("# Test plugin package")
        (plugin_pkg_dir_path / "module1.py").write_text("VALUE = 'plugin_module1_val'")

        another_plugin_pkg_dir_path = plugins_dir_path / "another_plugin"
        another_plugin_pkg_dir_path.mkdir()
        (another_plugin_pkg_dir_path / "__init__.py").write_text(
            "# Another test plugin package"
        )

        middleware_pkg_dir_inner_path = middleware_dir_path / "test_mw_package"
        middleware_pkg_dir_inner_path.mkdir()
        (middleware_pkg_dir_inner_path / "__init__.py").write_text(
            "# Test middleware package"
        )
        (middleware_pkg_dir_inner_path / "module1.py").write_text(
            "VALUE = 'mw_module1_val'"
        )

        loader_instance = Importer(directory=str(plugins_dir_path))

        return {
            "plugins_dir": plugins_dir_path,
            "middleware_dir": middleware_dir_path,
            "plugin_pkg_dir": plugin_pkg_dir_path,  # Actual package dir for "test_extension"
            "another_plugin_pkg_dir": another_plugin_pkg_dir_path,
            "middleware_pkg_dir_inner": middleware_pkg_dir_inner_path,
            "loader": loader_instance,
        }

    def test_load_module(self, setup_test_dirs):
        """Test loading a module from the plugins directory."""
        loader = setup_test_dirs["loader"]
        module = loader.load_module("test_extension.module1")
        assert module.VALUE == "plugin_module1_val"

    def test_load_package(self, setup_test_dirs):
        """Test loading a package from the plugins directory."""
        loader = setup_test_dirs["loader"]
        package = loader.load_module("test_extension")
        assert hasattr(package, "__package__")
        assert package.__package__ == "test_extensions.test_extension"

    def test_module_not_found(self, setup_test_dirs):
        """Test that loading a non-existent module raises an appropriate exception."""
        loader = setup_test_dirs["loader"]
        with pytest.raises(ModuleNotFoundError):
            loader.load_module("test_extension.non_existent_module")

    def test_package_not_found(self, setup_test_dirs):
        """Test that loading a non-existent package raises an appropriate exception."""
        loader = setup_test_dirs["loader"]
        with pytest.raises(ModuleNotFoundError):
            loader.load_module("non_existent_package")

    def test_cross_plugin_import(self, setup_test_dirs):
        """Test that one plugin can import another plugin's modules."""
        setup_test_dirs["plugins_dir"]
        another_extension_dir = setup_test_dirs["another_plugin_pkg_dir"]

        # Create a module in another_plugin that imports from test_extension
        cross_import_code = """
from test_extensions.test_extension.module1 import VALUE
IMPORTED_VALUE = VALUE
"""
        (another_extension_dir / "cross_import.py").write_text(cross_import_code)

        loader = setup_test_dirs["loader"]
        module = loader.load_module("another_plugin.cross_import")
        assert module.IMPORTED_VALUE == "plugin_module1_val"

    def test_nested_module(self, setup_test_dirs):
        """Test loading a nested module."""
        setup_test_dirs["plugins_dir"]
        extension_dir = setup_test_dirs["plugin_pkg_dir"]

        # Create a nested module structure
        nested_dir = extension_dir / "nested"
        nested_dir.mkdir()
        (nested_dir / "__init__.py").write_text("# Nested package")
        (nested_dir / "deep_module.py").write_text("NESTED_VALUE = 'nested_value'")

        loader = setup_test_dirs["loader"]
        module = loader.load_module("test_extension.nested.deep_module")
        assert module.NESTED_VALUE == "nested_value"

    def test_package_without_init(self, setup_test_dirs):
        """Test loading a package that doesn't have an __init__.py file."""
        plugins_dir = setup_test_dirs["plugins_dir"]

        # Create a package without __init__.py
        no_init_dir = plugins_dir / "no_init_pkg"
        no_init_dir.mkdir()
        (no_init_dir / "some_module.py").write_text("NO_INIT_VALUE = 'no_init_value'")

        loader = setup_test_dirs["loader"]
        module = loader.load_module("no_init_pkg.some_module")
        assert module.NO_INIT_VALUE == "no_init_value"

    def test_multiple_loaders(self, setup_test_dirs):
        """Test that multiple loader instances for different directories work correctly."""
        setup_test_dirs["plugins_dir"]
        middleware_dir = setup_test_dirs["middleware_dir"]

        # Load modules from the first loader first
        plugins_module = setup_test_dirs["loader"].load_module("test_extension.module1")
        assert plugins_module.VALUE == "plugin_module1_val"

        # Create a new loader for middleware directory after the first load is complete
        middleware_loader = Importer(directory=str(middleware_dir))

        # Load modules from the middleware loader
        middleware_module = middleware_loader.load_module("test_mw_package.module1")
        assert middleware_module.VALUE == "mw_module1_val"

    def test_loader_with_absolute_path(self, setup_test_dirs):
        """Test creating a loader with an absolute path."""
        plugins_dir = setup_test_dirs["plugins_dir"]
        absolute_path = plugins_dir.resolve()

        loader = Importer(directory=absolute_path)
        module = loader.load_module("test_extension.module1")
        assert module.VALUE == "plugin_module1_val"
