"""
Ommi-based audit logger implementation.

Provides comprehensive audit logging for authentication events using
Ommi for database persistence and efficient querying.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from bevy import Inject, auto_inject, injectable

from serv.auth.audit_logger import AuditLogger
from serv.auth.types import AuditEvent
from serv.database import DatabaseManager


class OmmiAuditLogger(AuditLogger):
    """Ommi-based audit logger implementation."""

    def _validate_config(self, config: dict[str, Any]) -> None:
        """Validate configuration for Ommi audit logger."""
        # No required config for basic implementation
        pass

    def __init__(self, config: dict[str, Any]):
        """
        Initialize Ommi audit logger.

        Args:
            config: Configuration dictionary containing:
                - database_qualifier: Database qualifier for Ommi (default: "audit")
                - retention_days: How long to keep audit logs (default: 365)
                - max_event_size: Maximum size for event data in bytes (default: 64KB)
        """
        super().__init__(config)

        self.database_qualifier = config.get("database_qualifier", "audit")
        self.retention_days = config.get("retention_days", 365)
        self.max_event_size = config.get("max_event_size", 65536)  # 64KB

    @auto_inject
    @injectable
    async def log_event(self, event: AuditEvent, database: Inject[DatabaseManager] = None) -> str:
        """
        Log an audit event to the database.

        Args:
            event: Audit event to log
            database: Database service injected via DI

        Returns:
            Event ID for the logged event

        Raises:
            RuntimeError: If logging fails
        """
        try:
            from ..models import AuditEventModel

            # Serialize event data
            event_data = json.dumps(event.event_data) if event.event_data else "{}"
            metadata = json.dumps(event.metadata) if event.metadata else "{}"

            # Check size limits
            if len(event_data) > self.max_event_size:
                # Truncate and add warning
                event_data = event_data[: self.max_event_size - 100] + "... [TRUNCATED]"
                metadata_dict = json.loads(metadata) if metadata != "{}" else {}
                metadata_dict["_truncated"] = True
                metadata = json.dumps(metadata_dict)

            # Create audit event model
            audit_model = AuditEventModel(
                event_id=event.event_id or str(uuid.uuid4()),
                event_type=event.event_type,
                user_id=event.user_id,
                session_id=event.session_id,
                timestamp=event.timestamp.isoformat() if event.timestamp else datetime.now(UTC).isoformat(),
                source_ip=event.source_ip,
                user_agent=event.user_agent,
                resource=event.resource,
                action=event.action,
                result=event.result,
                event_data=event_data,
                metadata=metadata,
            )

            # Get database connection
            if database is None:
                raise RuntimeError("Database service not available for audit logging")

            ommi_instance = await database.get_connection(self.database_qualifier)

            # Save audit event
            result = await ommi_instance.add(audit_model)
            match result:
                case result if hasattr(result, "or_raise"):
                    saved_models = await result.or_raise()
                    return saved_models[0].event_id
                case _:
                    raise RuntimeError("Failed to save audit event")

        except Exception as e:
            raise RuntimeError(f"Failed to log audit event: {e}") from e

    @auto_inject
    @injectable
    async def query_events(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        user_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        database: Inject[DatabaseManager] = None,
    ) -> list[AuditEvent]:
        """
        Query audit events from the database.

        Args:
            start_time: Start time for event range
            end_time: End time for event range
            user_id: Filter by user ID
            event_type: Filter by event type
            limit: Maximum number of events to return
            database: Database service injected via DI

        Returns:
            List of audit events matching criteria

        Raises:
            RuntimeError: If query fails
        """
        try:
            from ..models import AuditEventModel

            if database is None:
                raise RuntimeError("Database service not available for audit query")

            ommi_instance = await database.get_connection(self.database_qualifier)

            # Build query
            query = ommi_instance.find(AuditEventModel)

            # Apply filters
            if start_time:
                query = query.where(AuditEventModel.timestamp >= start_time.isoformat())
            if end_time:
                query = query.where(AuditEventModel.timestamp <= end_time.isoformat())
            if user_id:
                query = query.where(AuditEventModel.user_id == user_id)
            if event_type:
                query = query.where(AuditEventModel.event_type == event_type)

            # Execute query
            result = await query.all()
            event_models = await result.or_raise()

            # Convert to AuditEvent objects
            events = []
            async for model in event_models:
                event = AuditEvent(
                    event_id=model.event_id,
                    event_type=model.event_type,
                    user_id=model.user_id,
                    session_id=model.session_id,
                    timestamp=datetime.fromisoformat(model.timestamp),
                    source_ip=model.source_ip,
                    user_agent=model.user_agent,
                    resource=model.resource,
                    action=model.action,
                    result=model.result,
                    event_data=json.loads(model.event_data) if model.event_data else {},
                    metadata=json.loads(model.metadata) if model.metadata else {},
                )
                events.append(event)

                # Respect limit
                if len(events) >= limit:
                    break

            return events

        except Exception as e:
            raise RuntimeError(f"Failed to query audit events: {e}") from e

    @auto_inject
    @injectable
    async def get_event_statistics(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        database: Inject[DatabaseManager] = None,
    ) -> dict[str, Any]:
        """
        Get audit event statistics.

        Args:
            start_time: Start time for statistics range
            end_time: End time for statistics range
            database: Database service injected via DI

        Returns:
            Dictionary containing event statistics

        Raises:
            RuntimeError: If statistics query fails
        """
        try:
            from ..models import AuditEventModel

            if database is None:
                raise RuntimeError("Database service not available for audit statistics")

            ommi_instance = await database.get_connection(self.database_qualifier)

            # Build base query
            query = ommi_instance.find(AuditEventModel)

            # Apply time filters
            if start_time:
                query = query.where(AuditEventModel.timestamp >= start_time.isoformat())
            if end_time:
                query = query.where(AuditEventModel.timestamp <= end_time.isoformat())

            # Get total count
            total_count = await query.count().or_raise()

            # Get event type breakdown (simplified for stateless query)
            all_events_result = await query.all()
            all_events = await all_events_result.or_raise()

            event_types = {}
            user_activity = {}
            result_counts = {"success": 0, "failure": 0, "other": 0}

            async for event in all_events:
                # Count by event type
                event_types[event.event_type] = event_types.get(event.event_type, 0) + 1

                # Count by user
                if event.user_id:
                    user_activity[event.user_id] = user_activity.get(event.user_id, 0) + 1

                # Count by result
                if event.result in ["success", "failure"]:
                    result_counts[event.result] += 1
                else:
                    result_counts["other"] += 1

            return {
                "total_events": total_count,
                "time_range": {
                    "start": start_time.isoformat() if start_time else None,
                    "end": end_time.isoformat() if end_time else None,
                },
                "event_types": event_types,
                "top_users": dict(sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:10]),
                "result_breakdown": result_counts,
            }

        except Exception as e:
            raise RuntimeError(f"Failed to get event statistics: {e}") from e

    async def verify_log_integrity(self) -> bool:
        """
        Verify audit log integrity.

        For basic implementation, this checks that recent events
        can be queried successfully.

        Returns:
            True if logs appear intact, False otherwise
        """
        try:
            # Query recent events to verify log accessibility
            recent_time = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            await self.query_events(start_time=recent_time, limit=1)

            # If we can query without errors, logs are accessible
            return True

        except Exception:
            return False

    @auto_inject
    @injectable
    async def cleanup_old_events(self, database: Inject[DatabaseManager] = None) -> int:
        """
        Clean up old audit events based on retention policy.

        Args:
            database: Database service injected via DI

        Returns:
            Number of events cleaned up

        Raises:
            RuntimeError: If cleanup fails
        """
        try:
            from ..models import AuditEventModel

            if database is None:
                raise RuntimeError("Database service not available for audit cleanup")

            ommi_instance = await database.get_connection(self.database_qualifier)

            # Calculate cutoff date
            cutoff_date = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - self.retention_days)

            # Count events to be deleted
            count_query = ommi_instance.find(AuditEventModel).where(AuditEventModel.timestamp < cutoff_date.isoformat())
            count_to_delete = await count_query.count().or_raise()

            # Delete old events
            if count_to_delete > 0:
                delete_query = ommi_instance.find(AuditEventModel).where(
                    AuditEventModel.timestamp < cutoff_date.isoformat()
                )
                await delete_query.delete().or_raise()

            return count_to_delete

        except Exception as e:
            raise RuntimeError(f"Failed to cleanup old audit events: {e}") from e

    async def cleanup(self) -> None:
        """Clean up audit logger resources."""
        # No specific cleanup needed for Ommi-based implementation
        pass
