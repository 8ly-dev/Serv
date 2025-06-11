"""
CredentialVault interface for the Serv authentication framework.

This module defines the abstract base class for secure credential storage,
providing encryption, hashing, and secure credential management.

Security considerations:
- Credentials must be encrypted/hashed with strong algorithms
- Credential verification must be timing-attack resistant
- Credential storage must prevent information leakage
- Administrative access must be strictly controlled
"""

from abc import ABC, abstractmethod
from typing import Any

from .types import Credential, ReturnsAndEmits


class CredentialVault(ABC):
    """
    Abstract base class for credential storage and management.

    Credential vaults provide secure storage for user credentials including
    passwords, API keys, certificates, and other authentication artifacts.
    They handle encryption, hashing, and secure verification while
    protecting against timing attacks and information leakage.

    Security requirements:
    - Credentials MUST be encrypted or hashed with strong algorithms
    - Credential verification MUST use timing protection
    - Credential storage MUST prevent information leakage
    - Administrative access MUST be strictly controlled
    - Credential metadata MUST NOT expose sensitive data

    All implementations should be stateless and use dependency injection
    for cryptographic services and storage.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the credential vault.

        Args:
            config: Credential vault configuration
        """
        self.config = config.copy()  # Defensive copy
        self._validate_config(config)

    @abstractmethod
    def _validate_config(self, config: dict[str, Any]) -> None:
        """
        Validate credential vault configuration.

        Should validate cryptographic settings, storage configuration,
        and security parameters.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If configuration is invalid or insecure
        """
        pass

    @abstractmethod
    async def store_credential(
        self,
        user_id: str,
        credential_type: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
        expires_in: int | None = None,
    ) -> ReturnsAndEmits[str, ("credential_stored", "credential_store_failed")]:
        """
        Store a credential securely.

        Encrypts or hashes the credential data and stores it with
        appropriate metadata. Returns a credential ID for future reference.

        Security requirements:
        - MUST encrypt or hash credential data
        - MUST use cryptographically secure algorithms
        - MUST generate secure credential ID
        - MUST validate input data
        - SHOULD emit credential storage audit event

        Args:
            user_id: User the credential belongs to
            credential_type: Type of credential ("password", "api_key", etc.)
            data: Raw credential data (will be encrypted/hashed)
            metadata: Additional credential metadata (non-sensitive)
            expires_in: Credential lifetime in seconds

        Returns:
            Unique credential ID for future reference

        Raises:
            ValueError: If credential data is invalid

        Example:
            ```python
            async def store_credential(
                self,
                user_id: str,
                credential_type: str,
                data: bytes,
                metadata: dict[str, Any] | None = None,
                expires_in: int | None = None
            ) -> str:
                # Validate inputs
                if not data:
                    raise ValueError("Credential data cannot be empty")

                if not self._is_valid_credential_type(credential_type):
                    raise ValueError(f"Invalid credential type: {credential_type}")

                # Create credential record
                credential = Credential.create(
                    user_id=user_id,
                    credential_type=credential_type,
                    expires_in=expires_in
                )

                # Encrypt/hash the credential data
                if credential_type == "password":
                    encrypted_data = await self._hash_password(data)
                else:
                    encrypted_data = await self._encrypt_data(data)

                # Store credential
                await self._store_credential_data(
                    credential.credential_id,
                    encrypted_data,
                    credential,
                    metadata or {}
                )

                # Emit audit event
                await self._emit_credential_event("credential_stored", credential)

                return credential.credential_id
            ```
        """
        pass

    @abstractmethod
    async def verify_credential(
        self, credential_id: str, input_data: bytes
    ) -> ReturnsAndEmits[
        bool, ("credential_verified", "credential_verification_failed")
    ]:
        """
        Verify credential against stored value.

        Securely compares the input data against the stored credential
        using timing-attack resistant methods.

        Security requirements:
        - MUST use timing protection to prevent attacks
        - MUST handle expired credentials securely
        - MUST use secure comparison methods
        - MUST NOT leak information about stored credentials
        - SHOULD emit verification audit events

        Args:
            credential_id: Credential ID to verify against
            input_data: Input data to verify

        Returns:
            True if credential is valid, False otherwise

        Example:
            ```python
            async def verify_credential(
                self,
                credential_id: str,
                input_data: bytes
            ) -> bool:
                async with timing_protection(1.0):  # Prevent timing attacks
                    # Get credential record
                    credential = await self._get_credential(credential_id)
                    if not credential:
                        await self._emit_verification_event("credential_not_found", credential_id)
                        return False

                    # Check if expired
                    if credential.is_expired():
                        await self._emit_verification_event("credential_expired", credential_id)
                        return False

                    # Check if active
                    if not credential.is_active:
                        await self._emit_verification_event("credential_inactive", credential_id)
                        return False

                    # Get stored credential data
                    stored_data = await self._get_credential_data(credential_id)
                    if not stored_data:
                        await self._emit_verification_event("credential_data_missing", credential_id)
                        return False

                    # Verify based on credential type
                    is_valid = False
                    if credential.credential_type == "password":
                        is_valid = await self._verify_password(input_data, stored_data)
                    else:
                        decrypted_data = await self._decrypt_data(stored_data)
                        is_valid = secure_compare(input_data.decode(), decrypted_data.decode())

                    # Emit audit event
                    outcome = "success" if is_valid else "failure"
                    await self._emit_verification_event("credential_verified", credential_id, outcome)

                    return is_valid
            ```
        """
        pass

    @abstractmethod
    async def update_credential(
        self,
        credential_id: str,
        new_data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> ReturnsAndEmits[bool, ("credential_updated", "credential_update_failed")]:
        """
        Update an existing credential.

        Replaces the credential data with new encrypted/hashed data.
        Used for password changes, key rotation, etc.

        Security requirements:
        - MUST validate credential exists and is active
        - MUST encrypt/hash new data securely
        - MUST update metadata appropriately
        - SHOULD emit credential update audit event

        Args:
            credential_id: Credential ID to update
            new_data: New credential data
            metadata: Updated metadata

        Returns:
            True if credential was updated, False if not found

        Example:
            ```python
            async def update_credential(
                self,
                credential_id: str,
                new_data: bytes,
                metadata: dict[str, Any] | None = None
            ) -> bool:
                # Get existing credential
                credential = await self._get_credential(credential_id)
                if not credential or not credential.is_active:
                    return False

                # Encrypt/hash new data
                if credential.credential_type == "password":
                    encrypted_data = await self._hash_password(new_data)
                else:
                    encrypted_data = await self._encrypt_data(new_data)

                # Update credential
                credential.updated_at = datetime.now(timezone.utc)

                await self._update_credential_data(
                    credential_id,
                    encrypted_data,
                    credential,
                    metadata
                )

                # Emit audit event
                await self._emit_credential_event("credential_updated", credential)

                return True
            ```
        """
        pass

    @abstractmethod
    async def revoke_credential(
        self, credential_id: str
    ) -> ReturnsAndEmits[bool, ("credential_revoked", "credential_revocation_failed")]:
        """
        Revoke (deactivate) a credential.

        Marks the credential as inactive, making it unusable for
        future verification attempts.

        Security requirements:
        - MUST be immediate and irreversible
        - MUST preserve audit trail
        - SHOULD emit credential revocation audit event

        Args:
            credential_id: Credential ID to revoke

        Returns:
            True if credential was revoked, False if not found

        Example:
            ```python
            async def revoke_credential(self, credential_id: str) -> bool:
                # Get credential
                credential = await self._get_credential(credential_id)
                if not credential:
                    return False

                # Mark as inactive
                credential.is_active = False
                credential.updated_at = datetime.now(timezone.utc)

                # Update in storage
                await self._update_credential_record(credential)

                # Emit audit event
                await self._emit_credential_event("credential_revoked", credential)

                return True
            ```
        """
        pass

    async def get_user_credentials(
        self, user_id: str, credential_type: str | None = None, active_only: bool = True
    ) -> list[Credential]:
        """
        Get all credentials for a user.

        Returns credential metadata (not the actual credential data).
        Used for administration and user management.

        Args:
            user_id: User to get credentials for
            credential_type: Filter by credential type
            active_only: Whether to include only active credentials

        Returns:
            List of Credential objects (metadata only)
        """
        # Default implementation - providers should override
        return []

    async def revoke_user_credentials(
        self, user_id: str, credential_type: str | None = None
    ) -> int:
        """
        Revoke all credentials for a user.

        Used when account is compromised or user is deactivated.

        Args:
            user_id: User whose credentials should be revoked
            credential_type: Specific credential type to revoke

        Returns:
            Number of credentials revoked
        """
        credentials = await self.get_user_credentials(user_id, credential_type)

        count = 0
        for credential in credentials:
            if await self.revoke_credential(credential.credential_id):
                count += 1

        return count

    async def cleanup_expired_credentials(self) -> int:
        """
        Clean up expired credentials.

        Removes or marks expired credentials for cleanup.
        Should be called periodically by a background task.

        Returns:
            Number of credentials cleaned up
        """
        # Default implementation - providers should override
        return 0

    def get_supported_credential_types(self) -> list[str]:
        """
        Get list of supported credential types.

        Returns:
            List of supported credential type names
        """
        return ["password", "api_key", "certificate"]

    def _is_valid_credential_type(self, credential_type: str) -> bool:
        """
        Check if credential type is supported.

        Args:
            credential_type: Credential type to check

        Returns:
            True if credential type is supported
        """
        return credential_type in self.get_supported_credential_types()

    async def _get_encryption_key(self) -> bytes:
        """
        Get encryption key for credential data.

        Default implementation raises NotImplementedError.
        Providers must implement secure key management.

        Returns:
            Encryption key bytes

        Raises:
            NotImplementedError: If not implemented by provider
        """
        raise NotImplementedError(
            "Encryption key management must be implemented by provider"
        )

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup resources when credential vault is being shut down.

        Override this method to cleanup any resources (connections,
        encryption keys, etc.) when the credential vault is being destroyed.
        """
        pass
