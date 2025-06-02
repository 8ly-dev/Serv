"""
Protocol definitions for Serv framework.

This module defines abstract protocols to break circular dependencies
between core modules while maintaining type safety and clear interfaces.
"""

from typing import Protocol, Any, Dict, List, Callable, Optional
from abc import abstractmethod
from pathlib import Path


class EventEmitterProtocol(Protocol):
    """Protocol for event emission capabilities."""
    
    @abstractmethod
    async def emit(self, event: str, **kwargs) -> None:
        """Emit an event with optional parameters."""
        ...


class RouterProtocol(Protocol):
    """Protocol for request routing capabilities."""
    
    @abstractmethod
    def add_route(self, path: str, handler: Any, methods: List[str] = None) -> None:
        """Add a route to the router."""
        ...
    
    @abstractmethod
    def resolve_route(self, method: str, path: str) -> Any:
        """Resolve a route handler for method and path."""
        ...
    
    @abstractmethod
    def mount(self, path: str, sub_router: "RouterProtocol") -> None:
        """Mount a sub-router at the given path."""
        ...


class ContainerProtocol(Protocol):
    """Protocol for dependency injection container."""
    
    @abstractmethod
    def get(self, type_: type) -> Any:
        """Get an instance of the requested type."""
        ...
    
    @abstractmethod
    def register(self, type_: type, instance: Any) -> None:
        """Register a type with an instance."""
        ...
    
    @abstractmethod
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call a function with dependency injection."""
        ...


class ExtensionSpecProtocol(Protocol):
    """Protocol for extension specifications."""
    
    name: str
    path: Path
    version: str
    
    @abstractmethod
    def load(self) -> Any:
        """Load the extension."""
        ...


class AppContextProtocol(Protocol):
    """Protocol for application context."""
    
    name: str
    dev_mode: bool
    
    @abstractmethod
    def get_extension(self, name: str) -> Any:
        """Get extension by name."""
        ...
    
    @abstractmethod
    def add_extension(self, extension: Any) -> None:
        """Add extension to app."""
        ...


class ResponseBuilderProtocol(Protocol):
    """Protocol for response building."""
    
    @abstractmethod
    def set_status(self, status_code: int) -> None:
        """Set response status code."""
        ...
    
    @abstractmethod
    def add_header(self, name: str, value: str) -> None:
        """Add response header."""
        ...
    
    @abstractmethod
    def body(self, content: Any) -> None:
        """Set response body."""
        ...