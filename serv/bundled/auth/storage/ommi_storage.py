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

import json
import logging
from datetime import UTC, datetime
from typing import Any

from bevy import Inject, Options
from ommi import Ommi
from ommi.database.query_results import DBQueryResult
from ommi.database.results import DBResult

from serv.auth.session_manager import SessionManager
from serv.auth.types import Session
from serv.auth.utils import validate_session_fingerprint

from ..models import SessionModel, auth_collection

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

        logger.info(
            f"Ommi session storage initialized with qualifier '{database_qualifier}'"
        )

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
            # Ensure auth models are set up
            await db.use_models(auth_collection)

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

            # Create Ommi model instance
            session_model = SessionModel(
                session_id=session.session_id,
                user_id=session.user_id,
                user_context=json.dumps(session.user_context),
                device_fingerprint=session.device_fingerprint,
                created_at=session.created_at.isoformat(),
                expires_at=session.expires_at.isoformat(),
                last_activity=session.last_activity.isoformat(),
                metadata=json.dumps(session.metadata),
            )

            # Store in database using Ommi
            match await db.add(session_model):
                case DBResult.DBSuccess(_):
                    logger.info(
                        f"Created session {session.session_id} for user {session.user_id}"
                    )
                    return session
                case DBResult.DBFailure(exception):
                    logger.error(f"Failed to create session: {exception}")
                    raise exception

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
            # Ensure auth models are set up
            await db.use_models(auth_collection)

            # Query database for session using Ommi
            match await db.find(SessionModel.session_id == session_id).one():
                case DBQueryResult.DBQuerySuccess(session_model):
                    # Parse timestamps
                    created_at = datetime.fromisoformat(session_model.created_at)
                    expires_at = datetime.fromisoformat(session_model.expires_at)
                    last_activity = datetime.fromisoformat(session_model.last_activity)

                    # Check if session is expired
                    if datetime.now(UTC) >= expires_at:
                        logger.debug(f"Session {session_id} is expired")
                        await self.delete_session(session_id, db=db)
                        return None

                    # Parse JSON fields
                    user_context = json.loads(session_model.user_context)
                    metadata = json.loads(session_model.metadata)

                    # Reconstruct session object
                    session = Session(
                        session_id=session_model.session_id,
                        user_id=session_model.user_id,
                        user_context=user_context,
                        device_fingerprint=session_model.device_fingerprint,
                        created_at=created_at,
                        expires_at=expires_at,
                        last_activity=last_activity,
                        metadata=metadata,
                    )

                    return session

                case DBQueryResult.DBQueryFailure(exception):
                    logger.debug(
                        f"Session {session_id} not found or query failed: {exception}"
                    )
                    return None

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
            # Ensure auth models are set up
            await db.use_models(auth_collection)

            # Update session using Ommi
            match await db.find(SessionModel.session_id == session.session_id).update(
                user_context=json.dumps(session.user_context),
                last_activity=session.last_activity.isoformat(),
                metadata=json.dumps(session.metadata),
            ):
                case DBResult.DBSuccess(_):
                    logger.debug(f"Updated session {session.session_id}")
                    return True
                case DBResult.DBFailure(exception):
                    logger.warning(
                        f"Failed to update session {session.session_id}: {exception}"
                    )
                    return False

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
            # Ensure auth models are set up
            await db.use_models(auth_collection)

            # Delete session using Ommi
            match await db.find(SessionModel.session_id == session_id).delete():
                case DBResult.DBSuccess(_):
                    logger.info(f"Deleted session {session_id}")
                    return True
                case DBResult.DBFailure(exception):
                    logger.debug(f"Failed to delete session {session_id}: {exception}")
                    return False

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
                strict=self.strict_fingerprint_validation,
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
            # Ensure auth models are set up
            await db.use_models(auth_collection)

            current_time = datetime.now(UTC).isoformat()

            # Delete expired sessions using Ommi
            match await db.find(SessionModel.expires_at < current_time).delete():
                case DBResult.DBSuccess(deleted_sessions):
                    count = len(deleted_sessions) if deleted_sessions else 0
                    if count > 0:
                        logger.info(f"Cleaned up {count} expired sessions")
                    return count
                case DBResult.DBFailure(exception):
                    logger.error(f"Error cleaning up expired sessions: {exception}")
                    return 0

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
            # Ensure auth models are set up
            await db.use_models(auth_collection)

            current_time = datetime.now(UTC).isoformat()

            # Query for active sessions using Ommi
            match await db.find(
                SessionModel.user_id == user_id, SessionModel.expires_at > current_time
            ).all():
                case DBQueryResult.DBQuerySuccess(session_iterator):
                    sessions = []
                    async for session_model in session_iterator:
                        # Parse timestamps and JSON fields
                        created_at = datetime.fromisoformat(session_model.created_at)
                        expires_at = datetime.fromisoformat(session_model.expires_at)
                        last_activity = datetime.fromisoformat(
                            session_model.last_activity
                        )
                        user_context = json.loads(session_model.user_context)
                        metadata = json.loads(session_model.metadata)

                        session = Session(
                            session_id=session_model.session_id,
                            user_id=session_model.user_id,
                            user_context=user_context,
                            device_fingerprint=session_model.device_fingerprint,
                            created_at=created_at,
                            expires_at=expires_at,
                            last_activity=last_activity,
                            metadata=metadata,
                        )
                        sessions.append(session)

                    return sessions

                case DBQueryResult.DBQueryFailure(exception):
                    logger.error(
                        f"Error getting sessions for user {user_id}: {exception}"
                    )
                    return []

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
            strict_fingerprint_validation=config.get(
                "strict_fingerprint_validation", True
            ),
        )
