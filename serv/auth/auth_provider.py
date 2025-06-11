"""
AuthProvider interface for the Serv authentication framework.

This module defines the abstract base class for authentication providers,
along with the core authentication workflow and security considerations.

Security considerations:
- All authentication operations must use timing protection
- Credential validation should be secure against timing attacks
- Provider implementations must never expose sensitive data
- Event emission should include proper audit information
"""

from abc import ABC, abstractmethod
from typing import Any

from .types import AuthResult, RefreshResult, ValidationResult


class AuthProvider(ABC):
    """
    Abstract base class for authentication providers.

    Authentication providers handle the core authentication logic while
    remaining agnostic to storage, session management, and framework details.
    The framework manages all security aspects including timing protection,
    audit logging, and rate limiting.

    Security requirements:
    - Must use timing protection for all authentication operations
    - Must never log or expose sensitive credential data
    - Must validate all inputs to prevent injection attacks
    - Must emit appropriate events for audit logging

    All implementations should be stateless and rely on dependency injection
    for any required services.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the authentication provider.

        Args:
            config: Provider-specific configuration dictionary
        """
        self.config = config.copy()  # Defensive copy
        self._validate_config(config)

    @abstractmethod
    def _validate_config(self, config: dict[str, Any]) -> None:
        """
        Validate provider configuration.

        Should raise ValueError for invalid configuration.
        Implementations should validate all required configuration
        parameters and security settings.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If configuration is invalid or insecure
        """
        pass

    @abstractmethod
    async def initiate_auth(self, request_context: dict[str, Any]) -> AuthResult:
        """
        Initiate authentication process.

        This method begins the authentication workflow. The request_context
        contains all necessary information from the HTTP request, sanitized
        and validated by the framework.

        Security requirements:
        - MUST use timing protection to prevent timing attacks
        - MUST validate all input data
        - MUST NOT log sensitive data
        - SHOULD emit authentication events

        Args:
            request_context: Sanitized request data including:
                - headers: Relevant HTTP headers
                - body: Parsed request body
                - metadata: Additional framework metadata

        Returns:
            AuthResult indicating success/failure and user context

        Example:
            ```python
            async def initiate_auth(self, request_context: dict[str, Any]) -> AuthResult:
                async with timing_protection(2.0):  # Prevent timing attacks
                    username = request_context.get("username")
                    password = request_context.get("password")

                    if not username or not password:
                        return AuthResult(
                            status=AuthStatus.VALIDATION_ERROR,
                            error_message="Username and password required"
                        )

                    # Validate credentials securely
                    is_valid = await self._verify_credentials(username, password)

                    if is_valid:
                        return AuthResult(
                            status=AuthStatus.SUCCESS,
                            user_id=username,
                            user_context={"username": username}
                        )

                    return AuthResult(
                        status=AuthStatus.INVALID_CREDENTIALS,
                        error_message="Invalid credentials"
                    )
            ```
        """
        pass

    @abstractmethod
    async def validate_credential(
        self, credential_payload: dict[str, Any]
    ) -> ValidationResult:
        """
        Validate existing credentials (tokens, API keys, etc.).

        This method validates previously issued credentials for ongoing
        authentication. Used for validating tokens, API keys, or other
        persistent authentication artifacts.

        Security requirements:
        - MUST use timing protection
        - MUST validate credential format and integrity
        - MUST check expiration and revocation status
        - MUST NOT expose credential details in errors

        Args:
            credential_payload: Credential data to validate including:
                - credential: The credential to validate (token, key, etc.)
                - metadata: Additional validation context

        Returns:
            ValidationResult indicating validity and user context

        Example:
            ```python
            async def validate_credential(self, credential_payload: dict[str, Any]) -> ValidationResult:
                async with timing_protection(1.0):
                    token = credential_payload.get("credential")

                    if not token:
                        return ValidationResult(is_valid=False)

                    # Validate token securely
                    user_data = await self._validate_token(token)

                    if user_data:
                        return ValidationResult(
                            is_valid=True,
                            user_id=user_data["user_id"],
                            user_context=user_data
                        )

                    return ValidationResult(is_valid=False)
            ```
        """
        pass

    @abstractmethod
    async def refresh_session(self, session_data: dict[str, Any]) -> RefreshResult:
        """
        Refresh authentication session or token.

        This method handles refreshing expired or expiring authentication
        artifacts. Implementation depends on the authentication method
        (JWT refresh tokens, session extension, etc.).

        Security requirements:
        - MUST use timing protection
        - MUST validate refresh eligibility
        - MUST issue new credentials securely
        - MUST invalidate old credentials if applicable

        Args:
            session_data: Session refresh context including:
                - refresh_token: Token or data needed for refresh
                - user_context: Current user information
                - metadata: Additional refresh context

        Returns:
            RefreshResult with new credentials or failure reason

        Example:
            ```python
            async def refresh_session(self, session_data: dict[str, Any]) -> RefreshResult:
                async with timing_protection(1.0):
                    refresh_token = session_data.get("refresh_token")

                    if not refresh_token:
                        return RefreshResult(success=False, error_message="No refresh token")

                    # Validate and use refresh token
                    new_token = await self._refresh_token(refresh_token)

                    if new_token:
                        return RefreshResult(
                            success=True,
                            new_token=new_token["access_token"],
                            expires_at=new_token["expires_at"]
                        )

                    return RefreshResult(success=False, error_message="Invalid refresh token")
            ```
        """
        pass

    def get_provider_name(self) -> str:
        """
        Get the name of this authentication provider.

        Returns:
            Human-readable provider name
        """
        return self.__class__.__name__

    def get_supported_methods(self) -> list[str]:
        """
        Get list of authentication methods supported by this provider.

        Returns:
            List of supported authentication method names
        """
        return ["default"]

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup resources when provider is being shut down.

        Override this method to cleanup any resources (connections,
        caches, etc.) when the provider is being destroyed.
        """
        pass
