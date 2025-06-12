"""
Bundled authentication implementations for the Serv framework.

This package provides production-ready implementations of the authentication
interfaces using battle-tested security libraries.

Security-focused implementations:
- JWT authentication with algorithm confusion protection
- JWT-based token service with configurable expiration
- Memory-based rate limiting with sliding window algorithms
- Ommi-integrated session storage with lifecycle management
- bcrypt-based credential storage with secure defaults
- Database-backed audit logging for compliance
- Simple policy engine for authorization decisions
- Role and permission management with database persistence

All implementations follow the interface-based design allowing easy swapping
and configuration via serv.config.yaml.
"""

# Import all bundled implementations
from .auditing.ommi_audit_logger import OmmiAuditLogger
from .limiters.memory_limiter import MemoryRateLimiter
from .models import (
    AuditEventModel,
    CredentialModel,
    PermissionModel,
    RateLimitModel,
    RoleModel,
    RolePermissionModel,
    SessionModel,
    UserRoleModel,
    auth_collection,
)
from .policies.simple_policy_engine import SimplePolicyEngine
from .providers.jwt_provider import JWTAuthProvider as JwtAuthProvider
from .roles.ommi_role_registry import OmmiRoleRegistry
from .storage.ommi_storage import OmmiSessionStorage
from .tokens.jwt_token_service import JwtTokenService
from .vaults.bcrypt_vault import BcryptCredentialVault

__all__ = [
    # Auth providers
    "JwtAuthProvider",
    # Session storage
    "OmmiSessionStorage",
    # Credential vaults
    "BcryptCredentialVault",
    # Rate limiters
    "MemoryRateLimiter",
    # Token services
    "JwtTokenService",
    # Audit loggers
    "OmmiAuditLogger",
    # Policy engines
    "SimplePolicyEngine",
    # Role registries
    "OmmiRoleRegistry",
    # Database models
    "SessionModel",
    "CredentialModel",
    "RateLimitModel",
    "AuditEventModel",
    "RoleModel",
    "PermissionModel",
    "UserRoleModel",
    "RolePermissionModel",
    "auth_collection",
]
