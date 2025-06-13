"""Memory-based audit provider implementation."""

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from bevy import Container

from serv.auth.audit.events import AuditEventType
from serv.auth.types import AuditEvent, PolicyResult
from serv.auth.providers.audit import AuditProvider

from .store import MemoryStore


class MemoryAuditProvider(AuditProvider):
    """Memory-based audit provider with structured logging.
    
    This provider supports:
    - Structured audit event storage
    - Event querying and filtering
    - Automatic cleanup based on retention policies
    - Thread-safe operations
    - Event categorization and metadata
    - Export capabilities for compliance
    """
    
    def __init__(self, config: Dict[str, Any], container: Container):
        """Initialize memory audit provider.
        
        Args:
            config: Provider configuration
            container: Dependency injection container
        """
        self.config = config
        self.container = container
        
        # Initialize memory store
        cleanup_interval = config.get("cleanup_interval", 300.0)
        self.store = MemoryStore(cleanup_interval=cleanup_interval)
        
        # Audit configuration
        self.retention_days = config.get("retention_days", 90)
        self.max_events = config.get("max_events", 100000)
        self.include_sensitive_data = config.get("include_sensitive_data", False)
        self.event_categories = config.get("event_categories", {
            "authentication": [
                AuditEventType.AUTH_ATTEMPT,
                AuditEventType.AUTH_SUCCESS,
                AuditEventType.AUTH_FAILURE,
                AuditEventType.AUTH_LOGOUT,
            ],
            "authorization": [
                AuditEventType.AUTHZ_CHECK,
                AuditEventType.AUTHZ_GRANT,
                AuditEventType.AUTHZ_DENY,
            ],
            "user_management": [
                AuditEventType.USER_CREATE,
                AuditEventType.USER_UPDATE,
                AuditEventType.USER_DELETE,
            ],
            "session_management": [
                AuditEventType.SESSION_CREATE,
                AuditEventType.SESSION_EXPIRE,
                AuditEventType.SESSION_DESTROY,
            ],
        })
        
        # Internal tracking
        self._event_counter = 0
        
        # Start cleanup task
        self._cleanup_started = False
    
    async def _ensure_cleanup_started(self) -> None:
        """Ensure cleanup task is started."""
        if not self._cleanup_started:
            await self.store.start_cleanup()
            self._cleanup_started = True
    
    async def record_event(
        self,
        event_type: AuditEventType,
        user_id: str | None = None,
        session_id: str | None = None,
        resource: str | None = None,
        action: str | None = None,
        result: str | None = None,
        metadata: Dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEvent:
        """Record an audit event."""
        await self._ensure_cleanup_started()
        
        # Generate unique event ID
        self._event_counter += 1
        event_id = f"audit_{int(time.time())}_{self._event_counter}"
        
        # Create audit event
        event = AuditEvent(
            id=event_id,
            event_type=event_type,
            timestamp=datetime.now(),
            user_id=user_id,
            session_id=session_id,
            resource=resource,
            action=action,
            result=PolicyResult.ALLOW if result == "success" else PolicyResult.DENY if result == "failure" else None,
            metadata={
                "ip_address": ip_address,
                "user_agent": user_agent,
                "severity": self._determine_severity(event_type, result),
                **(metadata or {}),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Filter sensitive data if required
        if not self.include_sensitive_data:
            event = self._sanitize_event(event)
        
        # Store event with retention TTL
        retention_ttl = self.retention_days * 24 * 3600  # Convert days to seconds
        self.store.set("events", event.id, event, ttl_seconds=retention_ttl)
        
        # Store in time-based index for efficient querying
        time_key = f"time_{int(event.timestamp.timestamp() // 3600)}"  # Hour-based buckets
        hour_events = self.store.get("time_index", time_key) or []
        hour_events.append(event.id)
        self.store.set("time_index", time_key, hour_events, ttl_seconds=retention_ttl)
        
        # Store in user-based index
        if user_id:
            user_key = f"user_{user_id}"
            user_events = self.store.get("user_index", user_key) or []
            user_events.append(event.id)
            self.store.set("user_index", user_key, user_events, ttl_seconds=retention_ttl)
        
        # Store in event type index
        type_key = f"type_{event_type.value}"
        type_events = self.store.get("type_index", type_key) or []
        type_events.append(event.id)
        self.store.set("type_index", type_key, type_events, ttl_seconds=retention_ttl)
        
        # Enforce event limits
        await self._enforce_event_limits()
        
        return event
    
    async def store_audit_event(self, event: AuditEvent) -> None:
        """Store an audit event."""
        await self._ensure_cleanup_started()
        
        # Filter sensitive data if required
        if not self.include_sensitive_data:
            event = self._sanitize_event(event)
        
        # Store event with retention TTL
        retention_ttl = self.retention_days * 24 * 3600  # Convert days to seconds
        self.store.set("events", event.id, event, ttl_seconds=retention_ttl)
        
        # Store in time-based index for efficient querying
        time_key = f"time_{int(event.timestamp.timestamp() // 3600)}"  # Hour-based buckets
        hour_events = self.store.get("time_index", time_key) or []
        hour_events.append(event.id)
        self.store.set("time_index", time_key, hour_events, ttl_seconds=retention_ttl)
        
        # Store in user-based index
        if event.user_id:
            user_key = f"user_{event.user_id}"
            user_events = self.store.get("user_index", user_key) or []
            user_events.append(event.id)
            self.store.set("user_index", user_key, user_events, ttl_seconds=retention_ttl)
        
        # Store in event type index
        type_key = f"type_{event.event_type.value}"
        type_events = self.store.get("type_index", type_key) or []
        type_events.append(event.id)
        self.store.set("type_index", type_key, type_events, ttl_seconds=retention_ttl)
        
        # Enforce event limits
        await self._enforce_event_limits()
    
    async def get_event(self, event_id: str) -> AuditEvent | None:
        """Get specific audit event by ID."""
        await self._ensure_cleanup_started()
        return self.store.get("events", event_id)
    
    async def query_events(
        self,
        event_types: List[AuditEventType] | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        resource: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """Query audit events with filters."""
        await self._ensure_cleanup_started()
        
        events = []
        
        # Determine which events to check based on filters
        if user_id:
            # Use user index for efficiency
            user_key = f"user_{user_id}"
            event_ids = self.store.get("user_index", user_key) or []
        elif event_types and len(event_types) == 1:
            # Use event type index for single type queries
            type_key = f"type_{event_types[0].value}"
            event_ids = self.store.get("type_index", type_key) or []
        elif start_time or end_time:
            # Use time index for time-based queries
            event_ids = self._get_events_in_time_range(start_time, end_time)
        else:
            # Full scan (less efficient but comprehensive)
            event_ids = list(self.store.keys("events"))
        
        # Filter events
        for event_id in event_ids:
            event = self.store.get("events", event_id)
            if not event:
                continue
            
            # Apply filters
            if event_types and event.event_type not in event_types:
                continue
            if user_id and event.user_id != user_id:
                continue
            if session_id and event.session_id != session_id:
                continue
            if resource and event.resource != resource:
                continue
            if start_time and event.timestamp.timestamp() < start_time:
                continue
            if end_time and event.timestamp.timestamp() > end_time:
                continue
            
            events.append(event)
        
        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.timestamp.timestamp(), reverse=True)
        
        # Apply pagination
        return events[offset:offset + limit]
    
    async def get_user_events(
        self,
        user_id: str,
        event_types: List[AuditEventType] | None = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get audit events for a specific user."""
        return await self.query_events(
            user_id=user_id,
            event_types=event_types,
            limit=limit,
        )
    
    async def get_session_events(
        self,
        session_id: str,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get audit events for a specific session."""
        return await self.query_events(
            session_id=session_id,
            limit=limit,
        )
    
    async def get_events_by_category(
        self,
        category: str,
        start_time: float | None = None,
        end_time: float | None = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get events by category (authentication, authorization, etc.)."""
        event_types = self.event_categories.get(category, [])
        if not event_types:
            return []
        
        return await self.query_events(
            event_types=event_types,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
    
    async def get_failed_events(
        self,
        event_types: List[AuditEventType] | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get failed/denied audit events."""
        events = await self.query_events(
            event_types=event_types,
            start_time=start_time,
            end_time=end_time,
            limit=limit * 2,  # Get more to filter
        )
        
        # Filter for failed events
        failed_events = []
        for event in events:
            if (event.result in ["failure", "denied", "error"] or 
                event.event_type in [AuditEventType.AUTH_FAILURE, AuditEventType.AUTHZ_DENY]):
                failed_events.append(event)
                if len(failed_events) >= limit:
                    break
        
        return failed_events
    
    async def get_security_events(
        self,
        start_time: float | None = None,
        end_time: float | None = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get security-relevant events (failures, suspicious activity)."""
        security_event_types = [
            AuditEventType.AUTH_FAILURE,
            AuditEventType.AUTHZ_DENY,
            AuditEventType.SESSION_EXPIRE,
            AuditEventType.SESSION_DESTROY,
            AuditEventType.SECURITY_VIOLATION,
            AuditEventType.SECURITY_ANOMALY,
        ]
        
        return await self.query_events(
            event_types=security_event_types,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
    
    
    async def get_audit_events(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Get audit events within a time range."""
        start_timestamp = start_time.timestamp() if start_time else None
        end_timestamp = end_time.timestamp() if end_time else None
        
        return await self.query_events(
            start_time=start_timestamp,
            end_time=end_timestamp,
            limit=limit,
            offset=offset,
        )
    
    async def get_user_audit_events(
        self,
        user_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Get audit events for a specific user."""
        start_timestamp = start_time.timestamp() if start_time else None
        end_timestamp = end_time.timestamp() if end_time else None
        
        return await self.query_events(
            user_id=user_id,
            start_time=start_timestamp,
            end_time=end_timestamp,
            limit=limit,
            offset=offset,
        )
    
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
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Search audit events with various filters."""
        start_timestamp = start_time.timestamp() if start_time else None
        end_timestamp = end_time.timestamp() if end_time else None
        
        return await self.query_events(
            event_types=event_types,
            user_id=user_id,
            session_id=session_id,
            resource=resource,
            start_time=start_timestamp,
            end_time=end_timestamp,
            limit=limit,
            offset=offset,
        )
    
    async def cleanup_old_events(self, older_than: datetime) -> int:
        """Clean up audit events older than specified time."""
        await self._ensure_cleanup_started()
        
        cutoff_timestamp = older_than.timestamp()
        cleanup_count = 0
        
        # Clean up main events
        for event_id in list(self.store.keys("events")):
            event = self.store.get("events", event_id)
            if event and event.timestamp.timestamp() < cutoff_timestamp:
                self.store.delete("events", event_id)
                cleanup_count += 1
        
        # Clean up indexes
        for index_type in ["time_index", "user_index", "type_index"]:
            for key in list(self.store.keys(index_type)):
                event_ids = self.store.get(index_type, key) or []
                # Remove references to deleted events
                valid_event_ids = [
                    eid for eid in event_ids 
                    if self.store.exists("events", eid)
                ]
                if len(valid_event_ids) != len(event_ids):
                    if valid_event_ids:
                        self.store.set(index_type, key, valid_event_ids)
                    else:
                        self.store.delete(index_type, key)
        
        return cleanup_count
    
    async def export_events(
        self,
        format: str = "json",
        event_types: List[AuditEventType] | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> str:
        """Export events for compliance or backup purposes."""
        events = await self.query_events(
            event_types=event_types,
            start_time=start_time,
            end_time=end_time,
            limit=10000,  # Large limit for export
        )
        
        if format.lower() == "json":
            # Convert events to JSON-serializable format
            export_data = []
            for event in events:
                event_data = {
                    "event_id": event.id,
                    "event_type": event.event_type.value,
                    "timestamp": event.timestamp.isoformat(),
                    "user_id": event.user_id,
                    "session_id": event.session_id,
                    "resource": event.resource,
                    "action": event.action,
                    "result": event.result.value if event.result else None,
                    "metadata": event.metadata,
                    "ip_address": event.ip_address,
                    "user_agent": event.user_agent,
                }
                export_data.append(event_data)
            
            return json.dumps(export_data, indent=2, default=str)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get audit provider statistics."""
        await self._ensure_cleanup_started()
        
        total_events = self.store.size("events")
        
        # Count events by type
        event_type_counts = {}
        for event_type in AuditEventType:
            type_key = f"type_{event_type.value}"
            event_ids = self.store.get("type_index", type_key) or []
            event_type_counts[event_type.value] = len(event_ids)
        
        # Count events by category
        category_counts = {}
        for category, event_types in self.event_categories.items():
            count = sum(event_type_counts.get(et.value, 0) for et in event_types)
            category_counts[category] = count
        
        return {
            "total_events": total_events,
            "retention_days": self.retention_days,
            "max_events": self.max_events,
            "event_type_counts": event_type_counts,
            "category_counts": category_counts,
            "include_sensitive_data": self.include_sensitive_data,
        }
    
    def _determine_severity(self, event_type: AuditEventType, result: str | None) -> str:
        """Determine event severity based on type and result."""
        if event_type in [AuditEventType.AUTH_FAILURE, AuditEventType.AUTHZ_DENY]:
            return "warning"
        elif result in ["failure", "error", "denied"]:
            return "warning"
        elif event_type in [AuditEventType.USER_DELETED, AuditEventType.SESSION_REVOKED]:
            return "medium"
        else:
            return "low"
    
    def _sanitize_event(self, event: AuditEvent) -> AuditEvent:
        """Remove sensitive data from event if configured."""
        if not self.include_sensitive_data:
            # Create a copy and sanitize metadata
            sanitized_metadata = {}
            for key, value in event.metadata.items():
                if key.lower() in ["password", "token", "secret", "key", "credential"]:
                    sanitized_metadata[key] = "[REDACTED]"
                elif isinstance(value, str) and len(value) > 100:
                    # Truncate long strings that might contain sensitive data
                    sanitized_metadata[key] = value[:100] + "..."
                else:
                    sanitized_metadata[key] = value
            
            # Create new event with sanitized metadata
            event.metadata = sanitized_metadata
        
        return event
    
    def _get_events_in_time_range(
        self,
        start_time: float | None,
        end_time: float | None,
    ) -> List[str]:
        """Get event IDs in time range using time index."""
        if not start_time and not end_time:
            return list(self.store.keys("events"))
        
        event_ids = []
        current_time = time.time()
        
        # Calculate hour buckets to check
        start_hour = int((start_time or 0) // 3600)
        end_hour = int((end_time or current_time) // 3600)
        
        for hour in range(start_hour, end_hour + 1):
            time_key = f"time_{hour}"
            hour_events = self.store.get("time_index", time_key) or []
            event_ids.extend(hour_events)
        
        return event_ids
    
    async def _enforce_event_limits(self) -> None:
        """Enforce maximum event limits."""
        total_events = self.store.size("events")
        
        if total_events > self.max_events:
            # Remove oldest events to stay under limit
            events_to_remove = total_events - self.max_events + 1000  # Remove extra for buffer
            
            # Get all events and sort by timestamp
            all_events = []
            for event_id in self.store.keys("events"):
                event = self.store.get("events", event_id)
                if event:
                    all_events.append((event.timestamp.timestamp(), event_id))
            
            # Sort by timestamp (oldest first)
            all_events.sort(key=lambda x: x[0])
            
            # Remove oldest events
            for _, event_id in all_events[:events_to_remove]:
                self.store.delete("events", event_id)