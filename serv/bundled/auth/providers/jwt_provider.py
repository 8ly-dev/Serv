"""
JWT Authentication Provider using PyJWT.

This implementation provides secure JWT-based authentication with protection
against common JWT vulnerabilities including algorithm confusion attacks.

Security features:
- Algorithm validation with explicit allow-list
- Automatic expiration handling
- Secure secret key validation
- Protection against timing attacks
- Comprehensive error handling
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from serv.auth.auth_provider import AuthProvider
from serv.auth.types import AuthResult, AuthStatus, RefreshResult, ValidationResult
from serv.auth.utils import timing_protection
from serv.http import Request

logger = logging.getLogger(__name__)


class JWTAuthProvider(AuthProvider):
    """
    JWT authentication provider using PyJWT library.

    Provides secure JWT token generation and validation with protection
    against common JWT vulnerabilities.

    Security considerations:
    - Validates algorithm explicitly to prevent algorithm confusion
    - Uses secure defaults for token expiration
    - Protects against timing attacks during validation
    - Comprehensive logging for security monitoring
    """

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        token_expiry_minutes: int = 60,
        issuer: str | None = None,
        audience: str | None = None,
    ):
        """
        Initialize JWT authentication provider.

        Args:
            secret_key: Secret key for JWT signing (minimum 32 characters)
            algorithm: JWT algorithm (HS256, HS384, HS512, RS256, RS384, RS512)
            token_expiry_minutes: Default token expiration in minutes
            issuer: JWT issuer claim (optional)
            audience: JWT audience claim (optional)

        Raises:
            ValueError: If configuration is insecure
        """
        # Create config dict for parent class
        config = {
            "secret_key": secret_key,
            "algorithm": algorithm,
            "token_expiry_minutes": token_expiry_minutes,
            "issuer": issuer,
            "audience": audience,
        }

        # Call parent constructor which will call _validate_config
        super().__init__(config)

        # Set instance variables after validation
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expiry_minutes = token_expiry_minutes
        self.issuer = issuer
        self.audience = audience

        logger.info(f"JWT provider initialized with algorithm {algorithm}")

    def _validate_config(self, config: dict[str, Any]) -> None:
        """Validate JWT provider configuration."""
        secret_key = config.get("secret_key")
        if not secret_key or len(secret_key) < 32:
            raise ValueError("JWT secret key must be at least 32 characters")

        algorithm = config.get("algorithm", "HS256")
        allowed_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        if algorithm not in allowed_algorithms:
            raise ValueError(f"Unsupported JWT algorithm: {algorithm}")

        token_expiry = config.get("token_expiry_minutes", 60)
        if not isinstance(token_expiry, int) or token_expiry <= 0:
            raise ValueError("Token expiry must be a positive integer")

    async def authenticate_request(self, request: Request) -> AuthResult:
        """
        Authenticate request using JWT token.

        Security considerations:
        - Uses timing protection to prevent timing attacks
        - Validates token signature and claims thoroughly
        - Provides detailed error information for debugging

        Args:
            request: HTTP request to authenticate

        Returns:
            Authentication result with user context
        """
        async with timing_protection(0.1):  # Prevent timing attacks
            try:
                # Extract JWT token from Authorization header
                auth_header = request.headers.get("authorization", "")
                if not auth_header.startswith("Bearer "):
                    return AuthResult(
                        status=AuthStatus.INVALID_TOKEN,
                        error_message="Missing or invalid Authorization header",
                    )

                token = auth_header[7:]  # Remove "Bearer " prefix
                if not token:
                    return AuthResult(
                        status=AuthStatus.INVALID_TOKEN, error_message="Empty JWT token"
                    )

                # Validate and decode JWT token
                payload = self._decode_and_validate_token(token)
                if payload is None:
                    return AuthResult(
                        status=AuthStatus.INVALID_TOKEN,
                        error_message="Invalid JWT token",
                    )
                if payload == "EXPIRED":
                    return AuthResult(
                        status=AuthStatus.SESSION_EXPIRED,
                        error_message="JWT token has expired",
                    )

                # Extract user information from payload
                user_id = payload.get("sub")
                if not user_id:
                    return AuthResult(
                        status=AuthStatus.INVALID_TOKEN,
                        error_message="JWT token missing 'sub' claim",
                    )

                # Build user context from JWT claims
                user_context = {
                    "user_id": user_id,
                    "issued_at": payload.get("iat"),
                    "expires_at": payload.get("exp"),
                }

                # Include custom claims (excluding standard JWT claims)
                standard_claims = {"sub", "iat", "exp", "iss", "aud", "nbf", "jti"}
                for key, value in payload.items():
                    if key not in standard_claims:
                        user_context[key] = value

                logger.debug(f"Successfully authenticated user {user_id}")

                return AuthResult(
                    status=AuthStatus.SUCCESS,
                    user_id=user_id,
                    user_context=user_context,
                    metadata={"auth_method": "jwt", "algorithm": self.algorithm},
                )

            except Exception as e:
                logger.error(f"JWT authentication error: {e}")
                return AuthResult(
                    status=AuthStatus.INTERNAL_ERROR,
                    error_message="Authentication service error",
                )

    async def validate_credentials(
        self, credential_type: str, credential_data: dict[str, Any]
    ) -> ValidationResult:
        """
        Validate credentials and generate JWT token.

        This method is typically called after password verification
        to generate a JWT token for the authenticated user.

        Args:
            credential_type: Type of credentials (should be "jwt")
            credential_data: Must contain 'user_id' and optional claims

        Returns:
            Validation result with JWT token
        """
        async with timing_protection(0.1):  # Prevent timing attacks
            try:
                if credential_type != "jwt":
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Unsupported credential type: {credential_type}",
                    )

                user_id = credential_data.get("user_id")
                if not user_id:
                    return ValidationResult(
                        is_valid=False,
                        error_message="Missing user_id in credential data",
                    )

                # Generate JWT token
                now = datetime.now(UTC)
                expires_at = now + timedelta(minutes=self.token_expiry_minutes)

                payload = {
                    "sub": user_id,
                    "iat": int(now.timestamp()),
                    "exp": int(expires_at.timestamp()),
                }

                # Add optional claims
                if self.issuer:
                    payload["iss"] = self.issuer
                if self.audience:
                    payload["aud"] = self.audience

                # Include custom claims from credential data
                excluded_keys = {"user_id", "password", "password_hash"}
                for key, value in credential_data.items():
                    if key not in excluded_keys and not key.startswith("_"):
                        payload[key] = value

                # Generate token
                token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

                user_context = {
                    "user_id": user_id,
                    "token": token,
                    "expires_at": expires_at.isoformat(),
                    "issued_at": now.isoformat(),
                }

                logger.debug(f"Generated JWT token for user {user_id}")

                return ValidationResult(
                    is_valid=True,
                    user_id=user_id,
                    user_context=user_context,
                    metadata={
                        "auth_method": "jwt",
                        "algorithm": self.algorithm,
                        "expires_in_minutes": self.token_expiry_minutes,
                    },
                )

            except Exception as e:
                logger.error(f"JWT credential validation error: {e}")
                return ValidationResult(
                    is_valid=False, error_message="Credential validation service error"
                )

    async def initiate_auth(self, request_context: dict[str, Any]) -> AuthResult:
        """
        Initiate authentication using JWT from request context.

        Args:
            request_context: Sanitized request data with headers and metadata

        Returns:
            Authentication result
        """
        async with timing_protection(0.1):
            try:
                # Extract JWT token from authorization header
                headers = request_context.get("headers", {})
                auth_header = headers.get("authorization", "")

                if not auth_header.startswith("Bearer "):
                    return AuthResult(
                        status=AuthStatus.INVALID_TOKEN,
                        error_message="Missing or invalid Authorization header",
                    )

                token = auth_header[7:]  # Remove "Bearer " prefix
                if not token:
                    return AuthResult(
                        status=AuthStatus.INVALID_TOKEN, error_message="Empty JWT token"
                    )

                # Validate token using existing method
                credential_payload = {"credential": token}
                validation_result = await self.validate_credential(credential_payload)

                if validation_result.is_valid:
                    return AuthResult(
                        status=AuthStatus.SUCCESS,
                        user_id=validation_result.user_id,
                        user_context=validation_result.user_context,
                        metadata=validation_result.metadata,
                    )
                else:
                    return AuthResult(
                        status=AuthStatus.INVALID_TOKEN,
                        error_message="Invalid JWT token",
                    )

            except Exception as e:
                logger.error(f"JWT initiate_auth error: {e}")
                return AuthResult(
                    status=AuthStatus.INTERNAL_ERROR,
                    error_message="Authentication service error",
                )

    async def validate_credential(
        self, credential_payload: dict[str, Any]
    ) -> ValidationResult:
        """
        Validate JWT credential.

        Args:
            credential_payload: Contains JWT token to validate

        Returns:
            Validation result with user context
        """
        async with timing_protection(0.1):
            try:
                token = credential_payload.get("credential")
                if not token:
                    return ValidationResult(
                        is_valid=False, error_message="No credential provided"
                    )

                # Validate and decode JWT token
                payload = self._decode_and_validate_token(token)
                if payload is None:
                    return ValidationResult(
                        is_valid=False, error_message="Invalid token"
                    )
                if payload == "EXPIRED":
                    return ValidationResult(
                        is_valid=False, error_message="Token has expired"
                    )

                # Extract user information
                user_id = payload.get("sub")
                if not user_id:
                    return ValidationResult(
                        is_valid=False, error_message="Token missing user ID"
                    )

                # Build user context
                user_context = {
                    "user_id": user_id,
                    "issued_at": payload.get("iat"),
                    "expires_at": payload.get("exp"),
                }

                # Include custom claims
                standard_claims = {"sub", "iat", "exp", "iss", "aud", "nbf", "jti"}
                for key, value in payload.items():
                    if key not in standard_claims:
                        user_context[key] = value

                return ValidationResult(
                    is_valid=True,
                    user_id=user_id,
                    user_context=user_context,
                    metadata={"auth_method": "jwt", "algorithm": self.algorithm},
                )

            except Exception as e:
                logger.error(f"JWT validation error: {e}")
                return ValidationResult(
                    is_valid=False, error_message="Token validation service error"
                )

    async def refresh_session(self, session_data: dict[str, Any]) -> RefreshResult:
        """
        Refresh JWT session by issuing new token.

        Args:
            session_data: Current session context for refresh

        Returns:
            Refresh result with new token
        """
        async with timing_protection(0.1):
            try:
                user_context = session_data.get("user_context", {})
                user_id = user_context.get("user_id")

                if not user_id:
                    return RefreshResult(
                        success=False, error_message="No user ID in session data"
                    )

                # Generate new JWT token
                now = datetime.now(UTC)
                expires_at = now + timedelta(minutes=self.token_expiry_minutes)

                payload = {
                    "sub": user_id,
                    "iat": int(now.timestamp()),
                    "exp": int(expires_at.timestamp()),
                }

                # Add optional claims
                if self.issuer:
                    payload["iss"] = self.issuer
                if self.audience:
                    payload["aud"] = self.audience

                # Include custom claims from user context
                excluded_keys = {"user_id", "issued_at", "expires_at", "token"}
                for key, value in user_context.items():
                    if key not in excluded_keys and not key.startswith("_"):
                        payload[key] = value

                # Generate new token
                new_token = jwt.encode(
                    payload, self.secret_key, algorithm=self.algorithm
                )

                logger.debug(f"Refreshed JWT token for user {user_id}")

                return RefreshResult(
                    success=True,
                    new_token=new_token,
                    expires_at=expires_at,
                    metadata={
                        "user_id": user_id,
                        "token": new_token,
                        "expires_at": expires_at.isoformat(),
                        "issued_at": now.isoformat(),
                    },
                )

            except Exception as e:
                logger.error(f"JWT refresh error: {e}")
                return RefreshResult(
                    success=False, error_message="Token refresh service error"
                )

    async def cleanup(self) -> None:
        """Cleanup JWT provider resources."""
        # JWT provider is stateless, no cleanup needed
        logger.debug("JWT provider cleanup completed")

    def _decode_and_validate_token(self, token: str) -> dict[str, Any] | str | None:
        """
        Decode and validate JWT token.

        Args:
            token: JWT token string to decode

        Returns:
            Decoded payload dict if valid, "EXPIRED" if expired, None if invalid
        """
        try:
            return jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],  # Explicit algorithm validation
                issuer=self.issuer,
                audience=self.audience,
                options={
                    "require_exp": True,  # Require expiration
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                },
            )
        except jwt.ExpiredSignatureError:
            return "EXPIRED"
        except jwt.InvalidTokenError:
            return None

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "JWTAuthProvider":
        """
        Create JWT provider from configuration.

        Args:
            config: Configuration dictionary with JWT settings

        Returns:
            Configured JWT authentication provider

        Raises:
            ValueError: If configuration is invalid
        """
        secret_key = config.get("secret_key")
        if not secret_key:
            raise ValueError("JWT provider requires 'secret_key' in configuration")

        return cls(
            secret_key=secret_key,
            algorithm=config.get("algorithm", "HS256"),
            token_expiry_minutes=config.get("token_expiry_minutes", 60),
            issuer=config.get("issuer"),
            audience=config.get("audience"),
        )
