"""Main authentication provider interface."""

from abc import abstractmethod
from typing import Dict, Any, Optional

from .base import BaseProvider
from ..audit.enforcement import AuditEmitter, AuditRequired
from ..audit.events import AuditEventType
from ..types import Credentials, Session, User, Permission


class AuthProvider(BaseProvider):
    """Main authentication orchestrator interface."""
    
    @abstractmethod
    @AuditRequired(
        AuditEventType.AUTH_ATTEMPT >> (AuditEventType.AUTH_SUCCESS | AuditEventType.AUTH_FAILURE)
    )
    async def authenticate(
        self, 
        credentials: Credentials,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        audit_emitter: AuditEmitter = None
    ) -> Optional[Session]:
        """Authenticate user and create session.
        
        Args:
            credentials: User credentials
            ip_address: Client IP address
            user_agent: Client user agent
            audit_emitter: Audit emitter for tracking events
            
        Returns:
            Session if authentication successful, None otherwise
        """
        pass
    
    @abstractmethod
    @AuditRequired(
        AuditEventType.AUTHZ_CHECK >> (AuditEventType.AUTHZ_GRANT | AuditEventType.AUTHZ_DENY)
    )
    async def authorize(
        self,
        session_id: str,
        permission: Permission,
        context: Optional[Dict[str, Any]] = None,
        audit_emitter: AuditEmitter = None
    ) -> bool:
        """Check if session has permission for action.
        
        Args:
            session_id: ID of the session
            permission: Permission to check
            context: Additional context for authorization
            audit_emitter: Audit emitter for tracking events
            
        Returns:
            True if authorized, False otherwise
        """
        pass
    
    @abstractmethod
    @AuditRequired(AuditEventType.AUTH_LOGOUT)
    async def logout(
        self, 
        session_id: str,
        audit_emitter: AuditEmitter
    ) -> None:
        """Logout user and destroy session.
        
        Args:
            session_id: ID of the session to logout
            audit_emitter: Audit emitter for tracking events
        """
        pass
    
    @abstractmethod
    async def validate_session(self, session_id: str) -> Optional[Session]:
        """Validate session and return if valid.
        
        Args:
            session_id: ID of the session to validate
            
        Returns:
            Session if valid, None otherwise
        """
        pass
    
    @abstractmethod
    async def get_current_user(self, session_id: str) -> Optional[User]:
        """Get user for current session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            User if session is valid, None otherwise
        """
        pass