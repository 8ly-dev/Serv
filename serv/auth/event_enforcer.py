"""
Event emission enforcement for the Serv authentication framework.

This module provides utilities to enforce that methods emit required events
as declared in their abstract method signatures using ReturnsAndEmits annotations.

Security considerations:
- Event emission is critical for audit trails and security monitoring
- Missing events could indicate security bypasses or implementation errors
- Enforcement must be efficient to avoid performance impacts
"""

import inspect
from functools import wraps
from typing import Annotated, Any, get_args, get_origin
from weakref import WeakKeyDictionary

from .types import AuthEventEmissionError, ReturnsAndEmits


class EventHistory:
    """
    Thread-safe event history tracker for monitoring emissions.

    Tracks events emitted during method execution to verify required
    events are properly emitted.
    """

    def __init__(self, max_size: int = 100):
        """
        Initialize event history tracker.

        Args:
            max_size: Maximum number of events to track
        """
        self.__max_size = max_size
        self.__history: list[tuple[int, str]] = []
        self.__next_id = 0

    @property
    def last_id(self) -> int:
        """Get the ID of the last tracked event."""
        return self.__next_id - 1

    def add(self, event: str) -> None:
        """
        Add an event to the history.

        Args:
            event: Event name to track
        """
        if len(self.__history) >= self.__max_size:
            self.__history.pop(0)

        event_id = self.__next_id
        self.__next_id += 1
        self.__history.append((event_id, event))

    def since(self, event_id: int) -> dict[int, str]:
        """
        Get all events that occurred after the specified ID.

        Args:
            event_id: Event ID to get events after

        Returns:
            Dictionary mapping event IDs to event names
        """
        return {eid: event for eid, event in self.__history if eid > event_id}

    def clear(self) -> None:
        """Clear all tracked events."""
        self.__history = []
        self.__next_id = 0


