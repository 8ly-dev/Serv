# Authentication System Interface Contracts

This document defines the interface contracts and polymorphism requirements for the authentication system providers.

## Overview

The authentication system is built on abstract base classes that define strict interfaces. All concrete implementations must adhere to these interfaces to ensure polymorphic behavior and maintain architectural integrity.

## Core Principles

### 1. Interface Compliance
- All providers MUST implement every abstract method defined in their base class
- Method signatures MUST match the abstract interface exactly
- Return types MUST match the interface specification
- Exception handling MUST follow the patterns defined in the interface

### 2. Polymorphic Behavior
- Code SHOULD depend on abstract interfaces, not concrete implementations
- All providers of the same type SHOULD be interchangeable
- Implementation-specific methods SHOULD NOT be required for core functionality

### 3. Extension Guidelines
- Providers MAY implement additional public methods beyond the interface
- Extension methods SHOULD NOT break polymorphic usage
- Extension methods SHOULD be clearly documented as implementation-specific

## Provider Interfaces

### CredentialProvider

**Abstract Methods:**
- `verify_credentials(credentials: Credentials, audit_journal: AuditJournal) -> bool`
- `create_credentials(user_id: str, credentials: Credentials, audit_journal: AuditJournal) -> None`
- `update_credentials(user_id: str, old_credentials: Credentials, new_credentials: Credentials, audit_journal: AuditJournal) -> None`
- `delete_credentials(user_id: str, credential_type: CredentialType, audit_journal: AuditJournal) -> None`
- `get_credential_types(user_id: str) -> set[CredentialType]`
- `is_credential_compromised(credentials: Credentials) -> bool`

**Key Contracts:**
- All methods must handle audit logging properly
- Credentials objects use `type` field (not `credential_type`)
- Credentials objects use `data` field (not `credential_data`)
- Audit journal recording is required for create/update/delete operations
- Exceptions should follow the pattern: AuthenticationError for user errors, ProviderError for system errors

**Extension Methods (MemoryCredentialProvider):**
- `create_password_credentials()` - Password-specific creation
- `create_token_credentials()` - Token-specific creation
- `verify_password()` - Direct password verification
- `verify_token()` - Direct token verification
- `update_password()` - Password-specific updates
- `revoke_credentials()` - Credential revocation
- `get_credential_metadata()` - Metadata access
- `get_statistics()` - Provider statistics

### SessionProvider

**Abstract Methods:**
- `create_session(user_id: str, ip_address: str | None, user_agent: str | None, duration: timedelta | None, audit_journal: AuditJournal) -> Session`
- `get_session(session_id: str) -> Session | None`
- `refresh_session(session_id: str, audit_journal: AuditJournal) -> Session | None`
- `destroy_session(session_id: str, audit_journal: AuditJournal) -> None`
- `destroy_user_sessions(user_id: str) -> int`
- `cleanup_expired_sessions() -> int`
- `get_active_sessions(user_id: str) -> list[Session]`

**Key Contracts:**
- Session objects use datetime objects for timestamps (not unix timestamps)
- Duration parameter is a timedelta object
- Session objects use `id` field (not `session_id`)
- Audit journal recording is required for create/refresh/destroy operations
- Return types must match exactly (None vs bool for destroy_session)

**Extension Methods (MemorySessionProvider):**
- `validate_session()` - Session validation with security checks
- `get_session_count()` - Count of active sessions
- `get_statistics()` - Provider statistics

### UserProvider

**Abstract Methods:**
- `get_user_by_id(user_id: str) -> User | None`
- `get_user_by_username(username: str) -> User | None`
- `get_user_by_email(email: str) -> User | None`
- `create_user(username: str, email: str | None, metadata: dict[str, Any] | None, audit_journal: AuditJournal) -> User`
- `update_user(user_id: str, updates: dict[str, Any], audit_journal: AuditJournal) -> User`
- `delete_user(user_id: str, audit_journal: AuditJournal) -> None`
- `list_users(limit: int, offset: int, filters: dict[str, Any] | None) -> list[User]`
- `get_user_permissions(user_id: str) -> set[Permission]`
- `get_user_roles(user_id: str) -> set[Role]`
- `assign_role(user_id: str, role_name: str) -> None`
- `remove_role(user_id: str, role_name: str) -> None`

**Key Contracts:**
- Update operations use a dictionary of changes, not individual parameters
- Permission and Role objects must be hashable (implement `__hash__`)
- Return types: User objects for successful operations, exceptions for failures
- Audit journal recording is required for create/update/delete operations

**Extension Methods (MemoryUserProvider):**
- `has_permission()` - Permission checking
- `has_role()` - Role checking
- `create_role()` - Role management
- `update_role()` - Role management
- `delete_role()` - Role management
- `create_permission()` - Permission management
- `get_permission()` - Permission retrieval
- `list_roles()` - Role listing
- `list_permissions()` - Permission listing
- `get_statistics()` - Provider statistics

### AuditProvider

