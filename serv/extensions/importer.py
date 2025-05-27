"""
Package importer utility for Serv.

This module provides functionality to load packages from directories
without modifying sys.path. Packages are loaded and namespaced with
their respective folder names.
"""

import importlib.abc
import importlib.machinery
import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import TypeVar

import serv.extensions.loader as pl

logger = logging.getLogger(__name__)

T = TypeVar("T")
type DottedPath = str


class ImporterMetaPathFinder(importlib.abc.MetaPathFinder):
    def __init__(self, directory):
        self.directory = directory

    def find_spec(self, fullname, path, target=None):
        # Only inject for modules in your target package
        parts = fullname.split(".")
        if parts[0] != self.directory.name:
            try:
                extension_spec = pl.find_extension_spec(Path(path[0]))
            except (FileNotFoundError, IndexError, TypeError):
                return None
            else:
                return importlib.util.spec_from_loader(
                    fullname,
                    ExtensionSourceFileLoader(
                        fullname, str(Path(path[0]) / f"{parts[-1]}.py"), extension_spec
                    ),
                )

        try:
            extension_spec = pl.find_extension_spec(self.directory / parts[1])
        except (FileNotFoundError, IndexError):
            extension_spec = None

        path = self.directory
        if len(parts) > 1:
            path = Path(path, *parts[1:])

        if path.is_dir():
            if not (path / "__init__.py").exists():
                return importlib.util.spec_from_loader(
                    fullname, ImporterPackageInjector(self.directory, extension_spec)
                )

            path /= "__init__.py"

        else:
            path = path.with_suffix(".py")

        if path.exists():
            return importlib.util.spec_from_loader(
                fullname, ExtensionSourceFileLoader(fullname, str(path), extension_spec)
            )

    @classmethod
    def inject(cls, directory: Path):
        sys.meta_path.insert(0, ImporterMetaPathFinder(directory))


class ExtensionSourceFileLoader(importlib.machinery.SourceFileLoader):
    def __init__(self, fullname, path, extension_spec):
        super().__init__(fullname, path)
        self.extension_spec = extension_spec

    def exec_module(self, module):
        super().exec_module(module)
        module.__extension_spec__ = self.extension_spec
        module.__extension_spec__ = self.extension_spec  # Backward compatibility


class ImporterPackageInjector(importlib.abc.Loader):
    def __init__(self, path, extension_spec):
        self.path = path
        self.extension_spec = extension_spec

    def create_module(self, spec):
        class Module(ModuleType):
            __package__ = spec.name
            __loader__ = self
            __spec__ = spec
            __file__ = str(Path(self.path) / "__init__.py")
            __path__ = str(self.path)
            __name__ = spec.name
            __package_injector__ = True
            __extension_spec__ = self.extension_spec
            __extension_spec__ = self.extension_spec  # Backward compatibility

        return Module(spec.name)

    def exec_module(self, module):
        return


class Importer:
    """
    Loader for Serv packages.

    This class provides functionality to load packages/modules from a
    given package directory without modifying sys.path.
    """

    def __init__(self, directory: Path | str, dotpath: str | None = None):
        """
        Args:
            directory: Directory to search for packages
        """
        self.directory = Path(directory).resolve()
        self._dotpath = dotpath
        if not dotpath:
            self._dotpath = self.directory.name
            ImporterMetaPathFinder.inject(self.directory)

    def using_sub_module(self, name):
        return Importer(self.directory, f"{self._dotpath}.{name}")

    def load_module(self, module_path: DottedPath) -> ModuleType:
        """Imports a module from inside of the search directory package. This assumes that
        the dotted path directly correlates with the file structure and that the path is
        for a python file."""
        return importlib.import_module(f"{self._dotpath}.{module_path}")
