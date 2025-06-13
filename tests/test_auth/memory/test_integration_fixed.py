"""Integration tests for memory authentication providers using abstract interfaces only."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

import pytest

from serv.auth.audit.enforcement import AuditJournal
from serv.auth.types import AuditEvent, AuditEventType, Credentials, CredentialType
from serv.bundled.auth.memory.audit import MemoryAuditProvider
from serv.bundled.auth.memory.credential import MemoryCredentialProvider
from serv.bundled.auth.memory.session import MemorySessionProvider
from serv.bundled.auth.memory.user import MemoryUserProvider
from bevy import Container, get_registry


@pytest.fixture
def container():
    """Create a test container."""
    return Container(get_registry())


@pytest.fixture
def audit_journal():
    """Create a mock audit journal."""
    mock = MagicMock(spec=AuditJournal)
    mock.record_event = AsyncMock()
    return mock


@pytest.fixture
def base_config():
    """Create base configuration."""
    return {
        "cleanup_interval": 0.1,
        "retention_days": 90,
        "max_events": 100000,
        "default_permissions": [
            {
                "permission": "user:read",
                "description": "Read user data",
                "resource": "user",
                "action": "read"
            }
        ],
        "default_role_configs": [
            {
                "name": "user",
                "description": "Basic user role",
                "permissions": ["user:read"]
            }
        ]
    }


@pytest.fixture
def credential_provider(base_config, container):
    """Create credential provider."""
    config = {
        **base_config,
        "max_login_attempts": 3,
        "account_lockout_duration": 300.0,
        "password_min_length": 8,
        "require_password_complexity": True,
        "token_length": 32,
        "token_ttl": 3600,
        "argon2_time_cost": 1,
        "argon2_memory_cost": 1024,
        "argon2_parallelism": 1,
    }
    return MemoryCredentialProvider(config, container)


@pytest.fixture
def session_provider(base_config, container):
    """Create session provider."""
    config = {
        **base_config,
        "default_session_ttl": 3600,
        "max_session_ttl": 86400,
        "session_id_length": 32,
        "max_concurrent_sessions": 5,
        "require_ip_validation": False,
        "require_user_agent_validation": False,
        "session_refresh_threshold": 300,
    }
    return MemorySessionProvider(config, container)


@pytest.fixture
def user_provider(base_config, container):
    """Create user provider."""
    config = {
        **base_config,
        "allow_duplicate_emails": False,
        "auto_create_roles": True,
        "default_permissions": [
            {
                "permission": "user:read",
                "description": "Read user data",
                "resource": "user",
                "action": "read"
            }
        ],
        "default_role_configs": [
            {
                "name": "user",
                "description": "Basic user role",
                "permissions": ["user:read"]
            }
        ]
    }
    return MemoryUserProvider(config, container)


@pytest.fixture
def audit_provider(base_config, container):
    """Create audit provider."""
    config = {
        **base_config,
        "retention_days": 90,
        "max_events": 10000,
        "auto_cleanup": True,
        "index_by_user": True,
        "index_by_session": True,
        "index_by_resource": True,
    }
    return MemoryAuditProvider(config, container)


@pytest.fixture
def auth_system(credential_provider, session_provider, user_provider, audit_provider):
    """Create complete authentication system."""
    return {
        "credential": credential_provider,
        "session": session_provider,
        "user": user_provider,
        "audit": audit_provider,
    }


class TestMemoryProviderIntegration:
    """Test integration between memory providers using abstract interfaces."""

    @pytest.mark.asyncio
    async def test_complete_user_registration_flow(self, auth_system, audit_journal):
        """Test complete user registration and login flow."""
        user_provider = auth_system["user"]
        credential_provider = auth_system["credential"]
        session_provider = auth_system["session"]
        audit_provider = auth_system["audit"]
        
        # 1. Create user via abstract interface
        user = await user_provider.create_user(
            username="testuser",
            email="test@example.com",
            metadata={"display_name": "Test User"},
            audit_journal=audit_journal
        )
        
        # Record user creation in audit via abstract interface
        user_creation_event = AuditEvent(
            id="user_create_event",
            timestamp=datetime.now(),
            event_type=AuditEventType.USER_CREATED,
            user_id=user.id,
            session_id=None,
            resource="user",
            action="create",
            result="success",
            metadata={"email": user.email},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        await audit_provider.store_audit_event(user_creation_event)
        
        # 2. Create password credentials via abstract interface
        password = "SecurePassword123!"
        password_credentials = Credentials(
            id="password_cred_1",
            user_id=user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        await credential_provider.create_credentials(user.id, password_credentials, audit_journal)
        
        # Record credential creation in audit
        cred_creation_event = AuditEvent(
            id="cred_create_event",
            timestamp=datetime.now(),
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id=user.id,
            session_id=None,
            resource="credentials",
            action="create",
            result="success",
            metadata={"type": "password"},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        await audit_provider.store_audit_event(cred_creation_event)
        
        # 3. Verify credentials work
        verify_credentials = Credentials(
            id="verify_cred_1",
            user_id=user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        is_valid = await credential_provider.verify_credentials(verify_credentials, audit_journal)
        assert is_valid is True
        
        # 4. Create session via abstract interface
        session = await session_provider.create_session(
            user_id=user.id,
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0",
            audit_journal=audit_journal
        )
        
        # Record session creation in audit
        session_creation_event = AuditEvent(
            id="session_create_event",
            timestamp=datetime.now(),
            event_type=AuditEventType.SESSION_CREATED,
            user_id=user.id,
            session_id=session.id,
            resource="session",
            action="create",
            result="success",
            metadata={"ip_address": "192.168.1.1"},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        await audit_provider.store_audit_event(session_creation_event)
        
        # 5. Verify complete integration - retrieve all audit events for user
        user_events = await audit_provider.get_user_audit_events(
            user_id=user.id,
            limit=10,
            offset=0
        )
        
        # Should have 3 events: user creation, credential creation, session creation
        assert len(user_events) == 3
        event_types = {event.event_type for event in user_events}
        assert AuditEventType.USER_CREATED in event_types
        assert AuditEventType.LOGIN_SUCCESS in event_types
        assert AuditEventType.SESSION_CREATED in event_types

    @pytest.mark.asyncio
    async def test_authentication_flow_with_role_assignment(self, auth_system, audit_journal):
        """Test authentication flow with role and permission management."""
        user_provider = auth_system["user"]
        credential_provider = auth_system["credential"]
        session_provider = auth_system["session"]
        
        # 1. Create user
        user = await user_provider.create_user(
            username="roleuser",
            email="role@example.com",
            audit_journal=audit_journal
        )
        
        # 2. Assign role to user
        await user_provider.assign_role(user.id, "user")
        
        # 3. Verify user has correct permissions
        permissions = await user_provider.get_user_permissions(user.id)
        permission_names = {p.name for p in permissions}
        assert "user:read" in permission_names
        
        # 4. Verify user has correct roles
        roles = await user_provider.get_user_roles(user.id)
        role_names = {r.name for r in roles}
        assert "user" in role_names
        
        # 5. Create credentials and session for authenticated user
        password = "TestPassword123!"
        password_credentials = Credentials(
            id="role_password_cred",
            user_id=user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        await credential_provider.create_credentials(user.id, password_credentials, audit_journal)
        
        session = await session_provider.create_session(
            user_id=user.id,
            audit_journal=audit_journal
        )
        
        # 6. Verify session belongs to user with correct roles
        retrieved_session = await session_provider.get_session(session.id)
        assert retrieved_session.user_id == user.id
        
        # Verify user still has roles
        user_roles = await user_provider.get_user_roles(user.id)
        assert len(user_roles) == 1
        assert "user" in {r.name for r in user_roles}

    @pytest.mark.asyncio
    async def test_session_lifecycle_with_audit_trail(self, auth_system, audit_journal):
        """Test complete session lifecycle with audit trail."""
        user_provider = auth_system["user"]
        session_provider = auth_system["session"]
        audit_provider = auth_system["audit"]
        
        # 1. Create user
        user = await user_provider.create_user(
            username="sessionuser",
            email="session@example.com",
            audit_journal=audit_journal
        )
        
        # 2. Create session
        session = await session_provider.create_session(
            user_id=user.id,
            ip_address="192.168.1.100",
            user_agent="Integration Test Browser",
            audit_journal=audit_journal
        )
        
        # Store session creation audit event
        session_create_event = AuditEvent(
            id="session_lifecycle_create",
            timestamp=datetime.now(),
            event_type=AuditEventType.SESSION_CREATED,
            user_id=user.id,
            session_id=session.id,
            resource="session",
            action="create",
            result="success",
            metadata={"ip": "192.168.1.100"},
            ip_address="192.168.1.100",
            user_agent="Integration Test Browser"
        )
        await audit_provider.store_audit_event(session_create_event)
        
        # 3. Refresh session
        refreshed_session = await session_provider.refresh_session(session.id, audit_journal)
        assert refreshed_session is not None
        assert refreshed_session.id == session.id
        
        # Store session refresh audit event
        session_refresh_event = AuditEvent(
            id="session_lifecycle_refresh",
            timestamp=datetime.now(),
            event_type=AuditEventType.SESSION_CREATED,  # Reusing since no specific refresh type
            user_id=user.id,
            session_id=session.id,
            resource="session",
            action="refresh",
            result="success",
            metadata={"refreshed": True},
            ip_address="192.168.1.100",
            user_agent="Integration Test Browser"
        )
        await audit_provider.store_audit_event(session_refresh_event)
        
        # 4. Verify session exists and get active sessions
        active_sessions = await session_provider.get_active_sessions(user.id)
        assert len(active_sessions) == 1
        assert active_sessions[0].id == session.id
        
        # 5. Destroy session
        await session_provider.destroy_session(session.id, audit_journal)
        
        # Store session destruction audit event
        session_destroy_event = AuditEvent(
            id="session_lifecycle_destroy",
            timestamp=datetime.now(),
            event_type=AuditEventType.SESSION_DESTROYED,
            user_id=user.id,
            session_id=session.id,
            resource="session",
            action="destroy",
            result="success",
            metadata={"destroyed": True},
            ip_address="192.168.1.100",
            user_agent="Integration Test Browser"
        )
        await audit_provider.store_audit_event(session_destroy_event)
        
        # 6. Verify session no longer exists
        destroyed_session = await session_provider.get_session(session.id)
        assert destroyed_session is None
        
        # 7. Verify complete audit trail
        session_events = await audit_provider.search_audit_events(
            session_id=session.id,
            limit=10,
            offset=0
        )
        assert len(session_events) == 3  # create, refresh, destroy

    @pytest.mark.asyncio
    async def test_user_lifecycle_integration(self, auth_system, audit_journal):
        """Test complete user lifecycle with all providers."""
        user_provider = auth_system["user"]
        credential_provider = auth_system["credential"]
        session_provider = auth_system["session"]
        audit_provider = auth_system["audit"]
        
        # 1. Create user
        user = await user_provider.create_user(
            username="lifecycleuser",
            email="lifecycle@example.com",
            metadata={"department": "engineering"},
            audit_journal=audit_journal
        )
        
        # 2. Create multiple types of credentials
        password_creds = Credentials(
            id="lifecycle_password",
            user_id=user.id,
            type=CredentialType.PASSWORD,
            data={"password": "LifecyclePass123!"},
            metadata={}
        )
        await credential_provider.create_credentials(user.id, password_creds, audit_journal)
        
        token_creds = Credentials(
            id="lifecycle_token",
            user_id=user.id,
            type=CredentialType.TOKEN,
            data={"purpose": "api_access"},
            metadata={}
        )
        await credential_provider.create_credentials(user.id, token_creds, audit_journal)
        
        # 3. Verify credential types available
        credential_types = await credential_provider.get_credential_types(user.id)
        assert CredentialType.PASSWORD in credential_types
        assert CredentialType.TOKEN in credential_types
        
        # 4. Create multiple sessions
        session1 = await session_provider.create_session(
            user_id=user.id,
            ip_address="192.168.1.10",
            audit_journal=audit_journal
        )
        session2 = await session_provider.create_session(
            user_id=user.id,
            ip_address="192.168.1.20",
            audit_journal=audit_journal
        )
        
        # 5. Verify multiple active sessions
        active_sessions = await session_provider.get_active_sessions(user.id)
        assert len(active_sessions) == 2
        
        # 6. Update user information
        updates = {
            "email": "updated_lifecycle@example.com",
            "metadata": {"department": "devops", "updated": True}
        }
        updated_user = await user_provider.update_user(user.id, updates, audit_journal)
        assert updated_user.email == "updated_lifecycle@example.com"
        assert updated_user.metadata["department"] == "devops"
        
        # 7. Clean up - destroy all user sessions
        destroyed_count = await session_provider.destroy_user_sessions(user.id)
        assert destroyed_count == 2
        
        # 8. Delete all credentials
        await credential_provider.delete_credentials(user.id, CredentialType.PASSWORD, audit_journal)
        await credential_provider.delete_credentials(user.id, CredentialType.TOKEN, audit_journal)
        
        # 9. Verify credentials are gone
        remaining_types = await credential_provider.get_credential_types(user.id)
        assert len(remaining_types) == 0
        
        # 10. Delete user
        await user_provider.delete_user(user.id, audit_journal)
        
        # 11. Verify user is gone
        deleted_user = await user_provider.get_user_by_id(user.id)
        assert deleted_user is None

    @pytest.mark.asyncio
    async def test_concurrent_operations_integration(self, auth_system, audit_journal):
        """Test concurrent operations across all providers."""
        user_provider = auth_system["user"]
        credential_provider = auth_system["credential"]
        session_provider = auth_system["session"]
        audit_provider = auth_system["audit"]
        
        async def create_user_with_session(user_idx):
            try:
                # Create user
                user = await user_provider.create_user(
                    username=f"concurrent_user_{user_idx}",
                    email=f"concurrent_{user_idx}@example.com",
                    audit_journal=audit_journal
                )
                
                # Create credentials
                password_creds = Credentials(
                    id=f"concurrent_password_{user_idx}",
                    user_id=user.id,
                    type=CredentialType.PASSWORD,
                    data={"password": f"ConcurrentPass{user_idx}!"},
                    metadata={}
                )
                await credential_provider.create_credentials(user.id, password_creds, audit_journal)
                
                # Create session
                session = await session_provider.create_session(
                    user_id=user.id,
                    audit_journal=audit_journal
                )
                
                # Store audit event
                audit_event = AuditEvent(
                    id=f"concurrent_audit_{user_idx}",
                    timestamp=datetime.now(),
                    event_type=AuditEventType.LOGIN_SUCCESS,
                    user_id=user.id,
                    session_id=session.id,
                    resource="integration_test",
                    action="concurrent_create",
                    result="success",
                    metadata={"user_idx": user_idx},
                    ip_address="192.168.1.1",
                    user_agent="Concurrent Test"
                )
                await audit_provider.store_audit_event(audit_event)
                
                return {
                    "user_id": user.id,
                    "session_id": session.id,
                    "success": True
                }
            except Exception as e:
                return {
                    "error": str(e),
                    "success": False
                }
        
        # Run concurrent operations
        tasks = [create_user_with_session(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Verify all operations succeeded
        successful_results = [r for r in results if r["success"]]
        assert len(successful_results) == 5
        
        # Verify all audit events were stored
        all_events = await audit_provider.get_audit_events(limit=20, offset=0)
        concurrent_events = [e for e in all_events if e.resource == "integration_test"]
        assert len(concurrent_events) == 5
        
        # Clean up - verify we can list and access all created users
        for result in successful_results:
            user = await user_provider.get_user_by_id(result["user_id"])
            assert user is not None
            assert user.username.startswith("concurrent_user_")
            
            # Clean up sessions
            await session_provider.destroy_session(result["session_id"], audit_journal)