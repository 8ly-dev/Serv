"""
Session security tests.

These tests verify session management security including device fingerprinting,
session hijacking protection, and session lifecycle security.

⚠️  WARNING: These tests simulate session-based attacks.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from serv.auth import Session
from serv.auth.utils import generate_device_fingerprint, validate_session_fingerprint


class MockRequest:
    """Mock request for testing device fingerprinting."""

    def __init__(self, headers: dict[str, str] = None, client_host: str = "127.0.0.1"):
        self.headers = headers or {}
        self.client = MockClient(client_host)

    def get_header(self, name: str, default: str = "") -> str:
        return self.headers.get(name.lower(), default)


class MockClient:
    """Mock client for testing."""

    def __init__(self, host: str):
        self.host = host


class TestDeviceFingerprintingSecurity:
    """Test device fingerprinting security measures."""

    def test_device_fingerprint_generation(self):
        """Test device fingerprint generation from request headers."""
        # Create mock request with typical browser headers
        request = MockRequest(
            headers={
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "accept-language": "en-US,en;q=0.9",
                "accept-encoding": "gzip, deflate, br",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

        # Generate fingerprint
        fingerprint = generate_device_fingerprint(request)

        # Should be a consistent hex string
        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 64  # SHA256 hex length
        assert all(c in "0123456789abcdef" for c in fingerprint)

    def test_device_fingerprint_consistency(self):
        """Test that identical requests produce identical fingerprints."""
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "accept-language": "en-US,en;q=0.9,es;q=0.8",
            "accept-encoding": "gzip, deflate",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        request1 = MockRequest(headers=headers, client_host="192.168.1.100")
        request2 = MockRequest(headers=headers, client_host="192.168.1.100")

        fp1 = generate_device_fingerprint(request1)
        fp2 = generate_device_fingerprint(request2)

        assert fp1 == fp2, "Identical requests should produce identical fingerprints"

    def test_device_fingerprint_sensitivity(self):
        """Test that fingerprints change with different device characteristics."""
        base_headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "accept-language": "en-US,en;q=0.9",
            "accept-encoding": "gzip, deflate",
            "accept": "text/html,application/xhtml+xml",
        }

        base_request = MockRequest(headers=base_headers, client_host="192.168.1.100")
        base_fp = generate_device_fingerprint(base_request)

        # Test different user agents
        modified_headers = base_headers.copy()
        modified_headers["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        modified_request = MockRequest(
            headers=modified_headers, client_host="192.168.1.100"
        )
        modified_fp = generate_device_fingerprint(modified_request)

        assert base_fp != modified_fp, (
            "Different user agents should produce different fingerprints"
        )

        # Test different IP addresses
        different_ip_request = MockRequest(
            headers=base_headers, client_host="10.0.0.50"
        )
        different_ip_fp = generate_device_fingerprint(different_ip_request)

        assert base_fp != different_ip_fp, (
            "Different IP addresses should produce different fingerprints"
        )

        # Test different languages
        lang_headers = base_headers.copy()
        lang_headers["accept-language"] = "fr-FR,fr;q=0.9,en;q=0.8"
        lang_request = MockRequest(headers=lang_headers, client_host="192.168.1.100")
        lang_fp = generate_device_fingerprint(lang_request)

        assert base_fp != lang_fp, (
            "Different languages should produce different fingerprints"
        )

    def test_device_fingerprint_missing_headers(self):
        """Test fingerprint generation with missing headers."""
        # Request with minimal headers
        minimal_request = MockRequest(headers={}, client_host="127.0.0.1")
        minimal_fp = generate_device_fingerprint(minimal_request)

        # Should still generate a valid fingerprint
        assert isinstance(minimal_fp, str)
        assert len(minimal_fp) == 64

        # Request with some headers
        partial_request = MockRequest(
            headers={"user-agent": "TestAgent/1.0"}, client_host="127.0.0.1"
        )
        partial_fp = generate_device_fingerprint(partial_request)

        # Should be different from minimal
        assert minimal_fp != partial_fp

    def test_fingerprint_validation_strict_mode(self):
        """Test strict fingerprint validation."""
        stored_fp = "abc123def456"

        # Exact match should validate
        assert (
            validate_session_fingerprint(stored_fp, "abc123def456", strict=True) is True
        )

        # Different fingerprint should fail
        assert (
            validate_session_fingerprint(stored_fp, "different456", strict=True)
            is False
        )

        # Empty values should fail
        assert validate_session_fingerprint("", "abc123def456", strict=True) is False
        assert validate_session_fingerprint("abc123def456", "", strict=True) is False
        assert validate_session_fingerprint("", "", strict=True) is False

    def test_fingerprint_validation_non_strict_mode(self):
        """Test non-strict fingerprint validation."""
        stored_fp = "abc123def456"

        # Currently non-strict mode still requires exact match
        # This could be extended for fuzzy matching in the future
        assert (
            validate_session_fingerprint(stored_fp, "abc123def456", strict=False)
            is True
        )
        assert (
            validate_session_fingerprint(stored_fp, "different456", strict=False)
            is False
        )


class TestSessionSecurityLifecycle:
    """Test session security throughout the lifecycle."""

    def test_session_creation_security(self, sample_user_context):
        """Test secure session creation."""
        fingerprint = "secure_device_fingerprint_123"

        session = Session.create(
            user_id=sample_user_context["user_id"],
            user_context=sample_user_context,
            device_fingerprint=fingerprint,
        )

        # Session should have secure properties
        assert len(session.session_id) > 30  # Cryptographically secure length
        assert (
            session.session_id != sample_user_context["user_id"]
        )  # Not derived from user ID
        assert session.device_fingerprint == fingerprint
        assert not session.is_expired()

        # Timestamps should be logical
        assert session.created_at <= session.last_activity <= session.expires_at

    def test_session_expiration_security(self, sample_user_context):
        """Test session expiration behavior."""
        fingerprint = "test_fingerprint"

        # Create session with short timeout
        session = Session.create(
            user_id=sample_user_context["user_id"],
            user_context=sample_user_context,
            device_fingerprint=fingerprint,
            timeout_seconds=1,  # 1 second
        )

        # Should not be expired immediately
        assert not session.is_expired()

        # Manually set expiration to past (simulating time passage)
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)

        # Should now be expired
        assert session.is_expired()

    def test_session_activity_refresh(self, sample_user_context):
        """Test session activity refresh security."""
        fingerprint = "test_fingerprint"

        session = Session.create(
            user_id=sample_user_context["user_id"],
            user_context=sample_user_context,
            device_fingerprint=fingerprint,
        )

        original_activity = session.last_activity

        # Wait a small amount and refresh
        import time

        time.sleep(0.01)
        session.refresh_activity()

        # Activity should be updated
        assert session.last_activity > original_activity

    def test_session_context_immutability(self, sample_user_context):
        """Test that session context is protected from modification."""
        fingerprint = "test_fingerprint"
        original_context = sample_user_context.copy()

        session = Session.create(
            user_id=sample_user_context["user_id"],
            user_context=sample_user_context,
            device_fingerprint=fingerprint,
        )

        # Modify the original context
        sample_user_context["malicious_field"] = "injected_value"

        # Session context should be unaffected (defensive copy)
        assert "malicious_field" not in session.user_context
        assert session.user_context == original_context

    @pytest.mark.asyncio
    async def test_concurrent_session_access(
        self, mock_session_manager, sample_user_context
    ):
        """Test session security under concurrent access."""
        fingerprint = "concurrent_test_fp"

        # Create a session
        session = await mock_session_manager.create_session(
            sample_user_context, fingerprint
        )

        # Simulate concurrent validation attempts
        async def validate_session():
            return await mock_session_manager.validate_session(
                session.session_id, fingerprint
            )

        # Run multiple concurrent validations
        tasks = [validate_session() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed and return valid sessions
        assert all(result is not None for result in results)
        assert all(result.session_id == session.session_id for result in results)


class TestSessionHijackingProtection:
    """Test protection against session hijacking attacks."""

    @pytest.mark.asyncio
    async def test_device_fingerprint_binding(
        self, mock_session_manager, sample_user_context
    ):
        """Test that sessions are bound to device fingerprints."""
        original_fingerprint = "legitimate_device_fp"
        attacker_fingerprint = "attacker_device_fp"

        # Create session with original device
        session = await mock_session_manager.create_session(
            sample_user_context, original_fingerprint
        )

        # Legitimate device should be able to validate
        legitimate_result = await mock_session_manager.validate_session(
            session.session_id, original_fingerprint
        )
        assert legitimate_result is not None
        assert legitimate_result.session_id == session.session_id

        # Attacker with different fingerprint should fail
        attacker_result = await mock_session_manager.validate_session(
            session.session_id, attacker_fingerprint
        )
        assert attacker_result is None

    @pytest.mark.asyncio
    async def test_session_id_prediction_resistance(
        self, mock_session_manager, sample_user_context
    ):
        """Test that session IDs are unpredictable."""
        fingerprint = "test_fingerprint"

        # Create multiple sessions
        sessions = []
        for i in range(20):
            user_context = sample_user_context.copy()
            user_context["user_id"] = f"user_{i}"

            session = await mock_session_manager.create_session(
                user_context, fingerprint
            )
            sessions.append(session)

        session_ids = [s.session_id for s in sessions]

        # All session IDs should be unique
        assert len(set(session_ids)) == len(session_ids)

        # Session IDs should not follow predictable patterns
        for i in range(1, len(session_ids)):
            # Should not be sequential
            assert session_ids[i] != session_ids[i - 1]

            # Should not contain user information
            user_id = f"user_{i}"
            assert user_id not in session_ids[i]

            # Should not be simple increments
            assert not session_ids[i].endswith(str(i))

    @pytest.mark.asyncio
    async def test_session_fixation_protection(
        self, mock_session_manager, sample_user_context
    ):
        """Test protection against session fixation attacks."""
        fingerprint = "test_fingerprint"

        # Simulate attacker trying to fixate a session ID
        # In a real attack, attacker would try to force a specific session ID

        # Create legitimate session
        legitimate_session = await mock_session_manager.create_session(
            sample_user_context, fingerprint
        )

        # Create another session (should get different ID)
        another_session = await mock_session_manager.create_session(
            sample_user_context, fingerprint
        )

        # Session IDs should be different (generated, not fixable)
        assert legitimate_session.session_id != another_session.session_id

        # Both sessions should be valid independently
        result1 = await mock_session_manager.validate_session(
            legitimate_session.session_id, fingerprint
        )
        result2 = await mock_session_manager.validate_session(
            another_session.session_id, fingerprint
        )

        assert result1 is not None
        assert result2 is not None
        assert result1.session_id != result2.session_id

    @pytest.mark.asyncio
    async def test_session_invalidation_completeness(
        self, mock_session_manager, sample_user_context
    ):
        """Test that session invalidation is complete and immediate."""
        fingerprint = "test_fingerprint"

        # Create session
        session = await mock_session_manager.create_session(
            sample_user_context, fingerprint
        )

        # Verify session is valid
        valid_result = await mock_session_manager.validate_session(
            session.session_id, fingerprint
        )
        assert valid_result is not None

        # Invalidate session
        invalidation_success = await mock_session_manager.invalidate_session(
            session.session_id
        )
        assert invalidation_success is True

        # Session should be immediately invalid
        invalid_result = await mock_session_manager.validate_session(
            session.session_id, fingerprint
        )
        assert invalid_result is None

        # Multiple invalidation attempts should be safe
        second_invalidation = await mock_session_manager.invalidate_session(
            session.session_id
        )
        # Should return False (already invalidated) but not error
        assert second_invalidation is False

    @pytest.mark.asyncio
    async def test_cross_user_session_isolation(self, mock_session_manager):
        """Test that users cannot access each other's sessions."""
        fingerprint = "shared_fingerprint"

        # Create sessions for different users
        user1_context = {"user_id": "user_1", "username": "alice"}
        user2_context = {"user_id": "user_2", "username": "bob"}

        session1 = await mock_session_manager.create_session(user1_context, fingerprint)
        session2 = await mock_session_manager.create_session(user2_context, fingerprint)

        # Each user should only be able to access their own session
        user1_result = await mock_session_manager.validate_session(
            session1.session_id, fingerprint
        )
        user2_result = await mock_session_manager.validate_session(
            session2.session_id, fingerprint
        )

        assert user1_result.user_id == "user_1"
        assert user2_result.user_id == "user_2"

        # Users should not be able to access each other's sessions
        # (This would be enforced by checking user_id in a real implementation)
        assert user1_result.session_id != user2_result.session_id
        assert user1_result.user_context["username"] == "alice"
        assert user2_result.user_context["username"] == "bob"


