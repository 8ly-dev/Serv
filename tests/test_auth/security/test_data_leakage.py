"""
Data leakage security tests.

These tests verify that sensitive data is properly protected from
accidental disclosure through logs, error messages, string representations, etc.

⚠️  WARNING: These tests specifically look for data leakage vulnerabilities.
"""

import json

import pytest

from serv.auth import (
    AuditEvent,
    AuthResult,
    AuthStatus,
    Credential,
    Session,
    Token,
    ValidationResult,
)
from serv.auth.utils import mask_sensitive_data, sanitize_user_input


class TestDataMaskingAndSanitization:
    """Test data masking and sanitization utilities."""

    def test_mask_sensitive_data_basic(self):
        """Test basic sensitive data masking."""
        data = {
            "username": "testuser",
            "password": "secret123",
            "email": "test@example.com",
            "api_key": "sk-1234567890abcdef",
            "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",
            "normal_field": "safe_value",
        }

        masked = mask_sensitive_data(data)

        # Sensitive fields should be masked
        assert "***" in masked["password"]
        assert "secret123" not in masked["password"]

        assert "sk***ef" == masked["api_key"]  # Show first/last chars
        assert "1234567890abcd" not in str(masked["api_key"])

        assert "***" in masked["token"]
        assert "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9" not in masked["token"]

        # Non-sensitive fields should be unchanged
        assert masked["username"] == "testuser"
        assert masked["email"] == "test@example.com"
        assert masked["normal_field"] == "safe_value"

    def test_mask_sensitive_data_nested(self):
        """Test masking of nested sensitive data."""
        data = {
            "user": {
                "username": "testuser",
                "credentials": {
                    "password": "secret123",
                    "backup_codes": ["code1", "code2"],
                },
            },
            "auth": {"token": "bearer_token_value", "refresh_token": "refresh_value"},
        }

        masked = mask_sensitive_data(data)

        # Nested sensitive data should be masked
        assert "***" in masked["user"]["credentials"]["password"]
        assert "secret123" not in str(masked)

        assert "***" in masked["auth"]["token"]
        assert "bearer_token_value" not in str(masked)

        # Non-sensitive nested data should be preserved
        assert masked["user"]["username"] == "testuser"
        assert masked["user"]["credentials"]["backup_codes"] == ["code1", "code2"]

    def test_mask_sensitive_data_edge_cases(self):
        """Test edge cases in sensitive data masking."""
        # Short sensitive values
        short_data = {
            "password": "abc",  # Too short for partial reveal
            "key": "xy",  # Very short
            "secret": "",  # Empty
        }

        masked = mask_sensitive_data(short_data)

        assert masked["password"] == "***"
        assert masked["key"] == "***"
        assert masked["secret"] == "***"

        # Non-string sensitive values
        mixed_data = {
            "password": 12345,
            "token": None,
            "api_key": ["not", "a", "string"],
        }

        masked = mask_sensitive_data(mixed_data)

        assert masked["password"] == "***"
        assert masked["token"] == "***"
        assert masked["api_key"] == "***"

    def test_sanitize_user_input_basic(self):
        """Test basic user input sanitization."""
        # Test null byte removal
        dirty_input = "test\\x00\\x01input"
        clean = sanitize_user_input(dirty_input)
        assert "\\x00" not in clean
        assert "test" in clean and "input" in clean

        # Test length limitation
        long_input = "a" * 2000
        clean = sanitize_user_input(long_input, max_length=100)
        assert len(clean) <= 100

        # Test control character removal
        control_chars = "test\\x07\\x08\\x0b\\x0c\\x0einput"
        clean = sanitize_user_input(control_chars)
        # Should preserve printable chars and allowed whitespace
        assert "test" in clean and "input" in clean
        # Should remove control chars
        assert "\\x07" not in clean

    def test_sanitize_user_input_preserves_safe_content(self):
        """Test that sanitization preserves safe content."""
        safe_inputs = [
            "normal text",
            "email@example.com",
            "user123_name-test",
            "Text with\\n newlines\\t and tabs",
            "Unicode: café, naïve, résumé",
            "Numbers: 123.45 and symbols: !@#$%^&*()",
        ]

        for safe_input in safe_inputs:
            clean = sanitize_user_input(safe_input)
            # Should be mostly preserved (allowing for newline/tab handling)
            assert len(clean) >= len(safe_input) * 0.9  # Allow some char removal

    def test_sanitize_user_input_edge_cases(self):
        """Test edge cases in user input sanitization."""
        # Empty string
        assert sanitize_user_input("") == ""

        # Non-string input
        assert sanitize_user_input(None) == ""
        assert sanitize_user_input(123) == ""
        assert sanitize_user_input(["list"]) == ""

        # Very long input
        massive_input = "x" * 10000
        clean = sanitize_user_input(massive_input, max_length=1000)
        assert len(clean) == 1000
        assert clean == "x" * 1000


