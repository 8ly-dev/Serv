"""
Role registry implementations for Serv authentication.

This module provides concrete implementations of the RoleRegistry interface
for managing user roles and permissions with database persistence.
"""

from .ommi_role_registry import OmmiRoleRegistry

__all__ = ["OmmiRoleRegistry"]
