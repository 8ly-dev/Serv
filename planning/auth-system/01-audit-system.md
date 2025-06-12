# Audit System Design

## Overview

The audit system is the foundation of the authentication system, ensuring all security-related operations are properly logged and follow correct sequences. It provides mandatory audit enforcement with compile-time and runtime guarantees using a sophisticated pipeline-based approach that validates not just which events occur, but their proper sequence and flow.

## Core Innovation: Pipeline-Based Audit Requirements

Traditional audit systems only validate that certain events occurred. Our pipeline system validates the **sequence** and **flow** of operations, catching logic errors and ensuring proper business process compliance.

### Pipeline Syntax Examples

```python
# Simple sequence - events must occur in this exact order
AUTH_ATTEMPT >> AUTH_SUCCESS >> SESSION_CREATE

# OR groups within pipeline - one of the events in parentheses must occur
AUTH_ATTEMPT >> (AUTH_SUCCESS | AUTH_FAILURE)

# Multiple valid pipelines - any complete pipeline satisfies the requirement
AUTH_ATTEMPT >> AUTH_SUCCESS >> SESSION_CREATE |  # Success path
AUTH_ATTEMPT >> AUTH_FAILURE |                    # Failure path  
AUTH_ATTEMPT >> RATE_LIMIT_EXCEEDED              # Rate limit path

# Complex conditional flows
AUTH_ATTEMPT >> CREDENTIAL_VERIFY >> (AUTH_SUCCESS | AUTH_FAILURE) >> 
(SESSION_CREATE | AUDIT_FAILURE_REASON)
```

## Core Components

### 1. Enhanced Audit Events with Pipeline Support

```python
from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Union
from datetime import datetime

class AuditEventType(Enum):
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
    
    # Pipeline Operators
    def __or__(self, other):
        """Create OR group - one of these events must occur."""
        match other:
            case AuditEventGroup():
                return AuditEventGroup(self, *other.events)
            case AuditEventType():
                return AuditEventGroup(self, other)
            case _:
                raise ValueError(f"Cannot OR {type(other)} with AuditEventType")
    
    def __ror__(self, other):
        match other:
            case AuditEventGroup():
                return AuditEventGroup(*other.events, self)
            case AuditEventType():
                return AuditEventGroup(other, self)
            case _:
                raise ValueError(f"Cannot OR {type(other)} with AuditEventType")
    
    def __rshift__(self, other):
        """Create pipeline - this event then that event/group/pipeline."""
        match other:
            case AuditEventType() | AuditEventGroup():
                return AuditPipeline([self, other])
            case AuditPipeline():
                return AuditPipeline([self] + other.steps)
            case _:
                raise ValueError(f"Cannot create pipeline with {type(other)}")

@dataclass
class AuditEvent:
    event_type: AuditEventType
    timestamp: datetime
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource: Optional[str]
    action: Optional[str]
    result: str  # "success", "failure", "denied", etc.
    details: Dict[str, Any]
    risk_score: Optional[int] = None
    compliance_tags: List[str] = None
    sequence_id: Optional[str] = None  # Links events in a pipeline
```

### 2. Pipeline System Classes

