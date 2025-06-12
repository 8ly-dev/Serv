"""Tests for MemorySessionProvider."""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock

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
    return MagicMock(spec=AuditJournal)


@pytest.fixture
def config():
    """Create test configuration."""
    return {
        "cleanup_interval": 0.1,
        "session_ttl": 3600,  # 1 hour
        "session_id_length": 32,
        "max_sessions_per_user": 5,
        "validate_ip": True,
        "validate_user_agent": True,
        "extend_on_access": True,
        "cleanup_expired_on_access": True,
    }


@pytest.fixture
def provider(config, container):
    """Create a MemorySessionProvider instance."""
    return MemorySessionProvider(config, container)


@pytest.fixture
def test_user():
    """Create a test user."""
    return User(
        user_id="test_user",
        email="test@example.com",
        username="testuser",
        display_name="Test User",
    )


class TestMemorySessionProvider:
    """Test MemorySessionProvider functionality."""

    @pytest.mark.asyncio
    async def test_create_session_basic(self, provider, test_user):
        """Test basic session creation."""
        session = await provider.create_session(
            test_user,
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        assert isinstance(session, Session)
        assert session.user_id == test_user.user_id
        assert session.session_id is not None
        assert len(session.session_id) > 0
        assert session.created_at is not None
        assert session.expires_at is not None
        assert session.is_active is True
        
        # Check session was stored
        stored = provider.store.get("sessions", session.session_id)
        assert stored is not None
        assert stored.user_id == test_user.user_id

    @pytest.mark.asyncio
    async def test_create_session_custom_ttl(self, provider, test_user):
        """Test session creation with custom TTL."""
        custom_ttl = 7200  # 2 hours
        
        session = await provider.create_session(
            test_user,
            ttl_seconds=custom_ttl
        )
        
        expected_expiry = session.created_at + timedelta(seconds=custom_ttl)
        # Allow small timing differences
        assert abs((session.expires_at - expected_expiry).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_get_session_valid(self, provider, test_user):
        """Test getting a valid session."""
        session = await provider.create_session(test_user)
        
        retrieved = await provider.get_session(session.session_id)
        
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
        assert retrieved.user_id == test_user.user_id

    @pytest.mark.asyncio
    async def test_get_session_nonexistent(self, provider):
        """Test getting a non-existent session."""
        result = await provider.get_session("nonexistent_session_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_expired(self, config, container, test_user):
        """Test getting an expired session."""
        # Set very short TTL
        config["session_ttl"] = 0.1
        provider = MemorySessionProvider(config, container)
        
        session = await provider.create_session(test_user)
        
        # Wait for expiration
        await asyncio.sleep(0.2)
        
        retrieved = await provider.get_session(session.session_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_validate_session_success(self, provider, test_user):
        """Test successful session validation."""
        session = await provider.create_session(
            test_user,
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        result = await provider.validate_session(
            session.session_id,
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_session_ip_mismatch(self, provider, test_user):
        """Test session validation with IP mismatch."""
        session = await provider.create_session(
            test_user,
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        result = await provider.validate_session(
            session.session_id,
            ip_address="192.168.1.2",  # Different IP
            user_agent="Test Browser/1.0"
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_session_user_agent_mismatch(self, provider, test_user):
        """Test session validation with user agent mismatch."""
        session = await provider.create_session(
            test_user,
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        result = await provider.validate_session(
            session.session_id,
            ip_address="192.168.1.1",
            user_agent="Different Browser/2.0"  # Different user agent
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_session_disabled_checks(self, config, container, test_user):
        """Test session validation with disabled IP/UA checks."""
        config["validate_ip"] = False
        config["validate_user_agent"] = False
        provider = MemorySessionProvider(config, container)
        
        session = await provider.create_session(
            test_user,
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        # Should validate even with different IP/UA
        result = await provider.validate_session(
            session.session_id,
            ip_address="10.0.0.1",
            user_agent="Different Browser/2.0"
        )
        
        assert result is True

    @pytest.mark.asyncio
    async def test_refresh_session(self, provider, test_user):
        """Test session refresh."""
        session = await provider.create_session(test_user)
        original_expires_at = session.expires_at
        
        # Wait a bit to ensure timestamp difference
        await asyncio.sleep(0.01)
        
        refreshed = await provider.refresh_session(session.session_id)
        
        assert refreshed is not None
        assert refreshed.session_id == session.session_id
        assert refreshed.expires_at > original_expires_at

    @pytest.mark.asyncio
    async def test_refresh_session_nonexistent(self, provider):
        """Test refreshing a non-existent session."""
        result = await provider.refresh_session("nonexistent_session_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_destroy_session(self, provider, test_user):
        """Test session destruction."""
        session = await provider.create_session(test_user)
        
        # Verify session exists
        retrieved = await provider.get_session(session.session_id)
        assert retrieved is not None
        
        # Destroy session
        result = await provider.destroy_session(session.session_id)
        assert result is True
        
        # Session should no longer exist
        retrieved = await provider.get_session(session.session_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_destroy_session_nonexistent(self, provider):
        """Test destroying a non-existent session."""
        result = await provider.destroy_session("nonexistent_session_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_destroy_user_sessions(self, provider, test_user):
        """Test destroying all sessions for a user."""
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = await provider.create_session(
                test_user,
                ip_address=f"192.168.1.{i+1}"
            )
            sessions.append(session)
        
        # Verify all sessions exist
        for session in sessions:
            retrieved = await provider.get_session(session.session_id)
            assert retrieved is not None
        
        # Destroy all user sessions
        count = await provider.destroy_user_sessions(test_user.user_id)
        assert count == 3
        
        # All sessions should be gone
        for session in sessions:
            retrieved = await provider.get_session(session.session_id)
            assert retrieved is None

    @pytest.mark.asyncio
    async def test_max_sessions_enforcement(self, config, container, test_user):
        """Test maximum sessions per user enforcement."""
        config["max_sessions_per_user"] = 2
        provider = MemorySessionProvider(config, container)
        
        # Create sessions up to the limit
        sessions = []
        for i in range(2):
            session = await provider.create_session(test_user)
            sessions.append(session)
        
        # All sessions should exist
        for session in sessions:
            retrieved = await provider.get_session(session.session_id)
            assert retrieved is not None
        
        # Creating another session should remove the oldest
        new_session = await provider.create_session(test_user)
        
        # First session should be gone, others should remain
        first_session = await provider.get_session(sessions[0].session_id)
        assert first_session is None
        
        second_session = await provider.get_session(sessions[1].session_id)
        assert second_session is not None
        
        retrieved_new = await provider.get_session(new_session.session_id)
        assert retrieved_new is not None

    @pytest.mark.asyncio
    async def test_get_user_sessions(self, provider, test_user):
        """Test getting sessions for a user."""
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = await provider.create_session(test_user)
            sessions.append(session)
        
        # Get user sessions
        user_sessions = await provider.get_user_sessions(test_user.user_id)
        
        assert len(user_sessions) == 3
        session_ids = {s.session_id for s in user_sessions}
        expected_ids = {s.session_id for s in sessions}
        assert session_ids == expected_ids

    @pytest.mark.asyncio
    async def test_get_user_sessions_empty(self, provider):
        """Test getting sessions for user with no sessions."""
        sessions = await provider.get_user_sessions("nonexistent_user")
        assert sessions == []

    @pytest.mark.asyncio
    async def test_get_active_sessions(self, provider, test_user):
        """Test getting all active sessions."""
        # Initially no sessions
        active = await provider.get_active_sessions()
        assert len(active) == 0
        
        # Create some sessions
        sessions = []
        for i in range(3):
            session = await provider.create_session(test_user)
            sessions.append(session)
        
        # Get active sessions
        active = await provider.get_active_sessions()
        assert len(active) == 3

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, config, container, test_user):
        """Test cleanup of expired sessions."""
        config["session_ttl"] = 0.1  # Very short TTL
        provider = MemorySessionProvider(config, container)
        
        # Create sessions
        sessions = []
        for i in range(3):
            session = await provider.create_session(test_user)
            sessions.append(session)
        
        # Wait for expiration
        await asyncio.sleep(0.2)
        
        # Manual cleanup
        cleaned_count = await provider.cleanup_expired_sessions()
        assert cleaned_count == 3
        
        # All sessions should be gone
        active = await provider.get_active_sessions()
        assert len(active) == 0

    @pytest.mark.asyncio
    async def test_extend_on_access(self, config, container, test_user):
        """Test session extension on access."""
        config["extend_on_access"] = True
        provider = MemorySessionProvider(config, container)
        
        session = await provider.create_session(test_user)
        original_expires_at = session.expires_at
        
        # Wait a bit
        await asyncio.sleep(0.01)
        
        # Access session (should extend it)
        retrieved = await provider.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.expires_at > original_expires_at

    @pytest.mark.asyncio
    async def test_no_extend_on_access(self, config, container, test_user):
        """Test session not extended when disabled."""
        config["extend_on_access"] = False
        provider = MemorySessionProvider(config, container)
        
        session = await provider.create_session(test_user)
        original_expires_at = session.expires_at
        
        # Wait a bit
        await asyncio.sleep(0.01)
        
        # Access session (should not extend it)
        retrieved = await provider.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.expires_at == original_expires_at

    @pytest.mark.asyncio
    async def test_get_statistics(self, provider, test_user):
        """Test getting provider statistics."""
        # Initially empty
        stats = await provider.get_statistics()
        assert stats["total_sessions"] == 0
        assert stats["active_sessions"] == 0
        
        # Create some sessions
        for i in range(3):
            await provider.create_session(test_user)
        
        stats = await provider.get_statistics()
        assert stats["total_sessions"] == 3
        assert stats["active_sessions"] == 3

    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self, provider, test_user):
        """Test concurrent session operations don't cause race conditions."""
        import asyncio
        
        async def create_session_worker():
            try:
                session = await provider.create_session(test_user)
                return session.session_id
            except Exception:
                return None
        
        async def destroy_session_worker(session_id):
            try:
                return await provider.destroy_session(session_id)
            except Exception:
                return False
        
        # Create multiple sessions concurrently
        create_tasks = [create_session_worker() for _ in range(10)]
        session_ids = await asyncio.gather(*create_tasks)
        
        # Filter out any None results
        valid_session_ids = [sid for sid in session_ids if sid is not None]
        assert len(valid_session_ids) > 0
        
        # Destroy sessions concurrently
        destroy_tasks = [destroy_session_worker(sid) for sid in valid_session_ids]
        destroy_results = await asyncio.gather(*destroy_tasks)
        
        # Most should succeed (some might race with cleanup)
        success_count = sum(1 for result in destroy_results if result)
        assert success_count > 0

    @pytest.mark.asyncio
    async def test_session_metadata(self, provider, test_user):
        """Test session metadata handling."""
        custom_metadata = {
            "device_type": "mobile",
            "app_version": "1.2.3",
            "login_method": "oauth"
        }
        
        session = await provider.create_session(
            test_user,
            metadata=custom_metadata
        )
        
        # Metadata should be preserved
        for key, value in custom_metadata.items():
            assert session.metadata[key] == value
        
        # Should also have system metadata
        assert "created_at" in session.metadata
        assert "last_accessed" in session.metadata

    @pytest.mark.asyncio
    async def test_cleanup_lifecycle(self, provider):
        """Test cleanup task lifecycle."""
        # Start cleanup
        await provider._ensure_cleanup_started()
        assert provider._cleanup_started is True
        
        # Starting again should be idempotent
        await provider._ensure_cleanup_started()
        assert provider._cleanup_started is True

    @pytest.mark.asyncio
    async def test_edge_cases(self, provider, test_user):
        """Test edge cases and error conditions."""
        # Test with None IP/user agent
        session = await provider.create_session(
            test_user,
            ip_address=None,
            user_agent=None
        )
        assert session is not None
        
        # Validation should work with None values
        result = await provider.validate_session(
            session.session_id,
            ip_address=None,
            user_agent=None
        )
        assert result is True
        
        # Test empty metadata
        session2 = await provider.create_session(test_user, metadata={})
        assert session2 is not None
        assert isinstance(session2.metadata, dict)

    @pytest.mark.asyncio
    async def test_session_id_uniqueness(self, provider, test_user):
        """Test that session IDs are unique."""
        session_ids = set()
        
        # Create many sessions
        for _ in range(100):
            session = await provider.create_session(test_user)
            session_ids.add(session.session_id)
        
        # All IDs should be unique
        assert len(session_ids) == 100