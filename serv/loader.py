"""
Package loader utility for Serv.

This module provides functionality to load packages from directories
without modifying sys.path. Packages are loaded and namespaced with
their respective folder names.
"""

import importlib.util
import logging
import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Optional, TypeVar, Union, cast

logger = logging.getLogger(__name__)

T = TypeVar("T")

class ServLoader:
    """
    Loader for Serv packages.
    
    This class provides functionality to search for and load packages
    from a specified directory without modifying sys.path.
    """
    
    def __init__(self, directory: str = './packages'):
        """
        Initialize the loader with a directory.
        
        Args:
            directory: Directory to search for packages (default: './packages')
        """
        self.directory = Path(directory)

    def get_search_path(self) -> Path:
        """
        Get the search path.
        
        Returns:
            Path object representing search directory
        """
        path = Path(self.directory).resolve()
        return path if path.exists() and path.is_dir() else Path()

    def load_package(self, 
                     package_name: str,
                     namespace: Optional[str] = None) -> Optional[ModuleType]:
        """
        Load a specific package from the search path.
        
        Args:
            package_name: Name of the package to load
            namespace: Optional namespace to look in (if None, use directory name)
            
        Returns:
            The loaded module or None if not found
        """
        search_path = self.get_search_path()
        if not search_path.exists():
            logger.warning(f"Search path {self.directory} does not exist")
            return None
            
        # If namespace is provided, verify it matches
        if namespace and search_path.name != namespace:
            logger.warning(f"Namespace {namespace} does not match directory name {search_path.name}")
            return None
            
        package_path = search_path / package_name
        init_path = package_path / "__init__.py"
        
        if not init_path.exists():
            logger.warning(f"Package {package_name} not found in {search_path}")
            return None
            
        # Create import name in the format 'namespace.package_name'
        import_name = f"{search_path.name}.{package_name}"
        
        # If not in sys.modules, we need to add the directory
        # to sys.modules with appropriate namespace
        if import_name not in sys.modules:
            # Create parent namespace module if it doesn't exist
            parent_module_name = search_path.name
            if parent_module_name not in sys.modules:
                # Create a namespace module
                parent_module = ModuleType(parent_module_name)
                parent_module.__path__ = [str(search_path)]
                sys.modules[parent_module_name] = parent_module
            
            # Now load the actual package - this will automatically be cached in sys.modules
            try:
                spec = importlib.util.spec_from_file_location(
                    import_name, 
                    init_path,
                    submodule_search_locations=[str(package_path)]
                )
                if spec is None or spec.loader is None:
                    logger.warning(f"Could not create spec for {import_name}")
                    return None
                    
                module = importlib.util.module_from_spec(spec)
                sys.modules[import_name] = module
                spec.loader.exec_module(module)
                
                # Update our local cache
                return module
            except Exception as e:
                logger.error(f"Error loading {import_name}: {e}")
                # Remove from sys.modules if loading failed
                if import_name in sys.modules:
                    del sys.modules[import_name]
                return None
        else:
            # Already in sys.modules, just return it
            module = sys.modules[import_name]
            return module

    def import_path(self, import_path: str) -> Optional[Union[ModuleType, object]]:
        """
        Import a module or object using a dotted path.
        
        Args:
            import_path: Path to import, can contain attribute access (e.g., 'packages.auth.main:AuthPlugin')
            
        Returns:
            The imported module or object, or None if import fails
        """
        if ":" in import_path:
            module_path, obj_path = import_path.split(":", 1)
        else:
            module_path, obj_path = import_path, None
        
        try:
            module = import_module(module_path)
            if obj_path:
                obj = module
                for part in obj_path.split('.'):
                    obj = getattr(obj, part)
                return obj
            return module
        except (ImportError, AttributeError) as e:
            logger.error(f"Error importing {import_path}: {e}")
            return None 