"""
Serv Authentication Framework

A comprehensive authentication and authorization system for Serv applications.
Provides secure, extensible interfaces for authentication providers, session
management, rate limiting, auditing, and policy enforcement.

Security Notice:
This module handles sensitive security operations. All implementations
should follow security best practices including:
- Secure password hashing (bcrypt)
- Timing attack protection
- Input validation and sanitization
- Proper session management
- Rate limiting and audit logging
"""

from .audit_logger import AuditLogger
from .auth_provider import AuthProvider
from .credential_vault import CredentialVault
from .policy_engine import PolicyEngine
from .rate_limiter import RateLimiter
from .role_registry import RoleRegistry
from .session_manager import SessionManager
from .token_service import TokenService
from .types import (
    AuditEvent,
    AuthResult,
    AuthStatus,
    Credential,
    Permission,
    PolicyDecision,
    RateLimitResult,
    RefreshResult,
    Role,
    Session,
    Token,
    ValidationResult,
)

__all__ = [
    # Data types
    "AuthStatus",
    "AuthResult",
    "ValidationResult",
    "RefreshResult",
    "Session",
    "PolicyDecision",
    "Token",
    "RateLimitResult",
    "AuditEvent",
    "Role",
    "Permission",
    "Credential",
    # Interfaces
    "AuthProvider",
    "SessionManager",
    "PolicyEngine",
    "TokenService",
    "RateLimiter",
    "AuditLogger",
    "RoleRegistry",
    "CredentialVault",
]
