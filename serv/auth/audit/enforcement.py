"""Audit enforcement system with decorators and emitters."""

import inspect
import uuid
from datetime import datetime
from functools import wraps
from typing import Any, get_args, get_origin, get_type_hints

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
            # Find the audit emitter parameter
            sig = inspect.signature(func)
            emitter_param = _find_audit_emitter_parameter(sig, func)

            # Get or create the audit emitter for validation
            audit_emitter = _get_or_inject_audit_emitter(sig, emitter_param, args, kwargs)

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
                # Find the audit emitter parameter
                sig = inspect.signature(func)
                emitter_param = _find_audit_emitter_parameter(sig, func)

                # Get or create the audit emitter for validation
                audit_emitter = _get_or_inject_audit_emitter(sig, emitter_param, args, kwargs)

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

    match requirement:
        case AuditEventType():
            # Simple requirement - just check if the event occurred
            if requirement not in events:
                raise AuditError(f"Audit pipeline requirement not satisfied: {requirement} not found in events")

        case AuditEventGroup():
            # OR requirement - at least one event from the group must have occurred
            if not requirement.matches(events):
                raise AuditError(f"Audit pipeline requirement not satisfied: none of {requirement} found in events")

        case AuditPipeline():
            # Sequence requirement - events must follow the pipeline
            if not requirement.validates(events):
                raise AuditError(f"Audit pipeline requirement not satisfied: events {[e.value for e in events]} do not match pipeline {requirement}")

        case AuditPipelineSet():
            # Multiple pipeline requirement - events must satisfy at least one pipeline
            if not requirement.validates(events):
                raise AuditError(f"Audit pipeline requirement not satisfied: events {[e.value for e in events]} do not match any pipeline in {requirement}")

        case _:
            raise AuditError(f"Unknown audit requirement type: {type(requirement)}")


def _get_or_inject_audit_emitter(signature: inspect.Signature, emitter_param: str | None,
                                args: tuple, kwargs: dict) -> AuditEmitter:
    """Get existing audit emitter from args/kwargs or inject a new one.

    Args:
        signature: Function signature
        emitter_param: Name of the audit emitter parameter (if found)
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        AuditEmitter instance to use for validation
    """
    if not emitter_param:
        # No audit emitter parameter, create one for validation only
        return AuditEmitter()

    # Check if emitter was passed in kwargs
    if emitter_param in kwargs:
        emitter = kwargs[emitter_param]
        if isinstance(emitter, AuditEmitter):
            return emitter

    # Check if emitter was passed positionally
    param_names = list(signature.parameters.keys())
    if emitter_param in param_names:
        param_index = param_names.index(emitter_param)
        if param_index < len(args):
            emitter = args[param_index]
            if isinstance(emitter, AuditEmitter):
                return emitter

    # No emitter provided, create and inject one
    audit_emitter = AuditEmitter()
    if emitter_param not in kwargs:
        kwargs[emitter_param] = audit_emitter

    return audit_emitter


def _find_audit_emitter_parameter(signature: inspect.Signature, func: callable = None) -> str | None:
    """Find parameter annotated with AuditEmitter type.

    Args:
        signature: Function signature to inspect
        func: Optional function to use for type hint resolution

    Returns:
        Parameter name if found, None otherwise
    """
    # First try to resolve type hints if function is available
    if func is not None:
        try:
            # Use get_type_hints to resolve string annotations properly
            type_hints = get_type_hints(func)
            for param_name, _param in signature.parameters.items():
                if param_name in type_hints:
                    resolved_type = type_hints[param_name]
                    if _is_audit_emitter_type(resolved_type):
                        return param_name
        except (NameError, TypeError, AttributeError):
            # If get_type_hints fails, fall back to manual inspection
            pass

    # Fallback: manual annotation inspection
    for param_name, param in signature.parameters.items():
        if param.annotation == inspect.Parameter.empty:
            continue

        if _is_audit_emitter_type(param.annotation) or _is_audit_emitter_string(param.annotation):
            return param_name

    return None


def _is_audit_emitter_type(annotation: Any) -> bool:
    """Check if annotation is the AuditEmitter type or contains it.

    Args:
        annotation: The type annotation to check

    Returns:
        True if annotation represents AuditEmitter type
    """
    # Direct type check
    if annotation is AuditEmitter:
        return True

    # Check for union types like AuditEmitter | None
    origin = get_origin(annotation)
    if origin is not None:  # This is a generic type
        args = get_args(annotation)
        if AuditEmitter in args:
            return True

    return False


def _is_audit_emitter_string(annotation: Any) -> bool:
    """Check if string annotation likely represents AuditEmitter.

    Args:
        annotation: The annotation to check

    Returns:
        True if string annotation likely represents AuditEmitter
    """
    if not isinstance(annotation, str):
        return False

    # Clean up the string
    annotation_str = annotation.strip()

    # Check for simple AuditEmitter reference
    if annotation_str == 'AuditEmitter':
        return True

    # Check for qualified names ending with AuditEmitter
    if annotation_str.endswith('.AuditEmitter'):
        return True

    # Check for union patterns containing AuditEmitter
    union_patterns = [
        'AuditEmitter | None',
        'AuditEmitter|None',
        'None | AuditEmitter',
        'None|AuditEmitter',
        'Union[AuditEmitter, None]',
        'Union[None, AuditEmitter]'
    ]

    for pattern in union_patterns:
        if annotation_str == pattern:
            return True

    # Check if AuditEmitter appears in a union with other types
    if ('AuditEmitter' in annotation_str and
        ('|' in annotation_str or 'Union[' in annotation_str)):
        return True

    return False
