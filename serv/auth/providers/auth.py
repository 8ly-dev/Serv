"""Main authentication provider interface."""

from abc import abstractmethod
from typing import Any

from ..audit.enforcement import AuditJournal, AuditRequired
from ..audit.events import AuditEventType
from ..types import Credentials, Permission, Session, User
from .base import BaseProvider


class AuthProvider(BaseProvider):
    """Main authentication orchestrator interface."""

    @abstractmethod
    @AuditRequired(
        AuditEventType.AUTH_ATTEMPT
        >> (AuditEventType.AUTH_SUCCESS | AuditEventType.AUTH_FAILURE)
    )
    async def authenticate(
        self,
        credentials: Credentials,
        ip_address: str | None = None,
        user_agent: str | None = None,
        audit_journal: AuditJournal = None,
    ) -> Session | None:
        """Authenticate user and create session.

        Args:
            credentials: User credentials
            ip_address: Client IP address
            user_agent: Client user agent
            audit_journal: Audit journal for recording events

        Returns:
            Session if authentication successful, None otherwise

        Must Record:
            AUTH_ATTEMPT: Always recorded at the start of authentication
            AUTH_SUCCESS: Recorded when authentication succeeds
            AUTH_FAILURE: Recorded when authentication fails

            Required sequence: AUTH_ATTEMPT >> (AUTH_SUCCESS | AUTH_FAILURE)
        """
        pass

    @abstractmethod
    @AuditRequired(
        AuditEventType.AUTHZ_CHECK
        >> (AuditEventType.AUTHZ_GRANT | AuditEventType.AUTHZ_DENY)
    )
    async def authorize(
        self,
        session_id: str,
        permission: Permission,
        context: dict[str, Any] | None = None,
        audit_journal: AuditJournal = None,
    ) -> bool:
        """Check if session has permission for action.

        Args:
            session_id: ID of the session
            permission: Permission to check
            context: Additional context for authorization
            audit_journal: Audit journal for recording events

        Returns:
            True if authorized, False otherwise

        Must Record:
            AUTHZ_CHECK: Always recorded at the start of authorization check
            AUTHZ_GRANT: Recorded when permission is granted
            AUTHZ_DENY: Recorded when permission is denied

            Required sequence: AUTHZ_CHECK >> (AUTHZ_GRANT | AUTHZ_DENY)
        """
        pass

    @abstractmethod
    @AuditRequired(AuditEventType.AUTH_LOGOUT)
    async def logout(self, session_id: str, audit_journal: AuditJournal) -> None:
        """Logout user and destroy session.

        Args:
            session_id: ID of the session to logout
            audit_journal: Audit journal for recording events

        Must Record:
            AUTH_LOGOUT: Recorded when user logout is performed
        """
        pass

    @abstractmethod
    async def validate_session(self, session_id: str) -> Session | None:
        """Validate session and return if valid.

        Args:
            session_id: ID of the session to validate

        Returns:
            Session if valid, None otherwise
        """
        pass

    @abstractmethod
    async def get_current_user(self, session_id: str) -> User | None:
        """Get user for current session.

        Args:
            session_id: ID of the session

        Returns:
            User if session is valid, None otherwise
        """
        pass
