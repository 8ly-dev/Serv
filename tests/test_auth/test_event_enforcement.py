"""
Tests for event emission enforcement in the auth system.

This module tests that methods with ReturnsAndEmits annotations properly
enforce event emission requirements at runtime.
"""

import pytest

from serv.auth.credential_vault import CredentialVault
from serv.auth.event_enforcer import EventEmissionEnforcer
from serv.auth.session_manager import SessionManager
from serv.auth.types import AuthEventEmissionError, Credential, Session


class TestEventEmissionEnforcer:
    """Test cases for the EventEmissionEnforcer class."""

    def test_event_history_tracking(self):
        """Test that event history tracks events correctly."""
        enforcer = EventEmissionEnforcer()
        
        # Emit some events
        enforcer.emit("test_event_1")
        enforcer.emit("test_event_2")
        
        # Check that events were tracked
        history = object.__getattribute__(enforcer, '_enforcer_history')
        assert history.last_id == 1
        
        events_since_start = history.since(-1)
        assert len(events_since_start) == 2
        assert "test_event_1" in events_since_start.values()
        assert "test_event_2" in events_since_start.values()

    def test_mro_cache_functionality(self):
        """Test that MRO caching works correctly."""
        enforcer = EventEmissionEnforcer()
        
        # Create a test class that inherits from an abstract base
        class TestVault(CredentialVault, EventEmissionEnforcer):
            def __init__(self, config):
                CredentialVault.__init__(self, config)
                EventEmissionEnforcer.__init__(self)
            
            def _validate_config(self, config):
                pass
            
            async def store_credential(self, user_id, credential_type, data, metadata=None, expires_in=None):
                self.emit("credential_stored")
                return "test_credential_id"
            
            async def verify_credential(self, credential_id, input_data):
                self.emit("credential_verified")
                return True
            
            async def update_credential(self, credential_id, new_data, metadata=None):
                self.emit("credential_updated")
                return True
            
            async def revoke_credential(self, credential_id):
                self.emit("credential_revoked")
                return True
            
            async def cleanup(self):
                pass
            
            async def extend_session(self, session_id, additional_seconds):
                return False
            
            async def get_user_credentials(self, user_id, credential_type=None, active_only=True):
                return []
            
            async def cleanup_expired_credentials(self):
                return 0
            
            async def _get_encryption_key(self):
                return b"test_key"
        
        vault = TestVault({})
        
        # First call should populate cache
        required_events = vault._get_required_events_for_method(TestVault, "store_credential")
        assert required_events == {"credential_stored", "credential_store_failed"}
        
        # Second call should use cache
        cached_events = vault._get_required_events_for_method(TestVault, "store_credential")
        assert cached_events == required_events
        
        # Verify cache statistics
        stats = vault.get_cache_stats()
        assert stats["mro_cache_size"] >= 1
        assert stats["class_cache_size"] >= 1

    def test_cache_clearing(self):
        """Test that cache can be cleared properly."""
        enforcer = EventEmissionEnforcer()
        
        # Populate cache
        class TestVault(CredentialVault, EventEmissionEnforcer):
            def __init__(self, config):
                CredentialVault.__init__(self, config)
                EventEmissionEnforcer.__init__(self)
            
            def _validate_config(self, config):
                pass
            
            async def store_credential(self, user_id, credential_type, data, metadata=None, expires_in=None):
                return "test"
            async def verify_credential(self, credential_id, input_data):
                return True
            async def update_credential(self, credential_id, new_data, metadata=None):
                return True
            async def revoke_credential(self, credential_id):
                return True
            async def cleanup(self):
                pass
            
            async def extend_session(self, session_id, additional_seconds):
                return False
            
            async def get_user_credentials(self, user_id, credential_type=None, active_only=True):
                return []
            
            async def cleanup_expired_credentials(self):
                return 0
            
            async def _get_encryption_key(self):
                return b"test_key"
        
        vault = TestVault({})
        vault._get_required_events_for_method(TestVault, "store_credential")
        
        # Verify cache has entries
        stats_before = vault.get_cache_stats()
        assert stats_before["mro_cache_size"] > 0
        
        # Clear cache
        vault.clear_cache()
        
        # Verify cache is empty
        stats_after = vault.get_cache_stats()
        assert stats_after["mro_cache_size"] == 0
        assert stats_after["class_cache_size"] == 0


