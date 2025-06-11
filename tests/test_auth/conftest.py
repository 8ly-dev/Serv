"""
Pytest configuration and shared fixtures for auth tests.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from serv.auth import (
    AuditEvent,
    AuthProvider,
    AuthResult,
    AuthStatus,
    RefreshResult,
    Session,
    SessionManager,
    Token,
    ValidationResult,
)


class MockAuthProvider(AuthProvider):
    """Mock authentication provider for testing."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config or {})
        self.auth_attempts = []
        self.validation_attempts = []
        self.refresh_attempts = []

    def _validate_config(self, config: dict[str, Any]) -> None:
        # Mock validation - accepts any config
        pass

    async def initiate_auth(self, request_context: dict[str, Any]) -> AuthResult:
        self.auth_attempts.append(request_context)

        # Simulate different outcomes based on context
        username = request_context.get("username")
        password = request_context.get("password")

        if username == "valid_user" and password == "correct_password":
            return AuthResult(
                status=AuthStatus.SUCCESS,
                user_id="user_123",
                user_context={"username": username, "role": "user"},
            )
        elif username == "locked_user":
            return AuthResult(
                status=AuthStatus.ACCOUNT_LOCKED, error_message="Account is locked"
            )
        elif username == "disabled_user":
            return AuthResult(
                status=AuthStatus.ACCOUNT_DISABLED, error_message="Account is disabled"
            )
        else:
            return AuthResult(
                status=AuthStatus.INVALID_CREDENTIALS,
                error_message="Invalid username or password",
            )

    async def validate_credential(
        self, credential_payload: dict[str, Any]
    ) -> ValidationResult:
        self.validation_attempts.append(credential_payload)

        token = credential_payload.get("credential")
        if token == "valid_token":
            return ValidationResult(
                is_valid=True,
                user_id="user_123",
                user_context={"username": "valid_user", "role": "user"},
            )
        else:
            return ValidationResult(is_valid=False, error_message="Invalid token")

    async def refresh_session(self, session_data: dict[str, Any]) -> RefreshResult:
        self.refresh_attempts.append(session_data)

        refresh_token = session_data.get("refresh_token")
        if refresh_token == "valid_refresh":
            return RefreshResult(
                success=True,
                new_token="new_access_token",
                metadata={"token_type": "bearer"},
            )
        else:
            return RefreshResult(success=False, error_message="Invalid refresh token")

    async def cleanup(self) -> None:
        self.auth_attempts.clear()
        self.validation_attempts.clear()
        self.refresh_attempts.clear()


class MockSessionManager(SessionManager):
    """Mock session manager for testing."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config or {})
        self.sessions = {}
        self.create_attempts = []
        self.validation_attempts = []

    def _validate_config(self, config: dict[str, Any]) -> None:
        pass

    async def create_session(
        self,
        user_context: dict[str, Any],
        fingerprint: str,
        timeout_seconds: int | None = None,
    ) -> Session:
        self.create_attempts.append(
            {
                "user_context": user_context,
                "fingerprint": fingerprint,
                "timeout_seconds": timeout_seconds,
            }
        )

        session = Session.create(
            user_id=user_context["user_id"],
            user_context=user_context,
            device_fingerprint=fingerprint,
            timeout_seconds=timeout_seconds or 3600,
        )

        self.sessions[session.session_id] = session
        return session

    async def validate_session(
        self, session_id: str, fingerprint: str
    ) -> Session | None:
        self.validation_attempts.append(
            {"session_id": session_id, "fingerprint": fingerprint}
        )

        session = self.sessions.get(session_id)
        if (
            session
            and not session.is_expired()
            and session.device_fingerprint == fingerprint
        ):
            session.refresh_activity()
            return session
        return None

    async def invalidate_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    async def invalidate_user_sessions(self, user_id: str) -> int:
        count = 0
        to_remove = []
        for session_id, session in self.sessions.items():
            if session.user_id == user_id:
                to_remove.append(session_id)
                count += 1

        for session_id in to_remove:
            del self.sessions[session_id]

        return count

    async def cleanup_expired_sessions(self) -> int:
        count = 0
        to_remove = []
        for session_id, session in self.sessions.items():
            if session.is_expired():
                to_remove.append(session_id)
                count += 1

        for session_id in to_remove:
            del self.sessions[session_id]

        return count

    async def extend_session(self, session_id: str, additional_seconds: int) -> bool:
        session = self.sessions.get(session_id)
        if session and not session.is_expired():
            # Extend the session expiration time
            session.expires_at = datetime.fromtimestamp(
                session.expires_at.timestamp() + additional_seconds, UTC
            )
            return True
        return False

    async def cleanup(self) -> None:
        self.sessions.clear()
        self.create_attempts.clear()
        self.validation_attempts.clear()


@pytest.fixture
def mock_auth_provider():
    """Provide a mock authentication provider for testing."""
    return MockAuthProvider()


@pytest.fixture
def mock_session_manager():
    """Provide a mock session manager for testing."""
    return MockSessionManager()


@pytest.fixture
def sample_user_context():
    """Provide sample user context for testing."""
    return {
        "user_id": "user_123",
        "username": "testuser",
        "email": "test@example.com",
        "roles": ["user"],
        "permissions": ["read", "write"],
    }


@pytest.fixture
def sample_device_fingerprint():
    """Provide sample device fingerprint for testing."""
    return "fp_abc123def456"


@pytest.fixture
def sample_session(sample_user_context, sample_device_fingerprint):
    """Provide a sample session for testing."""
    return Session.create(
        user_id=sample_user_context["user_id"],
        user_context=sample_user_context,
        device_fingerprint=sample_device_fingerprint,
    )


@pytest.fixture
def sample_token():
    """Provide a sample token for testing."""
    return Token.create(
        token_value="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        token_type="access",
        user_id="user_123",
        payload={"sub": "user_123", "role": "user"},
        expires_in=3600,
    )


@pytest.fixture
def sample_audit_event():
    """Provide a sample audit event for testing."""
    return AuditEvent.create(
        event_type="authentication",
        actor_info={"actor_id": "user_123", "actor_type": "user"},
        resource_info={"resource_type": "session", "action": "create"},
        outcome="success",
    )
