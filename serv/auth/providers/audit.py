"""Audit provider interface."""

from abc import abstractmethod
from datetime import datetime
from typing import Any

from ..audit.events import AuditEventType
from ..types import AuditEvent
from .base import BaseProvider


class AuditProvider(BaseProvider):
    """Abstract base class for audit event storage and retrieval."""

    @abstractmethod
    async def store_audit_event(self, event: AuditEvent) -> None:
        """Store an audit event.

        Args:
            event: Audit event to store
        """
        pass

    @abstractmethod
    async def get_audit_events(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[AuditEvent]:
        """Get audit events within a time range.

        Args:
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List of audit events
        """
        pass

    @abstractmethod
    async def get_user_audit_events(
        self,
        user_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[AuditEvent]:
        """Get audit events for a specific user.

        Args:
            user_id: ID of the user
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List of audit events for the user
        """
        pass

    @abstractmethod
    async def search_audit_events(
        self,
        event_types: list[AuditEventType] | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        resource: str | None = None,
        filters: dict[str, Any] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[AuditEvent]:
        """Search audit events with various filters.

        Args:
            event_types: List of event types to filter by
            user_id: User ID to filter by
            session_id: Session ID to filter by
            resource: Resource to filter by
            filters: Additional custom filters
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List of matching audit events
        """
        pass

    @abstractmethod
    async def cleanup_old_events(self, older_than: datetime) -> int:
        """Clean up audit events older than specified time.

        Args:
            older_than: Delete events older than this datetime

        Returns:
            Number of events deleted
        """
        pass