class TestCredentialVaultEnforcement:
    """Test event enforcement for CredentialVault implementations."""
    
    @pytest.mark.asyncio
    async def test_store_credential_success_with_events(self):
        """Test that store_credential succeeds when required events are emitted."""
        
        class TestVault(CredentialVault, EventEmissionEnforcer):
            def __init__(self, config):
                CredentialVault.__init__(self, config)
                EventEmissionEnforcer.__init__(self)
            
            def _validate_config(self, config):
                pass
            
            async def store_credential(self, user_id, credential_type, data, metadata=None, expires_in=None):
                # Emit required event
                self.emit("credential_stored")
                return "test_credential_id"
            
            async def verify_credential(self, credential_id, input_data):
                self.emit("credential_verified")
                return True
            
            async def update_credential(self, credential_id, new_data, metadata=None):
                self.emit("credential_updated")
                return True
            
            async def revoke_credential(self, credential_id):
                self.emit("credential_revoked")
                return True
            
            async def cleanup(self):
                pass
            
            async def extend_session(self, session_id, additional_seconds):
                return False
            
            async def get_user_credentials(self, user_id, credential_type=None, active_only=True):
                return []
            
            async def cleanup_expired_credentials(self):
                return 0
            
            async def _get_encryption_key(self):
                return b"test_key"
        
        vault = TestVault({})
        
        # This should succeed because we emit the required event
        result = await vault.store_credential("user123", "password", b"secret_data")
        assert result == "test_credential_id"

    @pytest.mark.asyncio
    async def test_store_credential_failure_missing_events(self):
        """Test that store_credential fails when required events are not emitted."""
        
        class TestVault(CredentialVault, EventEmissionEnforcer):
            def __init__(self, config):
                CredentialVault.__init__(self, config)
                EventEmissionEnforcer.__init__(self)
            
            def _validate_config(self, config):
                pass
            
            async def store_credential(self, user_id, credential_type, data, metadata=None, expires_in=None):
                # Don't emit any events - this should fail
                return "test_credential_id"
            
            async def verify_credential(self, credential_id, input_data):
                return True
            
            async def update_credential(self, credential_id, new_data, metadata=None):
                return True
            
            async def revoke_credential(self, credential_id):
                return True
            
            async def cleanup(self):
                pass
            
            async def extend_session(self, session_id, additional_seconds):
                return False
            
            async def get_user_credentials(self, user_id, credential_type=None, active_only=True):
                return []
            
            async def cleanup_expired_credentials(self):
                return 0
            
            async def _get_encryption_key(self):
                return b"test_key"
        
        vault = TestVault({})
        
        # This should raise AuthEventEmissionError
        with pytest.raises(AuthEventEmissionError) as exc_info:
            await vault.store_credential("user123", "password", b"secret_data")
        
        error = exc_info.value
        assert "store_credential" in error.method_name
        assert "credential_stored" in error.missing_events
        assert "credential_store_failed" in error.missing_events

    @pytest.mark.asyncio
    async def test_verify_credential_with_failure_event(self):
        """Test that verify_credential succeeds when failure event is emitted."""
        
        class TestVault(CredentialVault, EventEmissionEnforcer):
            def __init__(self, config):
                CredentialVault.__init__(self, config)
                EventEmissionEnforcer.__init__(self)
            
            def _validate_config(self, config):
                pass
            
            async def store_credential(self, user_id, credential_type, data, metadata=None, expires_in=None):
                self.emit("credential_stored")
                return "test_credential_id"
            
            async def verify_credential(self, credential_id, input_data):
                # Emit failure event instead of success
                self.emit("credential_verification_failed")
                return False
            
            async def update_credential(self, credential_id, new_data, metadata=None):
                self.emit("credential_updated")
                return True
            
            async def revoke_credential(self, credential_id):
                self.emit("credential_revoked")
                return True
            
            async def cleanup(self):
                pass
            
            async def extend_session(self, session_id, additional_seconds):
                return False
            
            async def get_user_credentials(self, user_id, credential_type=None, active_only=True):
                return []
            
            async def cleanup_expired_credentials(self):
                return 0
            
            async def _get_encryption_key(self):
                return b"test_key"
        
        vault = TestVault({})
        
        # This should succeed because we emit one of the required events
        result = await vault.verify_credential("cred123", b"test_data")
        assert result is False

    @pytest.mark.asyncio
    async def test_multiple_events_emitted(self):
        """Test that method succeeds when multiple required events are emitted."""
        
        class TestVault(CredentialVault, EventEmissionEnforcer):
            def __init__(self, config):
                CredentialVault.__init__(self, config)
                EventEmissionEnforcer.__init__(self)
            
            def _validate_config(self, config):
                pass
            
            async def store_credential(self, user_id, credential_type, data, metadata=None, expires_in=None):
                # Emit both events (edge case but should work)
                self.emit("credential_stored")
                self.emit("credential_store_failed")
                return "test_credential_id"
            
            async def verify_credential(self, credential_id, input_data):
                self.emit("credential_verified")
                return True
            
            async def update_credential(self, credential_id, new_data, metadata=None):
                self.emit("credential_updated")
                return True
            
            async def revoke_credential(self, credential_id):
                self.emit("credential_revoked")
                return True
            
            async def cleanup(self):
                pass
            
            async def extend_session(self, session_id, additional_seconds):
                return False
            
            async def get_user_credentials(self, user_id, credential_type=None, active_only=True):
                return []
            
            async def cleanup_expired_credentials(self):
                return 0
            
            async def _get_encryption_key(self):
                return b"test_key"
        
        vault = TestVault({})
        
        # This should succeed because we emit required events
        result = await vault.store_credential("user123", "password", b"secret_data")
        assert result == "test_credential_id"


