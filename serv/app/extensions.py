"""Extension management system for Serv applications.

This module provides the ExtensionManager class that handles registration,
retrieval, and coordination of extensions within a Serv application. Extensions
are the primary way to add functionality to Serv applications.

The ExtensionManager coordinates with the ExtensionLoader to handle the loading
process and maintains a registry of all active extensions.
"""

import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from serv.extensions import Listener

if TYPE_CHECKING:
    from serv.extensions.loader import ExtensionLoader

logger = logging.getLogger(__name__)


class ExtensionManager:
    """Manages extension registration, retrieval, and lifecycle.

    The ExtensionManager serves as the central registry for all extensions
    within a Serv application. It provides methods to register new extensions,
    retrieve existing ones, and coordinate with the extension loading system.

    Extensions are organized by their filesystem path, allowing multiple
    listeners from the same extension to be grouped together.

    Examples:
        Basic extension registration:

        ```python
        from serv.app.extensions import ExtensionManager
        from serv.extensions import Listener

        manager = ExtensionManager()

        class MyListener(Listener):
            async def on_app_startup(self):
                print("App starting up!")

        # Register the extension
        listener = MyListener()
        manager.add_extension(listener)

        # Retrieve extension by path
        extension = manager.get_extension(Path("./extensions/my_extension"))
        ```

        Welcome extension loading:

        ```python
        # If no extensions are configured, the welcome extension is automatically loaded
        manager = ExtensionManager()
        extension_loader = ExtensionLoader(app, importer)

        # This will load the welcome extension if no others are present
        manager.load_welcome_extension_if_needed(extension_loader, [])
        ```

        Extension coordination with dependency injection:

        ```python
        from bevy.containers import Container

        manager = ExtensionManager()
        container = Container()

        # Extensions are automatically registered with the DI container
        manager.add_extension(MyListener(), container)
        ```

    Attributes:
        extensions: Dictionary mapping extension paths to lists of listener instances.
            This allows multiple listeners from the same extension to be grouped together.
    """

    def __init__(self):
        """Initialize a new ExtensionManager.

        Creates an empty extension registry using a defaultdict to automatically
        create new lists for extension paths when needed.
        """
        self._extensions: dict[Path, list[Listener]] = defaultdict(list)

    @property
    def extensions(self) -> dict[Path, list[Listener]]:
        """Get the current extension registry.

        Returns:
            Dictionary mapping extension paths to lists of listener instances.
            This is a read-only view of the internal extension storage.
        """
        return dict(self._extensions)

    def add_extension(self, extension: Listener, container=None) -> None:
        """Register a new extension listener with the manager.

        This method adds an extension listener to the registry and optionally
        registers it with a dependency injection container. The extension's
        path is determined from its extension spec or module information.

        Args:
            extension: The listener instance to register. Must be a subclass
                of Listener with proper extension metadata.
            container: Optional dependency injection container to register
                the extension with. If provided, the extension will be
                available for injection.

        Examples:
            Register a simple extension:

            ```python
            class NotificationListener(Listener):
                async def on_user_created(self, user_id: int):
                    await self.send_notification(user_id)

            manager = ExtensionManager()
            listener = NotificationListener()
            manager.add_extension(listener)
            ```

            Register with dependency injection:

            ```python
            from bevy.containers import Container

            container = Container()
            manager = ExtensionManager()

            manager.add_extension(NotificationListener(), container)

            # Extension is now available for injection
            injected_listener = container.get(NotificationListener)
            ```

            Stand-alone extension registration:

            ```python
            # For extensions not loaded from filesystem
            class StandAloneListener(Listener):
                _stand_alone = True

                async def on_request_begin(self):
                    pass

            manager.add_extension(StandAloneListener())
            ```

        Note:
            The extension path is determined in the following order:
            1. From the extension's __extension_spec__ attribute
            2. For stand-alone extensions, uses "__stand_alone__" path
            3. From the extension's module __extension_spec__ attribute

        Raises:
            AttributeError: If the extension doesn't have proper metadata
                for path determination.
        """
        # Determine the extension path for storage
        if hasattr(extension, "__extension_spec__") and extension.__extension_spec__:
            spec = extension.__extension_spec__
        elif hasattr(extension, "_stand_alone") and extension._stand_alone:
            # For stand-alone listeners, use a default path
            spec = type("MockSpec", (), {"path": Path("__stand_alone__")})()
        else:
            module = sys.modules[extension.__module__]
            spec = module.__extension_spec__

        # Register extension in our registry
        self._extensions[spec.path].append(extension)

        # Register with dependency injection container if provided
        if container is not None:
            container.add(extension)

        logger.debug(
            f"Registered extension {type(extension).__name__} at path {spec.path}"
        )

    def get_extension(self, path: Path) -> Listener | None:
        """Retrieve the first extension listener for a given path.

        Args:
            path: The filesystem path of the extension to retrieve.

        Returns:
            The first listener instance for the given path, or None if
            no extensions are registered at that path.

        Examples:
            Retrieve an extension by path:

            ```python
            from pathlib import Path

            manager = ExtensionManager()

            # Assume an extension was registered
            auth_path = Path("./extensions/auth")
            auth_extension = manager.get_extension(auth_path)

            if auth_extension:
                print(f"Found auth extension: {type(auth_extension).__name__}")
            else:
                print("No auth extension found")
            ```

            Check for stand-alone extensions:

            ```python
            standalone_extension = manager.get_extension(Path("__stand_alone__"))
            ```

        Note:
            If multiple listeners are registered for the same path, this method
            returns only the first one. Use the `extensions` property to access
            all listeners for a path.
        """
        extension_list = self._extensions.get(path, [])
        return extension_list[0] if extension_list else None

    def get_all_extensions(self, path: Path) -> list[Listener]:
        """Retrieve all extension listeners for a given path.

        Args:
            path: The filesystem path of the extensions to retrieve.

        Returns:
            List of all listener instances for the given path. Returns
            an empty list if no extensions are registered at that path.

        Examples:
            Get all listeners for a path:

            ```python
            auth_extensions = manager.get_all_extensions(Path("./extensions/auth"))

            for extension in auth_extensions:
                print(f"Auth listener: {type(extension).__name__}")
            ```
        """
        return list(self._extensions.get(path, []))

    def has_extensions(self) -> bool:
        """Check if any extensions are currently registered.

        Returns:
            True if at least one extension is registered, False otherwise.

        Examples:
            Check before loading welcome extension:

            ```python
            if not manager.has_extensions():
                manager.load_welcome_extension_if_needed(loader, [])
            ```
        """
        return len(self._extensions) > 0

    def load_welcome_extension_if_needed(
        self,
        extension_loader: "ExtensionLoader",
        loaded_extensions: list,
        loaded_middleware: list = None,
    ) -> bool:
        """Load the welcome extension if no other extensions are present.

        This method provides a default landing page for new Serv applications
        by loading the bundled welcome extension when no other extensions
        have been configured.

        Args:
            extension_loader: The ExtensionLoader instance to use for loading.
            loaded_extensions: List of already loaded extensions to check.
            loaded_middleware: List of already loaded middleware to check.

        Returns:
            True if the welcome extension was loaded, False if it wasn't needed
            or failed to load.

        Examples:
            Load welcome extension during app initialization:

            ```python
            from serv.extensions.loader import ExtensionLoader
            from serv.extensions.importer import Importer

            manager = ExtensionManager()
            importer = Importer("./extensions")
            loader = ExtensionLoader(app, importer)

            # This will load welcome extension if no others are configured
            success = manager.load_welcome_extension_if_needed(loader, [])

            if success:
                print("Welcome extension loaded")
            ```

            Skip welcome extension if others exist:

            ```python
            # If extensions are already loaded, welcome won't be loaded
            success = manager.load_welcome_extension_if_needed(loader, ["auth", "api"], [])
            # success will be False
            ```

        Raises:
            ExceptionGroup: If the welcome extension fails to load properly.
                This is typically re-raised from the ExtensionLoader.

        Note:
            The welcome extension is only loaded if both the loaded_extensions
            list is empty AND no extensions are currently registered in the
            manager. This prevents loading the welcome extension multiple times
            or when other extensions are present.
        """
        # Only load welcome extension if no extensions are configured or loaded
        if loaded_middleware is None:
            loaded_middleware = []
        if (
            not loaded_extensions
            and not loaded_middleware
            and not self.has_extensions()
        ):
            try:
                extension_spec, exceptions = extension_loader.load_extension(
                    "serv.bundled.extensions.welcome"
                )

                if exceptions:
                    raise ExceptionGroup(
                        "Exceptions raised while loading welcome extension", exceptions
                    )

                logger.info("Loaded welcome extension as default")
                return True

            except Exception as e:
                logger.error(f"Failed to load welcome extension: {e}")
                raise

        return False

    def clear_extensions(self) -> None:
        """Remove all registered extensions.

        This method clears the entire extension registry, removing all
        registered listeners. Primarily used for testing or application
        reset scenarios.

        Examples:
            Clear all extensions:

            ```python
            manager = ExtensionManager()
            # ... register some extensions ...

            manager.clear_extensions()
            assert not manager.has_extensions()
            ```

        Warning:
            This method does not unregister extensions from dependency
            injection containers. If you need to fully reset the application
            state, you may need to recreate the container as well.
        """
        self._extensions.clear()
        logger.debug("Cleared all extensions from registry")

    def get_extension_count(self) -> int:
        """Get the total number of registered extension listeners.

        Returns:
            The total count of individual listener instances across all paths.

        Examples:
            Check extension count:

            ```python
            count = manager.get_extension_count()
            print(f"Total extensions registered: {count}")
            ```
        """
        return sum(len(listeners) for listeners in self._extensions.values())

    def get_extension_paths(self) -> list[Path]:
        """Get all extension paths currently registered.

        Returns:
            List of filesystem paths where extensions are registered.

        Examples:
            List all extension paths:

            ```python
            paths = manager.get_extension_paths()
            for path in paths:
                print(f"Extensions at: {path}")
            ```
        """
        return list(self._extensions.keys())
