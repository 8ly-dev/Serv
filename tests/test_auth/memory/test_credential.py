"""Tests for MemoryCredentialProvider."""

import asyncio
import secrets
from unittest.mock import MagicMock

import pytest

from serv.auth.audit.enforcement import AuditJournal
from serv.auth.exceptions import AuthenticationError, AuthorizationError
from serv.auth.types import User
from serv.bundled.auth.memory.credential import MemoryCredentialProvider
from bevy import Container, get_registry


@pytest.fixture
def container():
    """Create a test container."""
    return Container(get_registry())


@pytest.fixture
def audit_journal():
    """Create a mock audit journal."""
    return MagicMock(spec=AuditJournal)


@pytest.fixture
def config():
    """Create test configuration."""
    return {
        "cleanup_interval": 0.1,
        "max_login_attempts": 3,
        "account_lockout_duration": 300.0,
        "password_min_length": 8,
        "require_password_complexity": True,
        "token_length": 32,
        "token_ttl": 3600,
        "argon2_time_cost": 1,  # Lower for faster tests
        "argon2_memory_cost": 1024,  # Lower for faster tests
        "argon2_parallelism": 1,
    }


@pytest.fixture
def provider(config, container):
    """Create a MemoryCredentialProvider instance."""
    return MemoryCredentialProvider(config, container)


@pytest.fixture
def test_user():
    """Create a test user."""
    return User(
        user_id="test_user",
        email="test@example.com",
        username="testuser",
        display_name="Test User",
    )


