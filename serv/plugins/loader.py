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

import serv.plugins as p
from serv.additional_context import ExceptionContext

if TYPE_CHECKING:
    from serv import App
    from serv.plugins.importer import Importer

logger = logging.getLogger(__name__)

known_plugins: "dict[Path, PluginSpec]" = {}


def find_plugin_spec(path: Path) -> "PluginSpec | None":
    _path = path
    while _path.exists() and _path != _path.parent:
        if _path in known_plugins:
            return known_plugins[_path]

        if not (_path / "plugin.yaml").exists():
            _path = _path.parent
            continue

        try:
            plugin_spec = PluginSpec.from_path(_path, {})
            known_plugins[_path] = plugin_spec
            return plugin_spec
        except Exception:
            logger.warning(f"Failed to load plugin spec from {path}")
            raise

    raise FileNotFoundError(f"Plugin directory not found for {_path}")


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


class EntryPointConfig(TypedDict):
    entry: str
    config: NotRequired[dict[str, Any]]


class RouterConfig(TypedDict):
    name: str
    routes: list[RouteConfig]
    mount: NotRequired[str]
    config: NotRequired[dict[str, Any]]


class PluginConfig(TypedDict):
    name: str
    version: str
    entry: NotRequired[str]
    entry_points: NotRequired[list[str | EntryPointConfig]]
    description: NotRequired[str]
    author: NotRequired[str]
    settings: NotRequired[dict[str, Any]]
    middleware: NotRequired[list[str]]
    routers: NotRequired[list[RouterConfig]]


class PluginSpec:
    def __init__(
        self,
        config: PluginConfig,
        path: Path,
        override_settings: dict[str, Any],
        importer: "Importer",
    ):
        self.name = config["name"]
        self.version = config["version"]
        self._config = config
        self._entry_points = config.get("entry_points", [])
        self._middleware = config.get("middleware", [])
        self._override_settings = override_settings
        self._path = path
        self._routers = config.get("routers", [])
        self._importer = importer

    @property
    def entry_points(self):
        return self._entry_points

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
    ) -> "PluginSpec":
        plugin_config = path / "plugin.yaml"
        if not plugin_config.exists():
            raise FileNotFoundError(f"plugin.yaml not found in {path}")

        with open(plugin_config) as f:
            raw_config_data = yaml.safe_load(f)

        # Convert settings to plugin_settings
        raw_config_data["plugin_settings"] = raw_config_data.pop("settings", {})

        # Handle single 'entry' field by converting it to 'entry_points' list
        if "entry" in raw_config_data:
            entry = raw_config_data.pop("entry")
            if "entry_points" not in raw_config_data:
                raw_config_data["entry_points"] = []
            raw_config_data["entry_points"].append(entry)

        return cls(raw_config_data, path, override_settings, importer)


