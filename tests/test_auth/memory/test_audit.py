"""Tests for MemoryAuditProvider using abstract interface only."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from serv.auth.types import AuditEvent, AuditEventType
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
        "max_events": 10000,
        "auto_cleanup": True,
        "index_by_user": True,
        "index_by_session": True,
        "index_by_resource": True,
    }


@pytest.fixture
def provider(config, container):
    """Create a MemoryAuditProvider instance."""
    return MemoryAuditProvider(config, container)


class TestMemoryAuditProvider:
    """Test MemoryAuditProvider functionality using abstract interface."""

    @pytest.mark.asyncio
    async def test_store_audit_event_basic(self, provider):
        """Test basic audit event storage via interface."""
        event = AuditEvent(
            id="event_1",
            timestamp=datetime.now(),
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="test_user",
            session_id="test_session",
            resource="login",
            action="authenticate",
            result="success",
            metadata={"login_method": "password"},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        await provider.store_audit_event(event)
        
        # Verify event was stored by retrieving it
        events = await provider.get_audit_events(limit=1, offset=0)
        assert len(events) == 1
        assert events[0].id == "event_1"
        assert events[0].event_type == AuditEventType.LOGIN_SUCCESS

    @pytest.mark.asyncio
    async def test_get_audit_events_empty(self, provider):
        """Test getting audit events when none exist."""
        events = await provider.get_audit_events(limit=10, offset=0)
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_get_audit_events_multiple(self, provider):
        """Test getting multiple audit events."""
        # Store multiple events
        for i in range(3):
            event = AuditEvent(
                id=f"event_{i}",
                timestamp=datetime.now(),
                event_type=AuditEventType.LOGIN_SUCCESS,
                user_id=f"user_{i}",
                session_id=f"session_{i}",
                resource="login",
                action="authenticate",
                result="success",
                metadata={},
                ip_address="192.168.1.1",
                user_agent="Test Browser/1.0"
            )
            await provider.store_audit_event(event)
        
        # Get all events
        events = await provider.get_audit_events(limit=10, offset=0)
        assert len(events) == 3
        
        # Events should be sorted by timestamp (newest first)
        event_ids = [e.id for e in events]
        assert "event_0" in event_ids
        assert "event_1" in event_ids
        assert "event_2" in event_ids

    @pytest.mark.asyncio
    async def test_get_audit_events_pagination(self, provider):
        """Test audit event pagination."""
        # Store multiple events
        for i in range(5):
            event = AuditEvent(
                id=f"event_{i}",
                timestamp=datetime.now(),
                event_type=AuditEventType.LOGIN_SUCCESS,
                user_id=f"user_{i}",
                session_id=f"session_{i}",
                resource="login",
                action="authenticate",
                result="success",
                metadata={},
                ip_address="192.168.1.1",
                user_agent="Test Browser/1.0"
            )
            await provider.store_audit_event(event)
        
        # Test pagination
        page1 = await provider.get_audit_events(limit=2, offset=0)
        page2 = await provider.get_audit_events(limit=2, offset=2)
        page3 = await provider.get_audit_events(limit=2, offset=4)
        
        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1
        
        # Ensure no duplicates
        all_event_ids = set()
        for event in page1 + page2 + page3:
            all_event_ids.add(event.id)
        assert len(all_event_ids) == 5

    @pytest.mark.asyncio
    async def test_get_audit_events_time_range(self, provider):
        """Test getting audit events within time range."""
        base_time = datetime.now()
        
        # Store events at different times
        event1 = AuditEvent(
            id="event_1",
            timestamp=base_time - timedelta(hours=2),
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="user_1",
            session_id="session_1",
            resource="login",
            action="authenticate",
            result="success",
            metadata={},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        event2 = AuditEvent(
            id="event_2",
            timestamp=base_time - timedelta(hours=1),
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="user_2",
            session_id="session_2",
            resource="login",
            action="authenticate",
            result="success",
            metadata={},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        event3 = AuditEvent(
            id="event_3",
            timestamp=base_time,
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="user_3",
            session_id="session_3",
            resource="login",
            action="authenticate",
            result="success",
            metadata={},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        await provider.store_audit_event(event1)
        await provider.store_audit_event(event2)
        await provider.store_audit_event(event3)
        
        # Get events from last 90 minutes (should get event2 and event3)
        start_time = base_time - timedelta(minutes=90)
        events = await provider.get_audit_events(
            start_time=start_time,
            end_time=base_time + timedelta(minutes=1),
            limit=10,
            offset=0
        )
        
        assert len(events) == 2
        event_ids = {e.id for e in events}
        assert "event_2" in event_ids
        assert "event_3" in event_ids

    @pytest.mark.asyncio
    async def test_get_user_audit_events(self, provider):
        """Test getting audit events for specific user."""
        # Store events for different users
        event1 = AuditEvent(
            id="event_1",
            timestamp=datetime.now(),
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="target_user",
            session_id="session_1",
            resource="login",
            action="authenticate",
            result="success",
            metadata={},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        event2 = AuditEvent(
            id="event_2",
            timestamp=datetime.now(),
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="other_user",
            session_id="session_2",
            resource="login",
            action="authenticate",
            result="success",
            metadata={},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        event3 = AuditEvent(
            id="event_3",
            timestamp=datetime.now(),
            event_type=AuditEventType.USER_CREATED,
            user_id="target_user",
            session_id="session_3",
            resource="user",
            action="create",
            result="success",
            metadata={},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        await provider.store_audit_event(event1)
        await provider.store_audit_event(event2)
        await provider.store_audit_event(event3)
        
        # Get events for target_user only
        events = await provider.get_user_audit_events(
            user_id="target_user",
            limit=10,
            offset=0
        )
        
        assert len(events) == 2
        event_ids = {e.id for e in events}
        assert "event_1" in event_ids
        assert "event_3" in event_ids
        assert "event_2" not in event_ids  # Different user

    @pytest.mark.asyncio
    async def test_search_audit_events_by_type(self, provider):
        """Test searching audit events by event type."""
        # Store events of different types
        event1 = AuditEvent(
            id="event_1",
            timestamp=datetime.now(),
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="user_1",
            session_id="session_1",
            resource="login",
            action="authenticate",
            result="success",
            metadata={},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        event2 = AuditEvent(
            id="event_2",
            timestamp=datetime.now(),
            event_type=AuditEventType.LOGIN_FAILURE,
            user_id="user_2",
            session_id="session_2",
            resource="login",
            action="authenticate",
            result="failure",
            metadata={},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        event3 = AuditEvent(
            id="event_3",
            timestamp=datetime.now(),
            event_type=AuditEventType.USER_CREATED,
            user_id="user_3",
            session_id="session_3",
            resource="user",
            action="create",
            result="success",
            metadata={},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        await provider.store_audit_event(event1)
        await provider.store_audit_event(event2)
        await provider.store_audit_event(event3)
        
        # Search for login events only
        events = await provider.search_audit_events(
            event_types=[AuditEventType.LOGIN_SUCCESS, AuditEventType.LOGIN_FAILURE],
            limit=10,
            offset=0
        )
        
        assert len(events) == 2
        event_ids = {e.id for e in events}
        assert "event_1" in event_ids
        assert "event_2" in event_ids
        assert "event_3" not in event_ids  # Different type

    @pytest.mark.asyncio
    async def test_search_audit_events_by_user(self, provider):
        """Test searching audit events by user ID."""
        # Store events for different users
        event1 = AuditEvent(
            id="event_1",
            timestamp=datetime.now(),
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="target_user",
            session_id="session_1",
            resource="login",
            action="authenticate",
            result="success",
            metadata={},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        event2 = AuditEvent(
            id="event_2",
            timestamp=datetime.now(),
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="other_user",
            session_id="session_2",
            resource="login",
            action="authenticate",
            result="success",
            metadata={},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        await provider.store_audit_event(event1)
        await provider.store_audit_event(event2)
        
        # Search for events by specific user
        events = await provider.search_audit_events(
            user_id="target_user",
            limit=10,
            offset=0
        )
        
        assert len(events) == 1
        assert events[0].id == "event_1"
        assert events[0].user_id == "target_user"

    @pytest.mark.asyncio
    async def test_cleanup_old_events(self, provider):
        """Test cleanup of old audit events."""
        base_time = datetime.now()
        
        # Store old event
        old_event = AuditEvent(
            id="old_event",
            timestamp=base_time - timedelta(days=100),  # Very old
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="user_1",
            session_id="session_1",
            resource="login",
            action="authenticate",
            result="success",
            metadata={},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        # Store recent event
        recent_event = AuditEvent(
            id="recent_event",
            timestamp=base_time - timedelta(days=1),  # Recent
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="user_2",
            session_id="session_2",
            resource="login",
            action="authenticate",
            result="success",
            metadata={},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        await provider.store_audit_event(old_event)
        await provider.store_audit_event(recent_event)
        
        # Cleanup events older than 30 days
        cutoff_time = base_time - timedelta(days=30)
        count = await provider.cleanup_old_events(cutoff_time)
        
        assert count == 1  # Only old event should be removed
        
        # Verify recent event still exists
        events = await provider.get_audit_events(limit=10, offset=0)
        assert len(events) == 1
        assert events[0].id == "recent_event"

    @pytest.mark.asyncio
    async def test_search_audit_events_complex(self, provider):
        """Test complex audit event search with multiple filters."""
        base_time = datetime.now()
        
        # Store events with various properties
        event1 = AuditEvent(
            id="event_1",
            timestamp=base_time - timedelta(hours=1),
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="target_user",
            session_id="target_session",
            resource="login",
            action="authenticate",
            result="success",
            metadata={"method": "password"},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        event2 = AuditEvent(
            id="event_2",
            timestamp=base_time - timedelta(hours=2),
            event_type=AuditEventType.LOGIN_FAILURE,
            user_id="target_user",
            session_id="other_session",
            resource="login",
            action="authenticate",
            result="failure",
            metadata={"method": "password"},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        event3 = AuditEvent(
            id="event_3",
            timestamp=base_time - timedelta(hours=3),
            event_type=AuditEventType.USER_CREATED,
            user_id="other_user",
            session_id="target_session",
            resource="user",
            action="create",
            result="success",
            metadata={"role": "admin"},
            ip_address="192.168.1.1",
            user_agent="Test Browser/1.0"
        )
        
        await provider.store_audit_event(event1)
        await provider.store_audit_event(event2)
        await provider.store_audit_event(event3)
        
        # Complex search: login events for target_user
        events = await provider.search_audit_events(
            event_types=[AuditEventType.LOGIN_SUCCESS, AuditEventType.LOGIN_FAILURE],
            user_id="target_user",
            resource="login",
            start_time=base_time - timedelta(hours=6),
            end_time=base_time,
            limit=10,
            offset=0
        )
        
        assert len(events) == 2
        event_ids = {e.id for e in events}
        assert "event_1" in event_ids
        assert "event_2" in event_ids
        assert "event_3" not in event_ids  # Different user and type

    @pytest.mark.asyncio
    async def test_concurrent_audit_operations(self, provider):
        """Test concurrent audit operations don't cause race conditions."""
        async def store_event_worker(event_id):
            try:
                event = AuditEvent(
                    id=event_id,
                    timestamp=datetime.now(),
                    event_type=AuditEventType.LOGIN_SUCCESS,
                    user_id=f"user_{event_id}",
                    session_id=f"session_{event_id}",
                    resource="login",
                    action="authenticate",
                    result="success",
                    metadata={},
                    ip_address="192.168.1.1",
                    user_agent="Test Browser/1.0"
                )
                await provider.store_audit_event(event)
                return event_id
            except Exception:
                return None
        
        # Store multiple events concurrently
        tasks = []
        for i in range(10):
            event_id = f"event_{i}"
            tasks.append(store_event_worker(event_id))
        
        event_ids = await asyncio.gather(*tasks)
        
        # All events should be stored successfully
        assert all(event_id is not None for event_id in event_ids)
        assert len(set(event_ids)) == 10  # All should be unique
        
        # Verify all events were stored
        events = await provider.get_audit_events(limit=20, offset=0)
        assert len(events) == 10