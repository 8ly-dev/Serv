"""Credential provider interface."""

from abc import abstractmethod

from ..audit.enforcement import AuditEmitter, AuditRequired
from ..audit.events import AuditEventType
from ..types import Credentials, CredentialType
from .base import BaseProvider


class CredentialProvider(BaseProvider):
    """Abstract base class for credential management."""

    @abstractmethod
    @AuditRequired(AuditEventType.CREDENTIAL_VERIFY)
    async def verify_credentials(
        self,
        credentials: Credentials,
        audit_emitter: AuditEmitter
    ) -> bool:
        """Verify if credentials are valid.

        Args:
            credentials: Credentials to verify
            audit_emitter: Audit emitter for tracking events

        Returns:
            True if credentials are valid, False otherwise
        """
        pass

    @abstractmethod
    @AuditRequired(AuditEventType.CREDENTIAL_CREATE)
    async def create_credentials(
        self,
        user_id: str,
        credentials: Credentials,
        audit_emitter: AuditEmitter
    ) -> None:
        """Create new credentials for a user.

        Args:
            user_id: ID of the user
            credentials: Credentials to create
            audit_emitter: Audit emitter for tracking events
        """
        pass

    @abstractmethod
    @AuditRequired(AuditEventType.CREDENTIAL_UPDATE)
    async def update_credentials(
        self,
        user_id: str,
        old_credentials: Credentials,
        new_credentials: Credentials,
        audit_emitter: AuditEmitter
    ) -> None:
        """Update existing credentials.

        Args:
            user_id: ID of the user
            old_credentials: Current credentials
            new_credentials: New credentials
            audit_emitter: Audit emitter for tracking events
        """
        pass

    @abstractmethod
    @AuditRequired(AuditEventType.CREDENTIAL_DELETE)
    async def delete_credentials(
        self,
        user_id: str,
        credential_type: CredentialType,
        audit_emitter: AuditEmitter
    ) -> None:
        """Delete credentials for a user.

        Args:
            user_id: ID of the user
            credential_type: Type of credentials to delete
            audit_emitter: Audit emitter for tracking events
        """
        pass

    @abstractmethod
    async def get_credential_types(self, user_id: str) -> set[CredentialType]:
        """Get available credential types for a user.

        Args:
            user_id: ID of the user

        Returns:
            Set of credential types available for the user
        """
        pass

    @abstractmethod
    async def is_credential_compromised(self, credentials: Credentials) -> bool:
        """Check if credentials are known to be compromised.

        Args:
            credentials: Credentials to check

        Returns:
            True if credentials are compromised, False otherwise
        """
        pass
