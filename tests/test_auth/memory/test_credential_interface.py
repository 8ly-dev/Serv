"""Tests for MemoryCredentialProvider using proper interface methods only."""

import pytest

from serv.auth.audit.enforcement import AuditJournal
from serv.auth.exceptions import AuthenticationError
from serv.auth.types import Credentials, CredentialType, User
from serv.bundled.auth.memory.credential import MemoryCredentialProvider
from bevy import Container, get_registry
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def container():
    """Create a test container."""
    return Container(get_registry())


@pytest.fixture
def audit_journal():
    """Create a mock audit journal."""
    journal = MagicMock(spec=AuditJournal)
    journal.record_event = AsyncMock()
    return journal


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
        "argon2_time_cost": 1,
        "argon2_memory_cost": 1024,
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


class TestMemoryCredentialProviderInterface:
    """Test MemoryCredentialProvider using only the abstract interface methods."""

    @pytest.mark.asyncio
    async def test_create_password_credentials(self, provider, test_user, audit_journal):
        """Test creating password credentials using interface method."""
        password = "SecurePassword123!"
        
        # Create credentials using interface method
        credentials = Credentials(
            id="cred_password_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        
        # This should not raise an exception
        await provider.create_credentials(test_user.id, credentials, audit_journal)
        
        # Verify credential types are available
        types = await provider.get_credential_types(test_user.id)
        assert CredentialType.PASSWORD in types
        
        # Verify credentials work
        result = await provider.verify_credentials(credentials, audit_journal)
        assert result is True

    @pytest.mark.asyncio
    async def test_create_token_credentials(self, provider, test_user, audit_journal):
        """Test creating token credentials using interface method."""
        # Create token credentials using interface method
        credentials = Credentials(
            id="cred_token_test",
            user_id=test_user.id,
            type=CredentialType.TOKEN,
            data={"purpose": "api_access"},
            metadata={}
        )
        
        # This should not raise an exception
        await provider.create_credentials(test_user.id, credentials, audit_journal)
        
        # Verify credential types are available
        types = await provider.get_credential_types(test_user.id)
        assert CredentialType.TOKEN in types

    @pytest.mark.asyncio
    async def test_verify_credentials_password(self, provider, test_user, audit_journal):
        """Test verifying password credentials."""
        password = "SecurePassword123!"
        
        # Create credentials
        credentials = Credentials(
            id="cred_password_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        
        await provider.create_credentials(test_user.id, credentials, audit_journal)
        
        # Test correct password
        result = await provider.verify_credentials(credentials, audit_journal)
        assert result is True
        
        # Test wrong password
        wrong_credentials = Credentials(
            id="cred_wrong_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": "WrongPassword456!"},
            metadata={}
        )
        result = await provider.verify_credentials(wrong_credentials, audit_journal)
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
        
        await provider.update_credentials(test_user.id, old_credentials, new_credentials, audit_journal)
        
        # Old password should not work
        result = await provider.verify_credentials(old_credentials, audit_journal)
        assert result is False
        
        # New password should work
        result = await provider.verify_credentials(new_credentials, audit_journal)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_credentials(self, provider, test_user, audit_journal):
        """Test deleting credentials."""
        password = "SecurePassword123!"
        
        # Create credentials
        credentials = Credentials(
            id="cred_password_test",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": password},
            metadata={}
        )
        
        await provider.create_credentials(test_user.id, credentials, audit_journal)
        
        # Verify they exist
        types = await provider.get_credential_types(test_user.id)
        assert CredentialType.PASSWORD in types
        
        # Delete credentials
        await provider.delete_credentials(test_user.id, CredentialType.PASSWORD, audit_journal)
        
        # Verify they're gone
        types = await provider.get_credential_types(test_user.id)
        assert CredentialType.PASSWORD not in types
        
        # Verify credentials no longer work
        result = await provider.verify_credentials(credentials, audit_journal)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_credential_types(self, provider, test_user, audit_journal):
        """Test getting available credential types."""
        # Initially no credentials
        types = await provider.get_credential_types(test_user.id)
        assert len(types) == 0
        
        # Add password credentials
        password_creds = Credentials(
            id="cred_password_types",
            user_id=test_user.id,
            type=CredentialType.PASSWORD,
            data={"password": "Password123!"},
            metadata={}
        )
        await provider.create_credentials(test_user.id, password_creds, audit_journal)
        
        types = await provider.get_credential_types(test_user.id)
        assert CredentialType.PASSWORD in types
        assert len(types) == 1
        
        # Add token credentials
        token_creds = Credentials(
            id="cred_token_types",
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
    async def test_unsupported_credential_type(self, provider, test_user, audit_journal):
        """Test handling of unsupported credential types."""
        # Test with API_KEY type (not implemented in memory provider)
        credentials = Credentials(
            id="cred_api_key_test",
            user_id=test_user.id,
            type=CredentialType.API_KEY,
            data={"api_key": "test_key"},
            metadata={}
        )
        
        # Should raise exception for unsupported type
        with pytest.raises(AuthenticationError, match="Unsupported credential type"):
            await provider.create_credentials(test_user.id, credentials, audit_journal)

    @pytest.mark.asyncio
    async def test_audit_events_recorded(self, provider, test_user, audit_journal):
        """Test that audit events are properly recorded."""
        password = "SecurePassword123!"
        
        # Create credentials
        credentials = Credentials(
            id="cred_password_test",
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