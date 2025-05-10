"""Defines a base type that can observe events happening in the Serv app. Handlers are defined as methods on the class
with names following the format '[optional_]on_{event_name}'. This gives the author the ability to make readable 
function names like 'set_role_on_user_create' or 'create_annotations_on_form_submit'."""


from collections import defaultdict
import re

from bevy import get_container
from bevy.containers import Container


type ObserverMapping = dict[str, list[str]]


class Observer:
    __observers__: ObserverMapping

    def __init_subclass__(cls, **kwargs) -> None:
        cls.__observers__ = defaultdict(list)

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
            cls.__observers__[event_name].append(name)

    async def on(self, event_name: str, container: Container | None = None, *args, **kwargs):
        for observer in self.__observers__[event_name]:
            callback = getattr(self, observer)
            await get_container(container).call(callback, *args, **kwargs)
