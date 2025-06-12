"""Test cases for auth provider interfaces."""

import pytest
from abc import ABC
from datetime import datetime, timedelta
from typing import Dict, Any, Set, Optional, List
from unittest.mock import Mock, AsyncMock

from serv.auth.providers.base import BaseProvider
from serv.auth.providers.credential import CredentialProvider
from serv.auth.providers.session import SessionProvider
from serv.auth.providers.user import UserProvider
from serv.auth.providers.auth import AuthProvider
from serv.auth.providers.audit import AuditProvider
from serv.auth.audit.decorators import AuditEnforced
from serv.auth.audit.enforcement import AuditJournal
from serv.auth.types import (
    User,
    Session,
    Credentials,
    Permission,
    Role,
    CredentialType,
    AuditEvent,
)


class TestBaseProvider:
    """Test base provider functionality."""

    def test_base_provider_is_abstract(self):
        """Test that BaseProvider is abstract."""
        with pytest.raises(TypeError):
            BaseProvider()

    def test_base_provider_inheritance(self):
        """Test BaseProvider inheritance from AuditEnforced."""
        assert issubclass(BaseProvider, AuditEnforced)


class TestCredentialProvider:
    """Test CredentialProvider interface."""

    def test_credential_provider_is_abstract(self):
        """Test that CredentialProvider is abstract."""
        with pytest.raises(TypeError):
            CredentialProvider()

    def test_credential_provider_inheritance(self):
        """Test CredentialProvider inheritance."""
        assert issubclass(CredentialProvider, BaseProvider)
        assert issubclass(CredentialProvider, ABC)

    def test_credential_provider_has_required_methods(self):
        """Test that CredentialProvider has all required abstract methods."""
        expected_methods = {
            "verify_credentials",
            "create_credentials",
            "update_credentials",
            "delete_credentials",
            "get_credential_types",
            "is_credential_compromised",
        }

        actual_methods = {
            name
            for name, method in CredentialProvider.__dict__.items()
            if getattr(method, "__isabstractmethod__", False)
        }

        assert expected_methods.issubset(actual_methods)


class TestSessionProvider:
    """Test SessionProvider interface."""

    def test_session_provider_is_abstract(self):
        """Test that SessionProvider is abstract."""
        with pytest.raises(TypeError):
            SessionProvider()

    def test_session_provider_inheritance(self):
        """Test SessionProvider inheritance."""
        assert issubclass(SessionProvider, BaseProvider)
        assert issubclass(SessionProvider, ABC)

    def test_session_provider_has_required_methods(self):
        """Test that SessionProvider has all required abstract methods."""
        expected_methods = {
            "create_session",
            "get_session",
            "refresh_session",
            "destroy_session",
            "destroy_user_sessions",
            "cleanup_expired_sessions",
            "get_active_sessions",
        }

        actual_methods = {
            name
            for name, method in SessionProvider.__dict__.items()
            if getattr(method, "__isabstractmethod__", False)
        }

        assert expected_methods.issubset(actual_methods)


class TestUserProvider:
    """Test UserProvider interface."""

    def test_user_provider_is_abstract(self):
        """Test that UserProvider is abstract."""
        with pytest.raises(TypeError):
            UserProvider()

    def test_user_provider_inheritance(self):
        """Test UserProvider inheritance."""
        assert issubclass(UserProvider, BaseProvider)
        assert issubclass(UserProvider, ABC)

    def test_user_provider_has_required_methods(self):
        """Test that UserProvider has all required abstract methods."""
        expected_methods = {
            "get_user_by_id",
            "get_user_by_username",
            "get_user_by_email",
            "create_user",
            "update_user",
            "delete_user",
            "list_users",
            "get_user_permissions",
            "get_user_roles",
            "assign_role",
            "remove_role",
        }

        actual_methods = {
            name
            for name, method in UserProvider.__dict__.items()
            if getattr(method, "__isabstractmethod__", False)
        }

        assert expected_methods.issubset(actual_methods)