```python
class AuditEventGroup:
    """Represents OR relationship - one of these events must occur."""
    
    def __init__(self, *events: AuditEventType):
        self.events = events
    
    def __or__(self, other):
        match other:
            case AuditEventGroup():
                return AuditEventGroup(*self.events, *other.events)
            case AuditEventType():
                return AuditEventGroup(*self.events, other)
            case _:
                raise ValueError(f"Cannot OR {type(other)} with AuditEventGroup")
    
    def __ror__(self, other):
        match other:
            case AuditEventGroup():
                return AuditEventGroup(*other.events, *self.events)
            case AuditEventType():
                return AuditEventGroup(other, *self.events)
            case _:
                raise ValueError(f"Cannot OR {type(other)} with AuditEventGroup")
    
    def __rshift__(self, other):
        """Create pipeline starting with this group."""
        match other:
            case AuditEventType() | AuditEventGroup():
                return AuditPipeline([self, other])
            case AuditPipeline():
                return AuditPipeline([self] + other.steps)
            case _:
                raise ValueError(f"Cannot create pipeline with {type(other)}")
    
    def matches(self, events: List[AuditEventType]) -> bool:
        """Check if any of the events in this group occurred."""
        return any(event in events for event in self.events)
    
    def __repr__(self):
        return f"({' | '.join(e.value for e in self.events)})"


class AuditPipeline:
    """Represents a sequence of events that must occur in order."""
    
    def __init__(self, steps: List[Union[AuditEventType, AuditEventGroup]]):
        self.steps = steps
    
    def __rshift__(self, other):
        """Extend pipeline with another step."""
        match other:
            case AuditEventType() | AuditEventGroup():
                return AuditPipeline(self.steps + [other])
            case AuditPipeline():
                return AuditPipeline(self.steps + other.steps)
            case _:
                raise ValueError(f"Cannot extend pipeline with {type(other)}")
    
    def __or__(self, other):
        """Create alternative pipeline - this pipeline OR that pipeline."""
        match other:
            case AuditPipeline():
                return AuditPipelineSet([self, other])
            case AuditPipelineSet():
                return AuditPipelineSet([self] + other.pipelines)
            case _:
                raise ValueError(f"Cannot OR pipeline with {type(other)}")
    
    def __ror__(self, other):
        match other:
            case AuditPipeline():
                return AuditPipelineSet([other, self])
            case AuditPipelineSet():
                return AuditPipelineSet(other.pipelines + [self])
            case _:
                raise ValueError(f"Cannot OR {type(other)} with pipeline")
    
    def validates(self, events: List[AuditEventType]) -> bool:
        """Check if the events match this pipeline sequence."""
        event_index = 0
        
        for step in self.steps:
            if isinstance(step, AuditEventType):
                # Must find this exact event
                while event_index < len(events):
                    if events[event_index] == step:
                        event_index += 1
                        break
                    event_index += 1
                else:
                    return False  # Event not found
                    
            elif isinstance(step, AuditEventGroup):
                # Must find one of the events in the group
                step_found = False
                while event_index < len(events):
                    if events[event_index] in step.events:
                        event_index += 1
                        step_found = True
                        break
                    event_index += 1
                
                if not step_found:
                    return False
        
        return True
    
    def __repr__(self):
        return ' >> '.join(str(step) for step in self.steps)


class AuditPipelineSet:
    """Represents multiple valid pipelines - any one of them can satisfy the requirement."""
    
    def __init__(self, pipelines: List[AuditPipeline]):
        self.pipelines = pipelines
    
    def __or__(self, other):
        match other:
            case AuditPipeline():
                return AuditPipelineSet(self.pipelines + [other])
            case AuditPipelineSet():
                return AuditPipelineSet(self.pipelines + other.pipelines)
            case _:
                raise ValueError(f"Cannot OR pipeline set with {type(other)}")
    
    def validates(self, events: List[AuditEventType]) -> bool:
        """Check if events satisfy any of the pipelines."""
        return any(pipeline.validates(events) for pipeline in self.pipelines)
    
    def __repr__(self):
        return f"({' | '.join(str(p) for p in self.pipelines)})"
```

### 3. Enhanced Audit Enforcement

