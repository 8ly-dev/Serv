"""
SessionManager interface for the Serv authentication framework.

This module defines the abstract base class for session management,
providing secure session creation, validation, and lifecycle management.

Security considerations:
- Sessions must be bound to device fingerprints to prevent hijacking
- Session IDs must be cryptographically secure
- Session data must never contain sensitive credentials
- Session invalidation must be immediate and thorough
"""

from abc import ABC, abstractmethod
from typing import Any

from .types import ReturnsAndEmits, Session


class SessionManager(ABC):
    """
    Abstract base class for session management.

    Session managers handle the creation, validation, and lifecycle of
    user sessions. They work with authentication providers to maintain
    user state while ensuring security through device binding and
    proper session hygiene.

    Security requirements:
    - Sessions MUST be bound to device fingerprints
    - Session IDs MUST be cryptographically secure
    - Session validation MUST use timing protection
    - Session data MUST NOT contain sensitive credentials
    - Session invalidation MUST be immediate and complete

    All implementations should be stateless and use dependency injection
    for storage and other services.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the session manager.

        Args:
            config: Session manager configuration
        """
        self.config = config.copy()  # Defensive copy
        self._validate_config(config)

    @abstractmethod
    def _validate_config(self, config: dict[str, Any]) -> None:
        """
        Validate session manager configuration.

        Should validate security settings like session timeouts,
        cleanup intervals, and storage configuration.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If configuration is invalid or insecure
        """
        pass

    @abstractmethod
    async def create_session(
        self,
        user_context: dict[str, Any],
        fingerprint: str,
        timeout_seconds: int | None = None,
    ) -> ReturnsAndEmits[Session, ("session_created", "session_creation_failed")]:
        """
        Create a new user session.

        Creates a secure session bound to the user and device fingerprint.
        The session should be immediately available for validation.

        Security requirements:
        - MUST generate cryptographically secure session ID
        - MUST bind session to device fingerprint
        - MUST set appropriate expiration time
        - MUST NOT store sensitive credentials in session
        - SHOULD emit session creation audit event

        Args:
            user_context: User information to store in session (no sensitive data)
            fingerprint: Device fingerprint to bind session to
            timeout_seconds: Session timeout override (uses config default if None)

        Returns:
            New Session object with secure session ID

        Raises:
            ValueError: If user_context contains sensitive data

        Example:
            ```python
            async def create_session(
                self,
                user_context: Dict[str, Any],
                fingerprint: str,
                timeout_seconds: int | None = None
            ) -> Session:
                # Validate no sensitive data in user_context
                self._validate_user_context(user_context)

                # Use config default or provided timeout
                timeout = timeout_seconds or self.config.get("session_timeout", 3600)

                # Create session with secure defaults
                session = Session.create(
                    user_id=user_context["user_id"],
                    user_context=user_context,
                    device_fingerprint=fingerprint,
                    timeout_seconds=timeout
                )

                # Store session securely
                await self._store_session(session)

                # Emit audit event
                await self._emit_session_event("session_created", session)

                return session
            ```
        """
        pass

    @abstractmethod
    async def validate_session(
        self, session_id: str, fingerprint: str
    ) -> ReturnsAndEmits[
        Session | None, ("session_validated", "session_validation_failed")
    ]:
        """
        Validate an existing session.

        Validates session ID and ensures it matches the device fingerprint.
        Returns the session if valid, None if invalid/expired/hijacked.

        Security requirements:
        - MUST use timing protection to prevent enumeration
        - MUST validate device fingerprint match
        - MUST check session expiration
        - MUST update last activity timestamp
        - SHOULD emit validation audit events for failures

        Args:
            session_id: Session ID to validate
            fingerprint: Current device fingerprint

        Returns:
            Session object if valid, None if invalid

        Example:
            ```python
            async def validate_session(
                self,
                session_id: str,
                fingerprint: str
            ) -> Session | None:
                async with timing_protection(0.5):  # Prevent enumeration
                    # Retrieve session from storage
                    session = await self._get_session(session_id)

                    if not session:
                        await self._emit_validation_event("session_not_found", session_id)
                        return None

                    # Check expiration
                    if session.is_expired():
                        await self._invalidate_session(session_id)
                        await self._emit_validation_event("session_expired", session_id)
                        return None

                    # Validate device fingerprint
                    if session.device_fingerprint != fingerprint:
                        await self._invalidate_session(session_id)
                        await self._emit_validation_event("session_hijack_attempt", session_id)
                        return None

                    # Update activity and return
                    session.refresh_activity()
                    await self._update_session(session)

                    return session
            ```
        """
        pass

    @abstractmethod
    async def invalidate_session(
        self, session_id: str
    ) -> ReturnsAndEmits[bool, ("session_invalidated", "session_invalidation_failed")]:
        """
        Invalidate a specific session.

        Immediately invalidates the session, making it unusable for
        future requests. Used for logout and security responses.

        Security requirements:
        - MUST be immediate and irreversible
        - MUST clean up all session data
        - SHOULD emit audit event

        Args:
            session_id: Session ID to invalidate

        Returns:
            True if session was found and invalidated, False if not found

        Example:
            ```python
            async def invalidate_session(self, session_id: str) -> bool:
                session = await self._get_session(session_id)

                if not session:
                    return False

                # Remove from storage
                await self._delete_session(session_id)

                # Emit audit event
                await self._emit_session_event("session_invalidated", session)

                return True
            ```
        """
        pass

    @abstractmethod
    async def invalidate_user_sessions(self, user_id: str) -> int:
        """
        Invalidate all sessions for a specific user.

        Used when user privileges change, password is reset, or
        account is compromised. Provides immediate security response.

        Security requirements:
        - MUST invalidate ALL user sessions
        - MUST be immediate and complete
        - SHOULD emit audit events

        Args:
            user_id: User whose sessions should be invalidated

        Returns:
            Number of sessions that were invalidated

        Example:
            ```python
            async def invalidate_user_sessions(self, user_id: str) -> int:
                sessions = await self._get_user_sessions(user_id)

                count = 0
                for session in sessions:
                    await self._delete_session(session.session_id)
                    count += 1

                # Emit audit event
                await self._emit_user_event("all_sessions_invalidated", user_id, count)

                return count
            ```
        """
        pass

    @abstractmethod
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions from storage.

        Removes expired sessions to maintain storage hygiene and
        prevent accumulation of stale session data.

        Returns:
            Number of sessions cleaned up
        """
        pass

    async def extend_session(self, session_id: str, additional_seconds: int) -> bool:
        """
        Extend session expiration time.

        Default implementation that can be overridden by providers
        that support session extension.

        Args:
            session_id: Session to extend
            additional_seconds: Seconds to add to expiration

        Returns:
            True if session was extended, False if not found
        """
        # Default implementation - providers can override
        return False

    def get_session_timeout(self) -> int:
        """
        Get default session timeout in seconds.

        Returns:
            Default session timeout from configuration
        """
        return self.config.get("session_timeout", 3600)  # 1 hour default

    def _validate_user_context(self, user_context: dict[str, Any]) -> None:
        """
        Validate that user context doesn't contain sensitive data.

        Args:
            user_context: User context to validate

        Raises:
            ValueError: If sensitive data is detected
        """
        sensitive_keys = {
            "password",
            "token",
            "secret",
            "key",
            "credential",
            "hash",
            "salt",
            "private",
        }

        for key in user_context:
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                raise ValueError(f"Sensitive data not allowed in user context: {key}")

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup resources when session manager is being shut down.

        Override this method to cleanup any resources (connections,
        caches, timers, etc.) when the session manager is being destroyed.
        """
        pass
