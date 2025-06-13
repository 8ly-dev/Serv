from pathlib import Path

import pytest
from bevy import get_registry
from bevy.containers import Container, get_container

from serv.app.lifecycle import EventEmitter
from serv.extensions import Listener, on
from serv.routes import Route


class TestableListener(Listener):
    def __init__(self):
        super().__init__(stand_alone=True)


@pytest.fixture(scope="function", autouse=True)
def setup_container():
    with get_registry().create_container() as container:
        container.instances[Container] = container
        yield container


@pytest.mark.asyncio
async def test_event_emitter():
    events_seen = []

    class TestListener(TestableListener):
        @on("test.event")
        async def handle_test_event(self, arg1, arg2):
            events_seen.append((arg1, arg2))

    listener = TestListener()
    from serv.app.extensions import ExtensionManager

    extension_manager = ExtensionManager()
    extension_manager._extensions[Path(".")] = [listener]
    emitter = EventEmitter(extension_manager)
    await emitter.emit(
        "test.event", container=get_container(), arg1="value1", arg2="value2"
    )
    assert events_seen == [("value1", "value2")]


@pytest.mark.asyncio
async def test_listener_emit():
    events_seen = []

    class TestListener(TestableListener):
        @on("test.event")
        async def handle_test_event(self, arg1, arg2):
            events_seen.append((arg1, arg2))

        async def send_event(self):
            await self.emit(
                "test.event",
                event_emitter,
                container=get_container(),
                arg1="value1",
                arg2="value2",
            )

    listener = TestListener()
    from serv.app.extensions import ExtensionManager

    extension_manager = ExtensionManager()
    extension_manager._extensions[Path(".")] = [listener]
    event_emitter = EventEmitter(extension_manager)
    get_container().instances[EventEmitter] = event_emitter
    # Register protocol for new architecture
    from serv.protocols import EventEmitterProtocol

    get_container().instances[EventEmitterProtocol] = event_emitter

    await listener.send_event()
    assert events_seen == [("value1", "value2")]


@pytest.mark.asyncio
async def test_emit_from_route():
    events_seen = []

    class TestListener(TestableListener):
        @on("test.event")
        async def handle_test_event(self, arg1, arg2):
            events_seen.append((arg1, arg2))

    class TestRoute(Route):
        async def send_event(self):
            await self.emit(
                "test.event",
                event_emitter,
                container=get_container(),
                arg1="value1",
                arg2="value2",
            )

    route = TestRoute()
    listener = TestListener()
    from serv.app.extensions import ExtensionManager

    extension_manager = ExtensionManager()
    extension_manager._extensions[Path(".")] = [listener]
    event_emitter = EventEmitter(extension_manager)
    get_container().instances[EventEmitter] = event_emitter
    # Register protocol for new architecture
    from serv.protocols import EventEmitterProtocol

    get_container().instances[EventEmitterProtocol] = event_emitter

    await route.send_event()
    assert events_seen == [("value1", "value2")]