```python
from functools import wraps
from typing import List, Dict, Any
import uuid
from datetime import datetime

class AuditEmitter:
    """Tracks and emits audit events for pipeline validation."""
    
    def __init__(self):
        self.events: List[AuditEventType] = []
        self.event_data: List[Dict[str, Any]] = []
        self.sequence_id = str(uuid.uuid4())
        
    def emit(self, event_type: AuditEventType, data: Dict[str, Any] = None):
        """Emit an audit event with sequence tracking."""
        self.events.append(event_type)
        self.event_data.append({
            **(data or {}),
            "sequence_id": self.sequence_id,
            "sequence_position": len(self.events),
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Send to actual audit provider for storage
        audit_event = AuditEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            sequence_id=self.sequence_id,
            details=data or {},
            **self._extract_context_from_data(data or {})
        )
        
        # Store event (implementation would send to audit provider)
        self._store_audit_event(audit_event)
    
    def _extract_context_from_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract standard fields from event data."""
        return {
            "user_id": data.get("user_id"),
            "session_id": data.get("session_id"),
            "ip_address": data.get("ip_address"),
            "user_agent": data.get("user_agent"),
            "resource": data.get("resource"),
            "action": data.get("action"),
            "result": data.get("result", "unknown")
        }
    
    def _store_audit_event(self, event: AuditEvent):
        """Store audit event via audit provider."""
        # Implementation would inject and use audit provider
        pass


def AuditRequired(pipeline_requirement):
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
            
            # Inject audit emitter into function context
            if 'audit_emitter' not in kwargs:
                kwargs['audit_emitter'] = audit_emitter
            
            try:
                result = await func(*args, **kwargs)
                
                # Validate that emitted events satisfy the pipeline requirement
                if not _validate_pipeline_requirement(pipeline_requirement, audit_emitter.events):
                    emitted = [e.value for e in audit_emitter.events]
                    raise AuditComplianceError(
                        f"Function {func.__name__} did not satisfy audit pipeline requirement.\n"
                        f"Required: {pipeline_requirement}\n"
                        f"Emitted: {emitted}\n"
                        f"Sequence ID: {audit_emitter.sequence_id}"
                    )
                
                return result
                
            except Exception as e:
                # Even on exceptions, validate audit compliance for exception paths
                # Some pipelines may be valid even with failures
                if not _validate_pipeline_requirement(pipeline_requirement, audit_emitter.events):
                    emitted = [e.value for e in audit_emitter.events]
                    # Log but don't override original exception - some exception paths may be valid
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Audit pipeline incomplete due to exception in {func.__name__}: "
                        f"Required: {pipeline_requirement}, Emitted: {emitted}, "
                        f"Sequence ID: {audit_emitter.sequence_id}"
                    )
                
                raise  # Re-raise the original exception
        
        return wrapper
    return decorator


def _validate_pipeline_requirement(requirement, events: List[AuditEventType]) -> bool:
    """Validate that events satisfy the pipeline requirement."""
    if isinstance(requirement, AuditEventType):
        return requirement in events
    elif hasattr(requirement, 'events'):  # AuditEventGroup
        return requirement.matches(events)
    elif hasattr(requirement, 'validates'):  # AuditPipeline or AuditPipelineSet
        return requirement.validates(events)
    else:
        raise ValueError(f"Unknown audit requirement type: {type(requirement)}")


class AuditComplianceError(Exception):
    """Raised when audit pipeline requirements are not met."""
    pass
```

### 4. Inheritance Enforcement

```python
class AuditEnforcedMeta(type):
    """Metaclass that ensures all auth providers implement audit requirements."""
    
    def __new__(mcs, name, bases, dct):
        cls = super().__new__(mcs, name, bases, dct)
        
        # Check if this class should have audit enforcement
        if any(base.__name__.endswith('Provider') for base in bases):
            mcs._validate_audit_compliance(cls, name, dct)
        
        return cls
    
    @staticmethod
    def _validate_audit_compliance(cls, name, dct):
        """Ensure all public methods have audit requirements."""
        audit_methods = []
        non_audit_methods = []
        
        for attr_name, attr_value in dct.items():
            if (callable(attr_value) and 
                not attr_name.startswith('_') and 
                not attr_name in ['__init__', '__new__']):
                
                if hasattr(attr_value, '_audit_pipeline'):
                    audit_methods.append(attr_name)
                else:
                    non_audit_methods.append(attr_name)
        
        if non_audit_methods:
            raise AuditEnforcementError(
                f"Class {name} has methods without audit requirements: {non_audit_methods}. "
                f"All provider methods must use @AuditRequired decorator."
            )


class AuditEnforced(metaclass=AuditEnforcedMeta):
    """Base class for all components requiring audit enforcement."""
    pass


class AuditEnforcementError(Exception):
    """Raised when audit enforcement requirements are violated."""
    pass
```

## Audit Pipeline System Benefits

### 1. **Semantic Flow Validation**
Pipelines capture the actual business logic flow, not just event presence:
```python
# Wrong: Just checks if events happened
@AuditRequired(AUTH_ATTEMPT, AUTH_SUCCESS, SESSION_CREATE)

# Right: Validates proper sequence
@AuditRequired(AUTH_ATTEMPT >> AUTH_SUCCESS >> SESSION_CREATE)
```

### 2. **Multiple Valid Paths**
Real authentication has different valid outcomes:
```python
@AuditRequired(
    AUTH_ATTEMPT >> AUTH_SUCCESS >> SESSION_CREATE |  # Success
    AUTH_ATTEMPT >> AUTH_FAILURE |                    # Failure
    AUTH_ATTEMPT >> RATE_LIMIT_EXCEEDED              # Rate limited
)
```

### 3. **Conditional Logic Support**
OR groups within pipelines handle conditional flows:
```python
# "Attempt, then either success or failure, then appropriate action"
AUTH_ATTEMPT >> (AUTH_SUCCESS | AUTH_FAILURE) >> SESSION_ACTION
```

