"""Tests for MemoryCredentialProvider using only abstract interface methods."""

import asyncio
import secrets
from unittest.mock import AsyncMock, MagicMock

import pytest

from serv.auth.audit.enforcement import AuditJournal
from serv.auth.exceptions import AuthenticationError, InvalidCredentialsError
from serv.auth.types import Credentials, CredentialType, User
from serv.bundled.auth.memory.credential import MemoryCredentialProvider
from bevy import Container, get_registry


@pytest.fixture
def container():
    """Create a test container."""
    return Container(get_registry())


@pytest.fixture
def audit_journal():
    """Create a mock audit journal."""
    mock = MagicMock(spec=AuditJournal)
    mock.record_event = AsyncMock()
    return mock


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
        id="test_user",
        email="test@example.com",
        username="testuser",
    )


class TestMemoryCredentialProvider:
    """Test MemoryCredentialProvider functionality using abstract interface."""

    @pytest.mark.asyncio
    async def test_create_password_credentials_valid(self, provider, test_user, audit_journal):
        """Test creating valid password credentials."""
        password = "SecurePassword123!"
        
        credentials = Credentials(
            id="cred_password_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        
        await provider.create_credentials(test_user.id, credentials, audit_journal)
        
        # Verify credentials were created
        types = await provider.get_credential_types(test_user.id)
        assert CredentialType.PASSWORD in types

    @pytest.mark.asyncio
    async def test_create_password_credentials_too_short(self, provider, test_user, audit_journal):
        """Test creating password that's too short."""
        password = "short"
        
        credentials = Credentials(
            id="cred_password_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        
        with pytest.raises(AuthenticationError, match="Password must be at least"):
            await provider.create_credentials(test_user.id, credentials, audit_journal)

    @pytest.mark.asyncio
    async def test_verify_password_credentials_success(self, provider, test_user, audit_journal):
        """Test successful password verification."""
        password = "SecurePassword123!"
        
        # Create credentials first
        credentials = Credentials(
            id="cred_password_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        await provider.create_credentials(test_user.id, credentials, audit_journal)
        
        # Verify credentials
        result = await provider.verify_credentials(credentials, audit_journal)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_password_credentials_wrong(self, provider, test_user, audit_journal):
        """Test password verification with wrong password."""
        correct_password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        
        # Create credentials first
        credentials = Credentials(
            id="cred_password_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": correct_password},
            metadata={}
        )
        await provider.create_credentials(test_user.id, credentials, audit_journal)
        
        # Verify with wrong password
        wrong_credentials = Credentials(
            id="cred_wrong_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": wrong_password},
            metadata={}
        )
        
        result = await provider.verify_credentials(wrong_credentials, audit_journal)
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_credentials_nonexistent_user(self, provider, audit_journal):
        """Test password verification for non-existent user."""
        credentials = Credentials(
            id="cred_nonexistent_test",
            user_id="nonexistent_user",
            type=CredentialType.PASSWORD,
            data={"password": "any_password"},
            metadata={}
        )
        
        result = await provider.verify_credentials(credentials, audit_journal)
        assert result is False

    @pytest.mark.asyncio
    async def test_create_token_credentials(self, provider, test_user, audit_journal):
        """Test creating token credentials."""
        credentials = Credentials(
            id="cred_token_test",
            user_id=test_user.id,
            type=CredentialType.TOKEN,
            data={"purpose": "test_purpose"},
            metadata={}
        )
        
        await provider.create_credentials(test_user.id, credentials, audit_journal)
        
        # Verify credentials were created
        types = await provider.get_credential_types(test_user.id)
        assert CredentialType.TOKEN in types

    @pytest.mark.asyncio
    async def test_verify_token_credentials_nonexistent(self, provider, audit_journal):
        """Test verification of non-existent token."""
        fake_token = secrets.token_hex(32)
        
        credentials = Credentials(
            id="cred_token_test",
            user_id="test_user",
            type=CredentialType.TOKEN,
            data={"token": fake_token},
            metadata={}
        )
        
        result = await provider.verify_credentials(credentials, audit_journal)
        assert result is False

    @pytest.mark.asyncio
    async def test_update_password_credentials(self, provider, test_user, audit_journal):
        """Test updating password credentials."""
        old_password = "OldPassword123!"
        new_password = "NewPassword456!"
        
        # Create initial credentials
        old_credentials = Credentials(
            id="cred_old_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": old_password},
            metadata={}
        )
        await provider.create_credentials(test_user.id, old_credentials, audit_journal)
        
        # Update credentials
        new_credentials = Credentials(
            id="cred_new_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": new_password},
            metadata={}
        )
        
        await provider.update_credentials(
            test_user.id, old_credentials, new_credentials, audit_journal
        )
        
        # Old password should not work
        result = await provider.verify_credentials(old_credentials, audit_journal)
        assert result is False
        
        # New password should work
        result = await provider.verify_credentials(new_credentials, audit_journal)
        assert result is True

    @pytest.mark.asyncio
    async def test_update_credentials_wrong_old_password(self, provider, test_user, audit_journal):
        """Test updating credentials with wrong old password."""
        old_password = "OldPassword123!"
        wrong_old = "WrongOld123!"
        new_password = "NewPassword456!"
        
        # Create initial credentials
        old_credentials = Credentials(
            id="cred_old_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": old_password},
            metadata={}
        )
        await provider.create_credentials(test_user.id, old_credentials, audit_journal)
        
        # Try to update with wrong old password
        wrong_old_credentials = Credentials(
            id="cred_wrong_old_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": wrong_old},
            metadata={}
        )
        new_credentials = Credentials(
            id="cred_new_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": new_password},
            metadata={}
        )
        
        with pytest.raises(AuthenticationError, match="Current password is incorrect"):
            await provider.update_credentials(
                test_user.id, wrong_old_credentials, new_credentials, audit_journal
            )

    @pytest.mark.asyncio
    async def test_delete_password_credentials(self, provider, test_user, audit_journal):
        """Test deleting password credentials."""
        password = "SecurePassword123!"
        
        # Create credentials first
        credentials = Credentials(
            id="cred_password_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        await provider.create_credentials(test_user.id, credentials, audit_journal)
        
        # Verify credentials exist
        types = await provider.get_credential_types(test_user.id)
        assert CredentialType.PASSWORD in types
        
        # Delete credentials
        await provider.delete_credentials(test_user.id, CredentialType.PASSWORD, audit_journal)
        
        # Verify credentials are gone
        types = await provider.get_credential_types(test_user.id)
        assert CredentialType.PASSWORD not in types
        
        # Verify credentials no longer work
        result = await provider.verify_credentials(credentials, audit_journal)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_credential_types_empty(self, provider, test_user):
        """Test getting credential types for user with no credentials."""
        types = await provider.get_credential_types(test_user.id)
        assert len(types) == 0

    @pytest.mark.asyncio
    async def test_get_credential_types_multiple(self, provider, test_user, audit_journal):
        """Test getting multiple credential types."""
        # Add password credentials
        password_creds = Credentials(
            id="cred_password_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": "Password123!"},
            metadata={}
        )
        await provider.create_credentials(test_user.id, password_creds, audit_journal)
        
        # Add token credentials
        token_creds = Credentials(
            id="cred_token_test",
            user_id=test_user.id,
            type=CredentialType.TOKEN,
            data={"purpose": "api"},
            metadata={}
        )
        await provider.create_credentials(test_user.id, token_creds, audit_journal)
        
        types = await provider.get_credential_types(test_user.id)
        assert CredentialType.PASSWORD in types
        assert CredentialType.TOKEN in types
        assert len(types) == 2

    @pytest.mark.asyncio
    async def test_is_credential_compromised(self, provider, test_user):
        """Test checking if credentials are compromised."""
        credentials = Credentials(
            id="cred_compromised_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": "Password123!"},
            metadata={}
        )
        
        # Memory provider should return False (no external checking)
        result = await provider.is_credential_compromised(credentials)
        assert result is False

    @pytest.mark.asyncio
    async def test_unsupported_credential_type_create(self, provider, test_user, audit_journal):
        """Test creating credentials with unsupported type."""
        credentials = Credentials(
            id="cred_api_key_test",
            user_id=test_user.id,
            type=CredentialType.API_KEY,  # Unsupported by memory provider
            data={"api_key": "test_key"},
            metadata={}
        )
        
        with pytest.raises(AuthenticationError, match="Unsupported credential type"):
            await provider.create_credentials(test_user.id, credentials, audit_journal)

    @pytest.mark.asyncio
    async def test_unsupported_credential_type_verify(self, provider, test_user, audit_journal):
        """Test verifying credentials with unsupported type."""
        credentials = Credentials(
            id="cred_api_key_test",
            user_id=test_user.id,
            type=CredentialType.API_KEY,  # Unsupported by memory provider
            data={"api_key": "test_key"},
            metadata={}
        )
        
        result = await provider.verify_credentials(credentials, audit_journal)
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_credentials_missing_password_field(self, provider, test_user, audit_journal):
        """Test verifying credentials with password field missing in data."""
        credentials = Credentials(
            id="cred_missing_password_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"other_field": "value"},  # Password field missing
            metadata={}
        )
        
        result = await provider.verify_credentials(credentials, audit_journal)
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_credentials_missing_token_field(self, provider, test_user, audit_journal):
        """Test verifying credentials with token field missing in data."""
        credentials = Credentials(
            id="cred_missing_token_test",
            user_id=test_user.id,
            type=CredentialType.TOKEN,
            data={"purpose": "test"},  # Token field missing
            metadata={}
        )
        
        result = await provider.verify_credentials(credentials, audit_journal)
        assert result is False

    @pytest.mark.asyncio
    async def test_create_credentials_missing_password_field(self, provider, test_user, audit_journal):
        """Test creating credentials with password field missing."""
        credentials = Credentials(
            id="cred_missing_password_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"other_field": "value"},  # Password field missing
            metadata={}
        )
        
        with pytest.raises(AuthenticationError, match="Password is required"):
            await provider.create_credentials(test_user.id, credentials, audit_journal)

    @pytest.mark.asyncio
    async def test_update_credentials_type_mismatch(self, provider, test_user, audit_journal):
        """Test updating credentials with different types."""
        password = "Password123!"
        
        # Create password credentials
        password_creds = Credentials(
            id="cred_password_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        await provider.create_credentials(test_user.id, password_creds, audit_journal)
        
        # Try to update to token type
        token_creds = Credentials(
            id="cred_token_test",
            user_id=test_user.id,
            type=CredentialType.TOKEN,
            data={"purpose": "api"},
            metadata={}
        )
        
        with pytest.raises(AuthenticationError, match="Cannot change credential type"):
            await provider.update_credentials(
                test_user.id, password_creds, token_creds, audit_journal
            )

    @pytest.mark.asyncio
    async def test_delete_nonexistent_credentials(self, provider, test_user, audit_journal):
        """Test deleting non-existent credentials."""
        # This should not raise an exception
        await provider.delete_credentials(test_user.id, CredentialType.PASSWORD, audit_journal)
        
        # Verify no credentials exist
        types = await provider.get_credential_types(test_user.id)
        assert len(types) == 0

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, provider, audit_journal):
        """Test concurrent operations don't cause race conditions."""
        async def create_and_verify_worker(user_id, password):
            try:
                credentials = Credentials(
                    id=f"cred_{user_id}",
                    user_id=user_id,
                    type=CredentialType.PASSWORD,
                    data={"password": password},
                    metadata={}
                )
                await provider.create_credentials(user_id, credentials, audit_journal)
                result = await provider.verify_credentials(credentials, audit_journal)
                return result
            except Exception:
                return False
        
        # Create multiple users concurrently
        tasks = []
        for i in range(10):
            user_id = f"user_{i}"
            password = f"Password{i}123!"
            tasks.append(create_and_verify_worker(user_id, password))
        
        results = await asyncio.gather(*tasks)
        assert all(results)  # All operations should succeed

    @pytest.mark.asyncio
    async def test_audit_events_recorded(self, provider, test_user, audit_journal):
        """Test that audit events are properly recorded."""
        password = "SecurePassword123!"
        
        # Create credentials
        credentials = Credentials(
            id="cred_audit_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        
        await provider.create_credentials(test_user.id, credentials, audit_journal)
        
        # Verify audit journal was called for creation
        audit_journal.record_event.assert_called()
        
        # Reset mock and verify credentials
        audit_journal.reset_mock()
        await provider.verify_credentials(credentials, audit_journal)
        
        # Verify audit journal was called for verification
        audit_journal.record_event.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_lifecycle(self, provider):
        """Test cleanup task lifecycle."""
        # Start cleanup (called internally)
        await provider._ensure_cleanup_started()
        assert provider._cleanup_started is True
        
        # Starting again should be idempotent
        await provider._ensure_cleanup_started()
        assert provider._cleanup_started is True