"""
Tests for JWT Authentication Provider.

These tests verify JWT token generation, validation, and authentication
with proper security considerations and error handling.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import jwt
import pytest

from serv.auth.types import AuthStatus
from serv.bundled.auth.providers.jwt_provider import JWTAuthProvider
from serv.http import Request


class TestJWTAuthProvider:
    """Test JWT authentication provider functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.secret_key = "test_secret_key_that_is_long_enough_for_jwt_validation_purposes"
        self.provider = JWTAuthProvider(
            secret_key=self.secret_key,
            algorithm="HS256",
            token_expiry_minutes=60,
            issuer="test-issuer",
            audience="test-audience",
        )

    def test_initialization_valid_config(self):
        """Test JWT provider initialization with valid configuration."""
        provider = JWTAuthProvider(
            secret_key="test_secret_key_that_is_long_enough_for_validation",
            algorithm="HS256",
            token_expiry_minutes=30,
        )

        assert provider.secret_key == "test_secret_key_that_is_long_enough_for_validation"
        assert provider.algorithm == "HS256"
        assert provider.token_expiry_minutes == 30
        assert provider.issuer is None
        assert provider.audience is None

    def test_initialization_with_issuer_and_audience(self):
        """Test JWT provider initialization with issuer and audience."""
        provider = JWTAuthProvider(
            secret_key="test_secret_key_that_is_long_enough_for_validation",
            issuer="test-issuer",
            audience="test-audience",
        )

        assert provider.issuer == "test-issuer"
        assert provider.audience == "test-audience"

    def test_initialization_invalid_secret_key_too_short(self):
        """Test initialization fails with short secret key."""
        with pytest.raises(ValueError, match="JWT secret key must be at least 32 characters"):
            JWTAuthProvider(secret_key="short")

    def test_initialization_invalid_algorithm(self):
        """Test initialization fails with invalid algorithm."""
        with pytest.raises(ValueError, match="Unsupported JWT algorithm"):
            JWTAuthProvider(
                secret_key="test_secret_key_that_is_long_enough_for_validation",
                algorithm="INVALID",
            )

    def test_initialization_invalid_token_expiry(self):
        """Test initialization fails with invalid token expiry."""
        with pytest.raises(ValueError, match="Token expiry must be a positive integer"):
            JWTAuthProvider(
                secret_key="test_secret_key_that_is_long_enough_for_validation",
                token_expiry_minutes=-10,
            )

    @pytest.mark.asyncio
    async def test_authenticate_request_valid_token(self):
        """Test successful authentication with valid JWT token."""
        # Generate a valid token
        now = datetime.now(UTC)
        payload = {
            "sub": "test-user-123",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iss": "test-issuer",
            "aud": "test-audience",
            "role": "admin",
        }
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        # Create mock request
        request = MagicMock(spec=Request)
        request.headers = {"authorization": f"Bearer {token}"}

        result = await self.provider.authenticate_request(request)

        assert result.status == AuthStatus.SUCCESS
        assert result.user_id == "test-user-123"
        assert result.user_context["user_id"] == "test-user-123"
        assert result.user_context["role"] == "admin"
        assert result.metadata["auth_method"] == "jwt"

    @pytest.mark.asyncio
    async def test_authenticate_request_missing_header(self):
        """Test authentication fails with missing Authorization header."""
        request = MagicMock(spec=Request)
        request.headers = {}

        result = await self.provider.authenticate_request(request)

        assert result.status == AuthStatus.INVALID_TOKEN
        assert "Missing or invalid Authorization header" in result.error_message

    @pytest.mark.asyncio
    async def test_authenticate_request_invalid_header_format(self):
        """Test authentication fails with invalid header format."""
        request = MagicMock(spec=Request)
        request.headers = {"authorization": "Basic invalid"}

        result = await self.provider.authenticate_request(request)

        assert result.status == AuthStatus.INVALID_TOKEN
        assert "Missing or invalid Authorization header" in result.error_message

    @pytest.mark.asyncio
    async def test_authenticate_request_empty_token(self):
        """Test authentication fails with empty token."""
        request = MagicMock(spec=Request)
        request.headers = {"authorization": "Bearer "}

        result = await self.provider.authenticate_request(request)

        assert result.status == AuthStatus.INVALID_TOKEN
        assert "Empty JWT token" in result.error_message

    @pytest.mark.asyncio
    async def test_authenticate_request_expired_token(self):
        """Test authentication fails with expired token."""
        # Generate an expired token
        past_time = datetime.now(UTC) - timedelta(hours=2)
        payload = {
            "sub": "test-user-123",
            "iat": int(past_time.timestamp()),
            "exp": int((past_time + timedelta(hours=1)).timestamp()),  # Expired
        }
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        request = MagicMock(spec=Request)
        request.headers = {"authorization": f"Bearer {token}"}

        result = await self.provider.authenticate_request(request)

        assert result.status == AuthStatus.SESSION_EXPIRED
        assert "JWT token has expired" in result.error_message

    @pytest.mark.asyncio
    async def test_authenticate_request_invalid_signature(self):
        """Test authentication fails with invalid signature."""
        # Generate token with wrong secret
        payload = {
            "sub": "test-user-123",
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        }
        token = jwt.encode(payload, "wrong_secret", algorithm="HS256")

        request = MagicMock(spec=Request)
        request.headers = {"authorization": f"Bearer {token}"}

        result = await self.provider.authenticate_request(request)

        assert result.status == AuthStatus.INVALID_TOKEN
        assert "Invalid JWT token" in result.error_message

    @pytest.mark.asyncio
    async def test_authenticate_request_missing_subject(self):
        """Test authentication fails when token missing 'sub' claim."""
        # Generate token without 'sub' claim
        now = datetime.now(UTC)
        payload = {
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iss": "test-issuer",
            "aud": "test-audience",
            # Missing 'sub'
        }
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        request = MagicMock(spec=Request)
        request.headers = {"authorization": f"Bearer {token}"}

        result = await self.provider.authenticate_request(request)

        assert result.status == AuthStatus.INVALID_TOKEN
        assert "JWT token missing 'sub' claim" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_credentials_success(self):
        """Test successful credential validation and token generation."""
        credential_data = {
            "user_id": "test-user-456",
            "role": "user",
            "email": "test@example.com",
        }

        result = await self.provider.validate_credentials("jwt", credential_data)

        assert result.is_valid is True
        assert result.user_id == "test-user-456"
        assert "token" in result.user_context
        assert result.user_context["user_id"] == "test-user-456"
        assert result.metadata["auth_method"] == "jwt"

        # Verify the generated token is valid
        token = result.user_context["token"]
        decoded = jwt.decode(
            token,
            self.secret_key,
            algorithms=["HS256"],
            audience="test-audience"
        )
        assert decoded["sub"] == "test-user-456"
        assert decoded["role"] == "user"
        assert decoded["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_validate_credentials_wrong_type(self):
        """Test validation fails with wrong credential type."""
        result = await self.provider.validate_credentials("password", {"user_id": "test"})

        assert result.is_valid is False
        assert "Unsupported credential type" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_credentials_missing_user_id(self):
        """Test validation fails when user_id is missing."""
        result = await self.provider.validate_credentials("jwt", {"role": "user"})

        assert result.is_valid is False
        assert "Missing user_id in credential data" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_credentials_excludes_sensitive_data(self):
        """Test that sensitive data is excluded from token payload."""
        credential_data = {
            "user_id": "test-user",
            "password": "secret_password",
            "password_hash": "hashed_password",
            "_internal_field": "internal_value",
            "role": "user",
        }

        result = await self.provider.validate_credentials("jwt", credential_data)

        # Decode token to check payload
        token = result.user_context["token"]
        decoded = jwt.decode(
            token,
            self.secret_key,
            algorithms=["HS256"],
            audience="test-audience"
        )

        assert "password" not in decoded
        assert "password_hash" not in decoded
        assert "_internal_field" not in decoded
        assert "role" in decoded

    @pytest.mark.asyncio
    async def test_initiate_auth_success(self):
        """Test successful auth initiation from request context."""
        # Generate a valid token
        now = datetime.now(UTC)
        payload = {
            "sub": "test-user-789",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iss": "test-issuer",
            "aud": "test-audience",
        }
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        request_context = {
            "headers": {"authorization": f"Bearer {token}"}
        }

        result = await self.provider.initiate_auth(request_context)

        assert result.status == AuthStatus.SUCCESS
        assert result.user_id == "test-user-789"

    @pytest.mark.asyncio
    async def test_initiate_auth_missing_header(self):
        """Test auth initiation fails with missing header."""
        request_context = {"headers": {}}

        result = await self.provider.initiate_auth(request_context)

        assert result.status == AuthStatus.INVALID_TOKEN
        assert "Missing or invalid Authorization header" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_credential_success(self):
        """Test successful credential validation."""
        # Generate a valid token
        now = datetime.now(UTC)
        payload = {
            "sub": "test-user-validate",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iss": "test-issuer",
            "aud": "test-audience",
            "role": "admin",
        }
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        credential_payload = {"credential": token}

        result = await self.provider.validate_credential(credential_payload)

        assert result.is_valid is True
        assert result.user_id == "test-user-validate"
        assert result.user_context["role"] == "admin"

    @pytest.mark.asyncio
    async def test_validate_credential_missing_credential(self):
        """Test credential validation fails when credential is missing."""
        result = await self.provider.validate_credential({})

        assert result.is_valid is False
        assert "No credential provided" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_credential_expired_token(self):
        """Test credential validation fails with expired token."""
        # Generate expired token
        past_time = datetime.now(UTC) - timedelta(hours=2)
        payload = {
            "sub": "test-user",
            "iat": int(past_time.timestamp()),
            "exp": int((past_time + timedelta(hours=1)).timestamp()),
            "iss": "test-issuer",
            "aud": "test-audience",
        }
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        result = await self.provider.validate_credential({"credential": token})

        assert result.is_valid is False
        assert "Token has expired" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_credential_invalid_token(self):
        """Test credential validation fails with invalid token."""
        result = await self.provider.validate_credential({"credential": "invalid.token.format"})

        assert result.is_valid is False
        assert "Invalid token" in result.error_message

    @pytest.mark.asyncio
    async def test_refresh_session_success(self):
        """Test successful session refresh."""
        session_data = {
            "user_context": {
                "user_id": "test-user-refresh",
                "role": "user",
                "email": "refresh@example.com",
            }
        }

        result = await self.provider.refresh_session(session_data)

        assert result.success is True
        assert result.new_token is not None
        assert result.expires_at is not None
        assert result.metadata["user_id"] == "test-user-refresh"

        # Verify new token is valid
        decoded = jwt.decode(
            result.new_token,
            self.secret_key,
            algorithms=["HS256"],
            audience="test-audience"
        )
        assert decoded["sub"] == "test-user-refresh"
        assert decoded["role"] == "user"
        assert decoded["email"] == "refresh@example.com"

    @pytest.mark.asyncio
    async def test_refresh_session_missing_user_id(self):
        """Test session refresh fails when user_id is missing."""
        session_data = {"user_context": {"role": "user"}}

        result = await self.provider.refresh_session(session_data)

        assert result.success is False
        assert "No user ID in session data" in result.error_message

    @pytest.mark.asyncio
    async def test_refresh_session_excludes_sensitive_fields(self):
        """Test that session refresh excludes sensitive fields from new token."""
        session_data = {
            "user_context": {
                "user_id": "test-user",
                "role": "user",
                "token": "old_token_value",
                "issued_at": "2023-01-01",
                "expires_at": "2023-01-02",
                "_private_field": "private_value",
            }
        }

        result = await self.provider.refresh_session(session_data)

        # Decode new token to check payload
        decoded = jwt.decode(
            result.new_token,
            self.secret_key,
            algorithms=["HS256"],
            audience="test-audience"
        )

        assert "token" not in decoded
        assert "issued_at" not in decoded  # Old issued_at
        assert "expires_at" not in decoded  # Old expires_at
        assert "_private_field" not in decoded
        assert "role" in decoded

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test cleanup method (should be no-op for stateless JWT provider)."""
        await self.provider.cleanup()
        # No assertions needed - just verify it doesn't crash

    def test_from_config_success(self):
        """Test creating JWT provider from configuration."""
        config = {
            "secret_key": "config_secret_key_that_is_long_enough_for_validation",
            "algorithm": "HS384",
            "token_expiry_minutes": 120,
            "issuer": "config-issuer",
            "audience": "config-audience",
        }

        provider = JWTAuthProvider.from_config(config)

        assert provider.secret_key == "config_secret_key_that_is_long_enough_for_validation"
        assert provider.algorithm == "HS384"
        assert provider.token_expiry_minutes == 120
        assert provider.issuer == "config-issuer"
        assert provider.audience == "config-audience"

    def test_from_config_minimal(self):
        """Test creating JWT provider from minimal configuration."""
        config = {"secret_key": "minimal_secret_key_that_is_long_enough_for_validation"}

        provider = JWTAuthProvider.from_config(config)

        assert provider.secret_key == "minimal_secret_key_that_is_long_enough_for_validation"
        assert provider.algorithm == "HS256"  # Default
        assert provider.token_expiry_minutes == 60  # Default
        assert provider.issuer is None
        assert provider.audience is None

    def test_from_config_missing_secret_key(self):
        """Test creating JWT provider fails when secret_key is missing."""
        config = {"algorithm": "HS256"}

        with pytest.raises(ValueError, match="JWT provider requires 'secret_key' in configuration"):
            JWTAuthProvider.from_config(config)

    @pytest.mark.asyncio
    async def test_timing_protection(self):
        """Test that timing protection is applied to prevent timing attacks."""
        import time

        # Test with invalid token - should still take some time
        request = MagicMock(spec=Request)
        request.headers = {"authorization": "Bearer invalid.token.here"}

        start_time = time.time()
        result = await self.provider.authenticate_request(request)
        elapsed_time = time.time() - start_time

        # Should take at least some time due to timing protection
        assert elapsed_time >= 0.05  # Should be at least 50ms due to timing protection
        assert result.status == AuthStatus.INVALID_TOKEN

    @pytest.mark.asyncio
    async def test_algorithm_validation_prevents_confusion_attack(self):
        """Test that algorithm validation prevents algorithm confusion attacks."""
        # Try to create a token with 'none' algorithm
        payload = {
            "sub": "test-user",
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        }

        # Create token with 'none' algorithm (unsigned)
        header = {"alg": "none", "typ": "JWT"}
        token_parts = [
            jwt.utils.base64url_encode(json.dumps(header).encode()),
            jwt.utils.base64url_encode(json.dumps(payload).encode()),
            b"",  # No signature for 'none' algorithm
        ]
        malicious_token = b".".join(token_parts).decode()

        request = MagicMock(spec=Request)
        request.headers = {"authorization": f"Bearer {malicious_token}"}

        result = await self.provider.authenticate_request(request)

        # Should reject the token due to algorithm validation
        assert result.status == AuthStatus.INVALID_TOKEN
        assert "Invalid JWT token" in result.error_message

    @pytest.mark.asyncio
    async def test_custom_claims_preserved(self):
        """Test that custom claims are preserved in user context."""
        credential_data = {
            "user_id": "test-user",
            "role": "admin",
            "department": "engineering",
            "permissions": ["read", "write", "admin"],
            "metadata": {"team": "backend", "level": "senior"},
        }

        result = await self.provider.validate_credentials("jwt", credential_data)

        # Verify custom claims are in user context
        # First decode the generated token to check the payload
        token = result.user_context["token"]
        decoded = jwt.decode(
            token,
            self.secret_key,
            algorithms=["HS256"],
            audience="test-audience"
        )

        assert decoded["role"] == "admin"
        assert decoded["department"] == "engineering"
        assert decoded["permissions"] == ["read", "write", "admin"]
        assert decoded["metadata"] == {"team": "backend", "level": "senior"}

    @pytest.mark.asyncio
    async def test_issuer_audience_validation(self):
        """Test that issuer and audience validation works correctly."""
        # Create provider with specific issuer/audience
        provider = JWTAuthProvider(
            secret_key=self.secret_key,
            issuer="valid-issuer",
            audience="valid-audience",
        )

        # Generate token with wrong issuer
        now = datetime.now(UTC)
        payload = {
            "sub": "test-user",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iss": "wrong-issuer",
            "aud": "valid-audience",
        }
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        request = MagicMock(spec=Request)
        request.headers = {"authorization": f"Bearer {token}"}

        result = await provider.authenticate_request(request)

        assert result.status == AuthStatus.INVALID_TOKEN
        assert "Invalid JWT token" in result.error_message