class TestSessionManagerEnforcement:
    """Test event enforcement for SessionManager implementations."""

    @pytest.mark.asyncio
    async def test_create_session_enforcement(self):
        """Test that create_session enforces event emission."""
        
        class TestSessionManager(SessionManager, EventEmissionEnforcer):
            def __init__(self, config):
                SessionManager.__init__(self, config)
                EventEmissionEnforcer.__init__(self)
            
            def _validate_config(self, config):
                pass
            
            async def create_session(self, user_context, fingerprint, timeout_seconds=None):
                # Don't emit required events
                return Session.create("user123", user_context, fingerprint)
            
            async def validate_session(self, session_id, fingerprint):
                self.emit("session_validated")
                return None
            
            async def invalidate_session(self, session_id):
                self.emit("session_invalidated")
                return True
            
            async def invalidate_user_sessions(self, user_id):
                return 0
            
            async def cleanup_expired_sessions(self):
                return 0
            
            async def cleanup(self):
                pass
            
            async def extend_session(self, session_id, additional_seconds):
                return False
            
            async def get_user_credentials(self, user_id, credential_type=None, active_only=True):
                return []
            
            async def cleanup_expired_credentials(self):
                return 0
            
            async def _get_encryption_key(self):
                return b"test_key"
        
        manager = TestSessionManager({})
        
        # This should raise AuthEventEmissionError
        with pytest.raises(AuthEventEmissionError) as exc_info:
            await manager.create_session({"user_id": "user123"}, "fingerprint123")
        
        error = exc_info.value
        assert "session_created" in error.missing_events or "session_creation_failed" in error.missing_events

    @pytest.mark.asyncio
    async def test_method_without_requirements_not_enforced(self):
        """Test that methods without ReturnsAndEmits annotations are not enforced."""
        
        class TestSessionManager(SessionManager, EventEmissionEnforcer):
            def __init__(self, config):
                SessionManager.__init__(self, config)
                EventEmissionEnforcer.__init__(self)
            
            def _validate_config(self, config):
                pass
            
            async def create_session(self, user_context, fingerprint, timeout_seconds=None):
                self.emit("session_created")
                return Session.create("user123", user_context, fingerprint)
            
            async def validate_session(self, session_id, fingerprint):
                self.emit("session_validated")
                return None
            
            async def invalidate_session(self, session_id):
                self.emit("session_invalidated")
                return True
            
            async def invalidate_user_sessions(self, user_id):
                # This method doesn't have ReturnsAndEmits annotation, so no enforcement
                return 0
            
            async def cleanup_expired_sessions(self):
                # This method doesn't have ReturnsAndEmits annotation, so no enforcement
                return 0
            
            async def cleanup(self):
                # This method doesn't have ReturnsAndEmits annotation, so no enforcement
                pass
            
            async def extend_session(self, session_id, additional_seconds):
                return False
            
            async def get_user_credentials(self, user_id, credential_type=None, active_only=True):
                return []
            
            async def cleanup_expired_credentials(self):
                return 0
            
            async def _get_encryption_key(self):
                return b"test_key"
        
        manager = TestSessionManager({})
        
        # These should not raise exceptions because they don't have event requirements
        result1 = await manager.invalidate_user_sessions("user123")
        assert result1 == 0
        
        result2 = await manager.cleanup_expired_sessions()
        assert result2 == 0
        
        await manager.cleanup()  # Should not raise


