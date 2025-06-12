# Provider Interfaces Design

## Overview

This document defines the abstract base classes and interfaces for all authentication system providers. These interfaces ensure consistency, testability, and extensibility across different implementations.

**Initial Scope**: Password and token-based authentication only. External providers (OAuth, LDAP, SAML) will be added in future versions.

## Core Types

```python
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

# User and Identity Types
@dataclass
class User:
    id: str
    username: str
    email: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "metadata": self.metadata or {}
        }

# Credential Types (Initial Scope)
class CredentialType(Enum):
    PASSWORD = "password"
    TOKEN = "token"
    # Future credential types:
    # API_KEY = "api_key"
    # CERTIFICATE = "certificate" 
    # BIOMETRIC = "biometric"
    # MULTI_FACTOR = "mfa"

@dataclass
class Credentials:
    type: CredentialType
    identifier: str  # username, email, token, etc.
    secret: str  # password, token value, etc.
    metadata: Dict[str, Any] = None

# Session Types
@dataclass
class Session:
    id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    last_accessed: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]
    metadata: Dict[str, Any] = None
    
    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
    
    @property
    def time_remaining(self) -> timedelta:
        return self.expires_at - datetime.utcnow()

# Permission and Policy Types
@dataclass
class Permission:
    resource: str  # e.g., "users", "posts", "admin"
    action: str    # e.g., "read", "write", "delete", "admin"
    conditions: Dict[str, Any] = None  # Additional constraints
    
    def __str__(self) -> str:
        return f"{self.action}:{self.resource}"

@dataclass
class Role:
    name: str
    permissions: Set[Permission]
    metadata: Dict[str, Any] = None

class PolicyResult(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ABSTAIN = "abstain"  # No opinion, defer to other policies

@dataclass
class PolicyEvaluation:
    result: PolicyResult
    reason: str
    metadata: Dict[str, Any] = None
```

## 1. Credential Provider Interface

```python
class CredentialProvider(ABC, AuditEnforced):
    """Abstract base class for credential management."""
    
    @abstractmethod
    @AuditRequired(AuditEventType.CREDENTIAL_VERIFY)
    async def verify_credentials(
        self, 
        credentials: Credentials,
        audit_emitter: AuditEmitter
    ) -> bool:
        """Verify if credentials are valid."""
        pass
    
    @abstractmethod
    @AuditRequired(AuditEventType.CREDENTIAL_CREATE)
    async def create_credentials(
        self, 
        user_id: str, 
        credentials: Credentials,
        audit_emitter: AuditEmitter
    ) -> None:
        """Create new credentials for a user."""
        pass
    
    @abstractmethod
    @AuditRequired(AuditEventType.CREDENTIAL_UPDATE)
    async def update_credentials(
        self, 
        user_id: str, 
        old_credentials: Credentials,
        new_credentials: Credentials,
        audit_emitter: AuditEmitter
    ) -> None:
        """Update existing credentials."""
        pass
    
    @abstractmethod
    @AuditRequired(AuditEventType.CREDENTIAL_DELETE)
    async def delete_credentials(
        self, 
        user_id: str, 
        credential_type: CredentialType,
        audit_emitter: AuditEmitter
    ) -> None:
        """Delete credentials for a user."""
        pass
    
    @abstractmethod
    async def get_credential_types(self, user_id: str) -> Set[CredentialType]:
        """Get available credential types for a user."""
        pass
    
    @abstractmethod
    async def is_credential_compromised(self, credentials: Credentials) -> bool:
        """Check if credentials are known to be compromised."""
        pass
```

## 2. Session Provider Interface

```python
class SessionProvider(ABC, AuditEnforced):
    """Abstract base class for session management."""
    
    @abstractmethod
    @AuditRequired(AuditEventType.SESSION_CREATE)
    async def create_session(
        self, 
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        duration: Optional[timedelta] = None,
        audit_emitter: AuditEmitter = None
    ) -> Session:
        """Create a new session."""
        pass
    
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve a session by ID."""
        pass
    
    @abstractmethod
    @AuditRequired(AuditEventType.SESSION_REFRESH)
    async def refresh_session(
        self, 
        session_id: str,
        audit_emitter: AuditEmitter
    ) -> Optional[Session]:
        """Refresh an existing session."""
        pass
    
    @abstractmethod
    @AuditRequired(AuditEventType.SESSION_DESTROY)
    async def destroy_session(
        self, 
        session_id: str,
        audit_emitter: AuditEmitter
    ) -> None:
        """Destroy a session."""
        pass
    
    @abstractmethod
    async def destroy_user_sessions(self, user_id: str) -> int:
        """Destroy all sessions for a user. Returns count destroyed."""
        pass
    
    @abstractmethod
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions. Returns count cleaned."""
        pass
    
    @abstractmethod
    async def get_active_sessions(self, user_id: str) -> List[Session]:
        """Get all active sessions for a user."""
        pass
```

## 3. User Provider Interface

