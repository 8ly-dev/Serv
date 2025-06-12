"""Session provider interface."""

from abc import abstractmethod
from datetime import timedelta

from ..audit.enforcement import AuditEmitter, AuditRequired
from ..audit.events import AuditEventType
from ..types import Session
from .base import BaseProvider


class SessionProvider(BaseProvider):
    """Abstract base class for session management."""

    @abstractmethod
    @AuditRequired(AuditEventType.SESSION_CREATE)
    async def create_session(
        self,
        user_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        duration: timedelta | None = None,
        audit_emitter: AuditEmitter = None
    ) -> Session:
        """Create a new session.

        Args:
            user_id: ID of the user
            ip_address: Client IP address
            user_agent: Client user agent
            duration: Session duration (uses default if None)
            audit_emitter: Audit emitter for tracking events

        Returns:
            Created session

        Must Emit:
            SESSION_CREATE: Emitted when session creation is performed
        """
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Session | None:
        """Retrieve a session by ID.

        Args:
            session_id: ID of the session

        Returns:
            Session if found, None otherwise
        """
        pass

    @abstractmethod
    @AuditRequired(AuditEventType.SESSION_REFRESH)
    async def refresh_session(
        self,
        session_id: str,
        audit_emitter: AuditEmitter
    ) -> Session | None:
        """Refresh an existing session.

        Args:
            session_id: ID of the session to refresh
            audit_emitter: Audit emitter for tracking events

        Returns:
            Refreshed session if successful, None otherwise

        Must Emit:
            SESSION_REFRESH: Emitted when session refresh is performed
        """
        pass

    @abstractmethod
    @AuditRequired(AuditEventType.SESSION_DESTROY)
    async def destroy_session(
        self,
        session_id: str,
        audit_emitter: AuditEmitter
    ) -> None:
        """Destroy a session.

        Args:
            session_id: ID of the session to destroy
            audit_emitter: Audit emitter for tracking events

        Must Emit:
            SESSION_DESTROY: Emitted when session destruction is performed
        """
        pass

    @abstractmethod
    async def destroy_user_sessions(self, user_id: str) -> int:
        """Destroy all sessions for a user.

        Args:
            user_id: ID of the user

        Returns:
            Number of sessions destroyed
        """
        pass

    @abstractmethod
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        pass

    @abstractmethod
    async def get_active_sessions(self, user_id: str) -> list[Session]:
        """Get all active sessions for a user.

        Args:
            user_id: ID of the user

        Returns:
            List of active sessions
        """
        pass
