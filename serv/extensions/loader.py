import importlib.util
import logging
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    NotRequired,
    TypedDict,
)

import yaml
from bevy import get_container

import serv.extensions as p
from serv.additional_context import ExceptionContext

if TYPE_CHECKING:
    from serv import App
    from serv.extensions.importer import Importer

logger = logging.getLogger(__name__)

known_extensions: "dict[Path, ExtensionSpec]" = {}


def find_extension_spec(path: Path) -> "ExtensionSpec | None":
    _path = path
    while _path.exists() and _path != _path.parent:
        if _path in known_extensions:
            return known_extensions[_path]

        if not (_path / "extension.yaml").exists():
            _path = _path.parent
            continue

        try:
            extension_spec = ExtensionSpec.from_path(_path, {})
            known_extensions[_path] = extension_spec
            return extension_spec
        except Exception:
            logger.warning(f"Failed to load extension spec from {path}")
            raise

    raise FileNotFoundError(f"Extension directory not found for {_path}")


def get_package_location(package_name: str) -> Path:
    """
    Retrieves the filesystem path of a Python package/module without importing it.

    Args:
        package_name: Dot-separated module/package name (e.g., "numpy" or "my_package.submodule")

    Returns:
        Absolute path to the package directory (for packages) or module file (for single-file modules)

    Raises:
        ValueError: If the package/module isn't found or is a built-in
    """
    spec = importlib.util.find_spec(package_name)

    if not spec:
        raise ValueError(f"'{package_name}' not found in Python path")
    if not spec.origin:
        raise ValueError(f"'{package_name}' is a built-in module with no file location")

    # Handle packages (multi-file)
    if spec.submodule_search_locations:
        return Path(spec.submodule_search_locations[0])

    # Handle single-file modules
    return Path(spec.origin).parent


