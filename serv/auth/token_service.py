"""
TokenService interface for the Serv authentication framework.

This module defines the abstract base class for token management,
providing secure token generation, validation, and lifecycle management.

Security considerations:
- Tokens must be cryptographically secure and non-predictable
- Token validation must be timing-attack resistant
- Expired tokens must be handled securely
- Token revocation must be immediate and complete
"""

from abc import ABC, abstractmethod
from typing import Any

from .types import Token


class TokenService(ABC):
    """
    Abstract base class for token services.

    Token services handle the generation, validation, and lifecycle of
    security tokens including access tokens, refresh tokens, API keys,
    and other authentication artifacts.

    Security requirements:
    - Tokens MUST be cryptographically secure
    - Token validation MUST use timing protection
    - Token generation MUST be non-predictable
    - Token storage MUST be secure
    - Token revocation MUST be immediate

    All implementations should be stateless and use dependency injection
    for storage and cryptographic services.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the token service.

        Args:
            config: Token service configuration
        """
        self.config = config.copy()  # Defensive copy
        self._validate_config(config)

    @abstractmethod
    def _validate_config(self, config: dict[str, Any]) -> None:
        """
        Validate token service configuration.

        Should validate cryptographic settings, expiration times,
        and security parameters.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If configuration is invalid or insecure
        """
        pass

    @abstractmethod
    async def generate_token(
        self,
        payload: dict[str, Any],
        token_type: str = "access",
        expires_in: int | None = None,
    ) -> Token:
        """
        Generate a new security token.

        Creates a cryptographically secure token with the specified
        payload and expiration. The token should be immediately
        available for validation.

        Security requirements:
        - MUST use cryptographically secure generation
        - MUST validate payload doesn't contain sensitive data
        - MUST set appropriate expiration
        - SHOULD emit token generation audit event

        Args:
            payload: Data to include in token (no sensitive data)
            token_type: Type of token ("access", "refresh", "api_key", etc.)
            expires_in: Token lifetime in seconds (uses config default if None)

        Returns:
            New Token object with secure token value

        Raises:
            ValueError: If payload contains sensitive data or is invalid

        Example:
            ```python
            async def generate_token(
                self,
                payload: Dict[str, Any],
                token_type: str = "access",
                expires_in: Optional[int] = None
            ) -> Token:
                # Validate payload
                self._validate_payload(payload)

                # Get expiration time
                if expires_in is None:
                    expires_in = self.config.get(f"{token_type}_expires_in", 3600)

                # Generate secure token value
                token_value = await self._generate_secure_token(payload, expires_in)

                # Create token object
                token = Token.create(
                    token_value=token_value,
                    token_type=token_type,
                    user_id=payload["user_id"],
                    payload=payload,
                    expires_in=expires_in
                )

                # Store token
                await self._store_token(token)

                # Emit audit event
                await self._emit_token_event("token_generated", token)

                return token
            ```
        """
        pass

    @abstractmethod
    async def validate_token(self, token_str: str) -> Token | None:
        """
        Validate and decode a token.

        Validates token integrity, expiration, and revocation status.
        Returns the token object if valid, None if invalid.

        Security requirements:
        - MUST use timing protection to prevent enumeration
        - MUST validate token integrity/signature
        - MUST check expiration
        - MUST check revocation status
        - SHOULD emit validation audit events for failures

        Args:
            token_str: Token string to validate

        Returns:
            Token object if valid, None if invalid

        Example:
            ```python
            async def validate_token(self, token_str: str) -> Optional[Token]:
                async with timing_protection(0.5):  # Prevent enumeration
                    if not token_str:
                        return None

                    # Decode and validate token
                    try:
                        token_data = await self._decode_token(token_str)
                    except Exception:
                        await self._emit_validation_event("token_decode_failed", token_str[:8])
                        return None

                    # Check if token exists in storage
                    token = await self._get_token(token_data["token_id"])
                    if not token:
                        await self._emit_validation_event("token_not_found", token_str[:8])
                        return None

                    # Check expiration
                    if token.is_expired():
                        await self._revoke_token(token.token_id)
                        await self._emit_validation_event("token_expired", token.token_id)
                        return None

                    # Validate token value matches
                    if not secure_compare(token.token_value, token_str):
                        await self._emit_validation_event("token_mismatch", token.token_id)
                        return None

                    return token
            ```
        """
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Token | None:
        """
        Generate new access token using refresh token.

        Validates the refresh token and generates a new access token.
        May also generate a new refresh token depending on configuration.

        Security requirements:
        - MUST use timing protection
        - MUST validate refresh token
        - MUST invalidate old tokens if configured
        - SHOULD emit refresh audit events

        Args:
            refresh_token: Refresh token string

        Returns:
            New access token if refresh is valid, None if invalid

        Example:
            ```python
            async def refresh_token(self, refresh_token: str) -> Optional[Token]:
                async with timing_protection(1.0):
                    # Validate refresh token
                    refresh_token_obj = await self.validate_token(refresh_token)
                    if not refresh_token_obj or refresh_token_obj.token_type != "refresh":
                        return None

                    # Generate new access token
                    new_token = await self.generate_token(
                        payload=refresh_token_obj.payload,
                        token_type="access"
                    )

                    # Optionally invalidate refresh token (rotation)
                    if self.config.get("rotate_refresh_tokens", False):
                        await self.revoke_token(refresh_token)

                    return new_token
            ```
        """
        pass

    @abstractmethod
    async def revoke_token(self, token_str: str) -> bool:
        """
        Revoke a specific token.

        Immediately invalidates the token, making it unusable for
        future requests. Used for logout and security responses.

        Security requirements:
        - MUST be immediate and irreversible
        - MUST clean up all token data
        - SHOULD emit audit event

        Args:
            token_str: Token string to revoke

        Returns:
            True if token was found and revoked, False if not found

        Example:
            ```python
            async def revoke_token(self, token_str: str) -> bool:
                # Find token
                token = await self.validate_token(token_str)
                if not token:
                    return False

                # Remove from storage
                await self._delete_token(token.token_id)

                # Emit audit event
                await self._emit_token_event("token_revoked", token)

                return True
            ```
        """
        pass

    async def revoke_user_tokens(
        self, user_id: str, token_type: str | None = None
    ) -> int:
        """
        Revoke all tokens for a specific user.

        Used when user privileges change, password is reset, or
        account is compromised. Provides immediate security response.

        Args:
            user_id: User whose tokens should be revoked
            token_type: Specific token type to revoke (None for all types)

        Returns:
            Number of tokens that were revoked
        """
        # Default implementation - providers should override for efficiency
        count = 0
        user_tokens = await self._get_user_tokens(user_id, token_type)

        for token in user_tokens:
            if await self.revoke_token(token.token_value):
                count += 1

        return count

    async def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens from storage.

        Removes expired tokens to maintain storage hygiene and
        prevent accumulation of stale token data.

        Returns:
            Number of tokens cleaned up
        """
        # Default implementation - providers should override
        return 0

    async def _get_user_tokens(
        self, user_id: str, token_type: str | None = None
    ) -> list[Token]:
        """
        Get all tokens for a user.

        Default implementation returns empty list.
        Providers should override to implement user token lookup.

        Args:
            user_id: User ID to search for
            token_type: Optional token type filter

        Returns:
            List of user's tokens
        """
        return []

    def _validate_payload(self, payload: dict[str, Any]) -> None:
        """
        Validate that token payload doesn't contain sensitive data.

        Args:
            payload: Payload to validate

        Raises:
            ValueError: If sensitive data is detected
        """
        sensitive_keys = {
            "password",
            "secret",
            "key",
            "credential",
            "hash",
            "salt",
            "private",
        }

        for key in payload:
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                raise ValueError(f"Sensitive data not allowed in token payload: {key}")

        # Ensure user_id is present
        if "user_id" not in payload:
            raise ValueError("Token payload must include user_id")

    def get_token_lifetime(self, token_type: str) -> int:
        """
        Get default lifetime for a token type.

        Args:
            token_type: Type of token

        Returns:
            Lifetime in seconds
        """
        default_lifetimes = {
            "access": 3600,  # 1 hour
            "refresh": 604800,  # 1 week
            "api_key": 31536000,  # 1 year
        }

        config_key = f"{token_type}_expires_in"
        return self.config.get(config_key, default_lifetimes.get(token_type, 3600))

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup resources when token service is being shut down.

        Override this method to cleanup any resources (connections,
        caches, etc.) when the token service is being destroyed.
        """
        pass
