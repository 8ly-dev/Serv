"""Memory-based credential provider implementation."""

import secrets
import time
from typing import Any, Dict, Optional

import argon2
from bevy import Container

from serv.auth.audit.enforcement import AuditJournal
from serv.auth.audit.events import AuditEventType
from serv.auth.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    ProviderInitializationError,
)
from serv.auth.providers.credential import CredentialProvider
from serv.auth.types import Credentials, CredentialType, User

from .store import MemoryStore


class MemoryCredentialProvider(CredentialProvider):
    """Memory-based credential provider with argon2 password hashing.
    
    This provider supports:
    - Password-based authentication with argon2 hashing
    - Token-based authentication 
    - In-memory storage with optional TTL
    - Thread-safe operations
    - Configurable security parameters
    """
    
    def __init__(self, config: Dict[str, Any], container: Container):
        """Initialize memory credential provider.
        
        Args:
            config: Provider configuration
            container: Dependency injection container
        """
        self.config = config
        self.container = container
        
        # Initialize memory store
        cleanup_interval = config.get("cleanup_interval", 300.0)
        self.store = MemoryStore(cleanup_interval=cleanup_interval)
        
        # Configure argon2 hasher with secure defaults
        self.hasher = argon2.PasswordHasher(
            time_cost=config.get("argon2_time_cost", 3),  # Number of iterations
            memory_cost=config.get("argon2_memory_cost", 65536),  # Memory usage in KiB
            parallelism=config.get("argon2_parallelism", 1),  # Number of parallel threads
            hash_len=config.get("argon2_hash_len", 32),  # Hash length in bytes
            salt_len=config.get("argon2_salt_len", 16),  # Salt length in bytes
        )
        
        # Token configuration
        self.token_length = config.get("token_length", 32)
        self.default_token_ttl = config.get("default_token_ttl", 3600)  # 1 hour
        
        # Password policy configuration
        self.min_password_length = config.get("min_password_length", 8)
        self.max_failed_attempts = config.get("max_failed_attempts", 5)
        self.lockout_duration = config.get("lockout_duration", 900)  # 15 minutes
        
        # Start cleanup task
        self._cleanup_started = False
    
    async def _ensure_cleanup_started(self) -> None:
        """Ensure cleanup task is started."""
        if not self._cleanup_started:
            await self.store.start_cleanup()
            self._cleanup_started = True
    
    async def create_password_credentials(
        self,
        user: User,
        password: str,
        audit_journal: AuditJournal,
    ) -> Credentials:
        """Create password-based credentials for a user."""
        await self._ensure_cleanup_started()
        
        # Validate password policy
        if len(password) < self.min_password_length:
            raise AuthenticationError(
                f"Password must be at least {self.min_password_length} characters"
            )
        
        # Hash password with argon2
        try:
            password_hash = self.hasher.hash(password)
        except Exception as e:
            raise ProviderInitializationError("Failed to hash password") from e
        
        # Create credentials
        credentials = Credentials(
            id=f"password_{user.id}_{int(time.time())}",
            user_id=user.id,
            type=CredentialType.PASSWORD,
            data={"password_hash": password_hash},
            metadata={
                "created_at": time.time(),
                "algorithm": "argon2",
                "last_used": None,
                "failed_attempts": 0,
                "locked_until": None,
            }
        )
        
        # Store credentials
        credential_key = f"password:{user.id}"
        self.store.set("credentials", credential_key, credentials)
        
        # Record audit event
        if audit_journal:
            await audit_journal.record_event(
                AuditEventType.CREDENTIAL_CREATE,
                user_id=user.id,
                result="success",
                metadata={"type": "password"}
            )
        
        return credentials
    
    async def create_token_credentials(
        self,
        user: User,
        ttl_seconds: Optional[int] = None,
        audit_journal: AuditJournal = None,
    ) -> Credentials:
        """Create token-based credentials for a user."""
        await self._ensure_cleanup_started()
        
        # Generate secure random token
        token = secrets.token_urlsafe(self.token_length)
        
        # Use provided TTL or default
        token_ttl = ttl_seconds or self.default_token_ttl
        
        # Create credentials
        credentials = Credentials(
            id=f"token_{user.id}_{int(time.time())}",
            user_id=user.id,
            type=CredentialType.TOKEN,
            data={"token": token},
            metadata={
                "created_at": time.time(),
                "expires_at": time.time() + token_ttl,
                "last_used": None,
            }
        )
        
        # Store credentials with TTL
        credential_key = f"token:{token}"
        self.store.set("credentials", credential_key, credentials, ttl_seconds=token_ttl)
        
        return credentials
    
    async def verify_password(
        self,
        user_id: str,
        password: str,
        audit_journal: AuditJournal,
    ) -> bool:
        """Verify password for a user."""
        await self._ensure_cleanup_started()
        
        # Get stored credentials
        credential_key = f"password:{user_id}"
        credentials = self.store.get("credentials", credential_key)
        
        if credentials is None:
            raise InvalidCredentialsError("No password credentials found for user")
        
        # Check if account is locked
        locked_until = credentials.metadata.get("locked_until")
        if locked_until and time.time() < locked_until:
            time_remaining = int(locked_until - time.time())
            raise AuthenticationError(
                f"Account locked for {time_remaining} more seconds"
            )
        
        # Verify password
        password_hash = credentials.data["password_hash"]
        try:
            self.hasher.verify(password_hash, password)
            
            # Reset failed attempts on successful verification
            credentials.metadata["failed_attempts"] = 0
            credentials.metadata["locked_until"] = None
            credentials.metadata["last_used"] = time.time()
            
            # Update stored credentials
            self.store.set("credentials", credential_key, credentials)
            
            return True
            
        except argon2.exceptions.VerifyMismatchError:
            # Increment failed attempts
            failed_attempts = credentials.metadata.get("failed_attempts", 0) + 1
            credentials.metadata["failed_attempts"] = failed_attempts
            
            # Lock account if too many failed attempts
            if failed_attempts >= self.max_failed_attempts:
                credentials.metadata["locked_until"] = time.time() + self.lockout_duration
            
            # Update stored credentials
            self.store.set("credentials", credential_key, credentials)
            
            return False
        
        except Exception as e:
            raise AuthenticationError("Password verification failed") from e
    
    async def verify_token(
        self,
        token: str,
        audit_journal: AuditJournal,
    ) -> Optional[str]:
        """Verify token and return user ID if valid."""
        await self._ensure_cleanup_started()
        
        # Get credentials by token
        credential_key = f"token:{token}"
        credentials = self.store.get("credentials", credential_key)
        
        if credentials is None:
            return None
        
        # Check expiration (TTL handled by store, but double-check)
        expires_at = credentials.metadata.get("expires_at")
        if expires_at and time.time() > expires_at:
            # Clean up expired token
            self.store.delete("credentials", credential_key)
            return None
        
        # Update last used time
        credentials.metadata["last_used"] = time.time()
        self.store.set("credentials", credential_key, credentials)
        
        return credentials.user_id
    
    async def revoke_credentials(
        self,
        user_id: str,
        credential_type: CredentialType,
        audit_journal: AuditJournal,
    ) -> bool:
        """Revoke credentials for a user."""
        await self._ensure_cleanup_started()
        
        if credential_type == CredentialType.PASSWORD:
            credential_key = f"password:{user_id}"
            return self.store.delete("credentials", credential_key)
        
        elif credential_type == CredentialType.TOKEN:
            # For tokens, we need to find all tokens for this user
            revoked_count = 0
            for key, credentials in self.store.items("credentials"):
                if (key.startswith("token:") and 
                    credentials.user_id == user_id and
                    credentials.credential_type == CredentialType.TOKEN):
                    self.store.delete("credentials", key)
                    revoked_count += 1
            
            return revoked_count > 0
        
        return False
    
    async def revoke_token(
        self,
        token: str,
        audit_journal: AuditJournal,
    ) -> bool:
        """Revoke a specific token."""
        await self._ensure_cleanup_started()
        
        credential_key = f"token:{token}"
        return self.store.delete("credentials", credential_key)
    
    async def update_password(
        self,
        user_id: str,
        new_password: str,
        audit_journal: AuditJournal,
    ) -> bool:
        """Update password for a user."""
        await self._ensure_cleanup_started()
        
        # Validate new password
        if len(new_password) < self.min_password_length:
            raise AuthenticationError(
                f"Password must be at least {self.min_password_length} characters"
            )
        
        # Get existing credentials
        credential_key = f"password:{user_id}"
        credentials = self.store.get("credentials", credential_key)
        
        if credentials is None:
            raise InvalidCredentialsError("No password credentials found for user")
        
        # Hash new password
        try:
            new_password_hash = self.hasher.hash(new_password)
        except Exception as e:
            raise ProviderInitializationError("Failed to hash new password") from e
        
        # Update credentials
        credentials.data["password_hash"] = new_password_hash
        credentials.metadata["last_updated"] = time.time()
        credentials.metadata["failed_attempts"] = 0  # Reset failed attempts
        credentials.metadata["locked_until"] = None  # Unlock account
        
        # Store updated credentials
        self.store.set("credentials", credential_key, credentials)
        
        return True
    
    async def get_credential_metadata(
        self,
        user_id: str,
        credential_type: CredentialType,
    ) -> Optional[Dict[str, Any]]:
        """Get metadata for user credentials."""
        await self._ensure_cleanup_started()
        
        if credential_type == CredentialType.PASSWORD:
            credential_key = f"password:{user_id}"
            credentials = self.store.get("credentials", credential_key)
            return credentials.metadata if credentials else None
        
        elif credential_type == CredentialType.TOKEN:
            # Return metadata for all active tokens
            token_metadata = []
            for key, credentials in self.store.items("credentials"):
                if (key.startswith("token:") and 
                    credentials.user_id == user_id and
                    credentials.credential_type == CredentialType.TOKEN):
                    token_metadata.append(credentials.metadata)
            
            return {"tokens": token_metadata} if token_metadata else None
        
        return None
    
    async def cleanup_expired(self) -> int:
        """Clean up expired credentials and return count removed."""
        # The MemoryStore handles TTL cleanup automatically
        # This method can be used for additional cleanup logic if needed
        return 0
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get provider statistics."""
        await self._ensure_cleanup_started()
        
        total_credentials = self.store.size("credentials")
        password_count = 0
        token_count = 0
        
        for key in self.store.keys("credentials"):
            if key.startswith("password:"):
                password_count += 1
            elif key.startswith("token:"):
                token_count += 1
        
        return {
            "total_credentials": total_credentials,
            "password_credentials": password_count,
            "token_credentials": token_count,
            "argon2_config": {
                "time_cost": self.hasher.time_cost,
                "memory_cost": self.hasher.memory_cost,
                "parallelism": self.hasher.parallelism,
                "hash_len": self.hasher.hash_len,
                "salt_len": self.hasher.salt_len,
            }
        }

    # Abstract methods from CredentialProvider interface
    
    async def verify_credentials(
        self, credentials: Credentials, audit_journal: AuditJournal
    ) -> bool:
        """Verify if credentials are valid."""
        await self._ensure_cleanup_started()
        
        try:
            if credentials.type == CredentialType.PASSWORD:
                password = credentials.data.get("password")
                if not password:
                    if audit_journal:
                        await audit_journal.record_event(
                            AuditEventType.CREDENTIAL_VERIFY,
                            user_id=credentials.user_id,
                            result="failure",
                            metadata={"reason": "missing_password", "type": "password"}
                        )
                    return False
                
                result = await self.verify_password(credentials.user_id, password, audit_journal)
                
                if audit_journal:
                    await audit_journal.record_event(
                        AuditEventType.CREDENTIAL_VERIFY,
                        user_id=credentials.user_id,
                        result="success" if result else "failure",
                        metadata={"type": "password"}
                    )
                
                return result
                
            elif credentials.type == CredentialType.TOKEN:
                token = credentials.data.get("token")
                purpose = credentials.data.get("purpose", "default")
                if not token:
                    if audit_journal:
                        await audit_journal.record_event(
                            AuditEventType.CREDENTIAL_VERIFY,
                            user_id=credentials.user_id,
                            result="failure",
                            metadata={"reason": "missing_token", "type": "token"}
                        )
                    return False
                
                verified_user_id = await self.verify_token(token, audit_journal)
                result = verified_user_id == credentials.user_id
                
                if audit_journal:
                    await audit_journal.record_event(
                        AuditEventType.CREDENTIAL_VERIFY,
                        user_id=credentials.user_id,
                        result="success" if result else "failure",
                        metadata={"type": "token", "purpose": purpose}
                    )
                
                return result
            
            else:
                if audit_journal:
                    await audit_journal.record_event(
                        AuditEventType.CREDENTIAL_VERIFY,
                        user_id=credentials.user_id,
                        result="failure",
                        metadata={"reason": "unsupported_type", "type": str(credentials.type)}
                    )
                return False
                
        except Exception as e:
            if audit_journal and hasattr(audit_journal, 'record_event'):
                await audit_journal.record_event(
                    AuditEventType.CREDENTIAL_VERIFY,
                    user_id=credentials.user_id,
                    result="error",
                    metadata={"error": str(e), "type": str(credentials.type)}
                )
            return False

    async def create_credentials(
        self, user_id: str, credentials: Credentials, audit_journal: AuditJournal
    ) -> None:
        """Create new credentials for a user."""
        await self._ensure_cleanup_started()
        
        try:
            if credentials.type == CredentialType.PASSWORD:
                password = credentials.data.get("password")
                if not password:
                    raise AuthenticationError("Password is required")
                
                # Create a temporary user object for credential creation
                temp_user = User(id=user_id, username=user_id, email=None)
                await self.create_password_credentials(temp_user, password, audit_journal)
                
                if audit_journal:
                    await audit_journal.record_event(
                        AuditEventType.CREDENTIAL_CREATE,
                        user_id=user_id,
                        result="success",
                        metadata={"type": "password"}
                    )
                    
            elif credentials.type == CredentialType.TOKEN:
                purpose = credentials.data.get("purpose", "default")
                # Create a temporary user object for credential creation
                temp_user = User(id=user_id, username=user_id, email=None)
                token_creds = await self.create_token_credentials(temp_user, audit_journal=audit_journal)
                
                if audit_journal:
                    await audit_journal.record_event(
                        AuditEventType.CREDENTIAL_CREATE,
                        user_id=user_id,
                        result="success",
                        metadata={"type": "token", "purpose": purpose}
                    )
            
            else:
                if audit_journal:
                    await audit_journal.record_event(
                        AuditEventType.CREDENTIAL_CREATE,
                        user_id=user_id,
                        result="failure",
                        metadata={"reason": "unsupported_type", "type": str(credentials.type)}
                    )
                raise AuthenticationError(f"Unsupported credential type: {credentials.type}")
                
        except Exception as e:
            if audit_journal and hasattr(audit_journal, 'record_event'):
                await audit_journal.record_event(
                    AuditEventType.CREDENTIAL_CREATE,
                    user_id=user_id,
                    result="error",
                    metadata={"error": str(e), "type": str(credentials.type)}
                )
            raise

    async def update_credentials(
        self,
        user_id: str,
        old_credentials: Credentials,
        new_credentials: Credentials,
        audit_journal: AuditJournal,
    ) -> None:
        """Update existing credentials."""
        await self._ensure_cleanup_started()
        
        try:
            if old_credentials.type != new_credentials.type:
                raise AuthenticationError("Cannot change credential type during update")
            
            if new_credentials.type == CredentialType.PASSWORD:
                old_password = old_credentials.data.get("password")
                new_password = new_credentials.data.get("password")
                
                if not old_password or not new_password:
                    raise AuthenticationError("Both old and new passwords are required")
                
                # Verify old password first
                verified = await self.verify_password(user_id, old_password, audit_journal)
                if not verified:
                    raise AuthenticationError("Current password is incorrect")
                
                # Update password
                await self.update_password(user_id, new_password, audit_journal)
                
                if audit_journal:
                    await audit_journal.record_event(
                        AuditEventType.CREDENTIAL_UPDATE,
                        user_id=user_id,
                        result="success",
                        metadata={"type": "password"}
                    )
            
            else:
                if audit_journal:
                    await audit_journal.record_event(
                        AuditEventType.CREDENTIAL_UPDATE,
                        user_id=user_id,
                        result="failure",
                        metadata={"reason": "unsupported_type", "type": str(new_credentials.type)}
                    )
                raise AuthenticationError(f"Credential type {new_credentials.type} does not support updates")
                
        except Exception as e:
            if audit_journal and hasattr(audit_journal, 'record_event'):
                await audit_journal.record_event(
                    AuditEventType.CREDENTIAL_UPDATE,
                    user_id=user_id,
                    result="error",
                    metadata={"error": str(e), "type": str(new_credentials.type)}
                )
            raise

    async def delete_credentials(
        self, user_id: str, credential_type: CredentialType, audit_journal: AuditJournal
    ) -> None:
        """Delete credentials for a user."""
        await self._ensure_cleanup_started()
        
        try:
            if credential_type == CredentialType.PASSWORD:
                result = await self.delete_credentials_internal(user_id, audit_journal)
                
                if audit_journal:
                    await audit_journal.record_event(
                        AuditEventType.CREDENTIAL_DELETE,
                        user_id=user_id,
                        result="success" if result else "failure",
                        metadata={"type": "password"}
                    )
                    
            elif credential_type == CredentialType.TOKEN:
                count = await self.revoke_user_tokens(user_id, audit_journal)
                
                if audit_journal:
                    await audit_journal.record_event(
                        AuditEventType.CREDENTIAL_DELETE,
                        user_id=user_id,
                        result="success",
                        metadata={"type": "token", "count": count}
                    )
            
            else:
                if audit_journal:
                    await audit_journal.record_event(
                        AuditEventType.CREDENTIAL_DELETE,
                        user_id=user_id,
                        result="failure",
                        metadata={"reason": "unsupported_type", "type": str(credential_type)}
                    )
                raise AuthenticationError(f"Unsupported credential type: {credential_type}")
                
        except Exception as e:
            if audit_journal and hasattr(audit_journal, 'record_event'):
                await audit_journal.record_event(
                    AuditEventType.CREDENTIAL_DELETE,
                    user_id=user_id,
                    result="error",
                    metadata={"error": str(e), "type": str(credential_type)}
                )
            raise

    async def get_credential_types(self, user_id: str) -> set[CredentialType]:
        """Get available credential types for a user."""
        await self._ensure_cleanup_started()
        
        credential_types = set()
        
        # Check for password credentials
        password_key = f"password:{user_id}"
        if self.store.exists("credentials", password_key):
            credential_types.add(CredentialType.PASSWORD)
        
        # Check for token credentials
        for key in self.store.keys("credentials"):
            if key.startswith("token:"):
                cred = self.store.get("credentials", key)
                if cred and cred.user_id == user_id:
                    credential_types.add(CredentialType.TOKEN)
                    break
        
        return credential_types

    async def is_credential_compromised(self, credentials: Credentials) -> bool:
        """Check if credentials are known to be compromised."""
        # For memory provider, we don't have external compromise checking
        # This could be extended to check against known compromised password lists
        # For now, return False (not compromised)
        return False
    
    # Helper method for delete_credentials to avoid name conflict
    async def delete_credentials_internal(self, user_id: str, audit_journal: AuditJournal) -> bool:
        """Internal method to delete all credentials for a user."""
        await self._ensure_cleanup_started()
        
        deleted_any = False
        
        # Delete password credentials
        password_key = f"password:{user_id}"
        if self.store.delete("credentials", password_key):
            deleted_any = True
        
        # Delete token credentials
        tokens_deleted = await self.revoke_user_tokens(user_id, audit_journal)
        if tokens_deleted > 0:
            deleted_any = True
        
        # Delete lockout data
        lockout_key = f"lockout:{user_id}"
        if self.store.delete("lockouts", lockout_key):
            deleted_any = True
        
        return deleted_any
    
    async def revoke_user_tokens(self, user_id: str, audit_journal: AuditJournal) -> int:
        """Revoke all tokens for a user."""
        count = 0
        keys_to_delete = []
        for key, credentials in self.store.items("credentials"):
            if (key.startswith("token:") and 
                credentials.user_id == user_id and
                credentials.type == CredentialType.TOKEN):
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            if self.store.delete("credentials", key):
                count += 1
        
        return count