class PluginLoader:
    """Handles loading and management of plugins and middleware."""

    def __init__(self, app: "App", plugin_loader: "Importer"):
        """Initialize the PluginLoader.

        Args:
            plugin_loader: Importer instance for loading plugin packages
        """
        self._app = app
        self._plugin_loader = plugin_loader

    def load_plugins(
        self, plugins_config: list[dict[str, Any]]
    ) -> "tuple[list[p.Plugin], list[Callable[[], AsyncIterator[None]]]]":
        """Load plugins from a list of plugin configs.

        Args:
            plugins_config: List of plugin configs (usually from serv.config.yaml)

        Returns:
            Tuple of (Plugin specs, Middleware iterators)

        Raises:
            ExceptionGroup: If any errors occurred during loading
        """
        exceptions = []
        loaded_plugins = []
        middleware_list = []
        for plugin_settings in plugins_config:
            try:
                plugin_import, settings = self._process_app_plugin_settings(
                    plugin_settings
                )
                plugin_spec, plugin_exceptions = self.load_plugin(
                    plugin_import, settings
                )

            except Exception as e:
                e.add_note(f" - Failed to load plugin {plugin_settings}")
                exceptions.append(e)
                continue
            else:
                if plugin_spec:
                    known_plugins[plugin_spec.path] = plugin_spec
                    loaded_plugins.append(plugin_spec)
                    middleware_list.extend(plugin_spec.middleware)

                if plugin_exceptions:
                    exceptions.extend(plugin_exceptions)

        if exceptions:
            logger.warning(
                f"Encountered {len(exceptions)} errors during plugin and middleware loading."
            )
            raise ExceptionGroup(
                "Exceptions raised while loading plugins and middleware", exceptions
            )

        return loaded_plugins, middleware_list

    def load_plugin(
        self, plugin_import: str, app_plugin_settings: dict[str, Any] | None = None
    ) -> tuple[PluginSpec | None, list[Exception]]:
        """Load a single plugin.

        Args:
            plugin_import: Dot-separated import path to the plugin

        Returns:
            Tuple of (plugin_spec, exceptions)
        """
        exceptions = []
        try:
            plugin_spec = self._load_plugin_spec(
                plugin_import, app_plugin_settings or {}
            )
        except Exception as e:
            e.add_note(f" - Failed to load plugin spec for {plugin_import}")
            exceptions.append(e)
            return None, exceptions

        try:
            _, failed_entry_points = self._load_plugin_entry_points(
                plugin_spec.entry_points, plugin_import
            )
        except Exception as e:
            e.add_note(f" - Failed while loading entry points for {plugin_import}")
            exceptions.append(e)
        else:
            exceptions.extend(failed_entry_points)

        try:
            _, failed_middleware = self._load_plugin_middleware(
                plugin_spec.middleware, plugin_import
            )
        except Exception as e:
            e.add_note(f" - Failed while loading middleware for {plugin_import}")
            exceptions.append(e)
        else:
            exceptions.extend(failed_middleware)

        try:
            self._setup_router_plugin(plugin_spec)
        except Exception as e:
            e.add_note(f" - Failed while setting up router plugin for {plugin_import}")
            exceptions.append(e)

        logger.info(f"Loaded plugin {plugin_spec.name!r}")
        return plugin_spec, exceptions

    def _setup_router_plugin(self, plugin_spec: PluginSpec):
        from serv.plugins.router_plugin import RouterPlugin

        self._app.add_plugin(RouterPlugin(plugin_spec=plugin_spec))

    def _load_plugin_entry_points(
        self, entry_points: list[str], plugin_import: str
    ) -> tuple[int, list[Exception]]:
        succeeded = 0
        failed = []
        for entry_point in entry_points:
            module_path, class_name = entry_point.split(":")
            with (
                ExceptionContext()
                .apply_note(f" - Attempting to load entry point {entry_point}")
                .capture(failed.append)
            ):
                with ExceptionContext().apply_note(
                    f" - Attempting to import module {plugin_import}.{module_path}:{class_name}"
                ):
                    try:
                        module = self._plugin_loader.load_module(
                            f"{plugin_import}.{module_path}"
                        )
                    except ModuleNotFoundError as e:
                        e.add_note(
                            " - Attempted to import relative to plugins directory"
                        )
                        module = importlib.import_module(
                            f"{plugin_import}.{module_path}"
                        )

                entry_point_class = getattr(module, class_name)

                if not issubclass(entry_point_class, p.Plugin):
                    raise ValueError(
                        f"Entry point {entry_point} from {plugin_import}.{module_path} is not a subclass of Plugin"
                    )

                self._app.add_plugin(get_container().call(entry_point_class))
                succeeded += 1

        return succeeded, failed

    def _load_plugin_middleware(
        self, middleware_entries: list[str], plugin_import: str
    ) -> tuple[int, list[Exception]]:
        succeeded = 0
        failed = []
        for entry_point in middleware_entries:
            module_path, class_name = entry_point.split(":")
            try:
                module = self._plugin_loader.import_path(
                    f"{plugin_import}.{module_path}"
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

    def _load_plugin_spec(
        self, plugin_import: str, app_plugin_settings: dict[str, Any]
    ) -> PluginSpec:
        if (self._plugin_loader.directory / plugin_import).exists():
            plugin_path = self._plugin_loader.directory / plugin_import

        else:
            plugin_path = Path(get_package_location(plugin_import))

        if plugin_path in known_plugins:
            return known_plugins[plugin_path]

        try:
            plugin_spec = PluginSpec.from_path(
                plugin_path,
                app_plugin_settings,
                self._plugin_loader.using_sub_module(plugin_import),
            )
        except Exception as e:
            e.add_note(
                f" - Failed while attempting to load plugin spec from {plugin_path}"
            )
            raise
        else:
            known_plugins[plugin_path] = plugin_spec
            return plugin_spec

    def _process_app_plugin_settings(
        self, plugin_settings: dict[str, Any] | str
    ) -> tuple[str, dict[str, Any]]:
        """Process plugin settings from serv.config.yaml.

        Args:
            plugin_settings: Plugin settings from serv.config.yaml

        Returns:
            Tuple of (module_path, settings)
        """
        match plugin_settings:
            case str() as module_path:
                return module_path, {}
            case {"plugin": str() as plugin, "settings": dict() as settings}:
                return plugin, settings
            case {"plugin": str() as plugin}:
                return plugin, {}
            case _:
                raise ValueError(f"Invalid plugin settings: {plugin_settings}")
