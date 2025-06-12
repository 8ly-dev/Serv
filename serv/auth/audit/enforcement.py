"""Audit enforcement system with decorators and emitters."""

import inspect
import uuid
from datetime import datetime
from functools import wraps
from typing import Any

from ..exceptions import AuditError
from ..types import AuditEvent
from .events import AuditEventType
from .pipeline import AuditEventGroup, AuditPipeline, AuditPipelineSet


class AuditEmitter:
    """Tracks and emits audit events for pipeline validation."""

    def __init__(self):
        self.events: list[AuditEventType] = []
        self.event_data: list[dict[str, Any]] = []
        self.sequence_id = str(uuid.uuid4())

    def emit(self, event_type: AuditEventType, data: dict[str, Any] | None = None):
        """Emit an audit event with sequence tracking."""
        self.events.append(event_type)
        event_data = {
            **(data or {}),
            "sequence_id": self.sequence_id,
            "sequence_position": len(self.events),
            "timestamp": datetime.now().isoformat()
        }
        self.event_data.append(event_data)

        # Send to actual audit provider for storage
        audit_event = AuditEvent(
            id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.now(),
            metadata={**event_data, "sequence_id": self.sequence_id},
            **self._extract_context_from_data(data or {})
        )

        # Store event (implementation would send to audit provider)
        self._store_audit_event(audit_event)

    def _extract_context_from_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Extract standard fields from event data."""
        return {
            "user_id": data.get("user_id"),
            "session_id": data.get("session_id"),
            "ip_address": data.get("ip_address"),
            "user_agent": data.get("user_agent"),
            "resource": data.get("resource"),
            "action": data.get("action")
        }

    def _store_audit_event(self, event: AuditEvent):
        """Store audit event via audit provider."""
        # Implementation would inject and use audit provider
        # For now, this is a no-op for testing
        pass


def AuditRequired(pipeline_requirement: AuditEventType | AuditEventGroup | AuditPipeline | AuditPipelineSet):
    """
    Decorator that enforces audit event pipeline requirements.

    Args:
        pipeline_requirement: Can be:
            - Single AuditEventType (simple requirement)
            - AuditEventGroup (OR relationship)
            - AuditPipeline (sequence requirement)
            - AuditPipelineSet (multiple valid sequences)

    Example:
        @AuditRequired(
            AuditEventType.AUTH_ATTEMPT >> AuditEventType.AUTH_SUCCESS >> AuditEventType.SESSION_CREATE |
            AuditEventType.AUTH_ATTEMPT >> AuditEventType.AUTH_FAILURE |
            AuditEventType.AUTH_ATTEMPT >> AuditEventType.RATE_LIMIT_EXCEEDED
        )
        async def authenticate(self, credentials, audit_emitter):
            # Implementation must follow one of the specified pipelines
            pass
    """
    def decorator(func):
        # Store audit requirements on function for introspection
        func._audit_pipeline = pipeline_requirement

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create audit emitter for this operation
            audit_emitter = AuditEmitter()

            # Inject audit_emitter into kwargs if function expects it
            sig = inspect.signature(func)
            if 'audit_emitter' in sig.parameters:
                kwargs['audit_emitter'] = audit_emitter

            try:
                # Execute the function
                result = await func(*args, **kwargs)

                # Validate that the audit pipeline was satisfied
                _validate_audit_pipeline(pipeline_requirement, audit_emitter.events)

                return result
            except Exception as e:
                # Always validate audit trail even on exception
                try:
                    _validate_audit_pipeline(pipeline_requirement, audit_emitter.events)
                except AuditError:
                    # If audit validation fails, that's the primary error
                    raise
                # Re-raise the original exception if audit is satisfied
                raise e

        # Handle sync functions too
        if not inspect.iscoroutinefunction(func):
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                audit_emitter = AuditEmitter()

                sig = inspect.signature(func)
                if 'audit_emitter' in sig.parameters:
                    kwargs['audit_emitter'] = audit_emitter

                try:
                    result = func(*args, **kwargs)
                    _validate_audit_pipeline(pipeline_requirement, audit_emitter.events)
                    return result
                except Exception as e:
                    try:
                        _validate_audit_pipeline(pipeline_requirement, audit_emitter.events)
                    except AuditError:
                        raise
                    raise e

            return sync_wrapper

        return wrapper
    return decorator


def _validate_audit_pipeline(requirement: AuditEventType | AuditEventGroup | AuditPipeline | AuditPipelineSet,
                           events: list[AuditEventType]):
    """Validate that events satisfy the audit requirement."""

    if isinstance(requirement, AuditEventType):
        # Simple requirement - just check if the event occurred
        if requirement not in events:
            raise AuditError(f"Audit pipeline requirement not satisfied: {requirement} not found in events")

    elif isinstance(requirement, AuditEventGroup):
        # OR requirement - at least one event from the group must have occurred
        if not requirement.matches(events):
            raise AuditError(f"Audit pipeline requirement not satisfied: none of {requirement} found in events")

    elif isinstance(requirement, AuditPipeline):
        # Sequence requirement - events must follow the pipeline
        if not requirement.validates(events):
            raise AuditError(f"Audit pipeline requirement not satisfied: events {[e.value for e in events]} do not match pipeline {requirement}")

    elif isinstance(requirement, AuditPipelineSet):
        # Multiple pipeline requirement - events must satisfy at least one pipeline
        if not requirement.validates(events):
            raise AuditError(f"Audit pipeline requirement not satisfied: events {[e.value for e in events]} do not match any pipeline in {requirement}")

    else:
        raise AuditError(f"Unknown audit requirement type: {type(requirement)}")