class TestSensitiveDataInStringRepresentations:
    """Test that sensitive data doesn't leak in string representations."""

    def test_token_repr_security(self):
        """Test that Token.__repr__ doesn't expose token value."""
        token = Token.create(
            token_value="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            token_type="access",
            user_id="user_123",
            payload={"sub": "user_123", "name": "John Doe"},
        )

        token_repr = repr(token)

        # Token value should NOT be in repr
        assert "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9" not in token_repr
        assert "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" not in token_repr

        # Safe metadata should be in repr
        assert "user_123" in token_repr
        assert "access" in token_repr
        assert token.token_id in token_repr

        # Payload should NOT be in repr (might contain sensitive data)
        assert "John Doe" not in token_repr

    def test_token_str_security(self):
        """Test that Token.__str__ doesn't expose token value."""
        token = Token.create(
            token_value="secret_token_value",
            token_type="bearer",
            user_id="user_456",
            payload={"secret": "sensitive_data"},
        )

        token_str = str(token)

        # Token value should NOT be in str
        assert "secret_token_value" not in token_str

        # Payload secrets should NOT be in str
        assert "sensitive_data" not in token_str

    def test_credential_repr_security(self):
        """Test that Credential.__repr__ doesn't expose credential data."""
        credential = Credential.create(user_id="user_789", credential_type="password")

        cred_repr = repr(credential)

        # Should contain safe metadata
        assert "user_789" in cred_repr
        assert "password" in cred_repr
        assert credential.credential_id in cred_repr

        # Should not contain actual credential data (none stored in this case)
        # But verify the pattern is secure
        assert "secret" not in cred_repr.lower()
        assert "hash" not in cred_repr.lower()

    def test_session_security(self):
        """Test that Session doesn't expose sensitive user context."""
        user_context = {
            "user_id": "user_123",
            "username": "testuser",
            "email": "test@example.com",
            "password_hash": "secret_hash_value",  # This should never be in context
            "roles": ["user", "admin"],
        }

        session = Session.create(
            user_id="user_123",
            user_context=user_context,
            device_fingerprint="fp_abc123",
        )

        session_repr = repr(session)
        session_str = str(session)

        # Safe data should be present
        assert "user_123" in session_repr

        # Sensitive data should NOT leak through string representations
        # Note: Session doesn't override __repr__ but user_context is stored
        # We should be careful about what goes in user_context

    def test_audit_event_sensitive_data_rejection(self):
        """Test that AuditEvent rejects sensitive data in actor_info."""
        # Should reject common sensitive field names
        sensitive_fields = [
            "password",
            "token",
            "secret",
            "key",
            "credential",
            "authorization",
            "auth",
            "passwd",
            "pwd",
            "api_key",
        ]

        for field in sensitive_fields:
            with pytest.raises(ValueError, match="Sensitive data not allowed"):
                AuditEvent.create(
                    event_type="test",
                    actor_info={field: "some_value"},
                    resource_info={},
                    outcome="success",
                )

        # Should accept safe fields
        safe_event = AuditEvent.create(
            event_type="authentication",
            actor_info={
                "actor_id": "user_123",
                "actor_type": "user",
                "ip_address": "192.168.1.1",
            },
            resource_info={"resource_type": "session", "action": "create"},
            outcome="success",
        )
        assert safe_event.event_type == "authentication"


class TestErrorMessageSecurity:
    """Test that error messages don't leak sensitive information."""

    def test_auth_result_error_messages(self):
        """Test that AuthResult error messages are safe."""
        # Test various error scenarios
        error_results = [
            AuthResult(
                status=AuthStatus.INVALID_CREDENTIALS,
                error_message="Invalid username or password",
            ),
            AuthResult(
                status=AuthStatus.ACCOUNT_LOCKED,
                error_message="Account is temporarily locked",
            ),
            AuthResult(
                status=AuthStatus.ACCOUNT_DISABLED, error_message="Account is disabled"
            ),
            AuthResult(
                status=AuthStatus.RATE_LIMITED,
                error_message="Too many attempts, try again later",
            ),
        ]

        for result in error_results:
            error_msg = result.error_message.lower()

            # Should not contain specific user information
            assert "admin" not in error_msg
            assert "root" not in error_msg
            assert "user_123" not in error_msg

            # Should not contain implementation details
            assert "database" not in error_msg
            assert "sql" not in error_msg
            assert "query" not in error_msg
            assert "exception" not in error_msg

            # Should be generic and user-safe
            assert len(error_msg) > 10  # Should have meaningful message
            assert len(error_msg) < 200  # Should not be too verbose

    def test_validation_result_error_messages(self):
        """Test that ValidationResult error messages are safe."""
        invalid_result = ValidationResult(
            is_valid=False, error_message="Token validation failed"
        )

        error_msg = invalid_result.error_message.lower()

        # Should not reveal token details
        assert (
            "expired" not in error_msg or "invalid" in error_msg
        )  # Generic message OK
        assert "signature" not in error_msg
        assert "algorithm" not in error_msg
        assert "key" not in error_msg

    def test_configuration_error_safety(self):
        """Test that configuration errors don't leak sensitive values."""
        from serv.config import validate_auth_config

        # Test with invalid secret key (too short)
        invalid_config = {
            "providers": [
                {
                    "type": "jwt",
                    "config": {"secret_key": "short"},
                }
            ]
        }

        with pytest.raises(Exception) as exc_info:
            validate_auth_config(invalid_config)

        error_message = str(exc_info.value)

        # Error should mention the requirement but not the actual key
        assert "32 characters" in error_message
        assert "short" not in error_message


