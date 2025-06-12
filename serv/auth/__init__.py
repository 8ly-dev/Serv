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
from .config_loader import AuthConfigLoader, configure_auth_from_app_config
from .credential_vault import CredentialVault
from .declarative import AuthRule, DeclarativeAuthProcessor
from .factory import (
    AuthConfigError,
    AuthSystemFactory,
    BackendLoader,
    create_auth_system,
)
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
from .utils import (
    configure_trusted_proxies,
    generate_csrf_token,
    generate_device_fingerprint,
    get_client_ip,
    get_common_trusted_proxies,
    mask_sensitive_data,
    sanitize_user_input,
    secure_compare,
    timing_protection,
    validate_session_fingerprint,
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
    # Declarative auth
    "AuthRule",
    "DeclarativeAuthProcessor",
    # Configuration and factory
    "AuthConfigError",
    "AuthSystemFactory",
    "BackendLoader",
    "create_auth_system",
    "AuthConfigLoader",
    "configure_auth_from_app_config",
    # Utilities
    "configure_trusted_proxies",
    "generate_csrf_token",
    "generate_device_fingerprint",
    "get_client_ip",
    "get_common_trusted_proxies",
    "mask_sensitive_data",
    "sanitize_user_input",
    "secure_compare",
    "timing_protection",
    "validate_session_fingerprint",
]
