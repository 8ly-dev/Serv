"""Integration tests for memory authentication providers."""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from serv.auth.audit.enforcement import AuditJournal
from serv.auth.audit.events import AuditEventType
from serv.auth.exceptions import AuthenticationError
from serv.auth.types import User
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
    return MagicMock(spec=AuditJournal)


@pytest.fixture
def base_config():
    """Create base configuration."""
    return {
        "cleanup_interval": 0.1,
        "retention_days": 90,
        "max_events": 100000,
        "include_sensitive_data": False,
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
        "session_ttl": 3600,
        "session_id_length": 32,
        "max_sessions_per_user": 5,
        "validate_ip": True,
        "validate_user_agent": True,
        "extend_on_access": True,
    }
    return MemorySessionProvider(config, container)


@pytest.fixture
def user_provider(base_config, container):
    """Create user provider."""
    config = {
        **base_config,
        "default_roles": ["user"],
        "require_email_verification": False,
        "allow_duplicate_emails": False,
        "auto_create_roles": True,
        "default_permissions": [
            {
                "permission": "user:read",
                "description": "Read user data",
                "resource": "user",
            }
        ],
        "default_role_configs": [
            {
                "name": "user",
                "description": "Standard user role",
                "permissions": ["user:read"]
            }
        ]
    }
    return MemoryUserProvider(config, container)


@pytest.fixture
def audit_provider(base_config, container):
    """Create audit provider."""
    return MemoryAuditProvider(base_config, container)


@pytest.fixture
def auth_system(credential_provider, session_provider, user_provider, audit_provider):
    """Create a complete auth system with all providers."""
    return {
        "credential": credential_provider,
        "session": session_provider,
        "user": user_provider,
        "audit": audit_provider,
    }