### 4. **Order Enforcement**
Catches implementation bugs where events occur in wrong order:
```python
# This would fail if SESSION_CREATE happens before AUTH_SUCCESS
AUTH_ATTEMPT >> AUTH_SUCCESS >> SESSION_CREATE
```

### 5. **Documentation Value**
Pipeline decorators serve as executable documentation:
```python
@AuditRequired(
    # Success flow: attempt -> verify -> success -> create session
    AUTH_ATTEMPT >> CREDENTIAL_VERIFY >> AUTH_SUCCESS >> SESSION_CREATE |
    # Failure flow: attempt -> verify -> failure
    AUTH_ATTEMPT >> CREDENTIAL_VERIFY >> AUTH_FAILURE |
    # Rate limit flow: attempt -> rate limit
    AUTH_ATTEMPT >> RATE_LIMIT_EXCEEDED
)
async def authenticate(self, credentials, audit_emitter):
    """The decorator tells the complete story of authentication flows."""
```

## Usage Examples

### 1. Authentication Provider

```python
class DatabaseAuthProvider(AuthProvider, AuditEnforced):
    
    @AuditRequired(
        AuditEventType.AUTH_ATTEMPT >> AuditEventType.AUTH_SUCCESS >> AuditEventType.SESSION_CREATE |
        AuditEventType.AUTH_ATTEMPT >> AuditEventType.AUTH_FAILURE |
        AuditEventType.AUTH_ATTEMPT >> AuditEventType.RATE_LIMIT_EXCEEDED
    )
    async def authenticate(
        self, 
        credentials: Credentials,
        audit_emitter: AuditEmitter  # Injected by decorator
    ) -> Optional[User]:
        audit_emitter.emit(AuditEventType.AUTH_ATTEMPT, {
            "credential_type": type(credentials).__name__,
            "username": credentials.identifier,
            "ip_address": self._get_client_ip(),
            "user_agent": self._get_user_agent()
        })
        
        # Check rate limiting first
        if await self._is_rate_limited(credentials.identifier):
            audit_emitter.emit(AuditEventType.RATE_LIMIT_EXCEEDED, {
                "username": credentials.identifier,
                "rate_limit_type": "login_attempts"
            })
            raise RateLimitExceededError("Too many authentication attempts")
        
        try:
            user = await self._verify_credentials(credentials)
            if user:
                audit_emitter.emit(AuditEventType.AUTH_SUCCESS, {
                    "user_id": user.id,
                    "username": user.username,
                    "authentication_method": "password"
                })
                
                # Create session
                session = await self._create_session(user)
                audit_emitter.emit(AuditEventType.SESSION_CREATE, {
                    "session_id": session.id,
                    "user_id": user.id,
                    "session_duration": session.duration,
                    "session_type": "standard"
                })
                
                return user
            else:
                audit_emitter.emit(AuditEventType.AUTH_FAILURE, {
                    "username": credentials.identifier,
                    "reason": "invalid_credentials",
                    "failure_type": "credential_mismatch"
                })
                return None
        except Exception as e:
            audit_emitter.emit(AuditEventType.AUTH_FAILURE, {
                "username": credentials.identifier,
                "reason": "system_error", 
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise
    
    @AuditRequired(AuditEventType.SESSION_DESTROY)
    async def logout(self, session_id: str, audit_emitter: AuditEmitter):
        """Simple pipeline - just session destruction."""
        await self._destroy_session(session_id)
        audit_emitter.emit(AuditEventType.SESSION_DESTROY, {
            "session_id": session_id,
            "logout_reason": "user_initiated"
        })
```

### 2. Token Verification

```python
class TokenCredentialProvider(CredentialProvider, AuditEnforced):
    
    @AuditRequired(
        AuditEventType.CREDENTIAL_VERIFY >> (AuditEventType.AUTH_SUCCESS | AuditEventType.AUTH_FAILURE)
    )
    async def verify_token(self, token: str, audit_emitter: AuditEmitter) -> bool:
        audit_emitter.emit(AuditEventType.CREDENTIAL_VERIFY, {
            "credential_type": "jwt_token",
            "token_length": len(token),
            "verification_method": "jwt"
        })
        
        try:
            is_valid = await self._validate_jwt_token(token)
            
            if is_valid:
                audit_emitter.emit(AuditEventType.AUTH_SUCCESS, {
                    "credential_type": "jwt_token",
                    "verification_result": "valid"
                })
                return True
            else:
                audit_emitter.emit(AuditEventType.AUTH_FAILURE, {
                    "credential_type": "jwt_token",
                    "verification_result": "invalid",
                    "failure_reason": "token_invalid"
                })
                return False
                
        except Exception as e:
            audit_emitter.emit(AuditEventType.AUTH_FAILURE, {
                "credential_type": "jwt_token",
                "verification_result": "error",
                "error": str(e)
            })
            raise
```

