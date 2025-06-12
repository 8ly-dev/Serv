"""
Tests for Ommi role registry implementation.

Comprehensive test suite covering role definition, permission management,
user role assignment, and caching for the Ommi-based role registry.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from serv.auth.types import Permission, Role
from serv.bundled.auth.roles.ommi_role_registry import OmmiRoleRegistry


class TestOmmiRoleRegistry:
    """Test Ommi role registry implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            "database_qualifier": "test_auth",
            "cache_expiry": 300,
            "case_sensitive": False,
        }
        self.registry = OmmiRoleRegistry(self.config)

    def test_init_with_valid_config(self):
        """Test initialization with valid configuration."""
        assert self.registry.database_qualifier == "test_auth"
        assert self.registry.cache_expiry == 300
        assert self.registry.case_sensitive is False

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        registry = OmmiRoleRegistry({})
        
        assert registry.database_qualifier == "auth"
        assert registry.cache_expiry == 300
        assert registry.case_sensitive is True

    def test_normalize_name_case_insensitive(self):
        """Test name normalization when case insensitive."""
        assert self.registry._normalize_name("Admin") == "admin"
        assert self.registry._normalize_name("USER:READ") == "user:read"

    def test_normalize_name_case_sensitive(self):
        """Test name normalization when case sensitive."""
        config = self.config.copy()
        config["case_sensitive"] = True
        registry = OmmiRoleRegistry(config)
        
        assert registry._normalize_name("Admin") == "Admin"
        assert registry._normalize_name("USER:READ") == "USER:READ"

    @pytest.mark.asyncio
    async def test_is_cache_valid_expired(self):
        """Test cache validity check for expired entries."""
        # Add expired entry
        self.registry._last_cache_update["test_key"] = datetime.now(UTC).replace(year=2020)
        
        is_valid = await self.registry._is_cache_valid("test_key")
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_is_cache_valid_fresh(self):
        """Test cache validity check for fresh entries."""
        # Add fresh entry
        self.registry._last_cache_update["test_key"] = datetime.now(UTC)
        
        is_valid = await self.registry._is_cache_valid("test_key")
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_is_cache_valid_missing(self):
        """Test cache validity check for missing entries."""
        is_valid = await self.registry._is_cache_valid("missing_key")
        assert is_valid is False

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.roles.ommi_role_registry.injectable")
    @patch("serv.bundled.auth.roles.ommi_role_registry.auto_inject")
    async def test_define_role_success(self, mock_auto_inject, mock_injectable):
        """Test successful role definition."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock role doesn't exist check
        mock_existing_result = AsyncMock()
        mock_existing_result.is_success.return_value = False
        mock_ommi.find.return_value.one.return_value = mock_existing_result
        
        # Mock successful role creation
        mock_add_result = AsyncMock()
        mock_saved_role = MagicMock()
        mock_saved_role.created_at = datetime.now(UTC).isoformat()
        mock_add_result.or_raise.return_value = [mock_saved_role]
        mock_ommi.add.return_value = mock_add_result
        
        # Mock permission creation for role permissions
        with patch.object(self.registry, '_ensure_permission_exists') as mock_ensure:
            mock_ensure.return_value = None
            
            role = await self.registry.define_role(
                name="admin",
                description="Administrator role",
                permissions=["user:read", "user:write"],
                database=mock_database,
            )
        
        assert isinstance(role, Role)
        assert role.name == "admin"
        assert role.description == "Administrator role"
        assert "user:read" in role.permissions
        assert "user:write" in role.permissions
        
        # Verify database operations
        mock_database.get_connection.assert_called_with("test_auth")
        assert mock_ommi.add.call_count >= 1  # Role + permission assignments

    @pytest.mark.asyncio
    async def test_define_role_no_database(self):
        """Test role definition fails without database service."""
        with pytest.raises(RuntimeError, match="Database service not available"):
            await self.registry.define_role("admin", database=None)

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.roles.ommi_role_registry.injectable")
    @patch("serv.bundled.auth.roles.ommi_role_registry.auto_inject")
    async def test_define_role_already_exists(self, mock_auto_inject, mock_injectable):
        """Test role definition fails when role already exists."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock role already exists
        mock_existing_result = AsyncMock()
        mock_existing_result.is_success.return_value = True
        mock_ommi.find.return_value.one.return_value = mock_existing_result
        
        with pytest.raises(ValueError, match="Role 'admin' already exists"):
            await self.registry.define_role("admin", database=mock_database)

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.roles.ommi_role_registry.injectable")
    @patch("serv.bundled.auth.roles.ommi_role_registry.auto_inject")
    async def test_define_permission_success(self, mock_auto_inject, mock_injectable):
        """Test successful permission definition."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock permission doesn't exist check
        mock_existing_result = AsyncMock()
        mock_existing_result.is_success.return_value = False
        mock_ommi.find.return_value.one.return_value = mock_existing_result
        
        # Mock successful permission creation
        mock_add_result = AsyncMock()
        mock_saved_permission = MagicMock()
        mock_saved_permission.created_at = datetime.now(UTC).isoformat()
        mock_add_result.or_raise.return_value = [mock_saved_permission]
        mock_ommi.add.return_value = mock_add_result
        
        permission = await self.registry.define_permission(
            name="user:read",
            description="Read user data",
            resource="/api/users",
            database=mock_database,
        )
        
        assert isinstance(permission, Permission)
        assert permission.name == "user:read"
        assert permission.description == "Read user data"
        assert permission.resource == "/api/users"

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.roles.ommi_role_registry.injectable")
    @patch("serv.bundled.auth.roles.ommi_role_registry.auto_inject")
    async def test_define_permission_already_exists(self, mock_auto_inject, mock_injectable):
        """Test permission definition fails when permission already exists."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock permission already exists
        mock_existing_result = AsyncMock()
        mock_existing_result.is_success.return_value = True
        mock_ommi.find.return_value.one.return_value = mock_existing_result
        
        with pytest.raises(ValueError, match="Permission 'user:read' already exists"):
            await self.registry.define_permission("user:read", database=mock_database)

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.roles.ommi_role_registry.injectable")
    @patch("serv.bundled.auth.roles.ommi_role_registry.auto_inject")
    async def test_assign_role_success(self, mock_auto_inject, mock_injectable):
        """Test successful role assignment."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock role exists
        mock_role_result = AsyncMock()
        mock_role = MagicMock()
        mock_role.role_id = "role-123"
        mock_role_result.or_raise.return_value = mock_role
        
        # Mock assignment doesn't exist
        mock_existing_result = AsyncMock()
        mock_existing_result.is_success.return_value = False
        
        # Mock successful assignment creation
        mock_add_result = AsyncMock()
        mock_add_result.or_raise.return_value = [MagicMock()]
        
        mock_ommi.find.side_effect = [
            MagicMock(one=lambda: mock_role_result),  # Role lookup
            MagicMock(one=lambda: mock_existing_result),  # Assignment check
        ]
        mock_ommi.add.return_value = mock_add_result
        
        result = await self.registry.assign_role("user-123", "admin", database=mock_database)
        
        assert result is True
        mock_ommi.add.assert_called_once()

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.roles.ommi_role_registry.injectable")
    @patch("serv.bundled.auth.roles.ommi_role_registry.auto_inject")
    async def test_assign_role_already_assigned(self, mock_auto_inject, mock_injectable):
        """Test role assignment when already assigned."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock role exists
        mock_role_result = AsyncMock()
        mock_role = MagicMock()
        mock_role.role_id = "role-123"
        mock_role_result.or_raise.return_value = mock_role
        
        # Mock assignment already exists
        mock_existing_result = AsyncMock()
        mock_existing_result.is_success.return_value = True
        
        mock_ommi.find.side_effect = [
            MagicMock(one=lambda: mock_role_result),  # Role lookup
            MagicMock(one=lambda: mock_existing_result),  # Assignment check
        ]
        
        result = await self.registry.assign_role("user-123", "admin", database=mock_database)
        
        assert result is True  # Should return True even if already assigned
        mock_ommi.add.assert_not_called()  # Should not add duplicate

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.roles.ommi_role_registry.injectable")
    @patch("serv.bundled.auth.roles.ommi_role_registry.auto_inject")
    async def test_assign_role_nonexistent_role(self, mock_auto_inject, mock_injectable):
        """Test role assignment fails for nonexistent role."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock role doesn't exist (or_raise throws exception)
        mock_role_result = AsyncMock()
        mock_role_result.or_raise.side_effect = Exception("Role not found")
        
        mock_ommi.find.return_value.one.return_value = mock_role_result
        
        with pytest.raises(ValueError, match="Role 'nonexistent' not found"):
            await self.registry.assign_role("user-123", "nonexistent", database=mock_database)

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.roles.ommi_role_registry.injectable")
    @patch("serv.bundled.auth.roles.ommi_role_registry.auto_inject")
    async def test_revoke_role_success(self, mock_auto_inject, mock_injectable):
        """Test successful role revocation."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock role exists
        mock_role_result = AsyncMock()
        mock_role = MagicMock()
        mock_role.role_id = "role-123"
        mock_role_result.or_raise.return_value = mock_role
        mock_role_result.is_success.return_value = True
        
        # Mock successful deletion
        mock_delete_result = AsyncMock()
        mock_delete_result.or_raise.return_value = None
        
        mock_ommi.find.side_effect = [
            MagicMock(one=lambda: mock_role_result),  # Role lookup
            MagicMock(delete=lambda: mock_delete_result),  # Assignment deletion
        ]
        
        result = await self.registry.revoke_role("user-123", "admin", database=mock_database)
        
        assert result is True

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.roles.ommi_role_registry.injectable")
    @patch("serv.bundled.auth.roles.ommi_role_registry.auto_inject")
    async def test_revoke_role_nonexistent_role(self, mock_auto_inject, mock_injectable):
        """Test role revocation for nonexistent role."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock role doesn't exist
        mock_role_result = AsyncMock()
        mock_role_result.is_success.return_value = False
        
        mock_ommi.find.return_value.one.return_value = mock_role_result
        
        result = await self.registry.revoke_role("user-123", "nonexistent", database=mock_database)
        
        assert result is True  # Should return True even if role doesn't exist

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.roles.ommi_role_registry.injectable")
    @patch("serv.bundled.auth.roles.ommi_role_registry.auto_inject")
    async def test_check_permission_success(self, mock_auto_inject, mock_injectable):
        """Test successful permission check."""
        # Mock get_user_permissions to return permissions
        with patch.object(self.registry, 'get_user_permissions') as mock_get_perms:
            mock_get_perms.return_value = ["user:read", "user:write"]
            
            result = await self.registry.check_permission("user-123", "user:read", database=MagicMock())
            
            assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_case_insensitive(self):
        """Test permission check with case insensitive matching."""
        with patch.object(self.registry, 'get_user_permissions') as mock_get_perms:
            mock_get_perms.return_value = ["user:read"]
            
            # Should match despite case difference
            result = await self.registry.check_permission("user-123", "USER:READ", database=MagicMock())
            
            assert result is True

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.roles.ommi_role_registry.injectable")
    @patch("serv.bundled.auth.roles.ommi_role_registry.auto_inject")
    async def test_get_user_roles_from_cache(self, mock_auto_inject, mock_injectable):
        """Test getting user roles from cache."""
        # Set up cache
        self.registry._user_roles_cache["user-123"] = ["admin", "user"]
        self.registry._last_cache_update["user_roles_user-123"] = datetime.now(UTC)
        
        roles = await self.registry.get_user_roles("user-123", database=MagicMock())
        
        assert roles == ["admin", "user"]

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.roles.ommi_role_registry.injectable")
    @patch("serv.bundled.auth.roles.ommi_role_registry.auto_inject")
    async def test_get_user_roles_from_database(self, mock_auto_inject, mock_injectable):
        """Test getting user roles from database."""
        mock_database = AsyncMock()
        mock_ommi = AsyncMock()
        mock_database.get_connection.return_value = mock_ommi
        
        # Mock user role assignments
        mock_user_role_result = AsyncMock()
        mock_user_role_iterator = AsyncMock()
        
        mock_user_role1 = MagicMock()
        mock_user_role1.role_id = "role-1"
        mock_user_role2 = MagicMock()
        mock_user_role2.role_id = "role-2"
        
        async def mock_aiter():
            yield mock_user_role1
            yield mock_user_role2
        
        mock_user_role_iterator.__aiter__ = mock_aiter
        mock_user_role_result.or_raise.return_value = mock_user_role_iterator
        
        # Mock role details
        mock_role_result1 = AsyncMock()
        mock_role1 = MagicMock()
        mock_role1.name = "admin"
        mock_role_result1.is_success.return_value = True
        mock_role_result1.or_raise.return_value = mock_role1
        
        mock_role_result2 = AsyncMock()
        mock_role2 = MagicMock()
        mock_role2.name = "user"
        mock_role_result2.is_success.return_value = True
        mock_role_result2.or_raise.return_value = mock_role2
        
        mock_ommi.find.side_effect = [
            MagicMock(all=lambda: mock_user_role_result),  # User role query
            MagicMock(one=lambda: mock_role_result1),      # Role 1 lookup
            MagicMock(one=lambda: mock_role_result2),      # Role 2 lookup
        ]
        
        roles = await self.registry.get_user_roles("user-123", database=mock_database)
        
        assert "admin" in roles
        assert "user" in roles
        assert len(roles) == 2

    @pytest.mark.asyncio
    @patch("serv.bundled.auth.roles.ommi_role_registry.injectable")
    @patch("serv.bundled.auth.roles.ommi_role_registry.auto_inject")
    async def test_get_user_permissions_cached(self, mock_auto_inject, mock_injectable):
        """Test getting user permissions from cache."""
        cache_key = "user_permissions_user-123"
        self.registry._user_roles_cache[cache_key] = ["user:read", "user:write"]
        self.registry._last_cache_update[cache_key] = datetime.now(UTC)
        
        permissions = await self.registry.get_user_permissions("user-123", database=MagicMock())
        
        assert "user:read" in permissions
        assert "user:write" in permissions

    @pytest.mark.asyncio
    async def test_get_user_permissions_no_roles(self):
        """Test getting permissions for user with no roles."""
        with patch.object(self.registry, 'get_user_roles') as mock_get_roles:
            mock_get_roles.return_value = []
            
            permissions = await self.registry.get_user_permissions("user-123", database=MagicMock())
            
            assert permissions == []

    @pytest.mark.asyncio
    async def test_ensure_permission_exists_creates_permission(self):
        """Test that _ensure_permission_exists creates missing permissions."""
        with patch.object(self.registry, 'define_permission') as mock_define:
            mock_define.return_value = MagicMock()
            
            await self.registry._ensure_permission_exists("new:permission", database=MagicMock())
            
            mock_define.assert_called_once_with(
                "new:permission",
                "Auto-created permission: new:permission",
                database=mock_define.call_args[1]["database"]
            )

    @pytest.mark.asyncio
    async def test_ensure_permission_exists_ignores_existing(self):
        """Test that _ensure_permission_exists ignores existing permissions."""
        with patch.object(self.registry, 'define_permission') as mock_define:
            mock_define.side_effect = ValueError("Permission already exists")
            
            # Should not raise exception
            await self.registry._ensure_permission_exists("existing:permission", database=MagicMock())

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test registry cleanup."""
        # Add some test data to caches
        self.registry._role_cache["test"] = "data"
        self.registry._permission_cache["test"] = "data"
        self.registry._user_roles_cache["test"] = "data"
        self.registry._last_cache_update["test"] = datetime.now(UTC)
        
        await self.registry.cleanup()
        
        # All caches should be cleared
        assert len(self.registry._role_cache) == 0
        assert len(self.registry._permission_cache) == 0
        assert len(self.registry._user_roles_cache) == 0
        assert len(self.registry._last_cache_update) == 0

    @pytest.mark.asyncio
    async def test_case_sensitive_role_names(self):
        """Test role name handling with case sensitivity."""
        config = self.config.copy()
        config["case_sensitive"] = True
        registry = OmmiRoleRegistry(config)
        
        # Names should not be normalized when case sensitive
        assert registry._normalize_name("Admin") == "Admin"
        assert registry._normalize_name("USER") == "USER"

    def test_cache_configuration(self):
        """Test cache configuration options."""
        config = {"cache_expiry": 600}
        registry = OmmiRoleRegistry(config)
        
        assert registry.cache_expiry == 600

    @pytest.mark.asyncio
    async def test_get_user_roles_no_database(self):
        """Test get_user_roles fails without database service."""
        with pytest.raises(RuntimeError, match="Database service not available"):
            await self.registry.get_user_roles("user-123", database=None)

    @pytest.mark.asyncio
    async def test_get_user_permissions_no_database(self):
        """Test get_user_permissions fails without database service."""
        # Clear cache to force database lookup
        cache_key = "user_permissions_user-123"
        if cache_key in self.registry._user_roles_cache:
            del self.registry._user_roles_cache[cache_key]
        if cache_key in self.registry._last_cache_update:
            del self.registry._last_cache_update[cache_key]
        
        with patch.object(self.registry, 'get_user_roles') as mock_get_roles:
            mock_get_roles.return_value = ["admin"]
            
            with pytest.raises(RuntimeError, match="Database service not available"):
                await self.registry.get_user_permissions("user-123", database=None)