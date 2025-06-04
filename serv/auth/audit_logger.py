"""
AuditLogger interface for the Serv authentication framework.

This module defines the abstract base class for audit logging,
providing security event tracking and compliance support.

Security considerations:
- Audit logs must be tamper-evident and immutable
- Sensitive data must never be logged
- Audit events must be reliable and not lose data
- Log access must be controlled and monitored
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from .types import AuditEvent


class AuditLogger(ABC):
    """
    Abstract base class for audit logging services.

    Audit loggers provide secure, immutable logging of security-relevant
    events throughout the authentication system. They support compliance
    requirements and security monitoring by maintaining detailed records
    of authentication, authorization, and administrative events.

    Security requirements:
    - Audit logs MUST be tamper-evident
    - Audit logs MUST be immutable once written
    - Sensitive data MUST NOT be logged
    - Log writes MUST be reliable (not lost)
    - Log access MUST be controlled and audited

    All implementations should be stateless and use dependency injection
    for storage and configuration services.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the audit logger.

        Args:
            config: Audit logger configuration
        """
        self.config = config.copy()  # Defensive copy
        self._validate_config(config)

    @abstractmethod
    def _validate_config(self, config: dict[str, Any]) -> None:
        """
        Validate audit logger configuration.

        Should validate log storage configuration, retention policies,
        and security settings.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If configuration is invalid or insecure
        """
        pass

    @abstractmethod
    async def log_event(self, event: AuditEvent) -> None:
        """
        Log a security audit event.

        Records the audit event in secure, immutable storage.
        The event should be written immediately and reliably.

        Security requirements:
        - MUST write event immediately
        - MUST ensure event immutability
        - MUST validate event data
        - SHOULD include integrity protection
        - SHOULD never fail silently

        Args:
            event: AuditEvent to log

        Raises:
            AuditError: If event cannot be logged

        Example:
            ```python
            async def log_event(self, event: AuditEvent) -> None:
                # Validate event
                self._validate_event(event)

                # Add integrity protection
                event_with_integrity = self._add_integrity_hash(event)

                # Write to secure storage
                try:
                    await self._write_to_storage(event_with_integrity)
                except Exception as e:
                    # Critical: audit failure must be handled
                    await self._handle_audit_failure(event, e)
                    raise AuditError(f"Failed to log audit event: {e}")

                # Emit to monitoring systems
                await self._emit_to_monitoring(event)
            ```
        """
        pass

    @abstractmethod
    async def query_events(
        self,
        filters: dict[str, Any],
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AuditEvent]:
        """
        Query audit events with filters.

        Searches audit logs based on specified criteria.
        Should support common filters like time ranges, event types,
        actors, and outcomes.

        Security requirements:
        - MUST validate query permissions
        - MUST limit query scope for non-admin users
        - SHOULD log audit queries themselves
        - SHOULD be efficient for large log volumes

        Args:
            filters: Query filters including:
                - start_time: Earliest event time
                - end_time: Latest event time
                - event_type: Event type filter
                - actor_id: Actor identifier filter
                - outcome: Outcome filter ("success", "failure", "error")
                - resource_type: Resource type filter
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List of matching audit events

        Example:
            ```python
            async def query_events(
                self,
                filters: Dict[str, Any],
                limit: Optional[int] = None,
                offset: Optional[int] = None
            ) -> List[AuditEvent]:
                # Validate query permissions
                await self._validate_query_permissions(filters)

                # Build secure query
                query = self._build_query(filters, limit, offset)

                # Execute query
                raw_events = await self._execute_query(query)

                # Convert to AuditEvent objects
                events = [self._parse_audit_event(raw) for raw in raw_events]

                # Log the query itself
                await self._log_query_event(filters, len(events))

                return events
            ```
        """
        pass

    async def log_authentication_event(
        self,
        actor_id: str | None,
        outcome: str,
        method: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an authentication event.

        Convenience method for logging authentication attempts.

        Args:
            actor_id: User ID attempting authentication (None for invalid users)
            outcome: "success", "failure", or "error"
            method: Authentication method used
            ip_address: Client IP address
            user_agent: Client user agent
            metadata: Additional event metadata
        """
        actor_info = {
            "actor_id": actor_id or "unknown",
            "actor_type": "user",
            "ip_address": ip_address or "unknown",
            "user_agent": user_agent or "unknown",
        }

        resource_info = {
            "resource_type": "authentication",
            "resource_id": method,
            "action": "authenticate",
        }

        event = AuditEvent.create(
            event_type="authentication_attempt",
            actor_info=actor_info,
            resource_info=resource_info,
            outcome=outcome,
            metadata=metadata or {},
        )

        await self.log_event(event)

    async def log_authorization_event(
        self,
        user_id: str,
        action: str,
        resource: str,
        outcome: str,
        policy_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an authorization event.

        Convenience method for logging authorization decisions.

        Args:
            user_id: User requesting access
            action: Action being attempted
            resource: Resource being accessed
            outcome: "success", "failure", or "error"
            policy_name: Policy that made the decision
            metadata: Additional event metadata
        """
        actor_info = {"actor_id": user_id, "actor_type": "user"}

        resource_info = {
            "resource_type": "authorization",
            "resource_id": resource,
            "action": action,
        }

        event_metadata = metadata or {}
        if policy_name:
            event_metadata["policy_name"] = policy_name

        event = AuditEvent.create(
            event_type="authorization_check",
            actor_info=actor_info,
            resource_info=resource_info,
            outcome=outcome,
            metadata=event_metadata,
        )

        await self.log_event(event)

    async def log_administrative_event(
        self,
        admin_id: str,
        action: str,
        target_resource: str,
        outcome: str,
        changes: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an administrative event.

        Convenience method for logging administrative actions.

        Args:
            admin_id: Administrator performing action
            action: Administrative action
            target_resource: Resource being modified
            outcome: "success", "failure", or "error"
            changes: Changes made (sanitized)
            metadata: Additional event metadata
        """
        actor_info = {"actor_id": admin_id, "actor_type": "administrator"}

        resource_info = {
            "resource_type": "admin_action",
            "resource_id": target_resource,
            "action": action,
        }

        event_metadata = metadata or {}
        if changes:
            # Sanitize changes to remove sensitive data
            event_metadata["changes"] = self._sanitize_changes(changes)

        event = AuditEvent.create(
            event_type="administrative_action",
            actor_info=actor_info,
            resource_info=resource_info,
            outcome=outcome,
            metadata=event_metadata,
        )

        await self.log_event(event)

    async def get_event_statistics(
        self, start_time: datetime, end_time: datetime, group_by: str = "event_type"
    ) -> dict[str, int]:
        """
        Get audit event statistics for a time period.

        Args:
            start_time: Start of time period
            end_time: End of time period
            group_by: Field to group statistics by

        Returns:
            Dictionary mapping group values to event counts
        """
        # Default implementation - providers should override
        return {}

    async def verify_log_integrity(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> dict[str, Any]:
        """
        Verify integrity of audit logs.

        Checks for tampering or corruption in the audit log.

        Args:
            start_time: Start of verification period
            end_time: End of verification period

        Returns:
            Integrity verification results
        """
        # Default implementation - providers should override
        return {"verified": True, "issues": []}

    def _sanitize_changes(self, changes: dict[str, Any]) -> dict[str, Any]:
        """
        Sanitize change data to remove sensitive information.

        Args:
            changes: Raw change data

        Returns:
            Sanitized change data safe for logging
        """
        sensitive_keys = {
            "password",
            "token",
            "secret",
            "key",
            "credential",
            "hash",
            "salt",
            "private",
            "auth",
        }

        sanitized = {}
        for key, value in changes.items():
            key_lower = key.lower()
            is_sensitive = any(sensitive in key_lower for sensitive in sensitive_keys)

            if is_sensitive:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_changes(value)
            else:
                sanitized[key] = value

        return sanitized

    def is_event_type_enabled(self, event_type: str) -> bool:
        """
        Check if an event type is enabled for logging.

        Args:
            event_type: Event type to check

        Returns:
            True if event type should be logged
        """
        enabled_events = self.config.get("enabled_events", [])

        # If no specific events configured, log all
        if not enabled_events:
            return True

        return event_type in enabled_events

    async def cleanup_old_events(self, retention_days: int) -> int:
        """
        Clean up audit events older than retention period.

        Args:
            retention_days: Number of days to retain events

        Returns:
            Number of events cleaned up
        """
        # Default implementation - providers should override
        return 0

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup resources when audit logger is being shut down.

        Override this method to cleanup any resources (connections,
        buffers, etc.) when the audit logger is being destroyed.
        """
        pass