class RouteConfig(TypedDict):
    path: str
    handler: str
    config: NotRequired[dict[str, Any]]
    methods: NotRequired[
        list[Literal["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]]
    ]


class ListenerConfig(TypedDict):
    entry: str
    config: NotRequired[dict[str, Any]]


class RouterConfig(TypedDict):
    name: str
    routes: list[RouteConfig]
    mount: NotRequired[str]
    config: NotRequired[dict[str, Any]]


class ExtensionConfig(TypedDict):
    name: str
    version: str
    entry: NotRequired[str]
    listeners: NotRequired[list[str | ListenerConfig]]
    # Backward compatibility
    entry_points: NotRequired[list[str | ListenerConfig]]
    description: NotRequired[str]
    author: NotRequired[str]
    settings: NotRequired[dict[str, Any]]
    middleware: NotRequired[list[str]]
    routers: NotRequired[list[RouterConfig]]


class ExtensionSpec:
    def __init__(
        self,
        config: ExtensionConfig,
        path: Path,
        override_settings: dict[str, Any],
        importer: "Importer",
    ):
        self.name = config["name"]
        self.version = config["version"]
        self._config = config
        # Support both new 'listeners' and legacy 'entry_points' keys
        self._listeners = config.get("listeners", config.get("entry_points", []))
        self._middleware = config.get("middleware", [])
        self._override_settings = override_settings
        self._path = path
        self._routers = config.get("routers", [])
        self._importer = importer

    @property
    def listeners(self):
        return self._listeners

    @property
    def entry_points(self):
        """Backward compatibility property."""
        return self._listeners

    @property
    def description(self) -> str | None:
        return self._config.get("description")

    @property
    def author(self) -> str | None:
        return self._config.get("author")

    @property
    def middleware(self) -> list[str]:
        return self._middleware

    @property
    def routers(self) -> list[RouterConfig]:
        return self._routers

    @property
    def settings(self) -> dict[str, Any]:
        return self._config.get("settings", {}) | self._override_settings

    @property
    def importer(self) -> "Importer":
        return self._importer

    @property
    def path(self) -> Path:
        return self._path

    @classmethod
    def from_path(
        cls, path: Path, override_settings: dict[str, Any], importer: "Importer"
    ) -> "ExtensionSpec":
        # Try extension.yaml first, then extension.yaml for backward compatibility
        extension_config = path / "extension.yaml"
        extension_config = path / "extension.yaml"

        if extension_config.exists():
            config_file = extension_config
        elif extension_config.exists():
            config_file = extension_config
        else:
            raise FileNotFoundError(
                f"extension.yaml or extension.yaml not found in {path}"
            )

        with open(config_file) as f:
            raw_config_data = yaml.safe_load(f)

        # Convert settings to extension_settings (backward compatibility with extension_settings)
        if "settings" in raw_config_data:
            raw_config_data["extension_settings"] = raw_config_data.pop("settings")

        # Handle single 'entry' field by converting it to 'listeners' list
        if "entry" in raw_config_data:
            entry = raw_config_data.pop("entry")
            if (
                "listeners" not in raw_config_data
                and "entry_points" not in raw_config_data
            ):
                raw_config_data["listeners"] = []
            # Add to listeners if it exists, otherwise to entry_points for backward compatibility
            if "listeners" in raw_config_data:
                raw_config_data["listeners"].append(entry)
            else:
                if "entry_points" not in raw_config_data:
                    raw_config_data["entry_points"] = []
                raw_config_data["entry_points"].append(entry)

        return cls(raw_config_data, path, override_settings, importer)


class ExtensionLoader:
    """Handles loading and management of extensions and middleware."""

    def __init__(self, app: "App", extension_loader: "Importer"):
        """Initialize the ExtensionLoader.

        Args:
            extension_loader: Importer instance for loading extension packages
        """
        self._app = app
        self._extension_loader = extension_loader

    def load_extensions(
        self, extensions_config: list[dict[str, Any]]
    ) -> "tuple[list[p.Listener], list[Callable[[], AsyncIterator[None]]]]":
        """Load extensions from a list of extension configs.

        Args:
            extensions_config: List of extension configs (usually from serv.config.yaml)

        Returns:
            Tuple of (Extension specs, Middleware iterators)

        Raises:
            ExceptionGroup: If any errors occurred during loading
        """
        exceptions = []
        loaded_extensions = []
        middleware_list = []
        for extension_settings in extensions_config:
            try:
                extension_import, settings = self._process_app_extension_settings(
                    extension_settings
                )
                extension_spec, extension_exceptions = self.load_extension(
                    extension_import, settings
                )

            except Exception as e:
                e.add_note(f" - Failed to load extension {extension_settings}")
                exceptions.append(e)
                continue
            else:
                if extension_spec:
                    known_extensions[extension_spec.path] = extension_spec
                    loaded_extensions.append(extension_spec)
                    middleware_list.extend(extension_spec.middleware)

                if extension_exceptions:
                    exceptions.extend(extension_exceptions)

        if exceptions:
            logger.warning(
                f"Encountered {len(exceptions)} errors during extension and middleware loading."
            )
            raise ExceptionGroup(
                "Exceptions raised while loading extensions and middleware", exceptions
            )

        return loaded_extensions, middleware_list

    def load_extension(
        self,
        extension_import: str,
        app_extension_settings: dict[str, Any] | None = None,
    ) -> tuple[ExtensionSpec | None, list[Exception]]:
        """Load a single extension.

        Args:
            extension_import: Dot-separated import path to the extension

        Returns:
            Tuple of (extension_spec, exceptions)
        """
        exceptions = []
        try:
            extension_spec = self._load_extension_spec(
                extension_import, app_extension_settings or {}
            )
        except Exception as e:
            e.add_note(f" - Failed to load extension spec for {extension_import}")
            exceptions.append(e)
            return None, exceptions

        try:
            _, failed_listeners = self._load_extension_listeners(
                extension_spec.listeners, extension_import
            )
        except Exception as e:
            e.add_note(f" - Failed while loading listeners for {extension_import}")
            exceptions.append(e)
        else:
            exceptions.extend(failed_listeners)

        try:
            _, failed_middleware = self._load_extension_middleware(
                extension_spec.middleware, extension_import
            )
        except Exception as e:
            e.add_note(f" - Failed while loading middleware for {extension_import}")
            exceptions.append(e)
        else:
            exceptions.extend(failed_middleware)

        try:
            self._setup_router_extension(extension_spec)
        except Exception as e:
            e.add_note(
                f" - Failed while setting up router extension for {extension_import}"
            )
            exceptions.append(e)

        logger.info(f"Loaded extension {extension_spec.name!r}")
        return extension_spec, exceptions

    def _setup_router_extension(self, extension_spec: ExtensionSpec):
        from serv.extensions.router_extension import RouterExtension

        self._app.add_extension(RouterExtension(extension_spec=extension_spec))

    def _load_extension_listeners(
        self, listeners: list[str], extension_import: str
    ) -> tuple[int, list[Exception]]:
        succeeded = 0
        failed = []
        for listener in listeners:
            try:
                # Validate that listener is a string in the expected format
                if not isinstance(listener, str):
                    raise ValueError(
                        f"Listener must be a string in format 'module:class', but got {type(listener).__name__}: {repr(listener)}"
                    )

                if ":" not in listener:
                    raise ValueError(
                        f"Listener must be in format 'module:class', but got: {repr(listener)}"
                    )

                module_path, class_name = listener.split(":")
            except (ValueError, AttributeError) as e:
                # Add context about the invalid listener format
                e.add_note(
                    f" - Invalid listener format in extension '{extension_import}'"
                )
                e.add_note(" - Expected format: 'module:class' (string)")
                e.add_note(
                    f" - Actual value: {repr(listener)} (type: {type(listener).__name__})"
                )
                failed.append(e)
                continue

            with (
                ExceptionContext()
                .apply_note(f" - Attempting to load listener {listener}")
                .capture(failed.append)
            ):
                with ExceptionContext().apply_note(
                    f" - Attempting to import module {extension_import}.{module_path}:{class_name}"
                ):
                    try:
                        module = self._extension_loader.load_module(
                            f"{extension_import}.{module_path}"
                        )
                    except ModuleNotFoundError as e:
                        e.add_note(
                            " - Attempted to import relative to extensions directory"
                        )
                        module = importlib.import_module(
                            f"{extension_import}.{module_path}"
                        )

                listener_class = getattr(module, class_name)

                if not issubclass(listener_class, p.Listener):
                    raise ValueError(
                        f"Listener {listener} from {extension_import}.{module_path} is not a subclass of Listener"
                    )

                self._app.add_extension(get_container().call(listener_class))
                succeeded += 1

        return succeeded, failed

    def _load_extension_middleware(
        self, middleware_entries: list[str], extension_import: str
    ) -> tuple[int, list[Exception]]:
        succeeded = 0
        failed = []
        for entry_point in middleware_entries:
            try:
                # Validate that entry_point is a string in the expected format
                if not isinstance(entry_point, str):
                    raise ValueError(
                        f"Middleware entry must be a string in format 'module:class', but got {type(entry_point).__name__}: {repr(entry_point)}"
                    )

                if ":" not in entry_point:
                    raise ValueError(
                        f"Middleware entry must be in format 'module:class', but got: {repr(entry_point)}"
                    )

                module_path, class_name = entry_point.split(":")
            except (ValueError, AttributeError) as e:
                # Add context about the invalid middleware format
                e.add_note(
                    f" - Invalid middleware format in extension '{extension_import}'"
                )
                e.add_note(" - Expected format: 'module:class' (string)")
                e.add_note(
                    f" - Actual value: {repr(entry_point)} (type: {type(entry_point).__name__})"
                )
                failed.append(e)
                continue

            try:
                module = self._extension_loader.import_path(
                    f"{extension_import}.{module_path}"
                )
                entry_point_class = getattr(module, class_name)

                if not hasattr(entry_point_class, "__aiter__"):
                    raise ValueError(
                        f"Middleware object {entry_point} is does not implement the async iterator protocol"
                    )
            except Exception as e:
                e.add_note(f" - Failed to load middleware {entry_point}")
                failed.append(e)
            else:
                self._app.add_middleware(entry_point_class)
                succeeded += 1

        return succeeded, failed

    def _load_extension_spec(
        self, extension_import: str, app_extension_settings: dict[str, Any]
    ) -> ExtensionSpec:
        if (self._extension_loader.directory / extension_import).exists():
            extension_path = self._extension_loader.directory / extension_import

        else:
            extension_path = Path(get_package_location(extension_import))

        if extension_path in known_extensions:
            return known_extensions[extension_path]

        try:
            extension_spec = ExtensionSpec.from_path(
                extension_path,
                app_extension_settings,
                self._extension_loader.using_sub_module(extension_import),
            )
        except Exception as e:
            e.add_note(
                f" - Failed while attempting to load extension spec from {extension_path}"
            )
            raise
        else:
            known_extensions[extension_path] = extension_spec
            return extension_spec

    def _process_app_extension_settings(
        self, extension_settings: dict[str, Any] | str
    ) -> tuple[str, dict[str, Any]]:
        """Process extension settings from serv.config.yaml.

        Args:
            extension_settings: Extension settings from serv.config.yaml

        Returns:
            Tuple of (module_path, settings)
        """
        match extension_settings:
            case str() as module_path:
                return module_path, {}
            case {"extension": str() as extension, "settings": dict() as settings}:
                return extension, settings
            case {"extension": str() as extension}:
                return extension, {}
            # Backward compatibility with "extension" key
            case {"extension": str() as extension, "settings": dict() as settings}:
                return extension, settings
            case {"extension": str() as extension}:
                return extension, {}
            case _:
                raise ValueError(f"Invalid extension settings: {extension_settings}")
