"""Tests for MemoryAuditProvider."""

import asyncio
import json
import time
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from serv.auth.audit.events import AuditEventType
from serv.auth.types import AuditEvent, PolicyResult
from serv.bundled.auth.memory.audit import MemoryAuditProvider
from bevy import Container, get_registry


@pytest.fixture
def container():
    """Create a test container."""
    return Container(get_registry())


@pytest.fixture
def config():
    """Create test configuration."""
    return {
        "cleanup_interval": 0.1,
        "retention_days": 90,
        "max_events": 100000,
        "include_sensitive_data": False,
    }


@pytest.fixture
def provider(config, container):
    """Create a MemoryAuditProvider instance."""
    return MemoryAuditProvider(config, container)


class TestMemoryAuditProvider:
    """Test MemoryAuditProvider functionality."""

    @pytest.mark.asyncio
    async def test_record_event_basic(self, provider):
        """Test basic event recording."""
        event = await provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            user_id="test_user",
            session_id="test_session",
            resource="login",
            action="authenticate",
            result="success",
            metadata={"login_method": "password"},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        assert isinstance(event, AuditEvent)
        assert event.event_type == AuditEventType.AUTH_SUCCESS
        assert event.user_id == "test_user"
        assert event.session_id == "test_session"
        assert event.resource == "login"
        assert event.action == "authenticate"
        assert event.result == PolicyResult.ALLOW
        assert event.metadata["login_method"] == "password"
        assert event.ip_address == "192.168.1.1"
        assert event.user_agent == "Test Browser/1.0"
        assert event.id is not None
        assert event.timestamp is not None

    @pytest.mark.asyncio
    async def test_record_event_minimal(self, provider):
        """Test recording event with minimal parameters."""
        event = await provider.record_event(
            event_type=AuditEventType.AUTH_ATTEMPT
        )
        
        assert event.event_type == AuditEventType.AUTH_ATTEMPT
        assert event.user_id is None
        assert event.session_id is None
        assert event.metadata is not None

    @pytest.mark.asyncio
    async def test_get_event(self, provider):
        """Test getting a specific event."""
        event = await provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            user_id="test_user"
        )
        
        retrieved = await provider.get_event(event.id)
        assert retrieved is not None
        assert retrieved.id == event.id
        assert retrieved.event_type == event.event_type
        assert retrieved.user_id == event.user_id

    @pytest.mark.asyncio
    async def test_get_event_nonexistent(self, provider):
        """Test getting non-existent event."""
        result = await provider.get_event("nonexistent_event_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_query_events_by_user(self, provider):
        """Test querying events by user ID."""
        # Create events for different users
        await provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            user_id="user1"
        )
        
        await provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            user_id="user2"
        )
        
        await provider.record_event(
            event_type=AuditEventType.AUTH_FAILURE,
            user_id="user1"
        )
        
        # Query events for user1
        events = await provider.query_events(user_id="user1")
        assert len(events) == 2
        assert all(e.user_id == "user1" for e in events)

    @pytest.mark.asyncio
    async def test_query_events_by_type(self, provider):
        """Test querying events by type."""
        # Create different types of events
        await provider.record_event(event_type=AuditEventType.AUTH_SUCCESS)
        await provider.record_event(event_type=AuditEventType.AUTH_FAILURE)
        await provider.record_event(event_type=AuditEventType.AUTH_SUCCESS)
        
        # Query for AUTH_SUCCESS events
        events = await provider.query_events(
            event_types=[AuditEventType.AUTH_SUCCESS]
        )
        assert len(events) == 2
        assert all(e.event_type == AuditEventType.AUTH_SUCCESS for e in events)

    @pytest.mark.asyncio
    async def test_query_events_by_time_range(self, provider):
        """Test querying events by time range."""
        start_time = time.time()
        
        # Create event before range
        await provider.record_event(event_type=AuditEventType.AUTH_SUCCESS)
        
        # Wait a bit
        await asyncio.sleep(0.01)
        query_start = time.time()
        
        # Create events in range
        await provider.record_event(event_type=AuditEventType.AUTH_FAILURE)
        await provider.record_event(event_type=AuditEventType.AUTH_SUCCESS)
        
        query_end = time.time()
        await asyncio.sleep(0.01)
        
        # Create event after range
        await provider.record_event(event_type=AuditEventType.AUTH_SUCCESS)
        
        # Query events in time range
        events = await provider.query_events(
            start_time=query_start,
            end_time=query_end
        )
        
        # Should get the 2 events in the range
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_query_events_with_pagination(self, provider):
        """Test event querying with pagination."""
        # Create multiple events
        for i in range(10):
            await provider.record_event(
                event_type=AuditEventType.AUTH_SUCCESS,
                user_id=f"user_{i}"
            )
        
        # Query with pagination
        page1 = await provider.query_events(limit=5, offset=0)
        assert len(page1) == 5
        
        page2 = await provider.query_events(limit=5, offset=5)
        assert len(page2) == 5
        
        # Events should be different (ordered by timestamp)
        page1_ids = {e.id for e in page1}
        page2_ids = {e.id for e in page2}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_get_user_events(self, provider):
        """Test getting events for a specific user."""
        user_id = "test_user"
        
        # Create events for the user
        await provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            user_id=user_id
        )
        
        await provider.record_event(
            event_type=AuditEventType.SESSION_CREATE,
            user_id=user_id
        )
        
        # Create event for different user
        await provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            user_id="other_user"
        )
        
        events = await provider.get_user_events(user_id)
        assert len(events) == 2
        assert all(e.user_id == user_id for e in events)

    @pytest.mark.asyncio
    async def test_get_session_events(self, provider):
        """Test getting events for a specific session."""
        session_id = "test_session"
        
        # Create events for the session
        await provider.record_event(
            event_type=AuditEventType.SESSION_CREATE,
            session_id=session_id
        )
        
        await provider.record_event(
            event_type=AuditEventType.SESSION_ACCESS,
            session_id=session_id
        )
        
        events = await provider.get_session_events(session_id)
        assert len(events) == 2
        assert all(e.session_id == session_id for e in events)

    @pytest.mark.asyncio
    async def test_get_events_by_category(self, provider):
        """Test getting events by category."""
        # Create authentication events
        await provider.record_event(event_type=AuditEventType.AUTH_SUCCESS)
        await provider.record_event(event_type=AuditEventType.AUTH_FAILURE)
        
        # Create authorization events
        await provider.record_event(event_type=AuditEventType.AUTHZ_GRANT)
        
        # Create user management events
        await provider.record_event(event_type=AuditEventType.USER_CREATE)
        
        # Query authentication events
        auth_events = await provider.get_events_by_category("authentication")
        assert len(auth_events) == 2
        assert all(e.event_type in [AuditEventType.AUTH_SUCCESS, AuditEventType.AUTH_FAILURE] 
                  for e in auth_events)
        
        # Query authorization events
        authz_events = await provider.get_events_by_category("authorization")
        assert len(authz_events) == 1
        assert authz_events[0].event_type == AuditEventType.AUTHZ_GRANT

    @pytest.mark.asyncio
    async def test_get_failed_events(self, provider):
        """Test getting failed/denied events."""
        # Create various events
        await provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            result="success"
        )
        
        await provider.record_event(
            event_type=AuditEventType.AUTH_FAILURE,
            result="failure"
        )
        
        await provider.record_event(
            event_type=AuditEventType.AUTHZ_DENY,
            result="denied"
        )
        
        await provider.record_event(
            event_type=AuditEventType.SESSION_CREATE,
            result="success"
        )
        
        failed_events = await provider.get_failed_events()
        assert len(failed_events) == 2
        
        # Should include AUTH_FAILURE and AUTHZ_DENY
        event_types = {e.event_type for e in failed_events}
        assert AuditEventType.AUTH_FAILURE in event_types
        assert AuditEventType.AUTHZ_DENY in event_types

    @pytest.mark.asyncio
    async def test_get_security_events(self, provider):
        """Test getting security-relevant events."""
        # Create various events including security events
        await provider.record_event(event_type=AuditEventType.AUTH_SUCCESS)
        await provider.record_event(event_type=AuditEventType.AUTH_FAILURE)
        await provider.record_event(event_type=AuditEventType.AUTHZ_DENY)
        await provider.record_event(event_type=AuditEventType.SECURITY_VIOLATION)
        await provider.record_event(event_type=AuditEventType.SESSION_CREATE)
        
        security_events = await provider.get_security_events()
        
        # Should include security-relevant events
        security_types = {e.event_type for e in security_events}
        assert AuditEventType.AUTH_FAILURE in security_types
        assert AuditEventType.AUTHZ_DENY in security_types
        assert AuditEventType.SECURITY_VIOLATION in security_types
        assert AuditEventType.AUTH_SUCCESS not in security_types
        assert AuditEventType.SESSION_CREATE not in security_types

    @pytest.mark.asyncio
    async def test_cleanup_old_events(self, config, container):
        """Test cleanup of old events."""
        config["retention_days"] = 0.001  # Very short retention for testing
        provider = MemoryAuditProvider(config, container)
        
        # Create some events
        for i in range(5):
            await provider.record_event(
                event_type=AuditEventType.AUTH_SUCCESS,
                user_id=f"user_{i}"
            )
        
        # Wait for events to expire
        await asyncio.sleep(0.1)
        
        # Manual cleanup
        cleaned_count = await provider.cleanup_old_events()
        assert cleaned_count == 5
        
        # Events should be gone
        events = await provider.query_events()
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_export_events_json(self, provider):
        """Test exporting events to JSON format."""
        # Create some events
        event1 = await provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            user_id="user1",
            metadata={"method": "password"}
        )
        
        event2 = await provider.record_event(
            event_type=AuditEventType.AUTH_FAILURE,
            user_id="user2",
            ip_address="192.168.1.1"
        )
        
        # Export events
        exported = await provider.export_events(format="json")
        
        # Parse JSON
        data = json.loads(exported)
        assert isinstance(data, list)
        assert len(data) == 2
        
        # Check event data
        exported_ids = {event["event_id"] for event in data}
        assert event1.id in exported_ids
        assert event2.id in exported_ids

    @pytest.mark.asyncio
    async def test_export_events_unsupported_format(self, provider):
        """Test exporting events with unsupported format."""
        await provider.record_event(event_type=AuditEventType.AUTH_SUCCESS)
        
        with pytest.raises(ValueError, match="Unsupported export format: xml"):
            await provider.export_events(format="xml")

    @pytest.mark.asyncio
    async def test_get_statistics(self, provider):
        """Test getting audit provider statistics."""
        # Initially empty
        stats = await provider.get_statistics()
        assert stats["total_events"] == 0
        
        # Create some events
        await provider.record_event(event_type=AuditEventType.AUTH_SUCCESS)
        await provider.record_event(event_type=AuditEventType.AUTH_FAILURE)
        await provider.record_event(event_type=AuditEventType.AUTH_SUCCESS)
        await provider.record_event(event_type=AuditEventType.USER_CREATE)
        
        stats = await provider.get_statistics()
        assert stats["total_events"] == 4
        assert stats["event_type_counts"]["auth.success"] == 2
        assert stats["event_type_counts"]["auth.failure"] == 1
        assert stats["event_type_counts"]["user.create"] == 1

    @pytest.mark.asyncio
    async def test_event_indexing(self, provider):
        """Test that events are properly indexed for efficient querying."""
        user_id = "test_user"
        event_type = AuditEventType.AUTH_SUCCESS
        
        # Create event
        event = await provider.record_event(
            event_type=event_type,
            user_id=user_id
        )
        
        # Check user index
        user_key = f"user_{user_id}"
        user_events = provider.store.get("user_index", user_key)
        assert user_events is not None
        assert event.id in user_events
        
        # Check type index
        type_key = f"type_{event_type.value}"
        type_events = provider.store.get("type_index", type_key)
        assert type_events is not None
        assert event.id in type_events
        
        # Check time index
        hour_bucket = int(event.timestamp.timestamp() // 3600)
        time_key = f"time_{hour_bucket}"
        time_events = provider.store.get("time_index", time_key)
        assert time_events is not None
        assert event.id in time_events

    @pytest.mark.asyncio
    async def test_event_ttl_and_retention(self, config, container):
        """Test event TTL and retention policies."""
        config["retention_days"] = 0.01  # Very short retention
        provider = MemoryAuditProvider(config, container)
        
        # Create event
        event = await provider.record_event(event_type=AuditEventType.AUTH_SUCCESS)
        
        # Event should exist initially
        retrieved = await provider.get_event(event.id)
        assert retrieved is not None
        
        # Wait for TTL expiration
        await asyncio.sleep(0.01 * 24 * 3600 + 0.1)  # retention + buffer
        
        # Event should be gone due to TTL
        retrieved = await provider.get_event(event.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_max_events_enforcement(self, config, container):
        """Test maximum events limit enforcement."""
        config["max_events"] = 5  # Very low limit for testing
        provider = MemoryAuditProvider(config, container)
        
        # Create more events than the limit
        events = []
        for i in range(10):
            event = await provider.record_event(
                event_type=AuditEventType.AUTH_SUCCESS,
                user_id=f"user_{i}"
            )
            events.append(event)
        
        # Should have only max_events + buffer
        total_events = provider.store.size("events")
        assert total_events <= 6  # max_events + some buffer

    @pytest.mark.asyncio
    async def test_sensitive_data_sanitization(self, config, container):
        """Test sanitization of sensitive data."""
        config["include_sensitive_data"] = False
        provider = MemoryAuditProvider(config, container)
        
        # Create event with sensitive metadata
        event = await provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            metadata={
                "password": "secret123",
                "token": "abc123def456",
                "safe_data": "this is safe",
                "long_string": "x" * 150  # Will be truncated
            }
        )
        
        # Sensitive data should be redacted
        assert event.metadata["password"] == "[REDACTED]"
        assert event.metadata["token"] == "[REDACTED]" 
        assert event.metadata["safe_data"] == "this is safe"
        assert event.metadata["long_string"].endswith("...")

    @pytest.mark.asyncio
    async def test_sensitive_data_included(self, config, container):
        """Test keeping sensitive data when configured."""
        config["include_sensitive_data"] = True
        provider = MemoryAuditProvider(config, container)
        
        # Create event with sensitive metadata
        event = await provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            metadata={
                "password": "secret123",
                "safe_data": "this is safe"
            }
        )
        
        # Sensitive data should be preserved
        assert event.metadata["password"] == "secret123"
        assert event.metadata["safe_data"] == "this is safe"

    @pytest.mark.asyncio
    async def test_severity_determination(self, provider):
        """Test event severity determination."""
        # Test different severity levels
        auth_failure = await provider.record_event(
            event_type=AuditEventType.AUTH_FAILURE
        )
        assert auth_failure.metadata["severity"] == "warning"
        
        auth_success = await provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS
        )
        assert auth_success.metadata["severity"] == "low"
        
        error_event = await provider.record_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            result="error"
        )
        assert error_event.metadata["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_concurrent_event_recording(self, provider):
        """Test concurrent event recording."""
        import asyncio
        
        async def record_event_worker(worker_id):
            try:
                event = await provider.record_event(
                    event_type=AuditEventType.AUTH_SUCCESS,
                    user_id=f"user_{worker_id}",
                    metadata={"worker": worker_id}
                )
                return event.id
            except Exception:
                return None
        
        # Record events concurrently
        tasks = [record_event_worker(i) for i in range(20)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        successful = [r for r in results if r is not None]
        assert len(successful) == 20
        
        # All event IDs should be unique
        assert len(set(successful)) == 20

    @pytest.mark.asyncio
    async def test_cleanup_lifecycle(self, provider):
        """Test cleanup task lifecycle."""
        await provider._ensure_cleanup_started()
        assert provider._cleanup_started is True
        
        # Starting again should be idempotent
        await provider._ensure_cleanup_started()
        assert provider._cleanup_started is True

    @pytest.mark.asyncio
    async def test_event_counter_uniqueness(self, provider):
        """Test that event counter ensures unique IDs."""
        # Record events rapidly
        events = []
        for _ in range(100):
            event = await provider.record_event(event_type=AuditEventType.AUTH_SUCCESS)
            events.append(event)
        
        # All event IDs should be unique
        event_ids = [e.id for e in events]
        assert len(set(event_ids)) == 100

    @pytest.mark.asyncio
    async def test_time_range_querying_efficiency(self, provider):
        """Test efficient time-range querying using time index."""
        # Create events over time
        events_by_hour = {}
        current_time = time.time()
        
        for hour_offset in range(5):
            # Simulate events from different hours
            event_time = current_time - (hour_offset * 3600)
            
            # Manually set time for testing
            event = await provider.record_event(
                event_type=AuditEventType.AUTH_SUCCESS,
                user_id=f"user_hour_{hour_offset}"
            )
            
            hour_bucket = int(event_time // 3600)
            if hour_bucket not in events_by_hour:
                events_by_hour[hour_bucket] = []
            events_by_hour[hour_bucket].append(event.id)
        
        # Query recent events (should use time index efficiently)
        recent_start = current_time - 3600  # Last hour
        recent_events = await provider.query_events(start_time=recent_start)
        
        # Should get events from recent time period
        assert len(recent_events) > 0