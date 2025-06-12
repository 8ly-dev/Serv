"""Test cases for auth core types."""

import pytest
from datetime import datetime, timedelta
from dataclasses import asdict

from serv.auth.types import (
    User, Session, Credentials, Permission, Role,
    CredentialType, AuditEventType, PolicyResult
)
from serv.auth.exceptions import AuthValidationError


class TestCoreTypes:
    """Test core auth data types."""
    
    def test_user_creation(self):
        """Test User dataclass creation and validation."""
        user = User(
            id="user123",
            username="testuser",
            email="test@example.com",
            is_active=True,
            created_at=datetime.now(),
            roles=["user"]
        )
        
        assert user.id == "user123"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert isinstance(user.created_at, datetime)
        assert user.roles == ["user"]
    
    def test_user_serialization(self):
        """Test User serialization to dict."""
        user = User(
            id="user123",
            username="testuser",
            email="test@example.com"
        )
        
        user_dict = asdict(user)
        assert isinstance(user_dict, dict)
        assert user_dict["id"] == "user123"
        assert user_dict["username"] == "testuser"
    
    def test_session_creation(self):
        """Test Session dataclass creation."""
        expires_at = datetime.now() + timedelta(hours=1)
        session = Session(
            id="session123",
            user_id="user123",
            created_at=datetime.now(),
            expires_at=expires_at,
            is_active=True
        )
        
        assert session.id == "session123"
        assert session.user_id == "user123"
        assert isinstance(session.created_at, datetime)
        assert session.expires_at == expires_at
        assert session.is_active is True
    
    def test_session_expiry_check(self):
        """Test session expiry check method."""
        # Create expired session
        expired_session = Session(
            id="session123",
            user_id="user123",
            created_at=datetime.now() - timedelta(hours=2),
            expires_at=datetime.now() - timedelta(hours=1),
            is_active=True
        )
        
        assert expired_session.is_expired() is True
        
        # Create active session
        active_session = Session(
            id="session456",
            user_id="user123",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1),
            is_active=True
        )
        
        assert active_session.is_expired() is False
    
    def test_credentials_creation(self):
        """Test Credentials dataclass creation."""
        credentials = Credentials(
            id="cred123",
            user_id="user123",
            type=CredentialType.PASSWORD,
            data={"password_hash": "hashed_password"},
            created_at=datetime.now(),
            is_active=True
        )
        
        assert credentials.id == "cred123"
        assert credentials.user_id == "user123"
        assert credentials.type == CredentialType.PASSWORD
        assert credentials.data["password_hash"] == "hashed_password"
        assert credentials.is_active is True
    
    def test_permission_creation(self):
        """Test Permission dataclass creation."""
        permission = Permission(
            name="read:posts", 
            description="Read posts permission"
        )
        
        assert permission.name == "read:posts"
        assert permission.description == "Read posts permission"
    
    def test_role_creation(self):
        """Test Role dataclass creation."""
        permissions = [
            Permission(name="read:posts", description="Read posts"),
            Permission(name="write:posts", description="Write posts")
        ]
        
        role = Role(
            name="editor",
            description="Content editor role",
            permissions=permissions
        )
        
        assert role.name == "editor"
        assert role.description == "Content editor role"
        assert len(role.permissions) == 2
        assert role.permissions[0].name == "read:posts"


class TestEnums:
    """Test auth enums."""
    
    def test_credential_type_enum(self):
        """Test CredentialType enum values."""
        assert CredentialType.PASSWORD.value == "password"
        assert CredentialType.TOKEN.value == "token"
        assert CredentialType.API_KEY.value == "api_key"
    
    def test_audit_event_type_enum(self):
        """Test AuditEventType enum values."""
        assert AuditEventType.LOGIN_ATTEMPT.value == "login_attempt"
        assert AuditEventType.LOGIN_SUCCESS.value == "login_success"
        assert AuditEventType.LOGIN_FAILURE.value == "login_failure"
        assert AuditEventType.LOGOUT.value == "logout"
        assert AuditEventType.PERMISSION_CHECK.value == "permission_check"
        assert AuditEventType.PERMISSION_DENIED.value == "permission_denied"
    
    def test_policy_result_enum(self):
        """Test PolicyResult enum values."""
        assert PolicyResult.ALLOW.value == "allow"
        assert PolicyResult.DENY.value == "deny"
        assert PolicyResult.ABSTAIN.value == "abstain"