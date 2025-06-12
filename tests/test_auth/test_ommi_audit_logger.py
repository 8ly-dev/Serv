"""
Tests for Ommi audit logger implementation.

Comprehensive test suite covering audit event logging, querying,
and cleanup operations for the Ommi-based audit logger.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from serv.auth.types import AuditEvent
from serv.bundled.auth.auditing.ommi_audit_logger import OmmiAuditLogger


class TestOmmiAuditLogger:
    """Test Ommi audit logger implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            "database_qualifier": "test_audit",
            "retention_days": 365,
            "max_event_size": 65536,
        }
        self.logger = OmmiAuditLogger(self.config)

    def test_init_with_valid_config(self):
        """Test initialization with valid configuration."""
        assert self.logger.database_qualifier == "test_audit"
        assert self.logger.retention_days == 365
        assert self.logger.max_event_size == 65536

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        logger = OmmiAuditLogger({})
        
        assert logger.database_qualifier == "audit"
        assert logger.retention_days == 365
        assert logger.max_event_size == 65536

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.injectable")
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.auto_inject")
    async def test_log_event_success(self, mock_auto_inject, mock_injectable):
        """Test successful event logging."""
        # Mock database and Ommi instance
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock successful add operation
        mock_result = AsyncMock()
        mock_saved_model = MagicMock()
        mock_saved_model.event_id = "test-event-id"
        mock_result.or_raise.return_value = [mock_saved_model]
        mock_ommi.add.return_value = mock_result
        
        # Create test event
        event = AuditEvent(
            event_id="test-event-id",
            event_type="authentication",
            user_id="test-user",
            session_id="test-session",
            timestamp=datetime.now(UTC),
            source_ip="192.168.1.1",
            user_agent="test-agent",
            resource="/api/login",
            action="POST",
            result="success",
            event_data={"username": "testuser"},
            metadata={"client": "web"},
        )
        
        # Test the method with dependency injection
        event_id = await self.logger.log_event(event, database=mock_database)
        
        assert event_id == "test-event-id"
        mock_database.get_connection.assert_called_once_with("test_audit")
        mock_ommi.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_event_no_database(self):
        """Test event logging fails without database service."""
        event = AuditEvent(
            event_type="test",
            user_id="test-user",
            timestamp=datetime.now(UTC),
            result="success",
        )
        
        with pytest.raises(RuntimeError, match="Database service not available"):
            await self.logger.log_event(event, database=None)

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.injectable")
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.auto_inject")
    async def test_log_event_truncates_large_data(self, mock_auto_inject, mock_injectable):
        """Test event data truncation for large events."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        mock_result = AsyncMock()
        mock_saved_model = MagicMock()
        mock_saved_model.event_id = "test-event-id"
        mock_result.or_raise.return_value = [mock_saved_model]
        mock_ommi.add.return_value = mock_result
        
        # Create event with large data
        large_data = {"large_field": "x" * 70000}  # Exceeds max_event_size
        event = AuditEvent(
            event_type="test",
            user_id="test-user",
            timestamp=datetime.now(UTC),
            result="success",
            event_data=large_data,
        )
        
        await self.logger.log_event(event, database=mock_database)
        
        # Verify that add was called and data was truncated
        mock_ommi.add.assert_called_once()
        call_args = mock_ommi.add.call_args[0][0]  # First positional argument
        
        # Event data should be truncated
        assert len(call_args.event_data) <= self.logger.max_event_size
        assert "[TRUNCATED]" in call_args.event_data
        
        # Metadata should indicate truncation
        import json
        metadata = json.loads(call_args.metadata)
        assert metadata.get("_truncated") is True

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.injectable")
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.auto_inject")
    async def test_query_events_success(self, mock_auto_inject, mock_injectable):
        """Test successful event querying."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock query result
        mock_query = AsyncMock()
        mock_result = AsyncMock()
        mock_event_iterator = AsyncMock()
        
        # Create mock event models
        mock_event_model1 = MagicMock()
        mock_event_model1.event_id = "event-1"
        mock_event_model1.event_type = "authentication"
        mock_event_model1.user_id = "user-1"
        mock_event_model1.session_id = "session-1"
        mock_event_model1.timestamp = datetime.now(UTC).isoformat()
        mock_event_model1.source_ip = "192.168.1.1"
        mock_event_model1.user_agent = "test-agent"
        mock_event_model1.resource = "/api/login"
        mock_event_model1.action = "POST"
        mock_event_model1.result = "success"
        mock_event_model1.event_data = '{"username": "user1"}'
        mock_event_model1.metadata = '{"client": "web"}'
        
        # Mock async iteration
        async def mock_aiter():
            yield mock_event_model1
        
        mock_event_iterator.__aiter__ = mock_aiter
        mock_result.or_raise.return_value = mock_event_iterator
        mock_query.all.return_value = mock_result
        mock_ommi.find.return_value = mock_query
        
        # Test query
        start_time = datetime.now(UTC) - timedelta(hours=1)
        events = await self.logger.query_events(
            start_time=start_time,
            user_id="user-1",
            event_type="authentication",
            limit=10,
            database=mock_database,
        )
        
        assert len(events) == 1
        assert events[0].event_id == "event-1"
        assert events[0].user_id == "user-1"
        assert events[0].event_type == "authentication"
        assert events[0].event_data == {"username": "user1"}
        assert events[0].metadata == {"client": "web"}

    @pytest.mark.asyncio
    async def test_query_events_no_database(self):
        """Test event querying fails without database service."""
        with pytest.raises(RuntimeError, match="Database service not available"):
            await self.logger.query_events(database=None)

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.injectable")
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.auto_inject")
    async def test_get_event_statistics(self, mock_auto_inject, mock_injectable):
        """Test getting event statistics."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock query and count
        mock_query = AsyncMock()
        mock_count_result = AsyncMock()
        mock_count_result.or_raise.return_value = 100
        mock_query.count.return_value = mock_count_result
        
        # Mock all events result
        mock_all_result = AsyncMock()
        mock_event_iterator = AsyncMock()
        
        # Mock events for statistics
        mock_event1 = MagicMock()
        mock_event1.event_type = "authentication"
        mock_event1.user_id = "user1"
        mock_event1.result = "success"
        
        mock_event2 = MagicMock()
        mock_event2.event_type = "authorization"
        mock_event2.user_id = "user1"
        mock_event2.result = "failure"
        
        async def mock_aiter():
            yield mock_event1
            yield mock_event2
        
        mock_event_iterator.__aiter__ = mock_aiter
        mock_all_result.or_raise.return_value = mock_event_iterator
        mock_query.all.return_value = mock_all_result
        mock_ommi.find.return_value = mock_query
        
        stats = await self.logger.get_event_statistics(database=mock_database)
        
        assert stats["total_events"] == 100
        assert stats["event_types"]["authentication"] == 1
        assert stats["event_types"]["authorization"] == 1
        assert stats["top_users"]["user1"] == 2
        assert stats["result_breakdown"]["success"] == 1
        assert stats["result_breakdown"]["failure"] == 1

    @pytest.mark.asyncio
    async def test_get_event_statistics_no_database(self):
        """Test statistics query fails without database service."""
        with pytest.raises(RuntimeError, match="Database service not available"):
            await self.logger.get_event_statistics(database=None)

    @pytest.mark.asyncio
    async def test_verify_log_integrity_success(self):
        """Test log integrity verification succeeds."""
        # Mock successful query
        with patch.object(self.logger, 'query_events', return_value=[]):
            result = await self.logger.verify_log_integrity()
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_log_integrity_failure(self):
        """Test log integrity verification fails on query error."""
        # Mock query failure
        with patch.object(self.logger, 'query_events', side_effect=Exception("DB error")):
            result = await self.logger.verify_log_integrity()
            assert result is False

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.injectable")
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.auto_inject")
    async def test_cleanup_old_events(self, mock_auto_inject, mock_injectable):
        """Test cleanup of old events."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock count query
        mock_count_query = AsyncMock()
        mock_count_result = AsyncMock()
        mock_count_result.or_raise.return_value = 50  # 50 events to delete
        mock_count_query.count.return_value = mock_count_result
        
        # Mock delete query
        mock_delete_query = AsyncMock()
        mock_delete_result = AsyncMock()
        mock_delete_result.or_raise.return_value = None
        mock_delete_query.delete.return_value = mock_delete_result
        
        # Mock find to return different queries for count and delete
        mock_ommi.find.side_effect = [mock_count_query, mock_delete_query]
        
        deleted_count = await self.logger.cleanup_old_events(database=mock_database)
        
        assert deleted_count == 50
        assert mock_ommi.find.call_count == 2  # Once for count, once for delete

    @pytest.mark.asyncio
    async def test_cleanup_old_events_no_database(self):
        """Test cleanup fails without database service."""
        with pytest.raises(RuntimeError, match="Database service not available"):
            await self.logger.cleanup_old_events(database=None)

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.injectable")
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.auto_inject")
    async def test_cleanup_old_events_none_to_delete(self, mock_auto_inject, mock_injectable):
        """Test cleanup when no events need to be deleted."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock count query returning 0
        mock_count_query = AsyncMock()
        mock_count_result = AsyncMock()
        mock_count_result.or_raise.return_value = 0
        mock_count_query.count.return_value = mock_count_result
        mock_ommi.find.return_value = mock_count_query
        
        deleted_count = await self.logger.cleanup_old_events(database=mock_database)
        
        assert deleted_count == 0
        # Should only call find once for count, not for delete
        assert mock_ommi.find.call_count == 1

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test logger cleanup."""
        # Should not raise any exceptions
        await self.logger.cleanup()

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.injectable")
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.auto_inject")
    async def test_log_event_generates_id_if_missing(self, mock_auto_inject, mock_injectable):
        """Test that event ID is generated if not provided."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        mock_result = AsyncMock()
        mock_saved_model = MagicMock()
        mock_result.or_raise.return_value = [mock_saved_model]
        mock_ommi.add.return_value = mock_result
        
        # Create event without event_id
        event = AuditEvent(
            event_type="test",
            user_id="test-user",
            timestamp=datetime.now(UTC),
            result="success",
        )
        
        # Mock UUID generation
        with patch("uuid.uuid4", return_value=MagicMock(spec=str)) as mock_uuid:
            mock_uuid.return_value.__str__ = lambda: "generated-uuid"
            mock_saved_model.event_id = "generated-uuid"
            
            event_id = await self.logger.log_event(event, database=mock_database)
            
            assert event_id == "generated-uuid"
            mock_uuid.assert_called_once()

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.injectable")
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.auto_inject")
    async def test_log_event_generates_timestamp_if_missing(self, mock_auto_inject, mock_injectable):
        """Test that timestamp is generated if not provided."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        mock_result = AsyncMock()
        mock_saved_model = MagicMock()
        mock_saved_model.event_id = "test-event-id"
        mock_result.or_raise.return_value = [mock_saved_model]
        mock_ommi.add.return_value = mock_result
        
        # Create event without timestamp
        event = AuditEvent(
            event_type="test",
            user_id="test-user",
            result="success",
            timestamp=None,
        )
        
        await self.logger.log_event(event, database=mock_database)
        
        # Verify that add was called with a timestamp
        mock_ommi.add.assert_called_once()
        call_args = mock_ommi.add.call_args[0][0]
        assert call_args.timestamp is not None

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.injectable")
    @patch("serv.bundled.auth.auditing.ommi_audit_logger.auto_inject")
    async def test_log_event_serializes_complex_data(self, mock_auto_inject, mock_injectable):
        """Test that complex event data is properly serialized."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        mock_result = AsyncMock()
        mock_saved_model = MagicMock()
        mock_saved_model.event_id = "test-event-id"
        mock_result.or_raise.return_value = [mock_saved_model]
        mock_ommi.add.return_value = mock_result
        
        # Create event with complex data structures
        complex_data = {
            "user": {"id": 123, "name": "Test User"},
            "settings": ["option1", "option2"],
            "metadata": {"nested": {"deep": "value"}},
        }
        complex_metadata = {"source": "api", "version": 2}
        
        event = AuditEvent(
            event_type="test",
            user_id="test-user",
            timestamp=datetime.now(UTC),
            result="success",
            event_data=complex_data,
            metadata=complex_metadata,
        )
        
        await self.logger.log_event(event, database=mock_database)
        
        # Verify data was serialized to JSON strings
        mock_ommi.add.assert_called_once()
        call_args = mock_ommi.add.call_args[0][0]
        
        import json
        # Should be able to parse back to original data
        assert json.loads(call_args.event_data) == complex_data
        assert json.loads(call_args.metadata) == complex_metadata

    def test_retention_calculation(self):
        """Test retention day calculation for cleanup."""
        # Test with different retention periods
        configs = [
            {"retention_days": 30},
            {"retention_days": 365},
            {"retention_days": 7},
        ]
        
        for config in configs:
            logger = OmmiAuditLogger(config)
            assert logger.retention_days == config["retention_days"]