### 3. Complex Authorization

```python
class PolicyEngine(AuditEnforced):
    
    @AuditRequired(
        AuditEventType.PERMISSION_CHECK >> AuditEventType.ACCESS_GRANTED |
        AuditEventType.PERMISSION_CHECK >> AuditEventType.ACCESS_DENIED |
        AuditEventType.PERMISSION_CHECK >> AuditEventType.SECURITY_VIOLATION
    )
    async def check_permission(
        self, 
        user: User, 
        resource: str, 
        action: str,
        audit_emitter: AuditEmitter
    ) -> bool:
        audit_emitter.emit(AuditEventType.PERMISSION_CHECK, {
            "user_id": user.id,
            "resource": resource,
            "action": action,
            "user_roles": [role.name for role in user.roles]
        })
        
        # Check for suspicious patterns
        if await self._is_suspicious_access(user, resource, action):
            audit_emitter.emit(AuditEventType.SECURITY_VIOLATION, {
                "user_id": user.id,
                "resource": resource,
                "action": action,
                "violation_type": "suspicious_pattern",
                "risk_score": 8
            })
            return False
        
        # Normal permission check
        has_permission = await self._evaluate_permissions(user, resource, action)
        
        if has_permission:
            audit_emitter.emit(AuditEventType.ACCESS_GRANTED, {
                "user_id": user.id,
                "resource": resource,
                "action": action,
                "granted_via": "role_permission"
            })
            return True
        else:
            audit_emitter.emit(AuditEventType.ACCESS_DENIED, {
                "user_id": user.id,
                "resource": resource,
                "action": action,
                "denial_reason": "insufficient_permissions"
            })
            return False
```

## Testing Pipeline Compliance

```python
# tests/auth/test_audit_pipelines.py
class TestAuditPipelines:
    
    async def test_authentication_success_pipeline(self, auth_provider):
        """Test that successful auth follows the correct pipeline."""
        credentials = {"username": "valid_user", "password": "correct_password"}
        
        # This should work and satisfy the pipeline
        user = await auth_provider.authenticate(credentials)
        assert user is not None
        
        # Verify the audit events were emitted in correct order
        # (Test implementation would capture and verify events)
    
    async def test_authentication_failure_pipeline(self, auth_provider):
        """Test that failed auth follows the correct pipeline."""
        credentials = {"username": "invalid_user", "password": "wrong_password"}
        
        # This should fail but still satisfy a valid pipeline
        user = await auth_provider.authenticate(credentials)
        assert user is None
        
        # Verify AUTH_ATTEMPT >> AUTH_FAILURE pipeline was followed
    
    async def test_pipeline_violation_detection(self, auth_provider):
        """Test that pipeline violations are detected."""
        # Mock an implementation that violates the pipeline
        # (e.g., emits SESSION_CREATE before AUTH_SUCCESS)
        
        with pytest.raises(AuditComplianceError) as exc_info:
            # Call a deliberately broken implementation
            await broken_auth_provider.authenticate(credentials)
        
        assert "did not satisfy audit pipeline requirement" in str(exc_info.value)
    
    async def test_complex_pipeline_validation(self, policy_engine):
        """Test complex multi-path pipeline validation."""
        user = create_test_user()
        
        # Test all valid paths through the permission check pipeline
        # Normal access granted
        result = await policy_engine.check_permission(user, "resource", "read")
        # Should satisfy PERMISSION_CHECK >> ACCESS_GRANTED
        
        # Access denied  
        result = await policy_engine.check_permission(user, "secret_resource", "read")
        # Should satisfy PERMISSION_CHECK >> ACCESS_DENIED
        
        # Security violation
        # (Test would set up suspicious access pattern)
        result = await policy_engine.check_permission(suspicious_user, "resource", "read")
        # Should satisfy PERMISSION_CHECK >> SECURITY_VIOLATION
```

This pipeline-based audit system transforms audit compliance from a simple "did events happen" check into a sophisticated "did the business logic flow correctly" validation system. It catches implementation bugs, ensures proper state transitions, and provides excellent documentation of expected system behavior.