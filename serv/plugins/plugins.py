"""Defines a base type that can observe events happening in the Serv app. Handlers are defined as methods on the class
with names following the format '[optional_]on_{event_name}'. This gives the author the ability to make readable 
function names like 'set_role_on_user_create' or 'create_annotations_on_form_submit'."""


from collections import defaultdict
from inspect import isawaitable
from pathlib import Path
import re
import sys
from typing import Any, TYPE_CHECKING

from bevy import get_container
from bevy.containers import Container

import serv.plugins.loader as pl
from serv.plugins.loader import find_plugin_spec

# Avoid circular imports by only importing Router for type checking
if TYPE_CHECKING:
    pass


type PluginMapping = dict[str, list[str]]


def search_for_plugin_directory(path: Path) -> Path | None:
    while path.name:
        if (path / "plugin.yaml").exists():
            return path

        path = path.parent

    raise Exception("Plugin directory not found")


class Plugin:
    def __init_subclass__(cls, **kwargs) -> None:
        cls.__plugins__ = defaultdict(list)

        for name in dir(cls):
            if name.startswith("_"):
                continue
            
            event = re.match(r"^(?:.+_)?on_(.*)$", name)
            if not event:
                continue

            callback = getattr(cls, name)
            if not callable(callback):
                continue
            
            event_name = event.group(1)
            cls.__plugins__[event_name].append(name)
    
    def __init__(self, *, stand_alone: bool = False):
        """Initialize the plugin.
        
        Loads plugin configuration and sets up any defined routers and routes
        if they are configured in the plugin.yaml file.
        
        Args:
            stand_alone: If True, don't attempt to load plugin.yaml
        """
        self._stand_alone = stand_alone

    async def on(self, event_name: str, container: Container | None = None, *args: Any, **kwargs: Any) -> None:
        """Receives event notifications.

        This method will be called by the application when an event this plugin
        is registered for occurs. Subclasses should implement this method to handle
        specific events.

        Args:
            event_name: The name of the event that occurred.
            **kwargs: Arbitrary keyword arguments associated with the event.
        """
        event_name = re.sub(r"[^a-z0-9]+", "_", event_name.lower())
        for plugin_handler_name in self.__plugins__[event_name]:
            callback = getattr(self, plugin_handler_name)
            result = get_container(container).call(callback, *args, **kwargs)
            if isawaitable(result):
                await result