```python
class UserProvider(ABC, AuditEnforced):
    """Abstract base class for user management."""
    
    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        pass
    
    @abstractmethod
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        pass
    
    @abstractmethod
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        pass
    
    @abstractmethod
    @AuditRequired(AuditEventType.USER_CREATE)
    async def create_user(
        self, 
        username: str,
        email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        audit_emitter: AuditEmitter = None
    ) -> User:
        """Create a new user."""
        pass
    
    @abstractmethod
    @AuditRequired(AuditEventType.USER_UPDATE)
    async def update_user(
        self, 
        user_id: str,
        updates: Dict[str, Any],
        audit_emitter: AuditEmitter
    ) -> User:
        """Update user information."""
        pass
    
    @abstractmethod
    @AuditRequired(AuditEventType.USER_DELETE)
    async def delete_user(
        self, 
        user_id: str,
        audit_emitter: AuditEmitter
    ) -> None:
        """Delete a user."""
        pass
    
    @abstractmethod
    async def list_users(
        self, 
        limit: int = 100, 
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[User]:
        """List users with pagination and filtering."""
        pass
    
    @abstractmethod
    async def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """Get all permissions for a user."""
        pass
    
    @abstractmethod
    async def get_user_roles(self, user_id: str) -> Set[Role]:
        """Get all roles for a user."""
        pass
    
    @abstractmethod
    async def assign_role(self, user_id: str, role_name: str) -> None:
        """Assign a role to a user."""
        pass
    
    @abstractmethod
    async def remove_role(self, user_id: str, role_name: str) -> None:
        """Remove a role from a user."""
        pass
```

## 4. Auth Provider Interface

```python
class AuthProvider(ABC, AuditEnforced):
    """Main authentication orchestrator interface."""
    
    def __init__(self, config: Dict[str, Any], container: Container):
        self.config = config
        self.container = container
        # Providers are injected via dependency injection, not constructor params
    
    @abstractmethod
    @AuditRequired(AuditEventType.AUTH_ATTEMPT, AuditEventType.AUTH_SUCCESS, AuditEventType.AUTH_FAILURE)
    async def authenticate(
        self, 
        credentials: Credentials,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        audit_emitter: AuditEmitter = None
    ) -> Optional[Session]:
        """Authenticate user and create session."""
        pass
    
    @abstractmethod
    @AuditRequired(AuditEventType.AUTHZ_CHECK, AuditEventType.AUTHZ_GRANT, AuditEventType.AUTHZ_DENY)
    async def authorize(
        self,
        session_id: str,
        permission: Permission,
        context: Optional[Dict[str, Any]] = None,
        audit_emitter: AuditEmitter = None
    ) -> bool:
        """Check if session has permission for action."""
        pass
    
    @abstractmethod
    @AuditRequired(AuditEventType.AUTH_LOGOUT)
    async def logout(
        self, 
        session_id: str,
        audit_emitter: AuditEmitter
    ) -> None:
        """Logout user and destroy session."""
        pass
    
    @abstractmethod
    async def validate_session(self, session_id: str) -> Optional[Session]:
        """Validate session and return if valid."""
        pass
    
    @abstractmethod
    async def get_current_user(self, session_id: str) -> Optional[User]:
        """Get user for current session."""
        pass
```

## 5. Policy Provider Interface

```python
class PolicyProvider(ABC):
    """Abstract base class for policy evaluation."""
    
    @abstractmethod
    async def evaluate_permission(
        self,
        user: User,
        permission: Permission,
        context: Optional[Dict[str, Any]] = None
    ) -> PolicyEvaluation:
        """Evaluate if user has permission."""
        pass
    
    @abstractmethod
    async def evaluate_route_access(
        self,
        user: User,
        route_path: str,
        method: str,
        context: Optional[Dict[str, Any]] = None
    ) -> PolicyEvaluation:
        """Evaluate if user can access route."""
        pass
    
    @abstractmethod
    async def get_user_permissions(self, user: User) -> Set[Permission]:
        """Get all effective permissions for user."""
        pass
    
    @abstractmethod
    async def register_policy(self, policy_name: str, policy_func: Callable) -> None:
        """Register a custom policy function."""
        pass
```

## Implementation Guidelines

### 1. Error Handling

```python
class AuthenticationError(Exception):
    """Base class for authentication errors."""
    pass

class InvalidCredentialsError(AuthenticationError):
    """Raised when credentials are invalid."""
    pass

class SessionExpiredError(AuthenticationError):
    """Raised when session has expired."""
    pass

class InsufficientPermissionsError(AuthenticationError):
    """Raised when user lacks required permissions."""
    pass

class AuditViolationException(Exception):
    """Raised when audit requirements are violated."""
    pass
```

### 2. Configuration Support

Each provider should support configuration via dependency injection:

```python
from dataclasses import dataclass

@dataclass
class CredentialConfig:
    password_min_length: int = 8
    password_complexity: bool = True
    token_expiry: timedelta = timedelta(hours=24)
    max_login_attempts: int = 5
    lockout_duration: timedelta = timedelta(minutes=30)

@dataclass
class SessionConfig:
    default_duration: timedelta = timedelta(hours=8)
    max_duration: timedelta = timedelta(days=30)
    inactivity_timeout: timedelta = timedelta(hours=2)
    concurrent_sessions: int = 5
```

### 3. Testing Utilities

```python
class MockCredentialProvider(CredentialProvider):
    """Mock implementation for testing."""
    
    def __init__(self, config: Dict[str, Any] = None, container: Container = None):
        self.config = config or {}
        self.container = container
        self.credentials = {}
        self.audit_calls = []
    
    async def verify_credentials(self, credentials: Credentials, audit_emitter: AuditEmitter) -> bool:
        audit_emitter.emit(AuditEventType.CREDENTIAL_VERIFY, identifier=credentials.identifier)
        return credentials.identifier in self.credentials
```

This interface design ensures:
- **Consistency**: All providers follow the same patterns
- **Testability**: Mock implementations can easily be created
- **Audit Compliance**: All security operations are audited
- **Extensibility**: New provider types can be added easily
- **Type Safety**: Strong typing throughout the system