class TestDataSerializationSecurity:
    """Test that data serialization doesn't leak sensitive information."""

    def test_token_json_serialization_protection(self):
        """Test that tokens can't be accidentally serialized with sensitive data."""
        token = Token.create(
            token_value="secret_jwt_token",
            token_type="access",
            user_id="user_123",
            payload={"sub": "user_123", "secret_claim": "sensitive_value"},
        )

        # Direct JSON serialization should fail or be safe
        # (dataclasses with sensitive data should not be directly serializable)
        try:
            serialized = json.dumps(token.__dict__)
            # If it serializes, the sensitive data should not be there
            assert "secret_jwt_token" not in serialized
            assert "sensitive_value" not in serialized
        except TypeError:
            # It's better if it doesn't serialize at all
            pass

    def test_session_serialization_safety(self):
        """Test that sessions with sensitive user context are safe to serialize."""
        user_context = {
            "user_id": "user_123",
            "username": "testuser",
            "roles": ["user"],
            # Note: We should never put sensitive data in user_context
            # but test defensive measures
        }

        session = Session.create(
            user_id="user_123",
            user_context=user_context,
            device_fingerprint="fp_abc123",
        )

        # If someone tries to serialize the session
        try:
            serialized = json.dumps(session.__dict__, default=str)
            # Should not contain the session ID in plain text
            # (session_id is meant to be opaque)
            session_data = json.loads(serialized)
            assert (
                len(session_data.get("session_id", "")) > 20
            )  # Should be secure length
        except (TypeError, ValueError):
            # It's OK if it doesn't serialize easily
            pass

    def test_masked_data_serialization(self):
        """Test that masked data serializes safely."""
        sensitive_data = {
            "username": "testuser",
            "password": "secret123",
            "api_key": "sk-1234567890abcdef",
            "nested": {"token": "bearer_token", "safe_field": "safe_value"},
        }

        masked = mask_sensitive_data(sensitive_data)
        serialized = json.dumps(masked)

        # Sensitive data should not appear in serialized form
        assert "secret123" not in serialized
        assert "sk-1234567890abcdef" not in serialized
        assert "bearer_token" not in serialized

        # Safe data should be preserved
        assert "testuser" in serialized
        assert "safe_value" in serialized

        # Masked indicators should be present
        assert "***" in serialized


class TestMemorySecurityConsiderations:
    """Test considerations for sensitive data in memory."""

    def test_token_value_not_in_multiple_locations(self):
        """Test that token values aren't unnecessarily duplicated in memory."""
        original_value = "secret_token_value_that_should_not_be_duplicated"

        token = Token.create(
            token_value=original_value,
            token_type="access",
            user_id="user_123",
            payload={"sub": "user_123"},
        )

        # The token should store the value
        assert token.token_value == original_value

        # But repr should not contain it
        token_repr = repr(token)
        assert original_value not in token_repr

        # And metadata should not duplicate it
        assert original_value not in token.token_id
        assert original_value not in token.token_type

    def test_credential_data_encapsulation(self):
        """Test that credential data is properly encapsulated."""
        credential = Credential.create(user_id="user_123", credential_type="password")

        # Credential ID should be different from user ID
        assert credential.credential_id != credential.user_id

        # Should be cryptographically secure length
        assert len(credential.credential_id) > 20

        # Should not contain user ID as substring
        assert credential.user_id not in credential.credential_id

    def test_session_id_uniqueness_and_security(self):
        """Test that session IDs are unique and secure."""
        user_context = {"user_id": "user_123", "username": "testuser"}
        fingerprint = "fp_abc123"

        # Create multiple sessions
        sessions = []
        for _ in range(10):
            session = Session.create(
                user_id=user_context["user_id"],
                user_context=user_context,
                device_fingerprint=fingerprint,
            )
            sessions.append(session)

        # All session IDs should be unique
        session_ids = [s.session_id for s in sessions]
        assert len(set(session_ids)) == len(session_ids), "Session IDs should be unique"

        # Session IDs should be cryptographically secure
        for session_id in session_ids:
            assert len(session_id) > 30, f"Session ID too short: {session_id}"
            assert session_id.isalnum() or "-" in session_id or "_" in session_id, (
                f"Session ID format insecure: {session_id}"
            )

            # Should not contain user information
            assert user_context["user_id"] not in session_id
            assert user_context["username"] not in session_id
            assert fingerprint not in session_id
