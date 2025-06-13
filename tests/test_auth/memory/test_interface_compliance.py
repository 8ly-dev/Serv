"""Tests for all memory providers using only abstract interface methods."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from serv.auth.audit.enforcement import AuditJournal
from serv.auth.audit.events import AuditEventType
from serv.auth.exceptions import AuthenticationError
from serv.auth.types import Credentials, CredentialType, User, Session, AuditEvent
from serv.bundled.auth.memory.credential import MemoryCredentialProvider
from serv.bundled.auth.memory.session import MemorySessionProvider
from serv.bundled.auth.memory.user import MemoryUserProvider
from serv.bundled.auth.memory.audit import MemoryAuditProvider
from bevy import Container, get_registry


@pytest.fixture
def container():
    """Create a test container."""
    return Container(get_registry())


@pytest.fixture
def audit_journal():
    """Create a mock audit journal."""
    from unittest.mock import AsyncMock
    journal = MagicMock(spec=AuditJournal)
    journal.record_event = AsyncMock(return_value=None)
    return journal


@pytest.fixture
def base_config():
    """Create test configuration."""
    return {
        "cleanup_interval": 0.1,
        "max_login_attempts": 3,
        "account_lockout_duration": 300.0,
        "password_min_length": 8,
        "token_length": 32,
        "token_ttl": 3600,
        "argon2_time_cost": 1,
        "argon2_memory_cost": 1024,
        "argon2_parallelism": 1,
    }


@pytest.fixture
def credential_provider(base_config, container):
    """Create a MemoryCredentialProvider instance."""
    return MemoryCredentialProvider(base_config, container)


@pytest.fixture
def session_provider(base_config, container):
    """Create a MemorySessionProvider instance."""
    return MemorySessionProvider(base_config, container)


@pytest.fixture
def user_provider(base_config, container):
    """Create a MemoryUserProvider instance."""
    return MemoryUserProvider(base_config, container)


@pytest.fixture
def audit_provider(base_config, container):
    """Create a MemoryAuditProvider instance."""
    return MemoryAuditProvider(base_config, container)


@pytest.fixture
def test_user():
    """Create a test user."""
    return User(
        id="test_user",
        username="testuser",
        email="test@example.com",
    )


class TestCredentialProviderInterface:
    """Test MemoryCredentialProvider using only abstract interface methods."""

    @pytest.mark.asyncio
    async def test_create_and_verify_password_credentials(self, credential_provider, test_user, audit_journal):
        """Test creating and verifying password credentials."""
        password = "SecurePassword123!"
        
        # Create credentials using interface method
        credentials = Credentials(
            id="cred_password_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        
        # Create credentials
        await credential_provider.create_credentials(test_user.id, credentials, audit_journal)
        
        # Verify credential types are available
        types = await credential_provider.get_credential_types(test_user.id)
        assert CredentialType.PASSWORD in types
        
        # Verify credentials work
        result = await credential_provider.verify_credentials(credentials, audit_journal)
        assert result is True
        
        # Verify wrong password fails
        wrong_credentials = Credentials(
            id="cred_password_wrong",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": "WrongPassword456!"},
            metadata={}
        )
        result = await credential_provider.verify_credentials(wrong_credentials, audit_journal)
        assert result is False

    @pytest.mark.asyncio
    async def test_create_and_verify_token_credentials(self, credential_provider, test_user, audit_journal):
        """Test creating and verifying token credentials."""
        # Create token credentials
        credentials = Credentials(
            id="cred_token_test",
            user_id=test_user.id,
            type=CredentialType.TOKEN,
            data={"purpose": "api_access"},
            metadata={}
        )
        
        # Create credentials
        await credential_provider.create_credentials(test_user.id, credentials, audit_journal)
        
        # Verify credential types are available
        types = await credential_provider.get_credential_types(test_user.id)
        assert CredentialType.TOKEN in types

    @pytest.mark.asyncio
    async def test_update_credentials(self, credential_provider, test_user, audit_journal):
        """Test updating credentials."""
        old_password = "OldPassword123!"
        new_password = "NewPassword456!"
        
        # Create initial credentials
        old_credentials = Credentials(
            id="cred_old",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": old_password},
            metadata={}
        )
        
        await credential_provider.create_credentials(test_user.id, old_credentials, audit_journal)
        
        # Update credentials
        new_credentials = Credentials(
            id="cred_new",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": new_password},
            metadata={}
        )
        
        await credential_provider.update_credentials(test_user.id, old_credentials, new_credentials, audit_journal)
        
        # Old password should not work
        result = await credential_provider.verify_credentials(old_credentials, audit_journal)
        assert result is False
        
        # New password should work
        result = await credential_provider.verify_credentials(new_credentials, audit_journal)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_credentials(self, credential_provider, test_user, audit_journal):
        """Test deleting credentials."""
        password = "SecurePassword123!"
        
        # Create credentials
        credentials = Credentials(
            id="cred_delete_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        
        await credential_provider.create_credentials(test_user.id, credentials, audit_journal)
        
        # Verify they exist
        types = await credential_provider.get_credential_types(test_user.id)
        assert CredentialType.PASSWORD in types
        
        # Delete credentials
        await credential_provider.delete_credentials(test_user.id, CredentialType.PASSWORD, audit_journal)
        
        # Verify they're gone
        types = await credential_provider.get_credential_types(test_user.id)
        assert CredentialType.PASSWORD not in types

    @pytest.mark.asyncio
    async def test_is_credential_compromised(self, credential_provider, test_user):
        """Test checking if credentials are compromised."""
        credentials = Credentials(
            id="cred_compromise_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": "Password123!"},
            metadata={}
        )
        
        # Memory provider should return False (no external checking)
        result = await credential_provider.is_credential_compromised(credentials)
        assert result is False


class TestSessionProviderInterface:
    """Test MemorySessionProvider using only abstract interface methods."""

    @pytest.mark.asyncio
    async def test_create_session(self, session_provider, test_user, audit_journal):
        """Test creating a session."""
        # Create session
        session = await session_provider.create_session(
            user_id=test_user.id,
            ip_address="192.168.1.100",
            user_agent="Test Browser",
            duration=timedelta(hours=1),
            audit_journal=audit_journal
        )
        
        assert session.user_id == test_user.id
        assert session.id is not None
        assert session.is_active
        assert not session.is_expired()

    @pytest.mark.asyncio
    async def test_get_session(self, session_provider, test_user, audit_journal):
        """Test retrieving a session."""
        # Create session
        created_session = await session_provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        
        # Retrieve session
        retrieved_session = await session_provider.get_session(created_session.id)
        
        assert retrieved_session is not None
        assert retrieved_session.id == created_session.id
        assert retrieved_session.user_id == test_user.id

    @pytest.mark.asyncio
    async def test_refresh_session(self, session_provider, test_user, audit_journal):
        """Test refreshing a session."""
        # Create session
        session = await session_provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        
        # Refresh session
        refreshed = await session_provider.refresh_session(session.id, audit_journal)
        
        assert refreshed is not None
        assert refreshed.id == session.id

    @pytest.mark.asyncio
    async def test_destroy_session(self, session_provider, test_user, audit_journal):
        """Test destroying a session."""
        # Create session
        session = await session_provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        
        # Verify it exists
        retrieved = await session_provider.get_session(session.id)
        assert retrieved is not None
        
        # Destroy session
        await session_provider.destroy_session(session.id, audit_journal)
        
        # Verify it's gone
        retrieved = await session_provider.get_session(session.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_destroy_user_sessions(self, session_provider, test_user, audit_journal):
        """Test destroying all sessions for a user."""
        # Create multiple sessions
        session1 = await session_provider.create_session(user_id=test_user.id, audit_journal=audit_journal)
        session2 = await session_provider.create_session(user_id=test_user.id, audit_journal=audit_journal)
        
        # Destroy all user sessions
        count = await session_provider.destroy_user_sessions(test_user.id)
        
        assert count >= 2
        
        # Verify sessions are gone
        assert await session_provider.get_session(session1.id) is None
        assert await session_provider.get_session(session2.id) is None

    @pytest.mark.asyncio
    async def test_get_active_sessions(self, session_provider, test_user, audit_journal):
        """Test getting active sessions for a user."""
        # Create sessions
        session1 = await session_provider.create_session(user_id=test_user.id, audit_journal=audit_journal)
        session2 = await session_provider.create_session(user_id=test_user.id, audit_journal=audit_journal)
        
        # Get active sessions
        active_sessions = await session_provider.get_active_sessions(test_user.id)
        
        assert len(active_sessions) >= 2
        session_ids = [s.id for s in active_sessions]
        assert session1.id in session_ids
        assert session2.id in session_ids

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, session_provider):
        """Test cleaning up expired sessions."""
        # Test cleanup (should not error)
        count = await session_provider.cleanup_expired_sessions()
        assert isinstance(count, int)


class TestUserProviderInterface:
    """Test MemoryUserProvider using only abstract interface methods."""

    @pytest.mark.asyncio
    async def test_create_user(self, user_provider, audit_journal):
        """Test creating a user."""
        user = await user_provider.create_user(
            username="newuser",
            email="newuser@example.com",
            metadata={"role": "customer"},
            audit_journal=audit_journal
        )
        
        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.id is not None

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, user_provider, audit_journal):
        """Test getting user by ID."""
        # Create user
        created_user = await user_provider.create_user(
            username="testuser", 
            email="test@example.com",
            audit_journal=audit_journal
        )
        
        # Get user by ID
        retrieved_user = await user_provider.get_user_by_id(created_user.id)
        
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_by_username(self, user_provider, audit_journal):
        """Test getting user by username."""
        # Create user
        created_user = await user_provider.create_user(
            username="uniqueuser",
            email="unique@example.com", 
            audit_journal=audit_journal
        )
        
        # Get user by username
        retrieved_user = await user_provider.get_user_by_username("uniqueuser")
        
        assert retrieved_user is not None
        assert retrieved_user.username == "uniqueuser"
        assert retrieved_user.id == created_user.id

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, user_provider, audit_journal):
        """Test getting user by email."""
        # Create user
        created_user = await user_provider.create_user(
            username="emailuser",
            email="email@example.com",
            audit_journal=audit_journal
        )
        
        # Get user by email
        retrieved_user = await user_provider.get_user_by_email("email@example.com")
        
        assert retrieved_user is not None
        assert retrieved_user.email == "email@example.com"
        assert retrieved_user.id == created_user.id

    @pytest.mark.asyncio
    async def test_update_user(self, user_provider, audit_journal):
        """Test updating user information."""
        # Create user
        user = await user_provider.create_user(
            username="updateuser",
            email="update@example.com",
            audit_journal=audit_journal
        )
        
        # Update user
        updates = {
            "email": "updated@example.com",
            "is_active": False,
            "metadata": {"updated": True}
        }
        updated_user = await user_provider.update_user(user.id, updates, audit_journal)
        
        assert updated_user.email == "updated@example.com"
        assert not updated_user.is_active

    @pytest.mark.asyncio
    async def test_delete_user(self, user_provider, audit_journal):
        """Test deleting a user."""
        # Create user
        user = await user_provider.create_user(
            username="deleteuser",
            email="delete@example.com",
            audit_journal=audit_journal
        )
        
        # Verify user exists
        retrieved = await user_provider.get_user_by_id(user.id)
        assert retrieved is not None
        
        # Delete user
        await user_provider.delete_user(user.id, audit_journal)
        
        # Verify user is gone
        retrieved = await user_provider.get_user_by_id(user.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_users(self, user_provider, audit_journal):
        """Test listing users."""
        # Create users
        user1 = await user_provider.create_user("user1", "user1@example.com", audit_journal=audit_journal)
        user2 = await user_provider.create_user("user2", "user2@example.com", audit_journal=audit_journal)
        
        # List users
        users = await user_provider.list_users(limit=10, offset=0)
        
        assert len(users) >= 2
        user_ids = [u.id for u in users]
        assert user1.id in user_ids
        assert user2.id in user_ids

    @pytest.mark.asyncio
    async def test_assign_and_remove_role(self, user_provider, audit_journal):
        """Test assigning and removing roles."""
        # Create user
        user = await user_provider.create_user(
            username="roleuser",
            email="role@example.com",
            audit_journal=audit_journal
        )
        
        # Assign role
        await user_provider.assign_role(user.id, "admin")
        
        # Get user roles
        roles = await user_provider.get_user_roles(user.id)
        role_names = [r.name for r in roles]
        assert "admin" in role_names
        
        # Remove role
        await user_provider.remove_role(user.id, "admin")
        
        # Verify role removed
        roles = await user_provider.get_user_roles(user.id)
        role_names = [r.name for r in roles]
        assert "admin" not in role_names

    @pytest.mark.asyncio
    async def test_get_user_permissions(self, user_provider, audit_journal):
        """Test getting user permissions."""
        # Create user
        user = await user_provider.create_user(
            username="permuser",
            email="perm@example.com",
            audit_journal=audit_journal
        )
        
        # Assign role (should auto-create)
        await user_provider.assign_role(user.id, "viewer")
        
        # Get user permissions
        permissions = await user_provider.get_user_permissions(user.id)
        assert isinstance(permissions, set)


class TestAuditProviderInterface:
    """Test MemoryAuditProvider using only abstract interface methods."""

    @pytest.mark.asyncio
    async def test_store_audit_event(self, audit_provider):
        """Test storing an audit event."""
        event = AuditEvent(
            id="event_001",
            event_type=AuditEventType.AUTH_ATTEMPT,
            user_id="test_user",
            metadata={"ip": "192.168.1.1"},
            timestamp=datetime.now()
        )
        
        # Should not raise an exception
        await audit_provider.store_audit_event(event)

    @pytest.mark.asyncio
    async def test_get_audit_events(self, audit_provider):
        """Test getting audit events."""
        # Store an event first
        event = AuditEvent(
            id="event_002",
            event_type=AuditEventType.AUTH_SUCCESS,
            user_id="test_user",
            timestamp=datetime.now()
        )
        await audit_provider.store_audit_event(event)
        
        # Get events
        events = await audit_provider.get_audit_events(limit=10)
        
        assert isinstance(events, list)
        assert len(events) >= 1
        assert any(e.id == "event_002" for e in events)

    @pytest.mark.asyncio
    async def test_get_user_audit_events(self, audit_provider):
        """Test getting audit events for a specific user."""
        # Store events for different users
        event1 = AuditEvent(
            id="user_event_1",
            event_type=AuditEventType.AUTH_ATTEMPT,
            user_id="user1",
            timestamp=datetime.now()
        )
        event2 = AuditEvent(
            id="user_event_2",
            event_type=AuditEventType.AUTH_SUCCESS,
            user_id="user2",
            timestamp=datetime.now()
        )
        
        await audit_provider.store_audit_event(event1)
        await audit_provider.store_audit_event(event2)
        
        # Get events for user1
        user1_events = await audit_provider.get_user_audit_events("user1")
        
        assert len(user1_events) >= 1
        assert all(e.user_id == "user1" for e in user1_events)

    @pytest.mark.asyncio
    async def test_search_audit_events(self, audit_provider):
        """Test searching audit events."""
        # Store events
        event = AuditEvent(
            id="search_event",
            event_type=AuditEventType.PERMISSION_CHECK,
            user_id="search_user",
            resource="test_resource",
            timestamp=datetime.now()
        )
        await audit_provider.store_audit_event(event)
        
        # Search events
        events = await audit_provider.search_audit_events(
            event_types=[AuditEventType.PERMISSION_CHECK],
            user_id="search_user",
            limit=10
        )
        
        assert len(events) >= 1
        assert any(e.id == "search_event" for e in events)

    @pytest.mark.asyncio
    async def test_cleanup_old_events(self, audit_provider):
        """Test cleaning up old events."""
        from datetime import datetime, timedelta
        
        # Test cleanup (should not error)
        cutoff_time = datetime.now() - timedelta(days=30)
        count = await audit_provider.cleanup_old_events(cutoff_time)
        
        assert isinstance(count, int)
        assert count >= 0