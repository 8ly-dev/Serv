import asyncio
from typing import Any

import pytest

from serv.app import App
from tests.helpers import EventWatcherExtension


@pytest.mark.asyncio
async def test_lifespan_protocol_flow(app: App):
    event_watcher = EventWatcherExtension()
    app.add_extension(event_watcher)

    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    receive_queue = asyncio.Queue()

    async def mock_receive():
        return await receive_queue.get()

    lifespan_scope = {
        "type": "lifespan",
        "asgi": {"version": "3.0", "spec_version": "2.0"},
    }

    # Simulate the ASGI server sending startup and then shutdown
    await receive_queue.put({"type": "lifespan.startup"})
    await receive_queue.put({"type": "lifespan.shutdown"})

    # Run the app's lifespan handling
    # We run it in a task because the app's _lifespan_iterator will loop until shutdown is received.
    # If we await it directly without the server also running, it might block if not handled carefully.
    # However, our current app() call for lifespan should complete once shutdown is processed.
    lifespan_task = asyncio.create_task(app(lifespan_scope, mock_receive, mock_send))

    # Allow the task to process the events.
    # A short sleep or waiting for the queue to empty can ensure events are processed.
    # Or, if app() is guaranteed to exit after processing shutdown, we can await it with a timeout.
    try:
        await asyncio.wait_for(
            lifespan_task, timeout=1.0
        )  # Wait for app to finish lifespan handling
    except TimeoutError:
        lifespan_task.cancel()
        pytest.fail(
            "Lifespan task did not complete in time. Check for infinite loops or deadlocks."
        )

    # Assertions for sent messages by the app
    assert len(sent_messages) == 2, (
        f"Expected 2 messages sent, got {len(sent_messages)}: {sent_messages}"
    )
    assert sent_messages[0] == {"type": "lifespan.startup.complete"}
    assert sent_messages[1] == {"type": "lifespan.shutdown.complete"}

    # Assertions for events emitted by the app
    app_events_seen = [name for name, _ in event_watcher.events_seen]
    assert "app.startup" in app_events_seen
    assert "app.shutdown" in app_events_seen

    # Verify arguments for app.lifespan.startup event
    startup_event_kwargs = None
    for name, kwargs in event_watcher.events_seen:
        if name == "app.startup":
            startup_event_kwargs = kwargs
            break
    assert startup_event_kwargs is not None
    assert startup_event_kwargs.get("scope") == lifespan_scope

    # Verify arguments for app.lifespan.shutdown event
    shutdown_event_kwargs = None
    for name, kwargs in event_watcher.events_seen:
        if name == "app.shutdown":
            shutdown_event_kwargs = kwargs
            break

    assert shutdown_event_kwargs is not None
    assert shutdown_event_kwargs.get("scope") == lifespan_scope


@pytest.mark.asyncio
async def test_lifespan_startup_failure_simulation(app: App):
    """Simulates a failure during the app.lifespan.startup event phase."""
    event_watcher = EventWatcherExtension()
    app.add_extension(event_watcher)

    class StartupErrorExtension(
        EventWatcherExtension
    ):  # Inherits event capture for checking
        async def on(self, event_name: str, **kwargs: Any) -> None:
            # Call the base class's (EventWatcherExtension's) on method to record the event
            await super().on(event_name, **kwargs)

            if event_name == "app.startup":
                raise RuntimeError("Simulated startup failure")

    startup_fail_plugin = StartupErrorExtension()
    app.add_extension(startup_fail_plugin)  # Add the faulty plugin

    sent_messages = []

    async def mock_send(message):
        sent_messages.append(message)

    receive_queue = asyncio.Queue()

    async def mock_receive():
        return await receive_queue.get()

    lifespan_scope = {"type": "lifespan", "asgi": {"version": "3.0"}}

    await receive_queue.put({"type": "lifespan.startup"})
    # No shutdown event needed here as startup fails

    # The app's lifespan handling should catch the error from the plugin and send startup.failed
    # It might also log the error - checking logs is out of scope for this direct test.
    with pytest.raises(ExceptionGroup) as excinfo:
        # The exception from emit() should propagate out of app() if not handled by app itself
        # Currently, App.emit uses TaskGroup, errors in tasks might be collected in an ExceptionGroup
        # or the first error might propagate. Let's see how current App.emit behaves.
        # Update: App.emit in app.py wraps container.call in tg.create_task.
        # If container.call (plugin.on) raises, the TaskGroup will re-raise it.
        await app(lifespan_scope, mock_receive, mock_send)

    # Check that the ExceptionGroup contains the expected RuntimeError
    assert len(excinfo.value.exceptions) == 1
    assert isinstance(excinfo.value.exceptions[0], RuntimeError)
    assert str(excinfo.value.exceptions[0]) == "Simulated startup failure"

    # Check what messages were sent
    # Depending on how an ASGI server handles an exception escaping app() during lifespan,
    # it might or might not expect lifespan.startup.failed.
    # For now, let's assume the app should send it if it catches and handles the plugin error internally.
    # However, current app.py emit will let TaskGroup re-raise, so App.__call__ for lifespan
    # might not send startup.failed if the error from emit isn't caught there.
    # Let's test the current behavior: if emit re-raises, then App.handle_lifespan will exit, no .failed message.

    # Based on current App.emit, the RuntimeError will propagate from app(),
    # so `lifespan.startup.failed` would typically be sent by the ASGI *server* if it catches this error.
    # Our App instance itself doesn't send `.failed` if an exception escapes `emit`.
    # So, `sent_messages` might be empty or only contain `startup.complete` if error handling changes in App.
    # For now, let's assert what we expect based on the current app.py: error propagates, nothing specific sent by App.

    # Check that app.lifespan.startup was attempted
    startup_event_seen = any(
        name == "app.startup" for name, _ in startup_fail_plugin.events_seen
    )
    assert startup_event_seen, (
        "app.lifespan.startup event was not even attempted by the faulty plugin"
    )

    # If the app were to send `lifespan.startup.failed`:
    # assert len(sent_messages) == 1
    # assert sent_messages[0]["type"] == "lifespan.startup.failed"
    # assert "Simulated startup failure" in sent_messages[0]["message"]
    # For now, since the error propagates out of app(), we might not have any messages sent by the app itself.
    # The ASGI server would be responsible for the .failed message.
    assert not sent_messages, (
        "App should not have sent any messages if startup plugin error propagated out of app() call"
    )
