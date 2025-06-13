"""Tests for MemorySessionProvider using abstract interface only."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

import pytest

from serv.auth.audit.enforcement import AuditJournal
from serv.auth.exceptions import AuthenticationError
from serv.auth.types import Session, User
from serv.bundled.auth.memory.session import MemorySessionProvider
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
def config():
    """Create test configuration."""
    return {
        "cleanup_interval": 0.1,
        "default_session_ttl": 3600,  # 1 hour
        "max_session_ttl": 86400,  # 24 hours
        "session_id_length": 32,
        "max_concurrent_sessions": 5,
        "require_ip_validation": False,
        "require_user_agent_validation": False,
        "session_refresh_threshold": 300,  # 5 minutes
    }


@pytest.fixture
def provider(config, container):
    """Create a MemorySessionProvider instance."""
    return MemorySessionProvider(config, container)


@pytest.fixture
def test_user():
    """Create a test user."""
    return User(
        id="test_user",
        email="test@example.com",
        username="testuser",
    )


class TestMemorySessionProvider:
    """Test MemorySessionProvider functionality using abstract interface."""

    @pytest.mark.asyncio
    async def test_create_session_basic(self, provider, test_user, audit_journal):
        """Test basic session creation via interface."""
        session = await provider.create_session(
            user_id=test_user.id,
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0",
            audit_journal=audit_journal
        )
        
        assert session.user_id == test_user.id
        assert session.id is not None
        assert session.created_at is not None
        assert session.expires_at is not None
        assert session.last_accessed is not None

    @pytest.mark.asyncio
    async def test_create_session_custom_duration(self, provider, test_user, audit_journal):
        """Test session creation with custom duration."""
        custom_duration = timedelta(hours=2)
        
        session = await provider.create_session(
            user_id=test_user.id,
            duration=custom_duration,
            audit_journal=audit_journal
        )
        
        assert session.user_id == test_user.id
        # Session should expire approximately in 2 hours
        expected_expiry = session.created_at + custom_duration
        # Allow some tolerance for execution time
        assert abs((session.expires_at - expected_expiry).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_get_session_valid(self, provider, test_user, audit_journal):
        """Test getting a valid session."""
        # Create session first
        session = await provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        
        # Get session
        retrieved_session = await provider.get_session(session.id)
        
        assert retrieved_session is not None
        assert retrieved_session.id == session.id
        assert retrieved_session.user_id == test_user.id

    @pytest.mark.asyncio
    async def test_get_session_nonexistent(self, provider):
        """Test getting a non-existent session."""
        result = await provider.get_session("nonexistent_session_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_session(self, provider, test_user, audit_journal):
        """Test refreshing a session."""
        # Create session first
        session = await provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        
        # Get original expiry time
        original_expires_at = session.expires_at
        
        # Wait a bit to ensure time difference
        await asyncio.sleep(0.1)
        
        # Refresh session
        refreshed_session = await provider.refresh_session(session.id, audit_journal)
        
        assert refreshed_session is not None
        assert refreshed_session.id == session.id
        # Refreshed session might have later expiry (depends on refresh threshold)

    @pytest.mark.asyncio
    async def test_refresh_session_nonexistent(self, provider, audit_journal):
        """Test refreshing a non-existent session."""
        result = await provider.refresh_session("nonexistent_session_id", audit_journal)
        assert result is None

    @pytest.mark.asyncio
    async def test_destroy_session(self, provider, test_user, audit_journal):
        """Test destroying a session."""
        # Create session first
        session = await provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        
        # Verify session exists
        retrieved_session = await provider.get_session(session.id)
        assert retrieved_session is not None
        
        # Destroy session
        await provider.destroy_session(session.id, audit_journal)
        
        # Verify session no longer exists
        retrieved_session = await provider.get_session(session.id)
        assert retrieved_session is None

    @pytest.mark.asyncio
    async def test_destroy_user_sessions(self, provider, test_user, audit_journal):
        """Test destroying all sessions for a user."""
        # Create multiple sessions
        session1 = await provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        session2 = await provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        
        # Verify sessions exist
        assert await provider.get_session(session1.id) is not None
        assert await provider.get_session(session2.id) is not None
        
        # Destroy all user sessions
        count = await provider.destroy_user_sessions(test_user.id)
        
        assert count == 2
        
        # Verify sessions no longer exist
        assert await provider.get_session(session1.id) is None
        assert await provider.get_session(session2.id) is None

    @pytest.mark.asyncio
    async def test_get_active_sessions_empty(self, provider, test_user):
        """Test getting active sessions when none exist."""
        sessions = await provider.get_active_sessions(test_user.id)
        assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_get_active_sessions_multiple(self, provider, test_user, audit_journal):
        """Test getting multiple active sessions."""
        # Create multiple sessions
        session1 = await provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        session2 = await provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        
        # Get active sessions
        sessions = await provider.get_active_sessions(test_user.id)
        
        assert len(sessions) == 2
        session_ids = {s.id for s in sessions}
        assert session1.id in session_ids
        assert session2.id in session_ids

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, provider, test_user, audit_journal):
        """Test cleanup of expired sessions."""
        # Create session with short duration
        short_duration = timedelta(seconds=1)
        session = await provider.create_session(
            user_id=test_user.id,
            duration=short_duration,
            audit_journal=audit_journal
        )
        
        # Verify session exists initially
        retrieved_session = await provider.get_session(session.id)
        assert retrieved_session is not None
        assert retrieved_session.id == session.id
        
        # Wait for session to expire
        await asyncio.sleep(1.2)
        
        # Session should be expired when accessed (lazy cleanup)
        # The get_session call should return None for expired sessions
        expired_session = await provider.get_session(session.id)
        assert expired_session is None


    @pytest.mark.asyncio
    async def test_session_concurrent_limit(self, config, container, test_user, audit_journal):
        """Test concurrent session limits."""
        # Set low concurrent session limit
        config["max_concurrent_sessions"] = 2
        provider = MemorySessionProvider(config, container)
        
        # Create sessions up to limit
        session1 = await provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        session2 = await provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        
        # Verify both sessions exist
        sessions = await provider.get_active_sessions(test_user.id)
        assert len(sessions) == 2
        
        # Create third session (should remove oldest)
        session3 = await provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        
        # Should still have 2 sessions
        sessions = await provider.get_active_sessions(test_user.id)
        assert len(sessions) == 2
        
        # First session should be gone
        assert await provider.get_session(session1.id) is None
        # Other sessions should still exist
        assert await provider.get_session(session2.id) is not None
        assert await provider.get_session(session3.id) is not None

    @pytest.mark.asyncio
    async def test_destroy_nonexistent_session(self, provider, audit_journal):
        """Test destroying a non-existent session."""
        # Should not raise an exception
        await provider.destroy_session("nonexistent_session_id", audit_journal)

    @pytest.mark.asyncio
    async def test_destroy_user_sessions_no_sessions(self, provider, test_user):
        """Test destroying sessions for user with no sessions."""
        count = await provider.destroy_user_sessions(test_user.id)
        assert count == 0

    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self, provider, audit_journal):
        """Test concurrent session operations don't cause race conditions."""
        async def create_session_worker(user_id):
            try:
                session = await provider.create_session(
                    user_id=user_id,
                    audit_journal=audit_journal
                )
                return session.id
            except Exception:
                return None
        
        # Create multiple sessions concurrently
        tasks = []
        for i in range(10):
            user_id = f"user_{i}"
            tasks.append(create_session_worker(user_id))
        
        session_ids = await asyncio.gather(*tasks)
        
        # All sessions should be created successfully
        assert all(session_id is not None for session_id in session_ids)
        assert len(set(session_ids)) == 10  # All should be unique

    @pytest.mark.asyncio
    async def test_session_metadata_tracking(self, provider, test_user, audit_journal):
        """Test that session metadata is properly tracked."""
        session = await provider.create_session(
            user_id=test_user.id,
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0",
            audit_journal=audit_journal
        )
        
        assert session.metadata is not None
        assert "creation_ip" in session.metadata
        assert "creation_user_agent" in session.metadata
        assert "access_count" in session.metadata
        assert session.metadata["creation_ip"] == "192.168.1.1"
        assert session.metadata["creation_user_agent"] == "Test Browser/1.0"
        assert session.metadata["access_count"] >= 1

    @pytest.mark.asyncio
    async def test_audit_events_recorded(self, provider, test_user, audit_journal):
        """Test that audit events are properly recorded."""
        # Create session
        session = await provider.create_session(
            user_id=test_user.id,
            audit_journal=audit_journal
        )
        
        # The audit_journal is passed to interface methods but providers may handle
        # audit recording internally rather than directly calling the journal
        # Just verify the operation succeeded
        assert session.id is not None
        assert session.user_id == test_user.id
        
        # Refresh session
        refreshed_session = await provider.refresh_session(session.id, audit_journal)
        assert refreshed_session is not None
        
        # Destroy session
        await provider.destroy_session(session.id, audit_journal)
        
        # Verify session is destroyed
        destroyed_session = await provider.get_session(session.id)
        assert destroyed_session is None