**Abstract Methods:**
- `store_audit_event(event: AuditEvent) -> None`
- `get_audit_events(start_time: datetime | None, end_time: datetime | None, limit: int, offset: int) -> list[AuditEvent]`
- `get_user_audit_events(user_id: str, start_time: datetime | None, end_time: datetime | None, limit: int, offset: int) -> list[AuditEvent]`
- `search_audit_events(event_types: list[AuditEventType] | None, user_id: str | None, session_id: str | None, resource: str | None, filters: dict[str, Any] | None, start_time: datetime | None, end_time: datetime | None, limit: int, offset: int) -> list[AuditEvent]`
- `cleanup_old_events(older_than: datetime) -> int`

**Key Contracts:**
- All datetime parameters use datetime objects (not timestamps)
- AuditEvent objects must be stored with all fields intact
- Search methods support complex filtering
- Cleanup methods return count of items removed

**Extension Methods (MemoryAuditProvider):**
- `record_event()` - Convenient event recording
- `get_event()` - Single event retrieval
- `query_events()` - Flexible event querying
- `get_user_events()` - User-specific queries
- `get_session_events()` - Session-specific queries
- `get_events_by_category()` - Categorized retrieval
- `get_failed_events()` - Security-focused filtering
- `get_security_events()` - Security event retrieval
- `export_events()` - Event export functionality
- `get_statistics()` - Provider statistics

## Data Type Contracts

### Core Types

**Credentials:**
- `id: str` - Unique credential identifier
- `user_id: str` - Associated user ID
- `type: CredentialType` - Type of credential (PASSWORD, TOKEN, API_KEY)
- `data: dict[str, Any]` - Credential-specific data
- `created_at: datetime` - Creation timestamp
- `expires_at: datetime | None` - Optional expiration
- `is_active: bool` - Active status
- `metadata: dict[str, Any]` - Additional metadata

**Session:**
- `id: str` - Unique session identifier
- `user_id: str` - Associated user ID
- `created_at: datetime` - Creation timestamp
- `expires_at: datetime | None` - Optional expiration
- `is_active: bool` - Active status
- `metadata: dict[str, Any]` - Session metadata
- `last_accessed: datetime | None` - Last access time

**User:**
- `id: str` - Unique user identifier
- `username: str` - Username
- `email: str | None` - Email address
- `is_active: bool` - Active status
- `roles: list[str]` - Assigned role names
- `metadata: dict[str, Any]` - User metadata
- `created_at: datetime` - Creation timestamp

**Role:**
- `name: str` - Role name (must be hashable)
- `description: str | None` - Optional description
- `permissions: list[Permission]` - Associated permissions
- `is_active: bool` - Active status
- `created_at: datetime` - Creation timestamp

**Permission:**
- `name: str` - Permission name (must be hashable)
- `description: str | None` - Optional description
- `resource: str | None` - Resource this permission applies to
- `action: str | None` - Action this permission allows

## Testing Requirements

### Interface Compliance Tests
- All concrete providers MUST pass interface compliance tests
- Tests MUST use only abstract interface methods
- Tests MUST NOT depend on implementation-specific methods
- Tests MUST validate polymorphic behavior

### Extension Method Tests
- Extension methods MAY have their own specific tests
- Extension tests SHOULD be clearly separated from interface tests
- Extension tests SHOULD document provider-specific behavior

## Best Practices

### For Implementation Authors
1. **Always implement abstract methods first** before adding extensions
2. **Match signatures exactly** - parameter names, types, and return types
3. **Handle audit logging consistently** across all methods
4. **Use proper exception types** as defined in the interface contracts
5. **Make extension methods clearly identifiable** with documentation

### For Consumer Code Authors
1. **Depend on abstract interfaces** not concrete implementations
2. **Use dependency injection** to receive provider instances
3. **Avoid calling implementation-specific methods** in shared code
4. **Handle all defined exception types** appropriately
5. **Use extension methods only** when you know the specific provider type

### For Test Authors
1. **Test polymorphic behavior** by testing against abstract interfaces
2. **Validate exception handling** matches interface contracts
3. **Test data type contracts** ensure proper field usage
4. **Separate interface tests** from implementation-specific tests

## Enforcement

### Abstract Base Class (ABC) System
- Python's ABC system prevents instantiation of incomplete implementations
- Missing abstract methods will cause `TypeError` at instantiation time
- All providers MUST be testable through their abstract interfaces

### Continuous Integration
- Interface compliance tests are run on all provider implementations
- Signature mismatches will cause test failures
- Data type contract violations will cause test failures

### Code Review Guidelines
- New providers MUST implement all abstract methods
- Interface changes MUST be backward compatible or properly versioned
- Extension methods MUST be documented as implementation-specific
- Tests MUST validate interface compliance

## Migration Guidelines

When updating existing providers to comply with interface contracts:

1. **Identify signature mismatches** between implementation and interface
2. **Update field names** to match data type contracts (e.g., `credential_type` → `type`)
3. **Add missing abstract methods** with proper implementations
4. **Fix return types** to match interface specifications
5. **Update exception handling** to follow interface patterns
6. **Add proper audit logging** where required
7. **Test polymorphic behavior** through abstract interfaces

## Conclusion

Strict adherence to these interface contracts ensures:
- **Reliable polymorphic behavior** across all provider implementations
- **Consistent API experience** regardless of provider choice
- **Easier testing and debugging** through predictable interfaces
- **Better maintainability** through clear separation of concerns
- **Reduced coupling** between consumer code and implementation details

Following these guidelines will maintain the architectural integrity of the authentication system and enable seamless provider swapping for different deployment scenarios.