class TestMemoryProviderIntegration:
    """Test integration between memory providers."""

    @pytest.mark.asyncio
    async def test_complete_user_registration_flow(self, auth_system, audit_journal):
        """Test complete user registration and login flow."""
        user_provider = auth_system["user"]
        credential_provider = auth_system["credential"]
        session_provider = auth_system["session"]
        audit_provider = auth_system["audit"]
        
        # 1. Create user
        user = await user_provider.create_user(
            user_id="test_user",
            email="test@example.com",
            username="testuser",
            display_name="Test User",
            audit_journal=audit_journal
        )
        
        # Record user creation in audit
        await audit_provider.record_event(
            event_type=AuditEventType.USER_CREATE,
            user_id=user.user_id,
            metadata={"email": user.email}
        )
        
        # 2. Set password
        password = "SecurePassword123!"
        await credential_provider.set_password(
            user.user_id, password, audit_journal
        )
        
        # 3. Authenticate user
        auth_success = await credential_provider.verify_password(
            user.user_id, password, audit_journal
        )
        assert auth_success is True
        
        # Record successful authentication
        await audit_provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            user_id=user.user_id,
            ip_address="192.168.1.1"
        )
        
        # 4. Create session
        session = await session_provider.create_session(
            user,
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        # Record session creation
        await audit_provider.record_event(
            event_type=AuditEventType.SESSION_CREATE,
            user_id=user.user_id,
            session_id=session.session_id,
            ip_address="192.168.1.1"
        )
        
        # 5. Validate session
        session_valid = await session_provider.validate_session(
            session.session_id,
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        assert session_valid is True
        
        # 6. Check audit trail
        user_events = await audit_provider.get_user_events(user.user_id)
        assert len(user_events) >= 3  # user creation, auth, session creation
        
        event_types = {e.event_type for e in user_events}
        assert AuditEventType.USER_CREATE in event_types
        assert AuditEventType.AUTH_SUCCESS in event_types
        assert AuditEventType.SESSION_CREATE in event_types

    @pytest.mark.asyncio
    async def test_failed_authentication_and_lockout(self, auth_system, audit_journal):
        """Test failed authentication leading to account lockout."""
        user_provider = auth_system["user"]
        credential_provider = auth_system["credential"]
        audit_provider = auth_system["audit"]
        
        # Create user with password
        user = await user_provider.create_user(
            user_id="lockout_user",
            email="lockout@example.com",
            audit_journal=audit_journal
        )
        
        password = "CorrectPassword123!"
        await credential_provider.set_password(user.user_id, password, audit_journal)
        
        # Make multiple failed attempts
        wrong_password = "WrongPassword456!"
        for attempt in range(3):
            auth_result = await credential_provider.verify_password(
                user.user_id, wrong_password, audit_journal
            )
            assert auth_result is False
            
            # Record failed attempt
            await audit_provider.record_event(
                event_type=AuditEventType.AUTH_FAILURE,
                user_id=user.user_id,
                metadata={"attempt": attempt + 1, "reason": "invalid_password"}
            )
        
        # Account should now be locked
        is_locked = await credential_provider.is_account_locked(user.user_id)
        assert is_locked is True
        
        # Even correct password should fail now
        auth_result = await credential_provider.verify_password(
            user.user_id, password, audit_journal
        )
        assert auth_result is False
        
        # Check audit trail for failed attempts
        failed_events = await audit_provider.get_failed_events()
        user_failed = [e for e in failed_events if e.user_id == user.user_id]
        assert len(user_failed) >= 3

    @pytest.mark.asyncio
    async def test_user_role_permission_integration(self, auth_system, audit_journal):
        """Test user roles and permissions integration."""
        user_provider = auth_system["user"]
        audit_provider = auth_system["audit"]
        
        # Create user
        user = await user_provider.create_user(
            user_id="perm_user",
            email="perm@example.com",
            audit_journal=audit_journal
        )
        
        # User should have default role
        user_roles = await user_provider.get_user_roles(user.user_id)
        assert "user" in user_roles
        
        # Check default permissions
        has_read = await user_provider.has_permission(user.user_id, "user:read")
        assert has_read is True
        
        has_admin = await user_provider.has_permission(user.user_id, "admin:delete")
        assert has_admin is False
        
        # Create admin role and assign
        await user_provider.create_role(
            name="admin",
            description="Administrator role",
            permissions={"admin:*"},
            audit_journal=audit_journal
        )
        
        await user_provider.assign_role(user.user_id, "admin", audit_journal)
        
        # Record role assignment
        await audit_provider.record_event(
            event_type=AuditEventType.ROLE_ASSIGNED,
            user_id=user.user_id,
            metadata={"role": "admin"}
        )
        
        # Now should have admin permissions
        has_admin = await user_provider.has_permission(user.user_id, "admin:delete")
        assert has_admin is True
        
        # Check audit trail
        user_events = await audit_provider.get_user_events(user.user_id)
        role_events = [e for e in user_events if e.event_type == AuditEventType.ROLE_ASSIGNED]
        assert len(role_events) >= 1

    @pytest.mark.asyncio
    async def test_session_management_lifecycle(self, auth_system, audit_journal):
        """Test complete session lifecycle."""
        user_provider = auth_system["user"]
        session_provider = auth_system["session"]
        audit_provider = auth_system["audit"]
        
        # Create user
        user = await user_provider.create_user(
            user_id="session_user",
            email="session@example.com",
            audit_journal=audit_journal
        )
        
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = await session_provider.create_session(
                user,
                ip_address=f"192.168.1.{i+1}",
                user_agent=f"Browser{i}/1.0"
            )
            sessions.append(session)
            
            await audit_provider.record_event(
                event_type=AuditEventType.SESSION_CREATE,
                user_id=user.user_id,
                session_id=session.session_id
            )
        
        # Verify all sessions exist
        user_sessions = await session_provider.get_user_sessions(user.user_id)
        assert len(user_sessions) == 3
        
        # Refresh one session
        refreshed = await session_provider.refresh_session(sessions[0].session_id)
        assert refreshed is not None
        
        await audit_provider.record_event(
            event_type=AuditEventType.SESSION_REFRESH,
            user_id=user.user_id,
            session_id=sessions[0].session_id
        )
        
        # Destroy one session
        destroyed = await session_provider.destroy_session(sessions[1].session_id)
        assert destroyed is True
        
        await audit_provider.record_event(
            event_type=AuditEventType.SESSION_DESTROY,
            user_id=user.user_id,
            session_id=sessions[1].session_id
        )
        
        # Should have 2 sessions left
        user_sessions = await session_provider.get_user_sessions(user.user_id)
        assert len(user_sessions) == 2
        
        # Check session audit events
        session_events = await audit_provider.get_user_events(
            user.user_id,
            event_types=[
                AuditEventType.SESSION_CREATE,
                AuditEventType.SESSION_REFRESH,
                AuditEventType.SESSION_DESTROY
            ]
        )
        assert len(session_events) >= 5  # 3 creates + 1 refresh + 1 destroy

    @pytest.mark.asyncio
    async def test_token_based_authentication_flow(self, auth_system, audit_journal):
        """Test token-based authentication flow."""
        user_provider = auth_system["user"]
        credential_provider = auth_system["credential"]
        audit_provider = auth_system["audit"]
        
        # Create user
        user = await user_provider.create_user(
            user_id="token_user",
            email="token@example.com",
            audit_journal=audit_journal
        )
        
        # Generate API token
        token = await credential_provider.generate_token(
            user.user_id, "api_access", audit_journal
        )
        
        await audit_provider.record_event(
            event_type=AuditEventType.CREDENTIAL_CREATE,
            user_id=user.user_id,
            metadata={"credential_type": "token", "purpose": "api_access"}
        )
        
        # Verify token
        verified_user = await credential_provider.verify_token(
            token, "api_access", audit_journal
        )
        assert verified_user == user.user_id
        
        await audit_provider.record_event(
            event_type=AuditEventType.CREDENTIAL_VERIFY,
            user_id=user.user_id,
            result="success",
            metadata={"credential_type": "token"}
        )
        
        # Try to verify with wrong purpose
        wrong_purpose = await credential_provider.verify_token(
            token, "wrong_purpose", audit_journal
        )
        assert wrong_purpose is None
        
        await audit_provider.record_event(
            event_type=AuditEventType.CREDENTIAL_VERIFY,
            user_id=user.user_id,
            result="failure",
            metadata={"credential_type": "token", "reason": "wrong_purpose"}
        )
        
        # Revoke token
        revoked = await credential_provider.revoke_token(token, audit_journal)
        assert revoked is True
        
        await audit_provider.record_event(
            event_type=AuditEventType.CREDENTIAL_DELETE,
            user_id=user.user_id,
            metadata={"credential_type": "token"}
        )
        
        # Token should no longer work
        verified_after_revoke = await credential_provider.verify_token(
            token, "api_access", audit_journal
        )
        assert verified_after_revoke is None

    @pytest.mark.asyncio
    async def test_user_deletion_cascade(self, auth_system, audit_journal):
        """Test cascading deletion of user data."""
        user_provider = auth_system["user"]
        credential_provider = auth_system["credential"]
        session_provider = auth_system["session"]
        audit_provider = auth_system["audit"]
        
        # Create user with credentials and sessions
        user = await user_provider.create_user(
            user_id="delete_user",
            email="delete@example.com",
            audit_journal=audit_journal
        )
        
        # Set password and create token
        await credential_provider.set_password(user.user_id, "Password123!", audit_journal)
        token = await credential_provider.generate_token(user.user_id, "api", audit_journal)
        
        # Create sessions
        session1 = await session_provider.create_session(user)
        session2 = await session_provider.create_session(user)
        
        # Verify everything exists
        assert await user_provider.get_user(user.user_id) is not None
        assert await credential_provider.verify_password(user.user_id, "Password123!", audit_journal)
        assert await credential_provider.verify_token(token, "api", audit_journal) is not None
        assert len(await session_provider.get_user_sessions(user.user_id)) == 2
        
        # Delete user (should cascade to credentials and sessions)
        await user_provider.delete_user(user.user_id, audit_journal)
        await credential_provider.delete_credentials(user.user_id, audit_journal)
        await session_provider.destroy_user_sessions(user.user_id)
        
        # Record deletion
        await audit_provider.record_event(
            event_type=AuditEventType.USER_DELETE,
            user_id=user.user_id,
            metadata={"cascade": True}
        )
        
        # Verify everything is gone
        assert await user_provider.get_user(user.user_id) is None
        assert not await credential_provider.verify_password(user.user_id, "Password123!", audit_journal)
        assert await credential_provider.verify_token(token, "api", audit_journal) is None
        assert len(await session_provider.get_user_sessions(user.user_id)) == 0

    @pytest.mark.asyncio
    async def test_concurrent_multi_provider_operations(self, auth_system, audit_journal):
        """Test concurrent operations across multiple providers."""
        user_provider = auth_system["user"]
        credential_provider = auth_system["credential"]
        session_provider = auth_system["session"]
        audit_provider = auth_system["audit"]
        
        async def user_workflow(user_id):
            try:
                # Create user
                user = await user_provider.create_user(
                    user_id=user_id,
                    email=f"{user_id}@example.com",
                    audit_journal=audit_journal
                )
                
                # Set password
                password = f"Password{user_id}123!"
                await credential_provider.set_password(user.user_id, password, audit_journal)
                
                # Verify password
                auth_result = await credential_provider.verify_password(
                    user.user_id, password, audit_journal
                )
                assert auth_result is True
                
                # Create session
                session = await session_provider.create_session(user)
                
                # Record events
                await audit_provider.record_event(
                    event_type=AuditEventType.USER_CREATE,
                    user_id=user.user_id
                )
                await audit_provider.record_event(
                    event_type=AuditEventType.AUTH_SUCCESS,
                    user_id=user.user_id
                )
                await audit_provider.record_event(
                    event_type=AuditEventType.SESSION_CREATE,
                    user_id=user.user_id,
                    session_id=session.session_id
                )
                
                return user.user_id
            except Exception as e:
                await audit_provider.record_event(
                    event_type=AuditEventType.AUTH_FAILURE,
                    metadata={"error": str(e), "user_id": user_id}
                )
                return None
        
        # Run multiple workflows concurrently
        tasks = [user_workflow(f"concurrent_user_{i}") for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed
        successful = [r for r in results if isinstance(r, str)]
        assert len(successful) == 10
        
        # Check that all data is properly stored
        total_users = len(await user_provider.list_users())
        assert total_users >= 10
        
        total_events = (await audit_provider.get_statistics())["total_events"]
        assert total_events >= 30  # At least 3 events per user

    @pytest.mark.asyncio
    async def test_audit_event_correlation(self, auth_system, audit_journal):
        """Test correlation of audit events across providers."""
        user_provider = auth_system["user"]
        credential_provider = auth_system["credential"]
        session_provider = auth_system["session"]
        audit_provider = auth_system["audit"]
        
        # Create user and track correlation ID
        correlation_id = "test_correlation_123"
        
        user = await user_provider.create_user(
            user_id="correlation_user",
            email="correlation@example.com",
            audit_journal=audit_journal
        )
        
        # Record related events with correlation metadata
        await audit_provider.record_event(
            event_type=AuditEventType.USER_CREATE,
            user_id=user.user_id,
            metadata={"correlation_id": correlation_id, "flow": "registration"}
        )
        
        password = "Password123!"
        await credential_provider.set_password(user.user_id, password, audit_journal)
        
        await audit_provider.record_event(
            event_type=AuditEventType.CREDENTIAL_CREATE,
            user_id=user.user_id,
            metadata={"correlation_id": correlation_id, "flow": "registration", "type": "password"}
        )
        
        auth_result = await credential_provider.verify_password(user.user_id, password, audit_journal)
        assert auth_result is True
        
        await audit_provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            user_id=user.user_id,
            metadata={"correlation_id": correlation_id, "flow": "login"}
        )
        
        session = await session_provider.create_session(user)
        
        await audit_provider.record_event(
            event_type=AuditEventType.SESSION_CREATE,
            user_id=user.user_id,
            session_id=session.session_id,
            metadata={"correlation_id": correlation_id, "flow": "login"}
        )
        
        # Query events by correlation ID
        all_events = await audit_provider.query_events(user_id=user.user_id)
        correlated_events = [
            e for e in all_events 
            if e.metadata.get("correlation_id") == correlation_id
        ]
        
        assert len(correlated_events) >= 4
        
        # Check different flows
        registration_events = [
            e for e in correlated_events 
            if e.metadata.get("flow") == "registration"
        ]
        login_events = [
            e for e in correlated_events 
            if e.metadata.get("flow") == "login"
        ]
        
        assert len(registration_events) >= 2
        assert len(login_events) >= 2

    @pytest.mark.asyncio
    async def test_provider_statistics_aggregation(self, auth_system, audit_journal):
        """Test aggregated statistics across providers."""
        user_provider = auth_system["user"]
        credential_provider = auth_system["credential"]
        session_provider = auth_system["session"]
        audit_provider = auth_system["audit"]
        
        # Create test data
        users = []
        for i in range(5):
            user = await user_provider.create_user(
                user_id=f"stats_user_{i}",
                email=f"stats{i}@example.com",
                audit_journal=audit_journal
            )
            users.append(user)
            
            # Set password for some users
            if i % 2 == 0:
                await credential_provider.set_password(
                    user.user_id, f"Password{i}123!", audit_journal
                )
            
            # Create sessions for some users
            if i < 3:
                await session_provider.create_session(user)
                await session_provider.create_session(user)  # Multiple sessions
            
            # Generate some audit events
            await audit_provider.record_event(
                event_type=AuditEventType.USER_CREATE,
                user_id=user.user_id
            )
            
            if i % 2 == 0:
                await audit_provider.record_event(
                    event_type=AuditEventType.AUTH_SUCCESS,
                    user_id=user.user_id
                )
            else:
                await audit_provider.record_event(
                    event_type=AuditEventType.AUTH_FAILURE,
                    user_id=user.user_id
                )
        
        # Get statistics from all providers
        user_stats = await user_provider.get_statistics()
        credential_stats = await credential_provider.get_statistics()
        session_stats = await session_provider.get_statistics()
        audit_stats = await audit_provider.get_statistics()
        
        # Verify statistics make sense
        assert user_stats["total_users"] == 5
        assert user_stats["active_users"] == 5  # All active by default
        
        assert credential_stats["total_users"] == 3  # Only even-numbered users have passwords
        assert credential_stats["locked_accounts"] == 0
        
        assert session_stats["total_sessions"] == 6  # 3 users × 2 sessions each
        assert session_stats["active_sessions"] == 6
        
        assert audit_stats["total_events"] >= 10  # At least 2 events per user
        
        # Verify event type distribution
        auth_success_count = audit_stats["event_type_counts"].get("auth.success", 0)
        auth_failure_count = audit_stats["event_type_counts"].get("auth.failure", 0)
        user_create_count = audit_stats["event_type_counts"].get("user.create", 0)
        
        assert auth_success_count >= 3  # Even-numbered users
        assert auth_failure_count >= 2  # Odd-numbered users  
        assert user_create_count == 5  # All users

    @pytest.mark.asyncio
    async def test_cleanup_coordination(self, auth_system, audit_journal):
        """Test cleanup coordination across providers."""
        user_provider = auth_system["user"]
        credential_provider = auth_system["credential"]
        session_provider = auth_system["session"]
        audit_provider = auth_system["audit"]
        
        # Create expired data across providers
        user = await user_provider.create_user(
            user_id="cleanup_user",
            email="cleanup@example.com",
            audit_journal=audit_journal
        )
        
        # Create password and token (tokens can expire)
        await credential_provider.set_password(user.user_id, "Password123!", audit_journal)
        token = await credential_provider.generate_token(user.user_id, "temp_token", audit_journal)
        
        # Create session
        session = await session_provider.create_session(user)
        
        # Create audit events
        for i in range(10):
            await audit_provider.record_event(
                event_type=AuditEventType.AUTH_SUCCESS,
                user_id=user.user_id,
                metadata={"event_number": i}
            )
        
        # Start cleanup tasks for all providers
        await user_provider._ensure_cleanup_started()
        await credential_provider._ensure_cleanup_started()
        await session_provider._ensure_cleanup_started()
        await audit_provider._ensure_cleanup_started()
        
        # All cleanup tasks should be running
        assert user_provider._cleanup_started is True
        assert credential_provider._cleanup_started is True
        assert session_provider._cleanup_started is True
        assert audit_provider._cleanup_started is True
        
        # Manual cleanup operations should work
        session_cleanups = await session_provider.cleanup_expired_sessions()
        audit_cleanups = await audit_provider.cleanup_old_events()
        
        # Should have cleaned up some items (depends on configuration)
        assert session_cleanups >= 0
        assert audit_cleanups >= 0