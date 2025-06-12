"""Audit event types with pipeline support."""

from enum import Enum


class AuditEventType(Enum):
    """Types of audit events with pipeline operator support."""

    # Authentication Events
    AUTH_ATTEMPT = "auth.attempt"
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    AUTH_LOGOUT = "auth.logout"

    # Authorization Events
    AUTHZ_CHECK = "authz.check"
    AUTHZ_GRANT = "authz.grant"
    AUTHZ_DENY = "authz.deny"

    # Session Events
    SESSION_CREATE = "session.create"
    SESSION_REFRESH = "session.refresh"
    SESSION_EXPIRE = "session.expire"
    SESSION_DESTROY = "session.destroy"
    SESSION_ACCESS = "session.access"
    SESSION_INVALID = "session.invalid"

    # User Events
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_LOCK = "user.lock"
    USER_UNLOCK = "user.unlock"

    # Credential Events
    CREDENTIAL_CREATE = "credential.create"
    CREDENTIAL_UPDATE = "credential.update"
    CREDENTIAL_DELETE = "credential.delete"
    CREDENTIAL_VERIFY = "credential.verify"

    # Security Events
    SECURITY_VIOLATION = "security.violation"
    SECURITY_ANOMALY = "security.anomaly"
    RATE_LIMIT_EXCEEDED = "rate_limit.exceeded"
    PERMISSION_CHECK = "permission.check"
    ACCESS_GRANTED = "access.granted"
    ACCESS_DENIED = "access.denied"

    def __or__(self, other):
        """Create OR group - one of these events must occur."""
        from .pipeline import AuditEventGroup

        if isinstance(other, AuditEventGroup):
            return AuditEventGroup(self, *other.events)
        elif isinstance(other, AuditEventType):
            return AuditEventGroup(self, other)
        else:
            raise ValueError(f"Cannot OR {type(other)} with AuditEventType")

    def __ror__(self, other):
        """Reverse OR operation."""
        from .pipeline import AuditEventGroup

        if isinstance(other, AuditEventGroup):
            return AuditEventGroup(*other.events, self)
        elif isinstance(other, AuditEventType):
            return AuditEventGroup(other, self)
        else:
            raise ValueError(f"Cannot OR {type(other)} with AuditEventType")

    def __rshift__(self, other):
        """Create pipeline - this event then that event/group/pipeline."""
        from .pipeline import AuditEventGroup, AuditPipeline

        if isinstance(other, AuditEventType | AuditEventGroup):
            return AuditPipeline([self, other])
        elif isinstance(other, AuditPipeline):
            return AuditPipeline([self] + other.steps)
        else:
            raise ValueError(f"Cannot create pipeline with {type(other)}")

    def __repr__(self):
        return f"AuditEventType.{self.name}"
