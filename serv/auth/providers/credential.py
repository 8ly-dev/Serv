"""Credential provider interface."""

from abc import abstractmethod

from ..audit.enforcement import AuditJournal, AuditRequired
from ..audit.events import AuditEventType
from ..types import Credentials, CredentialType
from .base import BaseProvider


class CredentialProvider(BaseProvider):
    """Abstract base class for credential management."""

    @abstractmethod
    @AuditRequired(AuditEventType.CREDENTIAL_VERIFY)
    async def verify_credentials(
        self, credentials: Credentials, audit_journal: AuditJournal
    ) -> bool:
        """Verify if credentials are valid.

        Args:
            credentials: Credentials to verify
            audit_journal: Audit journal for recording events

        Returns:
            True if credentials are valid, False otherwise

        Must Record:
            CREDENTIAL_VERIFY: Recorded when credential verification is performed
        """
        pass

    @abstractmethod
    @AuditRequired(AuditEventType.CREDENTIAL_CREATE)
    async def create_credentials(
        self, user_id: str, credentials: Credentials, audit_journal: AuditJournal
    ) -> None:
        """Create new credentials for a user.

        Args:
            user_id: ID of the user
            credentials: Credentials to create
            audit_journal: Audit journal for recording events

        Must Record:
            CREDENTIAL_CREATE: Recorded when credential creation is performed
        """
        pass

    @abstractmethod
    @AuditRequired(AuditEventType.CREDENTIAL_UPDATE)
    async def update_credentials(
        self,
        user_id: str,
        old_credentials: Credentials,
        new_credentials: Credentials,
        audit_journal: AuditJournal,
    ) -> None:
        """Update existing credentials.

        Args:
            user_id: ID of the user
            old_credentials: Current credentials
            new_credentials: New credentials
            audit_journal: Audit journal for recording events

        Must Record:
            CREDENTIAL_UPDATE: Recorded when credential update is performed
        """
        pass

    @abstractmethod
    @AuditRequired(AuditEventType.CREDENTIAL_DELETE)
    async def delete_credentials(
        self, user_id: str, credential_type: CredentialType, audit_journal: AuditJournal
    ) -> None:
        """Delete credentials for a user.

        Args:
            user_id: ID of the user
            credential_type: Type of credentials to delete
            audit_journal: Audit journal for recording events

        Must Record:
            CREDENTIAL_DELETE: Recorded when credential deletion is performed
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
