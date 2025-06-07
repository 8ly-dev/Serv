"""
Bcrypt-based Credential Vault implementation.

This implementation provides secure credential storage using bcrypt for
password hashing with proper salt generation and timing attack protection.

Security features:
- bcrypt password hashing with configurable rounds
- Automatic salt generation for each password
- Timing attack protection during verification
- Secure credential metadata storage
- Comprehensive logging for security monitoring
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

import bcrypt
from bevy import Inject, Options
from ommi import Ommi
from ommi.database.query_results import DBQueryResult
from ommi.database.results import DBResult

from serv.auth.credential_vault import CredentialVault
from serv.auth.types import Credential, ValidationResult
from serv.auth.utils import timing_protection

from ..models import CredentialModel, auth_collection

logger = logging.getLogger(__name__)


class BcryptCredentialVault(CredentialVault):
    """
    Credential vault using bcrypt for secure password hashing.

    Provides secure storage and verification of user credentials with
    protection against common password-based attacks.

    Security considerations:
    - Uses bcrypt with configurable work factor
    - Automatic salt generation for each password
    - Timing attack protection during verification
    - Never stores plaintext passwords
    - Comprehensive audit logging
    """

    def __init__(
        self,
        database_qualifier: str = "auth",
        bcrypt_rounds: int = 12,
        min_password_length: int = 8,
    ):
        """
        Initialize bcrypt credential vault.

        Args:
            database_qualifier: Bevy qualifier for database injection
            bcrypt_rounds: bcrypt work factor (4-31, higher = more secure/slower)
            min_password_length: Minimum password length requirement
        """
        if bcrypt_rounds < 4 or bcrypt_rounds > 31:
            raise ValueError("bcrypt rounds must be between 4 and 31")

        if min_password_length < 1:
            raise ValueError("Minimum password length must be positive")

        self.database_qualifier = database_qualifier
        self.bcrypt_rounds = bcrypt_rounds
        self.min_password_length = min_password_length

        logger.info(
            f"Bcrypt credential vault initialized with {bcrypt_rounds} rounds "
            f"(min password length: {min_password_length})"
        )

    async def store_credential(
        self,
        user_id: str,
        credential_type: str,
        credential_data: dict[str, Any],
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> Credential:
        """
        Store user credential with secure hashing.

        Args:
            user_id: User identifier
            credential_type: Type of credential (e.g., "password", "api_key")
            credential_data: Credential information
            db: Injected database connection

        Returns:
            Stored credential with secure metadata
        """
        try:
            if credential_type == "password":
                return await self._store_password_credential(
                    user_id, credential_data, db=db
                )
            else:
                return await self._store_generic_credential(
                    user_id, credential_type, credential_data, db=db
                )

        except Exception as e:
            logger.error(f"Error storing credential for user {user_id}: {e}")
            raise

    async def _store_password_credential(
        self,
        user_id: str,
        credential_data: dict[str, Any],
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> Credential:
        """Store password credential with bcrypt hashing."""
        password = credential_data.get("password")
        if not password:
            raise ValueError("Password is required for password credential")

        if len(password) < self.min_password_length:
            raise ValueError(
                f"Password must be at least {self.min_password_length} characters"
            )

        # Generate bcrypt hash
        password_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt(rounds=self.bcrypt_rounds)
        password_hash = bcrypt.hashpw(password_bytes, salt)

        # Create credential
        credential = Credential.create(
            user_id=user_id,
            credential_type="password",
            credential_data={
                "password_hash": password_hash.decode("utf-8"),
                "bcrypt_rounds": self.bcrypt_rounds,
                "algorithm": "bcrypt",
            },
        )

        # Store in database
        await self._store_credential_in_db(credential, db=db)

        logger.info(f"Stored password credential for user {user_id}")
        return credential

    async def _store_generic_credential(
        self,
        user_id: str,
        credential_type: str,
        credential_data: dict[str, Any],
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> Credential:
        """Store non-password credential."""
        # For non-password credentials, store as-is (could be API keys, tokens, etc.)
        credential = Credential.create(
            user_id=user_id,
            credential_type=credential_type,
            credential_data=credential_data.copy(),
        )

        await self._store_credential_in_db(credential, db=db)

        logger.info(f"Stored {credential_type} credential for user {user_id}")
        return credential

    async def _store_credential_in_db(
        self,
        credential: Credential,
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> None:
        """Store credential in database using Ommi."""
        # Ensure auth models are set up
        await db.use_models(auth_collection)

        # Create Ommi model instance
        credential_model = CredentialModel(
            credential_id=credential.credential_id,
            user_id=credential.user_id,
            credential_type=credential.credential_type,
            credential_data=json.dumps(credential.credential_data),
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat(),
            is_active=credential.is_active,
            metadata=json.dumps(credential.metadata),
        )

        # Store in database using Ommi
        match await db.add(credential_model):
            case DBResult.DBSuccess(_):
                pass  # Success
            case DBResult.DBFailure(exception):
                raise exception

    async def verify_credential(
        self,
        user_id: str,
        credential_type: str,
        credential_data: dict[str, Any],
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> ValidationResult:
        """
        Verify user credential with timing attack protection.

        Args:
            user_id: User identifier
            credential_type: Type of credential to verify
            credential_data: Credential data to verify
            db: Injected database connection

        Returns:
            Validation result with user context
        """
        async with timing_protection(0.2):  # Prevent timing attacks
            try:
                if credential_type == "password":
                    return await self._verify_password_credential(
                        user_id, credential_data, db=db
                    )
                else:
                    return await self._verify_generic_credential(
                        user_id, credential_type, credential_data, db=db
                    )

            except Exception as e:
                logger.error(f"Error verifying credential for user {user_id}: {e}")
                return ValidationResult(
                    is_valid=False,
                    error_message="Credential verification service error",
                )

    async def _verify_password_credential(
        self,
        user_id: str,
        credential_data: dict[str, Any],
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> ValidationResult:
        """Verify password credential using bcrypt."""
        password = credential_data.get("password")
        if not password:
            return ValidationResult(
                is_valid=False, error_message="Password is required"
            )

        # Get stored credential
        credential = await self.get_credential(user_id, "password", db=db)
        if not credential or not credential.is_active:
            return ValidationResult(is_valid=False, error_message="Invalid credentials")

        # Verify password hash
        stored_hash = credential.credential_data.get("password_hash")
        if not stored_hash:
            return ValidationResult(
                is_valid=False, error_message="Invalid stored credential"
            )

        # Perform bcrypt verification
        password_bytes = password.encode("utf-8")
        stored_hash_bytes = stored_hash.encode("utf-8")

        is_valid = bcrypt.checkpw(password_bytes, stored_hash_bytes)

        if is_valid:
            logger.info(f"Password verification successful for user {user_id}")
            return ValidationResult(
                is_valid=True,
                user_id=user_id,
                user_context={
                    "user_id": user_id,
                    "auth_method": "password",
                    "credential_id": credential.credential_id,
                },
                metadata={
                    "credential_type": "password",
                    "algorithm": "bcrypt",
                    "verification_time": datetime.now(UTC).isoformat(),
                },
            )
        else:
            logger.warning(f"Password verification failed for user {user_id}")
            return ValidationResult(is_valid=False, error_message="Invalid credentials")

    async def _verify_generic_credential(
        self,
        user_id: str,
        credential_type: str,
        credential_data: dict[str, Any],
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> ValidationResult:
        """Verify non-password credential."""
        # Get stored credential
        credential = await self.get_credential(user_id, credential_type, db=db)
        if not credential or not credential.is_active:
            return ValidationResult(is_valid=False, error_message="Invalid credentials")

        # Simple comparison for non-password credentials
        # In production, you might want more sophisticated verification
        stored_data = credential.credential_data
        is_valid = all(
            stored_data.get(key) == value
            for key, value in credential_data.items()
            if not key.startswith("_")  # Skip internal keys
        )

        if is_valid:
            logger.info(f"{credential_type} verification successful for user {user_id}")
            return ValidationResult(
                is_valid=True,
                user_id=user_id,
                user_context={
                    "user_id": user_id,
                    "auth_method": credential_type,
                    "credential_id": credential.credential_id,
                },
                metadata={
                    "credential_type": credential_type,
                    "verification_time": datetime.now(UTC).isoformat(),
                },
            )
        else:
            logger.warning(f"{credential_type} verification failed for user {user_id}")
            return ValidationResult(is_valid=False, error_message="Invalid credentials")

    async def get_credential(
        self,
        user_id: str,
        credential_type: str,
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> Credential | None:
        """
        Retrieve stored credential.

        Args:
            user_id: User identifier
            credential_type: Type of credential
            db: Injected database connection

        Returns:
            Credential if found, None otherwise
        """
        try:
            # Ensure auth models are set up
            await db.use_models(auth_collection)

            # Query for credential using Ommi
            match await db.find(
                CredentialModel.user_id == user_id,
                CredentialModel.credential_type == credential_type,
                CredentialModel.is_active,
            ).one():
                case DBQueryResult.DBQuerySuccess(credential_model):
                    return Credential(
                        credential_id=credential_model.credential_id,
                        user_id=credential_model.user_id,
                        credential_type=credential_model.credential_type,
                        credential_data=json.loads(credential_model.credential_data),
                        created_at=datetime.fromisoformat(credential_model.created_at),
                        updated_at=datetime.fromisoformat(credential_model.updated_at),
                        is_active=credential_model.is_active,
                        metadata=json.loads(credential_model.metadata),
                    )
                case DBQueryResult.DBQueryFailure(_):
                    return None

        except Exception as e:
            logger.error(f"Error retrieving credential for user {user_id}: {e}")
            return None

    async def delete_credential(
        self,
        user_id: str,
        credential_type: str,
        db: Inject[Ommi, Options(qualifier="auth")] = None,
    ) -> bool:
        """
        Delete (deactivate) user credential.

        Args:
            user_id: User identifier
            credential_type: Type of credential to delete
            db: Injected database connection

        Returns:
            True if deleted successfully
        """
        try:
            # Ensure auth models are set up
            await db.use_models(auth_collection)

            # Update credential using Ommi
            match await db.find(
                CredentialModel.user_id == user_id,
                CredentialModel.credential_type == credential_type,
            ).update(is_active=False, updated_at=datetime.now(UTC).isoformat()):
                case DBResult.DBSuccess(updated_credentials):
                    success = (
                        len(updated_credentials) > 0 if updated_credentials else False
                    )
                    if success:
                        logger.info(
                            f"Deleted {credential_type} credential for user {user_id}"
                        )
                    return success
                case DBResult.DBFailure(exception):
                    logger.error(
                        f"Error deleting credential for user {user_id}: {exception}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error deleting credential for user {user_id}: {e}")
            return False

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "BcryptCredentialVault":
        """
        Create bcrypt credential vault from configuration.

        Args:
            config: Configuration dictionary

        Returns:
            Configured bcrypt credential vault
        """
        return cls(
            database_qualifier=config.get("database_qualifier", "auth"),
            bcrypt_rounds=config.get("bcrypt_rounds", 12),
            min_password_length=config.get("min_password_length", 8),
        )
