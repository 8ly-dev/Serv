"""
JWT-based token service implementation.

Provides secure token generation and validation using JWT (JSON Web Tokens)
with configurable algorithms and expiration times.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from serv.auth.token_service import TokenService
from serv.auth.types import Token


class JwtTokenService(TokenService):
    """JWT-based token service implementation."""

    def _validate_config(self, config: dict[str, Any]) -> None:
        """Validate configuration for JWT token service."""
        if "secret_key" not in config:
            raise ValueError("JWT token service requires 'secret_key' in configuration")

    def __init__(self, config: dict[str, Any]):
        """
        Initialize JWT token service.

        Args:
            config: Configuration dictionary containing:
                - secret_key: Secret key for JWT signing (required)
                - algorithm: JWT algorithm (default: HS256)
                - access_token_expiry: Access token expiry in seconds (default: 3600)
                - refresh_token_expiry: Refresh token expiry in seconds (default: 86400)
                - issuer: Token issuer (optional)
                - audience: Token audience (optional)
        """
        super().__init__(config)

        # Validate required configuration
        if "secret_key" not in config:
            raise ValueError("JWT token service requires 'secret_key' in configuration")

        self.secret_key = config["secret_key"]
        self.algorithm = config.get("algorithm", "HS256")
        self.access_token_expiry = config.get("access_token_expiry", 3600)  # 1 hour
        self.refresh_token_expiry = config.get("refresh_token_expiry", 86400)  # 24 hours
        self.issuer = config.get("issuer")
        self.audience = config.get("audience")

        # Validate algorithm
        if self.algorithm not in [
            "HS256",
            "HS384",
            "HS512",
            "RS256",
            "RS384",
            "RS512",
            "ES256",
            "ES384",
            "ES512",
        ]:
            raise ValueError(f"Unsupported JWT algorithm: {self.algorithm}")

    async def generate_token(
        self, payload: dict[str, Any], token_type: str = "access", expires_in: int | None = None
    ) -> Token:
        """
        Generate a JWT token.

        Args:
            payload: Token payload data
            token_type: Type of token ("access" or "refresh")
            expires_in: Token expiry in seconds (overrides default)

        Returns:
            Token instance with JWT data
        """
        token_id = str(uuid.uuid4())
        created_at = datetime.now(UTC)

        # Determine expiry time
        if expires_in is not None:
            expires_at = created_at + timedelta(seconds=expires_in)
        elif token_type == "refresh":
            expires_at = created_at + timedelta(seconds=self.refresh_token_expiry)
        else:
            expires_at = created_at + timedelta(seconds=self.access_token_expiry)

        # Build JWT claims
        claims = {
            "jti": token_id,  # JWT ID
            "iat": int(created_at.timestamp()),  # Issued at
            "exp": int(expires_at.timestamp()),  # Expires at
            "type": token_type,
            **payload,
        }

        # Add optional claims
        if self.issuer:
            claims["iss"] = self.issuer
        if self.audience:
            claims["aud"] = self.audience

        # Generate JWT
        try:
            token_value = jwt.encode(claims, self.secret_key, algorithm=self.algorithm)
        except Exception as e:
            raise RuntimeError(f"Failed to generate JWT token: {e}") from e

        return Token(
            token_id=token_id,
            token_value=token_value,
            token_type=token_type,
            user_id=payload.get("user_id", payload.get("sub")),
            payload=payload,
            created_at=created_at,
            expires_at=expires_at,
            metadata={"algorithm": self.algorithm},
        )

    async def validate_token(self, token_str: str) -> Token:
        """
        Validate and decode a JWT token.

        Args:
            token_str: JWT token string

        Returns:
            Token instance with decoded data

        Raises:
            ValueError: If token is invalid or expired
        """
        try:
            # Decode and validate JWT
            payload = jwt.decode(
                token_str,
                self.secret_key,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=self.audience,
            )
        except jwt.ExpiredSignatureError as e:
            raise ValueError("Token has expired") from e
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}") from e

        # Extract token data
        token_id = payload.get("jti")
        if not token_id:
            raise ValueError("Token missing required 'jti' claim")

        issued_at = payload.get("iat")
        expires_at = payload.get("exp")
        token_type = payload.get("type", "access")

        # Convert timestamps to datetime objects
        created_at = datetime.fromtimestamp(issued_at, UTC) if issued_at else None
        expires_at_dt = datetime.fromtimestamp(expires_at, UTC) if expires_at else None

        # Check if token is still active
        is_active = True
        if expires_at_dt and datetime.now(UTC) >= expires_at_dt:
            is_active = False

        # Extract user payload (remove JWT-specific claims)
        user_payload = {k: v for k, v in payload.items() if k not in ["jti", "iat", "exp", "iss", "aud", "type"]}

        return Token(
            token_id=token_id,
            token_value=token_str,
            token_type=token_type,
            user_id=payload.get("user_id", payload.get("sub")),
            payload=user_payload,
            created_at=created_at,
            expires_at=expires_at_dt,
            metadata={"algorithm": self.algorithm, "is_active": is_active},
        )

    async def refresh_token(self, refresh_token: str) -> Token:
        """
        Refresh an access token using a refresh token.

        Args:
            refresh_token: Refresh token string

        Returns:
            New access token

        Raises:
            ValueError: If refresh token is invalid
        """
        # Validate refresh token
        token = await self.validate_token(refresh_token)

        if token.token_type != "refresh":
            raise ValueError("Token is not a refresh token")

        if not token.is_active:
            raise ValueError("Refresh token has expired")

        # Generate new access token with the same payload
        return await self.generate_token(token.payload, token_type="access")

    async def revoke_token(self, token_str: str) -> bool:
        """
        Revoke a token (mark as inactive).

        Note: JWTs are stateless, so this implementation doesn't maintain
        a revocation list. For production use, consider implementing a
        token blacklist with database storage.

        Args:
            token_str: Token to revoke

        Returns:
            True if revocation was successful
        """
        # For stateless JWTs, we would need a blacklist mechanism
        # For now, we just validate the token exists
        try:
            await self.validate_token(token_str)
            return True
        except ValueError:
            return False

    async def revoke_user_tokens(self, user_id: str, token_type: str | None = None) -> int:
        """
        Revoke all tokens for a user.

        Note: JWTs are stateless, so this implementation doesn't maintain
        user token mappings. For production use, consider implementing
        user-based token tracking with database storage.

        Args:
            user_id: User whose tokens to revoke
            token_type: Optional token type filter

        Returns:
            Number of tokens revoked (always 0 for stateless implementation)
        """
        # For stateless JWTs, we cannot track user tokens
        # This would require database storage for token tracking
        return 0

    async def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens.

        Note: JWTs are stateless and self-expiring, so no cleanup is needed.

        Returns:
            Number of tokens cleaned up (always 0 for stateless implementation)
        """
        # JWTs are self-expiring, no cleanup needed
        return 0

    async def _get_user_tokens(self, user_id: str, token_type: str | None = None) -> list[Token]:
        """
        Get all tokens for a user.

        Note: JWTs are stateless, so this implementation cannot track
        user tokens. For production use, consider implementing token
        tracking with database storage.

        Args:
            user_id: User ID to get tokens for
            token_type: Optional token type filter

        Returns:
            Empty list for stateless implementation
        """
        # For stateless JWTs, we cannot track user tokens
        return []

    async def cleanup(self) -> None:
        """Clean up token service resources."""
        # No resources to clean up for JWT implementation
        pass