class TestAuthProvider:
    """Test AuthProvider interface."""

    def test_auth_provider_is_abstract(self):
        """Test that AuthProvider is abstract."""
        with pytest.raises(TypeError):
            AuthProvider()

    def test_auth_provider_inheritance(self):
        """Test AuthProvider inheritance."""
        assert issubclass(AuthProvider, BaseProvider)
        assert issubclass(AuthProvider, ABC)

    def test_auth_provider_has_required_methods(self):
        """Test that AuthProvider has all required abstract methods."""
        expected_methods = {
            "authenticate",
            "authorize",
            "logout",
            "validate_session",
            "get_current_user",
        }

        actual_methods = {
            name
            for name, method in AuthProvider.__dict__.items()
            if getattr(method, "__isabstractmethod__", False)
        }

        assert expected_methods.issubset(actual_methods)


class TestAuditProvider:
    """Test AuditProvider interface."""

    def test_audit_provider_is_abstract(self):
        """Test that AuditProvider is abstract."""
        with pytest.raises(TypeError):
            AuditProvider()

    def test_audit_provider_inheritance(self):
        """Test AuditProvider inheritance."""
        assert issubclass(AuditProvider, BaseProvider)
        assert issubclass(AuditProvider, ABC)

    def test_audit_provider_has_required_methods(self):
        """Test that AuditProvider has all required abstract methods."""
        expected_methods = {
            "store_audit_event",
            "get_audit_events",
            "get_user_audit_events",
            "search_audit_events",
            "cleanup_old_events",
        }

        actual_methods = {
            name
            for name, method in AuditProvider.__dict__.items()
            if getattr(method, "__isabstractmethod__", False)
        }

        assert expected_methods.issubset(actual_methods)


class MockCredentialProvider(CredentialProvider):
    """Mock implementation for testing interface compliance."""

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config or {})
        self.credentials = {}

    async def verify_credentials(
        self, credentials: Credentials, audit_journal: AuditJournal
    ) -> bool:
        return credentials.id in self.credentials

    async def create_credentials(
        self, user_id: str, credentials: Credentials, audit_journal: AuditJournal
    ) -> None:
        self.credentials[credentials.id] = credentials

    async def update_credentials(
        self,
        user_id: str,
        old_credentials: Credentials,
        new_credentials: Credentials,
        audit_journal: AuditJournal,
    ) -> None:
        if old_credentials.id in self.credentials:
            del self.credentials[old_credentials.id]
        self.credentials[new_credentials.id] = new_credentials

    async def delete_credentials(
        self, user_id: str, credential_type: CredentialType, audit_journal: AuditJournal
    ) -> None:
        to_delete = [
            cred_id
            for cred_id, cred in self.credentials.items()
            if cred.user_id == user_id and cred.type == credential_type
        ]
        for cred_id in to_delete:
            del self.credentials[cred_id]

    async def get_credential_types(self, user_id: str) -> Set[CredentialType]:
        return {
            cred.type for cred in self.credentials.values() if cred.user_id == user_id
        }

    async def is_credential_compromised(self, credentials: Credentials) -> bool:
        return False


class TestMockImplementation:
    """Test that mock implementations work correctly."""

    def test_mock_credential_provider_instantiation(self):
        """Test that mock credential provider can be instantiated."""
        provider = MockCredentialProvider()
        assert isinstance(provider, CredentialProvider)
        assert isinstance(provider, BaseProvider)

    @pytest.mark.asyncio
    async def test_mock_credential_provider_functionality(self):
        """Test basic functionality of mock provider."""
        provider = MockCredentialProvider()
        audit_journal = AuditJournal()

        credentials = Credentials(
            id="cred123",
            user_id="user123",
            type=CredentialType.PASSWORD,
            data={"password_hash": "hashed"},
        )

        # Initially should not verify
        assert not await provider.verify_credentials(credentials, audit_journal)

        # Create credentials
        await provider.create_credentials("user123", credentials, audit_journal)

        # Now should verify
        assert await provider.verify_credentials(credentials, audit_journal)

        # Check credential types
        types = await provider.get_credential_types("user123")
        assert CredentialType.PASSWORD in types

        # Check not compromised
        assert not await provider.is_credential_compromised(credentials)