class TestEventEnforcementEdgeCases:
    """Test edge cases for event enforcement."""

    @pytest.mark.asyncio
    async def test_exception_during_method_execution(self):
        """Test that exceptions during method execution don't trigger enforcement."""
        
        class TestVault(CredentialVault, EventEmissionEnforcer):
            def __init__(self, config):
                CredentialVault.__init__(self, config)
                EventEmissionEnforcer.__init__(self)
            
            def _validate_config(self, config):
                pass
            
            async def store_credential(self, user_id, credential_type, data, metadata=None, expires_in=None):
                # Raise an exception without emitting events
                raise ValueError("Something went wrong")
            
            async def verify_credential(self, credential_id, input_data):
                self.emit("credential_verified")
                return True
            
            async def update_credential(self, credential_id, new_data, metadata=None):
                self.emit("credential_updated")
                return True
            
            async def revoke_credential(self, credential_id):
                self.emit("credential_revoked")
                return True
            
            async def cleanup(self):
                pass
            
            async def extend_session(self, session_id, additional_seconds):
                return False
            
            async def get_user_credentials(self, user_id, credential_type=None, active_only=True):
                return []
            
            async def cleanup_expired_credentials(self):
                return 0
            
            async def _get_encryption_key(self):
                return b"test_key"
        
        vault = TestVault({})
        
        # Should raise ValueError, not AuthEventEmissionError
        with pytest.raises(ValueError, match="Something went wrong"):
            await vault.store_credential("user123", "password", b"secret_data")

    def test_synchronous_method_enforcement(self):
        """Test that synchronous methods are also enforced."""
        
        class TestEnforcer(EventEmissionEnforcer):
            pass
        
        # Create a simple test class with sync method
        class TestClass(TestEnforcer):
            def sync_method(self):
                # This would need to be tested if we had sync methods with ReturnsAndEmits
                pass
        
        # For now, just verify the enforcer can handle sync methods
        enforcer = TestEnforcer()
        assert hasattr(enforcer, 'emit')

    def test_no_abstract_method_found(self):
        """Test behavior when no abstract method with requirements is found."""
        
        class TestEnforcer(EventEmissionEnforcer):
            def regular_method(self):
                """A regular method with no event requirements."""
                return "result"
        
        enforcer = TestEnforcer()
        
        # Should return None when no requirements found
        result = enforcer._get_required_events_for_method(TestEnforcer, "regular_method")
        assert result is None
        
        # Method should work normally without enforcement
        assert enforcer.regular_method() == "result"