"""Test cases for audit enforcement system."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from serv.auth.audit.events import AuditEventType
from serv.auth.audit.pipeline import AuditEventGroup, AuditPipeline, AuditPipelineSet
from serv.auth.audit.enforcement import AuditEmitter, AuditRequired
from serv.auth.audit.decorators import AuditEnforced, AuditEnforcedMeta
from serv.auth.types import AuditEvent
from serv.auth.exceptions import AuditError


class TestAuditEventType:
    """Test AuditEventType enum with operator overloading."""
    
    def test_event_type_values(self):
        """Test that event types have correct values."""
        assert AuditEventType.AUTH_ATTEMPT.value == "auth.attempt"
        assert AuditEventType.AUTH_SUCCESS.value == "auth.success"
        assert AuditEventType.SESSION_CREATE.value == "session.create"
    
    def test_or_operator_with_event_type(self):
        """Test OR operator between two event types."""
        group = AuditEventType.AUTH_SUCCESS | AuditEventType.AUTH_FAILURE
        
        assert isinstance(group, AuditEventGroup)
        assert len(group.events) == 2
        assert AuditEventType.AUTH_SUCCESS in group.events
        assert AuditEventType.AUTH_FAILURE in group.events
    
    def test_or_operator_with_group(self):
        """Test OR operator between event type and group."""
        group1 = AuditEventType.AUTH_SUCCESS | AuditEventType.AUTH_FAILURE
        group2 = AuditEventType.RATE_LIMIT_EXCEEDED | group1
        
        assert isinstance(group2, AuditEventGroup)
        assert len(group2.events) == 3
        assert AuditEventType.RATE_LIMIT_EXCEEDED in group2.events
    
    def test_rshift_operator_with_event_type(self):
        """Test >> operator between two event types."""
        pipeline = AuditEventType.AUTH_ATTEMPT >> AuditEventType.AUTH_SUCCESS
        
        assert isinstance(pipeline, AuditPipeline)
        assert len(pipeline.steps) == 2
        assert pipeline.steps[0] == AuditEventType.AUTH_ATTEMPT
        assert pipeline.steps[1] == AuditEventType.AUTH_SUCCESS
    
    def test_rshift_operator_with_pipeline(self):
        """Test >> operator extending existing pipeline."""
        pipeline1 = AuditEventType.AUTH_ATTEMPT >> AuditEventType.AUTH_SUCCESS
        pipeline2 = pipeline1 >> AuditEventType.SESSION_CREATE
        
        assert isinstance(pipeline2, AuditPipeline)
        assert len(pipeline2.steps) == 3
        assert pipeline2.steps[2] == AuditEventType.SESSION_CREATE


class TestAuditEventGroup:
    """Test AuditEventGroup functionality."""
    
    def test_group_creation(self):
        """Test creating an audit event group."""
        group = AuditEventGroup(AuditEventType.AUTH_SUCCESS, AuditEventType.AUTH_FAILURE)
        
        assert len(group.events) == 2
        assert AuditEventType.AUTH_SUCCESS in group.events
        assert AuditEventType.AUTH_FAILURE in group.events
    
    def test_group_matches(self):
        """Test group matching against event list."""
        group = AuditEventGroup(AuditEventType.AUTH_SUCCESS, AuditEventType.AUTH_FAILURE)
        
        # Should match if any group event is in the list
        assert group.matches([AuditEventType.AUTH_SUCCESS])
        assert group.matches([AuditEventType.AUTH_FAILURE])
        assert group.matches([AuditEventType.AUTH_ATTEMPT, AuditEventType.AUTH_SUCCESS])
        
        # Should not match if no group events are in the list
        assert not group.matches([AuditEventType.AUTH_ATTEMPT])
        assert not group.matches([])
    
    def test_group_or_with_event(self):
        """Test OR operation between group and event type."""
        group1 = AuditEventGroup(AuditEventType.AUTH_SUCCESS, AuditEventType.AUTH_FAILURE)
        group2 = group1 | AuditEventType.RATE_LIMIT_EXCEEDED
        
        assert len(group2.events) == 3
        assert AuditEventType.RATE_LIMIT_EXCEEDED in group2.events
    
    def test_group_pipeline_creation(self):
        """Test creating pipeline from group."""
        group = AuditEventGroup(AuditEventType.AUTH_SUCCESS, AuditEventType.AUTH_FAILURE)
        pipeline = group >> AuditEventType.SESSION_CREATE
        
        assert isinstance(pipeline, AuditPipeline)
        assert len(pipeline.steps) == 2
        assert pipeline.steps[0] == group
        assert pipeline.steps[1] == AuditEventType.SESSION_CREATE


class TestAuditPipeline:
    """Test AuditPipeline functionality."""
    
    def test_pipeline_creation(self):
        """Test creating an audit pipeline."""
        pipeline = AuditPipeline([
            AuditEventType.AUTH_ATTEMPT,
            AuditEventType.AUTH_SUCCESS,
            AuditEventType.SESSION_CREATE
        ])
        
        assert len(pipeline.steps) == 3
        assert pipeline.steps[0] == AuditEventType.AUTH_ATTEMPT
    
    def test_pipeline_validation_success(self):
        """Test successful pipeline validation."""
        pipeline = AuditPipeline([
            AuditEventType.AUTH_ATTEMPT,
            AuditEventType.AUTH_SUCCESS,
            AuditEventType.SESSION_CREATE
        ])
        
        events = [
            AuditEventType.AUTH_ATTEMPT,
            AuditEventType.AUTH_SUCCESS,
            AuditEventType.SESSION_CREATE
        ]
        
        assert pipeline.validates(events)
    
    def test_pipeline_validation_with_extra_events(self):
        """Test pipeline validation with extra events in between."""
        pipeline = AuditPipeline([
            AuditEventType.AUTH_ATTEMPT,
            AuditEventType.AUTH_SUCCESS
        ])
        
        events = [
            AuditEventType.AUTH_ATTEMPT,
            AuditEventType.CREDENTIAL_VERIFY,  # Extra event
            AuditEventType.AUTH_SUCCESS
        ]
        
        assert pipeline.validates(events)
    
    def test_pipeline_validation_failure(self):
        """Test failed pipeline validation."""
        pipeline = AuditPipeline([
            AuditEventType.AUTH_ATTEMPT,
            AuditEventType.AUTH_SUCCESS,
            AuditEventType.SESSION_CREATE
        ])
        
        # Missing SESSION_CREATE
        events = [
            AuditEventType.AUTH_ATTEMPT,
            AuditEventType.AUTH_SUCCESS
        ]
        
        assert not pipeline.validates(events)
    
    def test_pipeline_validation_with_group(self):
        """Test pipeline validation with event groups."""
        group = AuditEventGroup(AuditEventType.AUTH_SUCCESS, AuditEventType.AUTH_FAILURE)
        pipeline = AuditPipeline([AuditEventType.AUTH_ATTEMPT, group])
        
        # Should validate with AUTH_SUCCESS
        events1 = [AuditEventType.AUTH_ATTEMPT, AuditEventType.AUTH_SUCCESS]
        assert pipeline.validates(events1)
        
        # Should validate with AUTH_FAILURE
        events2 = [AuditEventType.AUTH_ATTEMPT, AuditEventType.AUTH_FAILURE]
        assert pipeline.validates(events2)
        
        # Should not validate without group event
        events3 = [AuditEventType.AUTH_ATTEMPT, AuditEventType.SESSION_CREATE]
        assert not pipeline.validates(events3)
    
    def test_pipeline_or_operation(self):
        """Test OR operation between pipelines."""
        pipeline1 = AuditPipeline([AuditEventType.AUTH_ATTEMPT, AuditEventType.AUTH_SUCCESS])
        pipeline2 = AuditPipeline([AuditEventType.AUTH_ATTEMPT, AuditEventType.AUTH_FAILURE])
        
        pipeline_set = pipeline1 | pipeline2
        
        assert isinstance(pipeline_set, AuditPipelineSet)
        assert len(pipeline_set.pipelines) == 2


class TestAuditPipelineSet:
    """Test AuditPipelineSet functionality."""
    
    def test_pipeline_set_validation(self):
        """Test pipeline set validation."""
        pipeline1 = AuditPipeline([AuditEventType.AUTH_ATTEMPT, AuditEventType.AUTH_SUCCESS])
        pipeline2 = AuditPipeline([AuditEventType.AUTH_ATTEMPT, AuditEventType.AUTH_FAILURE])
        
        pipeline_set = AuditPipelineSet([pipeline1, pipeline2])
        
        # Should validate events matching first pipeline
        events1 = [AuditEventType.AUTH_ATTEMPT, AuditEventType.AUTH_SUCCESS]
        assert pipeline_set.validates(events1)
        
        # Should validate events matching second pipeline
        events2 = [AuditEventType.AUTH_ATTEMPT, AuditEventType.AUTH_FAILURE]
        assert pipeline_set.validates(events2)
        
        # Should not validate events matching neither pipeline
        events3 = [AuditEventType.SESSION_CREATE]
        assert not pipeline_set.validates(events3)


class TestAuditEmitter:
    """Test AuditEmitter functionality."""
    
    def test_audit_emitter_creation(self):
        """Test creating an audit emitter."""
        emitter = AuditEmitter()
        
        assert len(emitter.events) == 0
        assert len(emitter.event_data) == 0
        assert emitter.sequence_id is not None
    
    @patch('serv.auth.audit.enforcement.AuditEmitter._store_audit_event')
    def test_audit_emitter_emit(self, mock_store):
        """Test emitting audit events."""
        emitter = AuditEmitter()
        
        data = {"user_id": "user123", "action": "login"}
        emitter.emit(AuditEventType.AUTH_ATTEMPT, data)
        
        assert len(emitter.events) == 1
        assert emitter.events[0] == AuditEventType.AUTH_ATTEMPT
        assert len(emitter.event_data) == 1
        assert emitter.event_data[0]["user_id"] == "user123"
        assert emitter.event_data[0]["sequence_id"] == emitter.sequence_id
        
        # Should call storage
        mock_store.assert_called_once()
    
    def test_audit_emitter_sequence_tracking(self):
        """Test sequence tracking in audit emitter."""
        emitter = AuditEmitter()
        
        emitter.emit(AuditEventType.AUTH_ATTEMPT)
        emitter.emit(AuditEventType.AUTH_SUCCESS)
        
        assert len(emitter.events) == 2
        assert emitter.event_data[0]["sequence_position"] == 1
        assert emitter.event_data[1]["sequence_position"] == 2
        
        # Same sequence ID for all events
        assert emitter.event_data[0]["sequence_id"] == emitter.event_data[1]["sequence_id"]


class TestAuditRequired:
    """Test AuditRequired decorator."""
    
    @patch('serv.auth.audit.enforcement.AuditEmitter._store_audit_event')
    def test_audit_required_simple(self, mock_store):
        """Test AuditRequired decorator with simple requirement."""
        
        @AuditRequired(AuditEventType.AUTH_ATTEMPT)
        async def simple_function(audit_emitter):
            audit_emitter.emit(AuditEventType.AUTH_ATTEMPT)
            return "success"
        
        # Should have audit pipeline stored
        assert hasattr(simple_function, '_audit_pipeline')
        assert simple_function._audit_pipeline == AuditEventType.AUTH_ATTEMPT
    
    @patch('serv.auth.audit.enforcement.AuditEmitter._store_audit_event')
    def test_audit_required_pipeline_success(self, mock_store):
        """Test AuditRequired decorator with pipeline that succeeds."""
        
        pipeline = AuditEventType.AUTH_ATTEMPT >> AuditEventType.AUTH_SUCCESS
        
        @AuditRequired(pipeline)
        async def auth_function(audit_emitter):
            audit_emitter.emit(AuditEventType.AUTH_ATTEMPT)
            audit_emitter.emit(AuditEventType.AUTH_SUCCESS)
            return "authenticated"
        
        # Function should work when pipeline is satisfied
        import asyncio
        result = asyncio.run(auth_function())
        assert result == "authenticated"
    
    @patch('serv.auth.audit.enforcement.AuditEmitter._store_audit_event')
    def test_audit_required_pipeline_failure(self, mock_store):
        """Test AuditRequired decorator with pipeline that fails."""
        
        pipeline = AuditEventType.AUTH_ATTEMPT >> AuditEventType.AUTH_SUCCESS
        
        @AuditRequired(pipeline)
        async def bad_auth_function(audit_emitter):
            audit_emitter.emit(AuditEventType.AUTH_ATTEMPT)
            # Missing AUTH_SUCCESS event
            return "should fail"
        
        # Function should raise AuditError when pipeline is not satisfied
        import asyncio
        with pytest.raises(AuditError, match="Audit pipeline requirement not satisfied"):
            asyncio.run(bad_auth_function())


class TestAuditEnforcedMeta:
    """Test AuditEnforcedMeta metaclass."""
    
    def test_audit_enforced_metaclass(self):
        """Test that AuditEnforcedMeta enforces audit requirements."""
        
        class TestProvider(metaclass=AuditEnforcedMeta):
            @AuditRequired(AuditEventType.AUTH_ATTEMPT)
            async def authenticate(self, audit_emitter):
                audit_emitter.emit(AuditEventType.AUTH_ATTEMPT)
                return True
        
        provider = TestProvider()
        assert hasattr(provider.authenticate, '_audit_pipeline')
    
    def test_audit_enforced_inheritance(self):
        """Test audit enforcement through inheritance."""
        
        class BaseProvider(AuditEnforced):
            @AuditRequired(AuditEventType.AUTH_ATTEMPT)
            async def authenticate(self, audit_emitter):
                audit_emitter.emit(AuditEventType.AUTH_ATTEMPT)
                return True
        
        class ConcreteProvider(BaseProvider):
            async def additional_method(self):
                return "no audit needed"
        
        provider = ConcreteProvider()
        assert hasattr(provider.authenticate, '_audit_pipeline')
        assert not hasattr(provider.additional_method, '_audit_pipeline')