class TestSessionCleanupSecurity:
    """Test session cleanup and maintenance security."""

    @pytest.mark.asyncio
    async def test_expired_session_cleanup(
        self, mock_session_manager, sample_user_context
    ):
        """Test that expired sessions are properly cleaned up."""
        fingerprint = "test_fingerprint"

        # Create sessions with different timeouts
        short_session = await mock_session_manager.create_session(
            sample_user_context, fingerprint, timeout_seconds=1
        )
        long_session = await mock_session_manager.create_session(
            sample_user_context, fingerprint, timeout_seconds=3600
        )

        # Force short session to expire
        short_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        mock_session_manager.sessions[short_session.session_id] = short_session

        # Run cleanup
        cleaned_count = await mock_session_manager.cleanup_expired_sessions()

        # Should have cleaned up the expired session
        assert cleaned_count == 1

        # Expired session should be gone
        expired_result = await mock_session_manager.validate_session(
            short_session.session_id, fingerprint
        )
        assert expired_result is None

        # Valid session should remain
        valid_result = await mock_session_manager.validate_session(
            long_session.session_id, fingerprint
        )
        assert valid_result is not None

    @pytest.mark.asyncio
    async def test_user_session_cleanup_security(self, mock_session_manager):
        """Test that user session cleanup doesn't affect other users."""
        fingerprint = "test_fingerprint"

        # Create sessions for multiple users
        user1_context = {"user_id": "user_1", "username": "alice"}
        user2_context = {"user_id": "user_2", "username": "bob"}

        # User 1 has multiple sessions
        user1_session1 = await mock_session_manager.create_session(
            user1_context, fingerprint
        )
        user1_session2 = await mock_session_manager.create_session(
            user1_context, "other_fp"
        )

        # User 2 has one session
        user2_session = await mock_session_manager.create_session(
            user2_context, fingerprint
        )

        # Invalidate all sessions for user 1
        invalidated_count = await mock_session_manager.invalidate_user_sessions(
            "user_1"
        )

        # Should have invalidated 2 sessions for user 1
        assert invalidated_count == 2

        # User 1 sessions should be invalid
        user1_result1 = await mock_session_manager.validate_session(
            user1_session1.session_id, fingerprint
        )
        user1_result2 = await mock_session_manager.validate_session(
            user1_session2.session_id, "other_fp"
        )
        assert user1_result1 is None
        assert user1_result2 is None

        # User 2 session should still be valid
        user2_result = await mock_session_manager.validate_session(
            user2_session.session_id, fingerprint
        )
        assert user2_result is not None
        assert user2_result.user_id == "user_2"
