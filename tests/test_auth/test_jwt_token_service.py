"""
Tests for JWT token service implementation.

Comprehensive test suite covering token generation, validation, refresh,
and security aspects of the JWT token service.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest

from serv.auth.types import Token
from serv.bundled.auth.tokens.jwt_token_service import JwtTokenService


class TestJwtTokenService:
    """Test JWT token service implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            "secret_key": "test-secret-key-must-be-long-enough-for-hs256",
            "algorithm": "HS256",
            "access_token_expiry": 3600,  # 1 hour
            "refresh_token_expiry": 86400,  # 24 hours
            "issuer": "test-issuer",
            "audience": "test-audience",
        }
        self.service = JwtTokenService(self.config)

    def test_init_with_valid_config(self):
        """Test initialization with valid configuration."""
        assert self.service.secret_key == self.config["secret_key"]
        assert self.service.algorithm == "HS256"
        assert self.service.access_token_expiry == 3600
        assert self.service.refresh_token_expiry == 86400
        assert self.service.issuer == "test-issuer"
        assert self.service.audience == "test-audience"

    def test_init_missing_secret_key(self):
        """Test initialization fails without secret key."""
        config = {"algorithm": "HS256"}
        with pytest.raises(ValueError, match="JWT token service requires 'secret_key'"):
            JwtTokenService(config)

    def test_init_invalid_algorithm(self):
        """Test initialization fails with invalid algorithm."""
        config = {
            "secret_key": "test-secret",
            "algorithm": "INVALID",
        }
        with pytest.raises(ValueError, match="Unsupported JWT algorithm: INVALID"):
            JwtTokenService(config)

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        config = {"secret_key": "test-secret-key"}
        service = JwtTokenService(config)
        
        assert service.algorithm == "HS256"
        assert service.access_token_expiry == 3600
        assert service.refresh_token_expiry == 86400
        assert service.issuer is None
        assert service.audience is None

    @pytest.mark.asyncio
    async def test_generate_access_token(self):
        """Test generating an access token."""
        payload = {"user_id": "test-user", "email": "test@example.com"}
        
        token = await self.service.generate_token(payload, "access")
        
        assert isinstance(token, Token)
        assert token.token_type == "access"
        assert token.user_id == "test-user"
        assert token.payload == payload
        assert token.is_active is True
        assert token.token_value is not None
        assert len(token.token_id) == 36  # UUID length
        
        # Check expiry is approximately 1 hour from now
        expected_expiry = datetime.now(UTC) + timedelta(seconds=3600)
        assert abs((token.expires_at - expected_expiry).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_generate_refresh_token(self):
        """Test generating a refresh token."""
        payload = {"user_id": "test-user"}
        
        token = await self.service.generate_token(payload, "refresh")
        
        assert token.token_type == "refresh"
        assert token.user_id == "test-user"
        
        # Check expiry is approximately 24 hours from now
        expected_expiry = datetime.now(UTC) + timedelta(seconds=86400)
        assert abs((token.expires_at - expected_expiry).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_generate_token_with_custom_expiry(self):
        """Test generating token with custom expiry."""
        payload = {"user_id": "test-user"}
        custom_expiry = 7200  # 2 hours
        
        token = await self.service.generate_token(payload, "access", custom_expiry)
        
        expected_expiry = datetime.now(UTC) + timedelta(seconds=custom_expiry)
        assert abs((token.expires_at - expected_expiry).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_validate_valid_token(self):
        """Test validating a valid token."""
        payload = {"user_id": "test-user", "role": "admin"}
        original_token = await self.service.generate_token(payload)
        
        validated_token = await self.service.validate_token(original_token.token_value)
        
        assert validated_token.token_id == original_token.token_id
        assert validated_token.token_type == "access"
        assert validated_token.user_id == "test-user"
        assert validated_token.payload == payload
        assert validated_token.is_active is True

    @pytest.mark.asyncio
    async def test_validate_expired_token(self):
        """Test validating an expired token."""
        # Create token with very short expiry
        payload = {"user_id": "test-user"}
        token = await self.service.generate_token(payload, expires_in=1)
        
        # Wait for token to expire
        import asyncio
        await asyncio.sleep(2)
        
        with pytest.raises(ValueError, match="Token has expired"):
            await self.service.validate_token(token.token_value)

    @pytest.mark.asyncio
    async def test_validate_invalid_token_format(self):
        """Test validating token with invalid format."""
        with pytest.raises(ValueError, match="Invalid token"):
            await self.service.validate_token("invalid.token.format")

    @pytest.mark.asyncio
    async def test_validate_token_wrong_secret(self):
        """Test validating token signed with different secret."""
        # Create token with different service
        other_config = self.config.copy()
        other_config["secret_key"] = "different-secret-key"
        other_service = JwtTokenService(other_config)
        
        payload = {"user_id": "test-user"}
        token = await other_service.generate_token(payload)
        
        with pytest.raises(ValueError, match="Invalid token"):
            await self.service.validate_token(token.token_value)

    @pytest.mark.asyncio
    async def test_validate_token_missing_jti(self):
        """Test validating token without JTI claim."""
        # Manually create JWT without JTI
        payload = {"user_id": "test-user", "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp())}
        token_value = jwt.encode(payload, self.service.secret_key, algorithm=self.service.algorithm)
        
        with pytest.raises(ValueError, match="Token missing required 'jti' claim"):
            await self.service.validate_token(token_value)

    @pytest.mark.asyncio
    async def test_refresh_token_success(self):
        """Test successful token refresh."""
        payload = {"user_id": "test-user", "role": "admin"}
        refresh_token = await self.service.generate_token(payload, "refresh")
        
        new_access_token = await self.service.refresh_token(refresh_token.token_value)
        
        assert new_access_token.token_type == "access"
        assert new_access_token.user_id == "test-user"
        assert new_access_token.payload == payload
        assert new_access_token.token_id != refresh_token.token_id  # Different token

    @pytest.mark.asyncio
    async def test_refresh_token_with_access_token_fails(self):
        """Test refresh fails when using access token."""
        payload = {"user_id": "test-user"}
        access_token = await self.service.generate_token(payload, "access")
        
        with pytest.raises(ValueError, match="Token is not a refresh token"):
            await self.service.refresh_token(access_token.token_value)

    @pytest.mark.asyncio
    async def test_refresh_expired_token_fails(self):
        """Test refresh fails with expired refresh token."""
        payload = {"user_id": "test-user"}
        refresh_token = await self.service.generate_token(payload, "refresh", expires_in=1)
        
        # Wait for token to expire
        import asyncio
        await asyncio.sleep(2)
        
        with pytest.raises(ValueError, match="Token has expired"):
            await self.service.refresh_token(refresh_token.token_value)

    @pytest.mark.asyncio
    async def test_revoke_token(self):
        """Test token revocation (stateless implementation)."""
        payload = {"user_id": "test-user"}
        token = await self.service.generate_token(payload)
        
        # Revocation should succeed for valid token
        result = await self.service.revoke_token(token.token_value)
        assert result is True
        
        # Revocation should fail for invalid token
        result = await self.service.revoke_token("invalid.token")
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_user_tokens(self):
        """Test revoking user tokens (stateless implementation)."""
        # For stateless JWT, this always returns 0
        result = await self.service.revoke_user_tokens("test-user")
        assert result == 0
        
        result = await self.service.revoke_user_tokens("test-user", "access")
        assert result == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens(self):
        """Test cleaning up expired tokens (stateless implementation)."""
        # For stateless JWT, this always returns 0
        result = await self.service.cleanup_expired_tokens()
        assert result == 0

    @pytest.mark.asyncio
    async def test_get_user_tokens(self):
        """Test getting user tokens (stateless implementation)."""
        # For stateless JWT, this always returns empty list
        result = await self.service._get_user_tokens("test-user")
        assert result == []
        
        result = await self.service._get_user_tokens("test-user", "access")
        assert result == []

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test service cleanup."""
        # Should not raise any exceptions
        await self.service.cleanup()

    @pytest.mark.asyncio
    async def test_jwt_claims_structure(self):
        """Test that JWT contains expected claims."""
        payload = {"user_id": "test-user", "custom": "data"}
        token = await self.service.generate_token(payload)
        
        # Decode the JWT to inspect claims
        claims = jwt.decode(
            token.token_value,
            self.service.secret_key,
            algorithms=[self.service.algorithm],
            audience=self.service.audience,
        )
        
        assert "jti" in claims  # JWT ID
        assert "iat" in claims  # Issued at
        assert "exp" in claims  # Expires at
        assert "type" in claims  # Token type
        assert "iss" in claims  # Issuer
        assert "aud" in claims  # Audience
        assert claims["user_id"] == "test-user"
        assert claims["custom"] == "data"
        assert claims["type"] == "access"
        assert claims["iss"] == "test-issuer"
        assert claims["aud"] == "test-audience"

    @pytest.mark.asyncio
    async def test_algorithm_security(self):
        """Test that service rejects algorithm confusion attacks."""
        # Create token with different algorithm
        payload = {
            "jti": str(uuid.uuid4()),
            "user_id": "test-user",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "type": "access",
        }
        
        # Try to create token with 'none' algorithm (security risk)
        malicious_token = jwt.encode(payload, "", algorithm="none")
        
        with pytest.raises(ValueError, match="Invalid token"):
            await self.service.validate_token(malicious_token)

    @pytest.mark.asyncio
    async def test_token_generation_uniqueness(self):
        """Test that each token has a unique ID."""
        payload = {"user_id": "test-user"}
        
        token1 = await self.service.generate_token(payload)
        token2 = await self.service.generate_token(payload)
        
        assert token1.token_id != token2.token_id
        assert token1.token_value != token2.token_value

    def test_supported_algorithms(self):
        """Test that all supported algorithms can be used."""
        supported_algorithms = [
            "HS256", "HS384", "HS512",
            "RS256", "RS384", "RS512",
            "ES256", "ES384", "ES512"
        ]
        
        for algorithm in supported_algorithms:
            config = {
                "secret_key": "test-secret-key",
                "algorithm": algorithm,
            }
            service = JwtTokenService(config)
            assert service.algorithm == algorithm

    @pytest.mark.asyncio
    async def test_token_validation_timing_consistency(self):
        """Test that token validation timing is consistent (basic check)."""
        payload = {"user_id": "test-user"}
        valid_token = await self.service.generate_token(payload)
        
        # Time valid token validation
        start_time = datetime.now(UTC)
        await self.service.validate_token(valid_token.token_value)
        valid_duration = (datetime.now(UTC) - start_time).total_seconds()
        
        # Time invalid token validation
        start_time = datetime.now(UTC)
        try:
            await self.service.validate_token("invalid.token.format")
        except ValueError:
            pass
        invalid_duration = (datetime.now(UTC) - start_time).total_seconds()
        
        # Both should take roughly similar time (basic timing attack protection)
        # Note: This is a simple check, real timing attack protection needs more sophisticated measures
        assert abs(valid_duration - invalid_duration) < 0.1  # Within 100ms

    @pytest.mark.asyncio
    async def test_token_with_subject_claim(self):
        """Test token generation and validation with 'sub' claim instead of 'user_id'."""
        payload = {"sub": "subject-user", "role": "admin"}
        token = await self.service.generate_token(payload)
        
        validated_token = await self.service.validate_token(token.token_value)
        
        # Should use 'sub' as user_id when 'user_id' is not present
        assert validated_token.user_id == "subject-user"
        assert validated_token.payload == payload

    @pytest.mark.asyncio
    async def test_service_without_issuer_audience(self):
        """Test service works without issuer and audience."""
        config = {"secret_key": "test-secret-key"}
        service = JwtTokenService(config)
        
        payload = {"user_id": "test-user"}
        token = await service.generate_token(payload)
        validated_token = await service.validate_token(token.token_value)
        
        assert validated_token.user_id == "test-user"
        assert validated_token.payload == payload