class TestMemoryCredentialProvider:
    """Test MemoryCredentialProvider functionality."""

    @pytest.mark.asyncio
    async def test_set_password_valid(self, provider, test_user, audit_journal):
        """Test setting a valid password."""
        password = "SecurePassword123!"
        
        result = await provider.set_password(
            test_user.user_id, password, audit_journal
        )
        
        assert result is True
        
        # Verify password was stored
        stored = provider.store.get("passwords", test_user.user_id)
        assert stored is not None
        assert "password_hash" in stored
        assert "created_at" in stored

    @pytest.mark.asyncio
    async def test_set_password_too_short(self, provider, test_user, audit_journal):
        """Test setting a password that's too short."""
        password = "short"
        
        with pytest.raises(AuthenticationError, match="Password must be at least"):
            await provider.set_password(test_user.user_id, password, audit_journal)

    @pytest.mark.asyncio
    async def test_set_password_complexity_required(self, provider, test_user, audit_journal):
        """Test password complexity requirements."""
        # Simple password without complexity
        password = "simplepassword"
        
        with pytest.raises(AuthenticationError, match="Password must contain"):
            await provider.set_password(test_user.user_id, password, audit_journal)

    @pytest.mark.asyncio
    async def test_set_password_complexity_disabled(self, config, container, test_user, audit_journal):
        """Test password setting with complexity disabled."""
        config["require_password_complexity"] = False
        provider = MemoryCredentialProvider(config, container)
        
        password = "simplepassword"
        
        result = await provider.set_password(
            test_user.user_id, password, audit_journal
        )
        
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_password_success(self, provider, test_user, audit_journal):
        """Test successful password verification."""
        password = "SecurePassword123!"
        
        # Set password first
        await provider.set_password(test_user.user_id, password, audit_journal)
        
        # Verify password
        result = await provider.verify_password(
            test_user.user_id, password, audit_journal
        )
        
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_password_wrong(self, provider, test_user, audit_journal):
        """Test password verification with wrong password."""
        correct_password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        
        # Set password first
        await provider.set_password(test_user.user_id, correct_password, audit_journal)
        
        # Verify with wrong password
        result = await provider.verify_password(
            test_user.user_id, wrong_password, audit_journal
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_password_nonexistent_user(self, provider, audit_journal):
        """Test password verification for non-existent user."""
        result = await provider.verify_password(
            "nonexistent_user", "any_password", audit_journal
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_account_lockout(self, provider, test_user, audit_journal):
        """Test account lockout after multiple failed attempts."""
        password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        
        # Set password first
        await provider.set_password(test_user.user_id, password, audit_journal)
        
        # Make multiple failed attempts
        for _ in range(3):
            result = await provider.verify_password(
                test_user.user_id, wrong_password, audit_journal
            )
            assert result is False
        
        # Account should now be locked
        result = await provider.verify_password(
            test_user.user_id, password, audit_journal  # Even correct password should fail
        )
        assert result is False
        
        # Check lockout status
        is_locked = await provider.is_account_locked(test_user.user_id)
        assert is_locked is True

    @pytest.mark.asyncio
    async def test_unlock_account(self, provider, test_user, audit_journal):
        """Test unlocking a locked account."""
        password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        
        # Set password and lock account
        await provider.set_password(test_user.user_id, password, audit_journal)
        
        for _ in range(3):
            await provider.verify_password(test_user.user_id, wrong_password, audit_journal)
        
        # Verify account is locked
        assert await provider.is_account_locked(test_user.user_id) is True
        
        # Unlock account
        result = await provider.unlock_account(test_user.user_id, audit_journal)
        assert result is True
        
        # Verify account is unlocked
        assert await provider.is_account_locked(test_user.user_id) is False
        
        # Should be able to login again
        result = await provider.verify_password(test_user.user_id, password, audit_journal)
        assert result is True

    @pytest.mark.asyncio
    async def test_lockout_expiration(self, config, container, test_user, audit_journal):
        """Test that account lockout expires after configured duration."""
        # Set very short lockout duration for testing
        config["account_lockout_duration"] = 0.1
        provider = MemoryCredentialProvider(config, container)
        
        password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        
        # Set password and lock account
        await provider.set_password(test_user.user_id, password, audit_journal)
        
        for _ in range(3):
            await provider.verify_password(test_user.user_id, wrong_password, audit_journal)
        
        # Verify account is locked
        assert await provider.is_account_locked(test_user.user_id) is True
        
        # Wait for lockout to expire
        await asyncio.sleep(0.2)
        
        # Should be able to login again
        result = await provider.verify_password(test_user.user_id, password, audit_journal)
        assert result is True

    @pytest.mark.asyncio
    async def test_generate_token(self, provider, test_user, audit_journal):
        """Test token generation."""
        token = await provider.generate_token(
            test_user.user_id, "test_purpose", audit_journal
        )
        
        assert isinstance(token, str)
        assert len(token) == provider.token_length * 2  # hex encoding doubles length
        
        # Verify token was stored
        stored = provider.store.get("tokens", token)
        assert stored is not None
        assert stored["user_id"] == test_user.user_id
        assert stored["purpose"] == "test_purpose"

    @pytest.mark.asyncio
    async def test_verify_token_success(self, provider, test_user, audit_journal):
        """Test successful token verification."""
        token = await provider.generate_token(
            test_user.user_id, "test_purpose", audit_journal
        )
        
        result = await provider.verify_token(token, "test_purpose", audit_journal)
        assert result == test_user.user_id

    @pytest.mark.asyncio
    async def test_verify_token_wrong_purpose(self, provider, test_user, audit_journal):
        """Test token verification with wrong purpose."""
        token = await provider.generate_token(
            test_user.user_id, "test_purpose", audit_journal
        )
        
        result = await provider.verify_token(token, "wrong_purpose", audit_journal)
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_token_nonexistent(self, provider, audit_journal):
        """Test verification of non-existent token."""
        fake_token = secrets.token_hex(32)
        
        result = await provider.verify_token(fake_token, "any_purpose", audit_journal)
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_token_expired(self, config, container, test_user, audit_journal):
        """Test verification of expired token."""
        # Set very short TTL for testing
        config["token_ttl"] = 0.1
        provider = MemoryCredentialProvider(config, container)
        
        token = await provider.generate_token(
            test_user.user_id, "test_purpose", audit_journal
        )
        
        # Wait for token to expire
        await asyncio.sleep(0.2)
        
        result = await provider.verify_token(token, "test_purpose", audit_journal)
        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_token(self, provider, test_user, audit_journal):
        """Test token revocation."""
        token = await provider.generate_token(
            test_user.user_id, "test_purpose", audit_journal
        )
        
        # Verify token works
        result = await provider.verify_token(token, "test_purpose", audit_journal)
        assert result == test_user.user_id
        
        # Revoke token
        revoked = await provider.revoke_token(token, audit_journal)
        assert revoked is True
        
        # Token should no longer work
        result = await provider.verify_token(token, "test_purpose", audit_journal)
        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_user_tokens(self, provider, test_user, audit_journal):
        """Test revoking all tokens for a user."""
        # Generate multiple tokens
        tokens = []
        for i in range(3):
            token = await provider.generate_token(
                test_user.user_id, f"purpose_{i}", audit_journal
            )
            tokens.append(token)
        
        # Verify all tokens work
        for i, token in enumerate(tokens):
            result = await provider.verify_token(token, f"purpose_{i}", audit_journal)
            assert result == test_user.user_id
        
        # Revoke all user tokens
        count = await provider.revoke_user_tokens(test_user.user_id, audit_journal)
        assert count == 3
        
        # All tokens should be revoked
        for i, token in enumerate(tokens):
            result = await provider.verify_token(token, f"purpose_{i}", audit_journal)
            assert result is None

    @pytest.mark.asyncio
    async def test_change_password(self, provider, test_user, audit_journal):
        """Test changing password."""
        old_password = "OldPassword123!"
        new_password = "NewPassword456!"
        
        # Set initial password
        await provider.set_password(test_user.user_id, old_password, audit_journal)
        
        # Change password
        result = await provider.change_password(
            test_user.user_id, old_password, new_password, audit_journal
        )
        assert result is True
        
        # Old password should not work
        result = await provider.verify_password(
            test_user.user_id, old_password, audit_journal
        )
        assert result is False
        
        # New password should work
        result = await provider.verify_password(
            test_user.user_id, new_password, audit_journal
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self, provider, test_user, audit_journal):
        """Test changing password with wrong old password."""
        old_password = "OldPassword123!"
        wrong_old = "WrongOld123!"
        new_password = "NewPassword456!"
        
        # Set initial password
        await provider.set_password(test_user.user_id, old_password, audit_journal)
        
        # Try to change with wrong old password
        with pytest.raises(AuthenticationError, match="Current password is incorrect"):
            await provider.change_password(
                test_user.user_id, wrong_old, new_password, audit_journal
            )

    @pytest.mark.asyncio
    async def test_delete_credentials(self, provider, test_user, audit_journal):
        """Test deleting user credentials."""
        password = "SecurePassword123!"
        
        # Set password and generate token
        await provider.set_password(test_user.user_id, password, audit_journal)
        token = await provider.generate_token(
            test_user.user_id, "test_purpose", audit_journal
        )
        
        # Delete credentials
        result = await provider.delete_credentials(test_user.user_id, audit_journal)
        assert result is True
        
        # Password should not work
        result = await provider.verify_password(
            test_user.user_id, password, audit_journal
        )
        assert result is False
        
        # Token should not work
        result = await provider.verify_token(token, "test_purpose", audit_journal)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_statistics(self, provider, test_user, audit_journal):
        """Test getting provider statistics."""
        # Initially empty
        stats = await provider.get_statistics()
        assert stats["total_users"] == 0
        assert stats["locked_accounts"] == 0
        assert stats["active_tokens"] == 0
        
        # Add some data
        await provider.set_password(test_user.user_id, "Password123!", audit_journal)
        await provider.generate_token(test_user.user_id, "purpose", audit_journal)
        
        # Check updated stats
        stats = await provider.get_statistics()
        assert stats["total_users"] == 1
        assert stats["locked_accounts"] == 0
        assert stats["active_tokens"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, provider, audit_journal):
        """Test concurrent operations don't cause race conditions."""
        import asyncio
        
        async def set_password_worker(user_id, password):
            try:
                await provider.set_password(user_id, password, audit_journal)
                return True
            except Exception:
                return False
        
        async def verify_password_worker(user_id, password):
            try:
                return await provider.verify_password(user_id, password, audit_journal)
            except Exception:
                return False
        
        # Create multiple users concurrently
        tasks = []
        for i in range(10):
            user_id = f"user_{i}"
            password = f"Password{i}123!"
            tasks.append(set_password_worker(user_id, password))
        
        results = await asyncio.gather(*tasks)
        assert all(results)  # All password sets should succeed
        
        # Verify all passwords concurrently
        verify_tasks = []
        for i in range(10):
            user_id = f"user_{i}"
            password = f"Password{i}123!"
            verify_tasks.append(verify_password_worker(user_id, password))
        
        verify_results = await asyncio.gather(*verify_tasks)
        assert all(verify_results)  # All verifications should succeed

    @pytest.mark.asyncio
    async def test_cleanup_lifecycle(self, provider):
        """Test cleanup task lifecycle."""
        # Start cleanup
        await provider._ensure_cleanup_started()
        assert provider._cleanup_started is True
        
        # Starting again should be idempotent
        await provider._ensure_cleanup_started()
        assert provider._cleanup_started is True

    def test_password_complexity_validation(self, provider):
        """Test password complexity validation logic."""
        # Valid complex passwords
        assert provider._validate_password_complexity("SecurePassword123!")
        assert provider._validate_password_complexity("MyP@ssw0rd")
        assert provider._validate_password_complexity("Test123$")
        
        # Invalid passwords
        assert not provider._validate_password_complexity("onlylowercase")
        assert not provider._validate_password_complexity("ONLYUPPERCASE")
        assert not provider._validate_password_complexity("NoNumbers!")
        assert not provider._validate_password_complexity("NoSpecial123")
        assert not provider._validate_password_complexity("12345678")  # Only numbers

    @pytest.mark.asyncio
    async def test_error_handling(self, provider, test_user, audit_journal):
        """Test error handling in various scenarios."""
        # Test operations on non-existent user
        result = await provider.change_password(
            "nonexistent", "old", "new", audit_journal
        )
        assert result is False
        
        result = await provider.unlock_account("nonexistent", audit_journal)
        assert result is False
        
        result = await provider.delete_credentials("nonexistent", audit_journal)
        assert result is False
        
        # Test lockout operations on user without credentials
        is_locked = await provider.is_account_locked("nonexistent")
        assert is_locked is False