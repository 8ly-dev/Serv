"""Memory-based session provider implementation."""

import secrets
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

from bevy import Container

from serv.auth.audit.enforcement import AuditJournal
from serv.auth.exceptions import AuthenticationError, SessionExpiredError
from serv.auth.providers.session import SessionProvider
from serv.auth.types import Session, User

from .store import MemoryStore


class MemorySessionProvider(SessionProvider):
    """Memory-based session provider with expiration and cleanup.
    
    This provider supports:
    - Session creation with configurable TTL
    - Session validation and refresh
    - Automatic cleanup of expired sessions
    - Thread-safe operations
    - Session metadata tracking
    - Concurrent session limits per user
    """
    
    def __init__(self, config: Dict[str, Any], container: Container):
        """Initialize memory session provider.
        
        Args:
            config: Provider configuration
            container: Dependency injection container
        """
        self.config = config
        self.container = container
        
        # Initialize memory store
        cleanup_interval = config.get("cleanup_interval", 300.0)
        self.store = MemoryStore(cleanup_interval=cleanup_interval)
        
        # Session configuration
        self.default_session_ttl = config.get("default_session_ttl", 86400)  # 24 hours
        self.max_session_ttl = config.get("max_session_ttl", 604800)  # 7 days
        self.session_id_length = config.get("session_id_length", 32)
        self.max_concurrent_sessions = config.get("max_concurrent_sessions", 10)
        self.session_refresh_threshold = config.get("session_refresh_threshold", 3600)  # 1 hour
        
        # Security settings
        self.require_ip_validation = config.get("require_ip_validation", False)
        self.require_user_agent_validation = config.get("require_user_agent_validation", False)
        
        # Start cleanup task
        self._cleanup_started = False
    
    async def _ensure_cleanup_started(self) -> None:
        """Ensure cleanup task is started."""
        if not self._cleanup_started:
            await self.store.start_cleanup()
            self._cleanup_started = True
    
    async def create_session(
        self,
        user_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        duration: timedelta | None = None,
        audit_journal: AuditJournal = None,
    ) -> Session:
        """Create a new session for a user."""
        await self._ensure_cleanup_started()
        
        # Validate duration
        if duration:
            session_ttl = int(duration.total_seconds())
        else:
            session_ttl = self.default_session_ttl
        if session_ttl > self.max_session_ttl:
            session_ttl = self.max_session_ttl
        
        # Generate secure session ID
        session_id = secrets.token_urlsafe(self.session_id_length)
        
        # Ensure unique session ID (extremely unlikely collision, but safety first)
        while self.store.exists("sessions", session_id):
            session_id = secrets.token_urlsafe(self.session_id_length)
        
        # Check concurrent session limit
        await self._enforce_session_limits(user_id)
        
        # Create session
        from datetime import datetime, timedelta
        current_time = datetime.now()
        expires_time = current_time + timedelta(seconds=session_ttl)
        
        session = Session(
            id=session_id,
            user_id=user_id,
            created_at=current_time,
            expires_at=expires_time,
            last_accessed=current_time,
            metadata={
                "creation_ip": ip_address,
                "creation_user_agent": user_agent,
                "access_count": 1,
                "last_refresh": current_time.timestamp(),
            }
        )
        
        # Store session with TTL
        self.store.set("sessions", session_id, session, ttl_seconds=session_ttl)
        
        # Track user sessions
        user_sessions = self.store.get("user_sessions", user_id) or set()
        user_sessions.add(session_id)
        self.store.set("user_sessions", user_id, user_sessions, ttl_seconds=session_ttl)
        
        return session
    
    async def get_session(self, session_id: str) -> Session | None:
        """Get session by ID."""
        await self._ensure_cleanup_started()
        
        session = self.store.get("sessions", session_id)
        if session is None:
            return None
        
        # Check if session has expired
        from datetime import datetime
        current_time = datetime.now()
        if session.expires_at and current_time > session.expires_at:
            await self._cleanup_session(session_id, session.user_id)
            return None
        
        return session
    
    async def validate_session(
        self,
        session_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        audit_journal: AuditJournal = None,
    ) -> Session | None:
        """Validate session and update access time."""
        await self._ensure_cleanup_started()
        
        session = await self.get_session(session_id)
        if session is None:
            return None
        
        # Validate IP address if required
        if (self.require_ip_validation and 
            ip_address and 
            session.ip_address and 
            ip_address != session.ip_address):
            raise AuthenticationError("Session IP address mismatch")
        
        # Validate user agent if required
        if (self.require_user_agent_validation and 
            user_agent and 
            session.user_agent and 
            user_agent != session.user_agent):
            raise AuthenticationError("Session user agent mismatch")
        
        # Update session access time and metadata
        from datetime import datetime
        current_time = datetime.now()
        session.last_accessed = current_time
        session.metadata["access_count"] = session.metadata.get("access_count", 0) + 1
        
        # Update IP and user agent if provided
        if ip_address:
            session.ip_address = ip_address
        if user_agent:
            session.user_agent = user_agent
        
        # Calculate remaining TTL and store updated session
        remaining_ttl = (session.expires_at - current_time).total_seconds() if session.expires_at else None
        self.store.set("sessions", session_id, session, ttl_seconds=remaining_ttl)
        
        return session
    
    async def refresh_session(
        self, session_id: str, audit_journal: AuditJournal
    ) -> Session | None:
        """Refresh session expiration time."""
        await self._ensure_cleanup_started()
        
        session = await self.get_session(session_id)
        if session is None:
            return None
        
        # Check if session is eligible for refresh
        current_time = time.time()
        time_since_refresh = current_time - session.metadata.get("last_refresh", session.created_at)
        
        if time_since_refresh < self.session_refresh_threshold:
            # Too soon to refresh, return existing session
            return session
        
        # Calculate new expiration
        new_ttl = self.default_session_ttl
        if new_ttl > self.max_session_ttl:
            new_ttl = self.max_session_ttl
        
        # Update session
        session.expires_at = current_time + new_ttl
        session.metadata["last_refresh"] = current_time
        
        # Store updated session with new TTL
        self.store.set("sessions", session_id, session, ttl_seconds=new_ttl)
        
        # Update user sessions TTL
        user_sessions = self.store.get("user_sessions", session.user_id)
        if user_sessions:
            self.store.set("user_sessions", session.user_id, user_sessions, ttl_seconds=new_ttl)
        
        return session
    
    async def destroy_session(
        self,
        session_id: str,
        audit_journal: AuditJournal,
    ) -> None:
        """Destroy a session."""
        await self._ensure_cleanup_started()
        
        session = self.store.get("sessions", session_id)
        if session is None:
            return False
        
        # Clean up session
        await self._cleanup_session(session_id, session.user_id)
    
    async def destroy_user_sessions(self, user_id: str) -> int:
        """Destroy all sessions for a user, optionally except one."""
        await self._ensure_cleanup_started()
        
        user_sessions = self.store.get("user_sessions", user_id) or set()
        destroyed_count = 0
        
        for session_id in user_sessions.copy():
            if self.store.delete("sessions", session_id):
                destroyed_count += 1
                user_sessions.discard(session_id)
        
        # Update user sessions set
        if user_sessions:
            self.store.set("user_sessions", user_id, user_sessions)
        else:
            self.store.delete("user_sessions", user_id)
        
        return destroyed_count
    
    async def get_active_sessions(self, user_id: str) -> list[Session]:
        """Get all active sessions for a user."""
        await self._ensure_cleanup_started()
        
        user_sessions = self.store.get("user_sessions", user_id) or set()
        sessions = []
        expired_sessions = []
        
        from datetime import datetime
        current_time = datetime.now()
        
        for session_id in user_sessions:
            session = self.store.get("sessions", session_id)
            if session is None or (session.expires_at and current_time > session.expires_at):
                expired_sessions.append(session_id)
            else:
                sessions.append(session)
        
        # Clean up expired sessions
        if expired_sessions:
            for session_id in expired_sessions:
                user_sessions.discard(session_id)
            
            if user_sessions:
                self.store.set("user_sessions", user_id, user_sessions)
            else:
                self.store.delete("user_sessions", user_id)
        
        return sessions
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        await self._ensure_cleanup_started()
        
        # Let the store's TTL mechanism handle cleanup
        # This is called automatically by the cleanup task
        return 0
    
    async def get_session_count(self, user_id: str) -> int:
        """Get count of active sessions for a user."""
        sessions = await self.get_active_sessions(user_id)
        return len(sessions)
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions and return count removed."""
        # The MemoryStore handles TTL cleanup automatically
        # This method provides additional cleanup for consistency
        cleanup_count = 0
        current_time = time.time()
        
        # Check all sessions for expiration
        for session_id in self.store.keys("sessions").copy():
            session = self.store.get("sessions", session_id)
            if session and current_time > session.expires_at:
                await self._cleanup_session(session_id, session.user_id)
                cleanup_count += 1
        
        return cleanup_count
    
    async def _enforce_session_limits(self, user_id: str) -> None:
        """Enforce concurrent session limits for a user."""
        user_sessions = await self.get_active_sessions(user_id)
        
        if len(user_sessions) >= self.max_concurrent_sessions:
            # Remove oldest sessions to make room
            sessions_to_remove = len(user_sessions) - self.max_concurrent_sessions + 1
            
            # Sort by creation time (oldest first)
            user_sessions.sort(key=lambda s: s.created_at)
            
            for session in user_sessions[:sessions_to_remove]:
                await self._cleanup_session(session.id, user_id)
    
    async def _cleanup_session(self, session_id: str, user_id: str) -> None:
        """Clean up a session and its references."""
        # Remove session
        self.store.delete("sessions", session_id)
        
        # Remove from user sessions
        user_sessions = self.store.get("user_sessions", user_id)
        if user_sessions:
            user_sessions.discard(session_id)
            if user_sessions:
                self.store.set("user_sessions", user_id, user_sessions)
            else:
                self.store.delete("user_sessions", user_id)
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get provider statistics."""
        await self._ensure_cleanup_started()
        
        total_sessions = self.store.size("sessions")
        total_users_with_sessions = self.store.size("user_sessions")
        
        # Calculate average sessions per user
        avg_sessions_per_user = (
            total_sessions / total_users_with_sessions 
            if total_users_with_sessions > 0 else 0
        )
        
        return {
            "total_sessions": total_sessions,
            "users_with_sessions": total_users_with_sessions,
            "average_sessions_per_user": avg_sessions_per_user,
            "max_concurrent_sessions": self.max_concurrent_sessions,
            "default_session_ttl": self.default_session_ttl,
            "max_session_ttl": self.max_session_ttl,
        }