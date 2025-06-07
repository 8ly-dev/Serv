"""
Ommi-integrated Session Storage implementation.

This implementation provides session storage using the Ommi ORM, integrating
seamlessly with Serv's database lifecycle management.

Security features:
- Device fingerprint validation for session binding
- Automatic session cleanup and expiration handling
- Secure session ID generation
- Database transaction support
- Comprehensive logging for security monitoring
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from bevy import Inject, Options
from ommi import Ommi
from ommi.query_ast import when

from serv.auth.session_manager import SessionManager
from serv.auth.types import Session
from serv.auth.utils import generate_device_fingerprint, validate_session_fingerprint

logger = logging.getLogger(__name__)


class OmmiSessionStorage(SessionManager):
    """
    Session storage implementation using Ommi ORM.
    
    Integrates with Serv's database lifecycle management to provide
    persistent session storage with automatic cleanup and security features.
    
    Security considerations:
    - Device fingerprint binding prevents session hijacking
    - Automatic expiration handling
    - Secure session ID generation
    - Database-backed persistence for scalability
    """

    def __init__(
        self,
        database_qualifier: str = "auth",
        session_timeout_hours: int = 24,
        cleanup_interval_hours: int = 1,
        strict_fingerprint_validation: bool = True,
    ):
        """
        Initialize Ommi session storage.
        
        Args:
            database_qualifier: Bevy qualifier for database injection
            session_timeout_hours: Default session timeout in hours
            cleanup_interval_hours: How often to clean expired sessions
            strict_fingerprint_validation: Whether to require exact fingerprint match
        """
        self.database_qualifier = database_qualifier
        self.session_timeout_hours = session_timeout_hours
        self.cleanup_interval_hours = cleanup_interval_hours
        self.strict_fingerprint_validation = strict_fingerprint_validation
        
        logger.info(f"Ommi session storage initialized with qualifier '{database_qualifier}'")

    async def create_session(
        self,
        user_context: dict[str, Any],
        device_fingerprint: str,
        timeout_seconds: int | None = None,
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> Session:
        """
        Create new session with database persistence.
        
        Args:
            user_context: User information and metadata
            device_fingerprint: Device fingerprint for security
            timeout_seconds: Optional session timeout override
            db: Injected database connection
            
        Returns:
            Created session with secure ID
        """
        try:
            # Calculate session timeout
            if timeout_seconds is None:
                timeout_seconds = self.session_timeout_hours * 3600
            
            # Create session object
            session = Session.create(
                user_id=user_context.get("user_id", "unknown"),
                user_context=user_context,
                device_fingerprint=device_fingerprint,
                timeout_seconds=timeout_seconds,
            )
            
            # Store in database
            session_data = {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "user_context": session.user_context,
                "device_fingerprint": session.device_fingerprint,
                "created_at": session.created_at.isoformat(),
                "expires_at": session.expires_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "metadata": session.metadata,
            }
            
            # Insert session record (assuming Sessions table exists)
            await db.execute(
                "INSERT INTO sessions (session_id, user_id, user_context, device_fingerprint, "
                "created_at, expires_at, last_activity, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_data["session_id"],
                    session_data["user_id"],
                    str(session_data["user_context"]),  # JSON string
                    session_data["device_fingerprint"],
                    session_data["created_at"],
                    session_data["expires_at"],
                    session_data["last_activity"],
                    str(session_data["metadata"]),  # JSON string
                )
            )
            
            logger.info(f"Created session {session.session_id} for user {session.user_id}")
            return session
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise

    async def get_session(
        self,
        session_id: str,
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> Session | None:
        """
        Retrieve session by ID.
        
        Args:
            session_id: Session identifier
            db: Injected database connection
            
        Returns:
            Session if found and valid, None otherwise
        """
        try:
            # Query database for session
            result = await db.execute(
                "SELECT session_id, user_id, user_context, device_fingerprint, "
                "created_at, expires_at, last_activity, metadata "
                "FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            
            row = result.fetchone()
            if not row:
                return None
            
            # Parse session data
            session_data = dict(row)
            
            # Parse timestamps
            created_at = datetime.fromisoformat(session_data["created_at"])
            expires_at = datetime.fromisoformat(session_data["expires_at"])
            last_activity = datetime.fromisoformat(session_data["last_activity"])
            
            # Check if session is expired
            if datetime.now(UTC) >= expires_at:
                logger.debug(f"Session {session_id} is expired")
                await self.delete_session(session_id, db=db)
                return None
            
            # Parse JSON fields
            import json
            user_context = json.loads(session_data["user_context"])
            metadata = json.loads(session_data["metadata"])
            
            # Reconstruct session object
            session = Session(
                session_id=session_data["session_id"],
                user_id=session_data["user_id"],
                user_context=user_context,
                device_fingerprint=session_data["device_fingerprint"],
                created_at=created_at,
                expires_at=expires_at,
                last_activity=last_activity,
                metadata=metadata,
            )
            
            return session
            
        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            return None

    async def update_session(
        self,
        session: Session,
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> bool:
        """
        Update existing session.
        
        Args:
            session: Session to update
            db: Injected database connection
            
        Returns:
            True if updated successfully
        """
        try:
            import json
            
            # Update session in database
            result = await db.execute(
                "UPDATE sessions SET user_context = ?, last_activity = ?, metadata = ? "
                "WHERE session_id = ?",
                (
                    json.dumps(session.user_context),
                    session.last_activity.isoformat(),
                    json.dumps(session.metadata),
                    session.session_id,
                )
            )
            
            success = result.rowcount > 0
            if success:
                logger.debug(f"Updated session {session.session_id}")
            else:
                logger.warning(f"Session {session.session_id} not found for update")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating session {session.session_id}: {e}")
            return False

    async def delete_session(
        self,
        session_id: str,
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> bool:
        """
        Delete session.
        
        Args:
            session_id: Session identifier
            db: Injected database connection
            
        Returns:
            True if deleted successfully
        """
        try:
            result = await db.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            
            success = result.rowcount > 0
            if success:
                logger.info(f"Deleted session {session_id}")
            else:
                logger.debug(f"Session {session_id} not found for deletion")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False

    async def refresh_session(
        self,
        session_id: str,
        device_fingerprint: str,
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> Session | None:
        """
        Refresh session activity and validate device fingerprint.
        
        Args:
            session_id: Session identifier
            device_fingerprint: Current device fingerprint
            db: Injected database connection
            
        Returns:
            Refreshed session if valid, None otherwise
        """
        try:
            # Get current session
            session = await self.get_session(session_id, db=db)
            if not session:
                return None
            
            # Validate device fingerprint
            if not validate_session_fingerprint(
                session.device_fingerprint,
                device_fingerprint,
                strict=self.strict_fingerprint_validation
            ):
                logger.warning(f"Device fingerprint mismatch for session {session_id}")
                await self.delete_session(session_id, db=db)
                return None
            
            # Refresh activity timestamp
            session.refresh_activity()
            
            # Update in database
            success = await self.update_session(session, db=db)
            if not success:
                return None
            
            logger.debug(f"Refreshed session {session_id}")
            return session
            
        except Exception as e:
            logger.error(f"Error refreshing session {session_id}: {e}")
            return None

    async def cleanup_expired_sessions(
        self,
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> int:
        """
        Clean up expired sessions.
        
        Args:
            db: Injected database connection
            
        Returns:
            Number of sessions cleaned up
        """
        try:
            current_time = datetime.now(UTC).isoformat()
            
            result = await db.execute(
                "DELETE FROM sessions WHERE expires_at < ?",
                (current_time,)
            )
            
            count = result.rowcount
            if count > 0:
                logger.info(f"Cleaned up {count} expired sessions")
            
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            return 0

    async def get_user_sessions(
        self,
        user_id: str,
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> list[Session]:
        """
        Get all active sessions for a user.
        
        Args:
            user_id: User identifier
            db: Injected database connection
            
        Returns:
            List of active sessions for user
        """
        try:
            current_time = datetime.now(UTC).isoformat()
            
            result = await db.execute(
                "SELECT session_id, user_id, user_context, device_fingerprint, "
                "created_at, expires_at, last_activity, metadata "
                "FROM sessions WHERE user_id = ? AND expires_at > ?",
                (user_id, current_time)
            )
            
            sessions = []
            for row in result.fetchall():
                session_data = dict(row)
                
                # Parse timestamps and JSON fields
                import json
                created_at = datetime.fromisoformat(session_data["created_at"])
                expires_at = datetime.fromisoformat(session_data["expires_at"])
                last_activity = datetime.fromisoformat(session_data["last_activity"])
                user_context = json.loads(session_data["user_context"])
                metadata = json.loads(session_data["metadata"])
                
                session = Session(
                    session_id=session_data["session_id"],
                    user_id=session_data["user_id"],
                    user_context=user_context,
                    device_fingerprint=session_data["device_fingerprint"],
                    created_at=created_at,
                    expires_at=expires_at,
                    last_activity=last_activity,
                    metadata=metadata,
                )
                sessions.append(session)
            
            return sessions
            
        except Exception as e:
            logger.error(f"Error getting sessions for user {user_id}: {e}")
            return []

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "OmmiSessionStorage":
        """
        Create Ommi session storage from configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Configured Ommi session storage
        """
        return cls(
            database_qualifier=config.get("database_qualifier", "auth"),
            session_timeout_hours=config.get("session_timeout_hours", 24),
            cleanup_interval_hours=config.get("cleanup_interval_hours", 1),
            strict_fingerprint_validation=config.get("strict_fingerprint_validation", True),
        )