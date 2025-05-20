"""
Plugin and middleware loader utility for Serv.

This module provides functionality to load plugins and middleware from directories
without modifying sys.path. Plugins and middleware are loaded and namespaced with
their respective folder names.
"""

import importlib.util
import logging
import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Literal, Optional, TypeVar, Union, cast

logger = logging.getLogger(__name__)

LoaderType = Literal["plugin", "middleware"]
T = TypeVar("T")

class ServLoader:
    """
    Loader for Serv plugins and middleware.
    
    This class provides functionality to search for and load plugins/middleware
    from specified directories without modifying sys.path.
    """
    
    def __init__(self, 
                 plugin_dirs: List[str] = None,
                 middleware_dirs: List[str] = None):
        """
        Initialize the loader with plugin and middleware directories.
        
        Args:
            plugin_dirs: List of directories to search for plugins (default: ['./plugins'])
            middleware_dirs: List of directories to search for middleware (default: ['./middleware'])
        """
        self.plugin_dirs = plugin_dirs or ['./plugins']
        self.middleware_dirs = middleware_dirs or ['./middleware']
        self._module_cache: Dict[str, ModuleType] = {}
    
    def get_search_paths(self, loader_type: LoaderType) -> List[Path]:
        """
        Get the list of search paths for the specified loader type.
        
        Args:
            loader_type: Type of loader ('plugin' or 'middleware')
            
        Returns:
            List of Path objects representing search directories
        """
        if loader_type == "plugin":
            paths = [Path(p).resolve() for p in self.plugin_dirs]
        else:
            paths = [Path(p).resolve() for p in self.middleware_dirs]
            
        return [p for p in paths if p.exists() and p.is_dir()]
    
    def list_available(self, loader_type: LoaderType) -> Dict[str, List[str]]:
        """
        List all available plugins or middleware in the search paths.
        
        Args:
            loader_type: Type of loader ('plugin' or 'middleware')
            
        Returns:
            Dictionary mapping namespace to list of package names
        """
        result: Dict[str, List[str]] = {}
        
        for search_path in self.get_search_paths(loader_type):
            namespace = search_path.name
            packages = []
            
            for item in search_path.iterdir():
                if item.is_dir() and (item / "__init__.py").exists():
                    packages.append(item.name)
            
            if packages:
                result[namespace] = packages
        
        return result
    
    def load_package(self, 
                     loader_type: LoaderType, 
                     package_name: str,
                     namespace: Optional[str] = None) -> Optional[ModuleType]:
        """
        Load a specific package from the search paths.
        
        Args:
            loader_type: Type of loader ('plugin' or 'middleware')
            package_name: Name of the package to load
            namespace: Optional namespace to look in (if None, search all)
            
        Returns:
            The loaded module or None if not found
        """
        search_paths = self.get_search_paths(loader_type)
        
        # If namespace is provided, filter paths
        if namespace:
            search_paths = [p for p in search_paths if p.name == namespace]
            
        for search_path in search_paths:
            package_path = search_path / package_name
            init_path = package_path / "__init__.py"
            
            if not init_path.exists():
                continue
                
            # Create import name in the format 'namespace.package_name'
            import_name = f"{search_path.name}.{package_name}"
            
            # Return from cache if already loaded
            if import_name in self._module_cache:
                return self._module_cache[import_name]
                
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
                        continue
                        
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[import_name] = module
                    spec.loader.exec_module(module)
                    
                    # Update our local cache
                    self._module_cache[import_name] = module
                    return module
                except Exception as e:
                    logger.error(f"Error loading {import_name}: {e}")
                    # Remove from sys.modules if loading failed
                    if import_name in sys.modules:
                        del sys.modules[import_name]
                    continue
            else:
                # Already in sys.modules, just return it
                module = sys.modules[import_name]
                self._module_cache[import_name] = module
                return module
        
        logger.warning(f"Package {package_name} not found in any {loader_type} search paths")
        return None
    
    def load_all(self, loader_type: LoaderType) -> Dict[str, Dict[str, ModuleType]]:
        """
        Load all available plugins or middleware.
        
        Args:
            loader_type: Type of loader ('plugin' or 'middleware')
            
        Returns:
            Dictionary mapping namespace to a dict of package_name -> module
        """
        result: Dict[str, Dict[str, ModuleType]] = {}
        available = self.list_available(loader_type)
        
        for namespace, packages in available.items():
            namespace_packages: Dict[str, ModuleType] = {}
            
            for package_name in packages:
                module = self.load_package(loader_type, package_name, namespace)
                if module:
                    namespace_packages[package_name] = module
            
            if namespace_packages:
                result[namespace] = namespace_packages
        
        return result
    
    def import_path(self, import_path: str) -> Optional[Union[ModuleType, object]]:
        """
        Import a module or object using a dotted path.
        
        Args:
            import_path: Path to import, can contain attribute access (e.g., 'plugins.auth.main:AuthPlugin')
            
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