class EventEmissionEnforcer:
    """
    Enforces event emission requirements for authentication methods.

    Uses MRO inspection to find abstract method declarations with ReturnsAndEmits
    annotations and enforces that implementing methods emit the required events.

    Caches MRO lookups for efficiency.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the event emission enforcer."""
        super().__init__(*args, **kwargs)
        # Use instance attributes that won't conflict with __getattribute__
        self._enforcer_history = EventHistory()
        # Cache for MRO lookups - maps (class, method_name) to required events
        self._enforcer_mro_cache: dict[tuple[type, str], set[str] | None] = {}
        # Weak reference cache to avoid memory leaks
        self._enforcer_class_cache: WeakKeyDictionary[
            type, dict[str, set[str] | None]
        ] = WeakKeyDictionary()

    def emit(self, event: str, **kwargs) -> None:
        """
        Emit an event and track it in history.

        Args:
            event: Event name to emit
            **kwargs: Event payload (for logging/audit purposes)
        """
        # Track the event for enforcement - use object.__getattribute__ to avoid recursion
        history = object.__getattribute__(self, "_enforcer_history")
        history.add(event)

        # Here you would typically also emit to actual event system
        # For now, we just track for verification

    def _get_required_events_for_method(
        self, cls: type, method_name: str
    ) -> set[str] | None:
        """
        Get required events for a method by inspecting MRO.

        Args:
            cls: Class to inspect
            method_name: Method name to check

        Returns:
            Set of required event names, or None if no requirements found
        """
        cache_key = (cls, method_name)

        # Use object.__getattribute__ to avoid recursion
        mro_cache = object.__getattribute__(self, "_enforcer_mro_cache")
        class_cache = object.__getattribute__(self, "_enforcer_class_cache")

        # Check primary cache first
        if cache_key in mro_cache:
            return mro_cache[cache_key]

        # Check class-specific cache
        if cls in class_cache:
            class_methods = class_cache[cls]
            if method_name in class_methods:
                result = class_methods[method_name]
                mro_cache[cache_key] = result
                return result

        # Perform MRO lookup
        required_events = self._inspect_mro_for_events(cls, method_name)

        # Only cache non-None results to avoid polluting cache with methods that have no requirements
        if required_events is not None:
            if cls not in class_cache:
                class_cache[cls] = {}
            class_cache[cls][method_name] = required_events
            mro_cache[cache_key] = required_events

        return required_events

    def _inspect_mro_for_events(self, cls: type, method_name: str) -> set[str] | None:
        """
        Inspect MRO to find ReturnsAndEmits annotations for a method.

        Args:
            cls: Class to inspect
            method_name: Method name to check

        Returns:
            Set of required event names, or None if no requirements found
        """
        for base_class in inspect.getmro(cls):
            if hasattr(base_class, method_name):
                method = getattr(base_class, method_name)

                # Check if it's an abstract method with annotations
                if hasattr(method, "__isabstractmethod__") and hasattr(
                    method, "__annotations__"
                ):
                    return_annotation = method.__annotations__.get("return")
                    if return_annotation:
                        # Check if this is a ReturnsAndEmits annotation
                        origin = get_origin(return_annotation)
                        if origin is ReturnsAndEmits or (origin is Annotated):
                            args = get_args(return_annotation)
                            if len(args) >= 2:
                                # args[0] is the return type, args[1] should be the events tuple
                                events_tuple = args[1]
                                if isinstance(events_tuple, tuple) and all(
                                    isinstance(e, str) for e in events_tuple
                                ):
                                    return set(events_tuple) if events_tuple else None

        return None

    def __monitor_for_events(self, func, required_events: set[str]):
        """
        Create a wrapper that monitors event emissions for a method.

        Args:
            func: Function to wrap
            required_events: Set of events that must be emitted

        Returns:
            Wrapped function that enforces event emission
        """

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Record starting point - use object.__getattribute__ to avoid recursion
            history = object.__getattribute__(self, "_enforcer_history")
            start_id = history.last_id

            # Execute the method
            try:
                result = await func(*args, **kwargs)
            except Exception:
                # Don't enforce events on exceptions
                raise

            # Check if required events were emitted
            emitted_events = set(history.since(start_id).values())
            # Check if at least one of the required events was emitted
            if not (required_events & emitted_events):
                raise AuthEventEmissionError(func.__qualname__, required_events)

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Record starting point - use object.__getattribute__ to avoid recursion
            history = object.__getattribute__(self, "_enforcer_history")
            start_id = history.last_id

            # Execute the method
            try:
                result = func(*args, **kwargs)
            except Exception:
                # Don't enforce events on exceptions
                raise

            # Check if required events were emitted
            emitted_events = set(history.since(start_id).values())
            # Check if at least one of the required events was emitted
            if not (required_events & emitted_events):
                raise AuthEventEmissionError(func.__qualname__, required_events)

            return result

        # Return appropriate wrapper based on whether function is async
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    def __getattribute__(self, name: str) -> Any:
        """
        Override attribute access to wrap methods with event enforcement.

        When a method is accessed, check if it has event emission requirements
        and wrap it with enforcement logic if needed.
        """
        # Always get the value first
        value = super().__getattribute__(name)

        # Skip private methods and attributes
        if name.startswith("_"):
            return value

        # Only process callable methods that are bound to this instance
        if callable(value) and hasattr(value, "__self__") and value.__self__ is self:
            # Get the class of this instance
            cls = type(self)

            # Check if this method has event requirements
            try:
                required_events = self._get_required_events_for_method(cls, name)

                if required_events:
                    # Wrap the method with event enforcement
                    return self._EventEmissionEnforcer__monitor_for_events(
                        value, required_events
                    )
            except AttributeError:
                # If we can't access the cache attributes, just return the original value
                pass

        return value

    def clear_cache(self) -> None:
        """Clear MRO lookup caches."""
        mro_cache = object.__getattribute__(self, "_enforcer_mro_cache")
        class_cache = object.__getattribute__(self, "_enforcer_class_cache")
        mro_cache.clear()
        class_cache.clear()

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics for monitoring.

        Returns:
            Dictionary with cache statistics
        """
        mro_cache = object.__getattribute__(self, "_enforcer_mro_cache")
        class_cache = object.__getattribute__(self, "_enforcer_class_cache")
        return {
            "mro_cache_size": len(mro_cache),
            "class_cache_size": len(class_cache),
            "total_cached_methods": sum(
                len(methods) for methods in class_cache.values()
            ),
        }
