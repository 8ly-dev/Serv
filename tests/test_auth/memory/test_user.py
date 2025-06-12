"""Tests for MemoryUserProvider."""

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from serv.auth.audit.enforcement import AuditJournal
from serv.auth.exceptions import AuthenticationError, AuthorizationError
from serv.auth.types import Permission, Role, User
from serv.bundled.auth.memory.user import MemoryUserProvider
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
        "default_roles": ["user"],
        "require_email_verification": False,
        "allow_duplicate_emails": False,
        "auto_create_roles": True,
        "default_permissions": [
            {
                "permission": "user:read",
                "description": "Read user data",
                "resource": "user",
            },
            {
                "permission": "user:update",
                "description": "Update user data",
                "resource": "user",
            }
        ],
        "default_role_configs": [
            {
                "name": "user",
                "description": "Standard user role",
                "permissions": ["user:read", "user:update"]
            },
            {
                "name": "admin",
                "description": "Administrator role",
                "permissions": ["admin:*"]
            }
        ]
    }


@pytest.fixture
def provider(config, container):
    """Create a MemoryUserProvider instance."""
    return MemoryUserProvider(config, container)


class TestMemoryUserProvider:
    """Test MemoryUserProvider functionality."""

    @pytest.mark.asyncio
    async def test_create_user_basic(self, provider, audit_journal):
        """Test basic user creation."""
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            username="testuser",
            display_name="Test User",
            audit_journal=audit_journal
        )
        
        assert isinstance(user, User)
        assert user.user_id == "test_user"
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.display_name == "Test User"
        assert user.is_active is True
        assert user.is_verified is True  # Since verification not required
        assert "user" in user.roles  # Default role
        
        # Check metadata
        assert "created_at" in user.metadata
        assert "updated_at" in user.metadata
        assert user.metadata["login_count"] == 0

    @pytest.mark.asyncio
    async def test_create_user_minimal(self, provider, audit_journal):
        """Test user creation with minimal parameters."""
        user = await provider.create_user(
            user_id="minimal_user",
            email="minimal@example.com",
            audit_journal=audit_journal
        )
        
        assert user.user_id == "minimal_user"
        assert user.email == "minimal@example.com"
        assert user.username == "minimal_user"  # Defaults to user_id
        assert user.display_name == "minimal_user"  # Defaults to username

    @pytest.mark.asyncio
    async def test_create_user_duplicate_id(self, provider, audit_journal):
        """Test creating user with duplicate ID."""
        # Create first user
        await provider.create_user(
            user_id="duplicate_user",
            email="first@example.com",
            audit_journal=audit_journal
        )
        
        # Try to create another with same ID
        with pytest.raises(AuthenticationError, match="User duplicate_user already exists"):
            await provider.create_user(
                user_id="duplicate_user",
                email="second@example.com",
                audit_journal=audit_journal
            )

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, provider, audit_journal):
        """Test creating user with duplicate email."""
        # Create first user
        await provider.create_user(
            user_id="user1",
            email="shared@example.com",
            audit_journal=audit_journal
        )
        
        # Try to create another with same email
        with pytest.raises(AuthenticationError, match="User with email shared@example.com already exists"):
            await provider.create_user(
                user_id="user2",
                email="shared@example.com",
                audit_journal=audit_journal
            )

    @pytest.mark.asyncio
    async def test_create_user_allow_duplicate_emails(self, config, container, audit_journal):
        """Test creating users with duplicate emails when allowed."""
        config["allow_duplicate_emails"] = True
        provider = MemoryUserProvider(config, container)
        
        # Create users with same email
        user1 = await provider.create_user(
            user_id="user1",
            email="shared@example.com",
            audit_journal=audit_journal
        )
        
        user2 = await provider.create_user(
            user_id="user2",
            email="shared@example.com",
            audit_journal=audit_journal
        )
        
        assert user1.email == user2.email
        assert user1.user_id != user2.user_id

    @pytest.mark.asyncio
    async def test_get_user(self, provider, audit_journal):
        """Test getting user by ID."""
        # Create user
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            audit_journal=audit_journal
        )
        
        # Get user
        retrieved = await provider.get_user("test_user")
        assert retrieved is not None
        assert retrieved.user_id == user.user_id
        assert retrieved.email == user.email

    @pytest.mark.asyncio
    async def test_get_user_nonexistent(self, provider):
        """Test getting non-existent user."""
        result = await provider.get_user("nonexistent_user")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, provider, audit_journal):
        """Test getting user by email."""
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            audit_journal=audit_journal
        )
        
        retrieved = await provider.get_user_by_email("test@example.com")
        assert retrieved is not None
        assert retrieved.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_get_user_by_email_case_insensitive(self, provider, audit_journal):
        """Test getting user by email is case insensitive."""
        user = await provider.create_user(
            user_id="test_user",
            email="Test@Example.COM",
            audit_journal=audit_journal
        )
        
        # Should find with lowercase
        retrieved = await provider.get_user_by_email("test@example.com")
        assert retrieved is not None
        assert retrieved.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_get_user_by_username(self, provider, audit_journal):
        """Test getting user by username."""
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            username="testuser",
            audit_journal=audit_journal
        )
        
        retrieved = await provider.get_user_by_username("testuser")
        assert retrieved is not None
        assert retrieved.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_update_user(self, provider, audit_journal):
        """Test updating user information."""
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            username="testuser",
            audit_journal=audit_journal
        )
        
        # Update user
        updated = await provider.update_user(
            user_id="test_user",
            email="updated@example.com",
            username="updateduser",
            display_name="Updated User",
            is_active=False,
            metadata={"updated_field": "value"},
            audit_journal=audit_journal
        )
        
        assert updated is not None
        assert updated.email == "updated@example.com"
        assert updated.username == "updateduser"
        assert updated.display_name == "Updated User"
        assert updated.is_active is False
        assert updated.metadata["updated_field"] == "value"
        assert "updated_at" in updated.metadata

    @pytest.mark.asyncio
    async def test_update_user_nonexistent(self, provider, audit_journal):
        """Test updating non-existent user."""
        result = await provider.update_user(
            user_id="nonexistent",
            email="new@example.com",
            audit_journal=audit_journal
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_update_user_email_conflict(self, provider, audit_journal):
        """Test updating user email to existing email."""
        # Create two users
        await provider.create_user(
            user_id="user1",
            email="user1@example.com",
            audit_journal=audit_journal
        )
        
        await provider.create_user(
            user_id="user2",
            email="user2@example.com",
            audit_journal=audit_journal
        )
        
        # Try to update user2's email to user1's email
        with pytest.raises(AuthenticationError, match="User with email user1@example.com already exists"):
            await provider.update_user(
                user_id="user2",
                email="user1@example.com",
                audit_journal=audit_journal
            )

    @pytest.mark.asyncio
    async def test_delete_user(self, provider, audit_journal):
        """Test deleting a user."""
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            username="testuser",
            audit_journal=audit_journal
        )
        
        # Delete user
        result = await provider.delete_user("test_user", audit_journal)
        assert result is True
        
        # User should no longer exist
        retrieved = await provider.get_user("test_user")
        assert retrieved is None
        
        # Email and username indexes should be cleaned up
        by_email = await provider.get_user_by_email("test@example.com")
        assert by_email is None
        
        by_username = await provider.get_user_by_username("testuser")
        assert by_username is None

    @pytest.mark.asyncio
    async def test_delete_user_nonexistent(self, provider, audit_journal):
        """Test deleting non-existent user."""
        result = await provider.delete_user("nonexistent", audit_journal)
        assert result is False

    @pytest.mark.asyncio
    async def test_assign_role(self, provider, audit_journal):
        """Test assigning role to user."""
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            audit_journal=audit_journal
        )
        
        # Assign admin role
        result = await provider.assign_role("test_user", "admin", audit_journal)
        assert result is True
        
        # Check user has role
        user_roles = await provider.get_user_roles("test_user")
        assert "admin" in user_roles

    @pytest.mark.asyncio
    async def test_assign_role_auto_create(self, provider, audit_journal):
        """Test assigning non-existent role with auto-create enabled."""
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            audit_journal=audit_journal
        )
        
        # Assign non-existent role
        result = await provider.assign_role("test_user", "new_role", audit_journal)
        assert result is True
        
        # Role should be auto-created
        role = await provider.get_role("new_role")
        assert role is not None
        assert role.name == "new_role"
        assert role.metadata["auto_created"] is True

    @pytest.mark.asyncio
    async def test_assign_role_no_auto_create(self, config, container, audit_journal):
        """Test assigning non-existent role with auto-create disabled."""
        config["auto_create_roles"] = False
        provider = MemoryUserProvider(config, container)
        
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            audit_journal=audit_journal
        )
        
        # Try to assign non-existent role
        with pytest.raises(AuthorizationError, match="Role nonexistent does not exist"):
            await provider.assign_role("test_user", "nonexistent", audit_journal)

    @pytest.mark.asyncio
    async def test_revoke_role(self, provider, audit_journal):
        """Test revoking role from user."""
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            audit_journal=audit_journal
        )
        
        # Assign then revoke role
        await provider.assign_role("test_user", "admin", audit_journal)
        result = await provider.revoke_role("test_user", "admin", audit_journal)
        assert result is True
        
        # User should not have role
        user_roles = await provider.get_user_roles("test_user")
        assert "admin" not in user_roles

    @pytest.mark.asyncio
    async def test_get_user_permissions(self, provider, audit_journal):
        """Test getting user permissions."""
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            audit_journal=audit_journal
        )
        
        # Assign admin role (which has admin:* permission)
        await provider.assign_role("test_user", "admin", audit_journal)
        
        permissions = await provider.get_user_permissions("test_user")
        assert "admin:*" in permissions
        assert "user:read" in permissions  # From default user role

    @pytest.mark.asyncio
    async def test_has_permission_exact_match(self, provider, audit_journal):
        """Test permission checking with exact match."""
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            audit_journal=audit_journal
        )
        
        # User role has user:read permission
        result = await provider.has_permission("test_user", "user:read")
        assert result is True
        
        # User doesn't have admin permissions
        result = await provider.has_permission("test_user", "admin:delete")
        assert result is False

    @pytest.mark.asyncio
    async def test_has_permission_wildcard(self, provider, audit_journal):
        """Test permission checking with wildcards."""
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            audit_journal=audit_journal
        )
        
        # Assign admin role (has admin:* permission)
        await provider.assign_role("test_user", "admin", audit_journal)
        
        # Should match admin:* wildcard
        result = await provider.has_permission("test_user", "admin:delete")
        assert result is True
        
        result = await provider.has_permission("test_user", "admin:create")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_permission_super_admin(self, provider, audit_journal):
        """Test permission checking with super admin permissions."""
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            audit_journal=audit_journal
        )
        
        # Create super admin role
        await provider.create_role(
            name="superadmin",
            permissions={"*:*"},
            audit_journal=audit_journal
        )
        
        await provider.assign_role("test_user", "superadmin", audit_journal)
        
        # Should have any permission
        result = await provider.has_permission("test_user", "anything:whatever")
        assert result is True

    @pytest.mark.asyncio
    async def test_create_role(self, provider, audit_journal):
        """Test creating a role."""
        role = await provider.create_role(
            name="custom_role",
            description="Custom role for testing",
            permissions={"custom:read", "custom:write"},
            metadata={"created_by": "test"},
            audit_journal=audit_journal
        )
        
        assert role.name == "custom_role"
        assert role.description == "Custom role for testing"
        assert "custom:read" in role.permissions
        assert "custom:write" in role.permissions
        assert role.metadata["created_by"] == "test"

    @pytest.mark.asyncio
    async def test_create_role_duplicate(self, provider, audit_journal):
        """Test creating duplicate role."""
        await provider.create_role(name="duplicate_role", audit_journal=audit_journal)
        
        with pytest.raises(AuthorizationError, match="Role duplicate_role already exists"):
            await provider.create_role(name="duplicate_role", audit_journal=audit_journal)

    @pytest.mark.asyncio
    async def test_update_role(self, provider, audit_journal):
        """Test updating a role."""
        role = await provider.create_role(
            name="test_role",
            description="Original description",
            permissions={"test:read"},
            audit_journal=audit_journal
        )
        
        updated = await provider.update_role(
            name="test_role",
            description="Updated description",
            permissions={"test:read", "test:write"},
            metadata={"updated": True},
            audit_journal=audit_journal
        )
        
        assert updated.description == "Updated description"
        assert "test:write" in updated.permissions
        assert updated.metadata["updated"] is True

    @pytest.mark.asyncio
    async def test_delete_role(self, provider, audit_journal):
        """Test deleting a role."""
        # Create role and assign to user
        await provider.create_role(name="temp_role", audit_journal=audit_journal)
        
        user = await provider.create_user(
            user_id="test_user",
            email="test@example.com",
            audit_journal=audit_journal
        )
        
        await provider.assign_role("test_user", "temp_role", audit_journal)
        
        # Delete role
        result = await provider.delete_role("temp_role", audit_journal)
        assert result is True
        
        # Role should be gone
        role = await provider.get_role("temp_role")
        assert role is None
        
        # Should be removed from user
        user_roles = await provider.get_user_roles("test_user")
        assert "temp_role" not in user_roles

    @pytest.mark.asyncio
    async def test_create_permission(self, provider, audit_journal):
        """Test creating a permission."""
        permission = await provider.create_permission(
            permission="custom:action",
            description="Custom permission",
            resource="custom_resource",
            audit_journal=audit_journal
        )
        
        assert permission.permission == "custom:action"
        assert permission.description == "Custom permission"
        assert permission.resource == "custom_resource"

    @pytest.mark.asyncio
    async def test_list_users(self, provider, audit_journal):
        """Test listing users."""
        # Initially empty
        users = await provider.list_users()
        assert len(users) == 0
        
        # Create some users
        for i in range(5):
            await provider.create_user(
                user_id=f"user_{i}",
                email=f"user{i}@example.com",
                audit_journal=audit_journal
            )
        
        # List all users
        users = await provider.list_users()
        assert len(users) == 5
        
        # Test pagination
        users_page1 = await provider.list_users(limit=3, offset=0)
        assert len(users_page1) == 3
        
        users_page2 = await provider.list_users(limit=3, offset=3)
        assert len(users_page2) == 2

    @pytest.mark.asyncio
    async def test_list_users_active_only(self, provider, audit_journal):
        """Test listing only active users."""
        # Create active and inactive users
        await provider.create_user(
            user_id="active_user",
            email="active@example.com",
            audit_journal=audit_journal
        )
        
        inactive_user = await provider.create_user(
            user_id="inactive_user",
            email="inactive@example.com",
            audit_journal=audit_journal
        )
        
        # Deactivate one user
        await provider.update_user(
            user_id="inactive_user",
            is_active=False,
            audit_journal=audit_journal
        )
        
        # List all users
        all_users = await provider.list_users(active_only=False)
        assert len(all_users) == 2
        
        # List only active users
        active_users = await provider.list_users(active_only=True)
        assert len(active_users) == 1
        assert active_users[0].user_id == "active_user"

    @pytest.mark.asyncio
    async def test_get_statistics(self, provider, audit_journal):
        """Test getting provider statistics."""
        # Initially empty
        stats = await provider.get_statistics()
        assert stats["total_users"] == 0
        assert stats["active_users"] == 0
        assert stats["verified_users"] == 0
        
        # Create some users
        await provider.create_user(
            user_id="user1",
            email="user1@example.com",
            audit_journal=audit_journal
        )
        
        await provider.create_user(
            user_id="user2", 
            email="user2@example.com",
            audit_journal=audit_journal
        )
        
        # Deactivate one user
        await provider.update_user(
            user_id="user2",
            is_active=False,
            audit_journal=audit_journal
        )
        
        stats = await provider.get_statistics()
        assert stats["total_users"] == 2
        assert stats["active_users"] == 1
        assert stats["verified_users"] == 2  # Both verified by default

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, provider, audit_journal):
        """Test concurrent user operations."""
        import asyncio
        
        async def create_user_worker(user_id):
            try:
                user = await provider.create_user(
                    user_id=user_id,
                    email=f"{user_id}@example.com",
                    audit_journal=audit_journal
                )
                return user.user_id
            except Exception:
                return None
        
        # Create multiple users concurrently
        tasks = [create_user_worker(f"user_{i}") for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful results
        successful = [r for r in results if isinstance(r, str)]
        assert len(successful) == 10

    @pytest.mark.asyncio
    async def test_initialization_with_defaults(self, config, container):
        """Test provider initialization with default roles and permissions."""
        provider = MemoryUserProvider(config, container)
        
        # Default permissions should be created
        user_read = await provider.get_permission("user:read")
        assert user_read is not None
        assert user_read.description == "Read user data"
        
        # Default roles should be created
        user_role = await provider.get_role("user")
        assert user_role is not None
        assert "user:read" in user_role.permissions
        
        admin_role = await provider.get_role("admin")
        assert admin_role is not None
        assert "admin:*" in admin_role.permissions

    @pytest.mark.asyncio
    async def test_cleanup_lifecycle(self, provider):
        """Test cleanup task lifecycle."""
        await provider._ensure_cleanup_started()
        assert provider._cleanup_started is True
        
        # Starting again should be idempotent
        await provider._ensure_cleanup_started()
        assert provider._cleanup_started is True