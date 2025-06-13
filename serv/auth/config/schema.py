"""Configuration schema models using Pydantic."""

from __future__ import annotations

import re
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class PolicyType(str, Enum):
    """Policy types for authentication and authorization."""

    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    PERMISSION = "permission"
    ROLE = "role"
    ATTRIBUTE = "attribute"
    COMPLEX = "complex"
    CUSTOM = "custom"


class ProviderConfig(BaseModel):
    """Configuration for a single provider."""

    provider: str = Field(..., description="Provider type or import path")
    config: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific configuration"
    )

    @field_validator("provider")
    @classmethod
    def validate_provider_spec(cls, v):
        """Validate provider specification format."""
        if not v:
            raise ValueError("Provider specification cannot be empty")

        # Simple name (bundled): alphanumeric, underscores, hyphens
        # Import path (external): module.path:ClassName
        if not re.match(r'^([a-zA-Z_][a-zA-Z0-9_-]*|[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*:[a-zA-Z_][a-zA-Z0-9_]*)$', v):
            raise ValueError(
                "Provider must be a simple name (e.g., 'memory') or import path (e.g., 'module.path:ClassName')"
            )

        return v


class ProvidersConfig(BaseModel):
    """Configuration for all auth providers."""

    credential: ProviderConfig = Field(
        ..., description="Credential provider configuration"
    )
    session: ProviderConfig = Field(..., description="Session provider configuration")
    user: ProviderConfig = Field(..., description="User provider configuration")
    audit: ProviderConfig = Field(..., description="Audit provider configuration")
    policy: ProviderConfig = Field(..., description="Policy provider configuration")


class SecurityHeadersConfig(BaseModel):
    """Security headers configuration."""

    strict_transport_security: bool = Field(True, description="Enable HSTS header")
    content_security_policy: Optional[str] = Field(
        "default-src 'self'", description="CSP header value"
    )
    x_frame_options: str = Field("DENY", description="X-Frame-Options header")
    x_content_type_options: str = Field(
        "nosniff", description="X-Content-Type-Options header"
    )


class PasswordSecurityConfig(BaseModel):
    """Password security configuration."""

    breach_checking: bool = Field(
        True, description="Check passwords against breach databases"
    )
    common_password_list: str = Field(
        "top_10k", description="Common password list to check against"
    )
    similarity_threshold: float = Field(
        0.8, description="Threshold for password similarity checks"
    )

    @field_validator("similarity_threshold")
    @classmethod
    def validate_similarity_threshold(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Similarity threshold must be between 0.0 and 1.0")
        return v


class SessionSecurityConfig(BaseModel):
    """Session security configuration."""

    ip_validation: bool = Field(True, description="Validate session IP addresses")
    user_agent_validation: bool = Field(
        True, description="Validate session user agents"
    )
    geo_blocking: bool = Field(False, description="Enable geolocation-based blocking")
    concurrent_login_limit: int = Field(
        3, description="Maximum concurrent sessions per user"
    )

    @field_validator("concurrent_login_limit")
    @classmethod
    def validate_concurrent_limit(cls, v):
        if v < 1:
            raise ValueError("Concurrent login limit must be at least 1")
        return v


class SecurityConfig(BaseModel):
    """Security configuration."""

    headers: SecurityHeadersConfig = Field(default_factory=SecurityHeadersConfig)
    password_security: PasswordSecurityConfig = Field(
        default_factory=PasswordSecurityConfig
    )
    session_security: SessionSecurityConfig = Field(
        default_factory=SessionSecurityConfig
    )


class DevelopmentUserConfig(BaseModel):
    """Development user configuration."""

    username: str = Field(..., description="Username for development user")
    password: str = Field(..., description="Password for development user")
    roles: List[str] = Field(
        default_factory=list, description="Roles for development user"
    )


class DevelopmentConfig(BaseModel):
    """Development and testing configuration."""

    mock_providers: bool = Field(False, description="Use mock providers for testing")
    bypass_mfa: bool = Field(
        False, description="Bypass MFA requirements in development"
    )
    debug_audit: bool = Field(False, description="Enable detailed audit logging")
    test_users: List[DevelopmentUserConfig] = Field(
        default_factory=list, description="Pre-configured test users"
    )


class AuthConfig(BaseModel):
    """Main authentication configuration."""

    enabled: bool = Field(True, description="Enable authentication system")
    providers: ProvidersConfig = Field(..., description="Provider configurations")
    security: SecurityConfig = Field(
        default_factory=SecurityConfig, description="Security settings"
    )
    development: DevelopmentConfig = Field(
        default_factory=DevelopmentConfig, description="Development settings"
    )


# Extension configuration models


class PolicyCondition(BaseModel):
    """A single policy condition."""

    type: PolicyType = Field(..., description="Type of condition")
    permission: Optional[str] = Field(None, description="Required permission")
    roles: Optional[List[str]] = Field(None, description="Required roles")
    attributes: Optional[Dict[str, Any]] = Field(
        None, description="Required attributes"
    )
    conditions: Optional[List[PolicyCondition]] = Field(
        None, description="Nested conditions"
    )
    operator: str = Field("AND", description="Logical operator for nested conditions")

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v):
        if v not in ["AND", "OR", "NOT"]:
            raise ValueError("Operator must be AND, OR, or NOT")
        return v


class PolicyConfig(BaseModel):
    """Policy configuration for routes and routers."""

    type: Optional[PolicyType] = Field(None, description="Policy type")
    permission: Optional[str] = Field(None, description="Required permission")
    roles: Optional[List[str]] = Field(None, description="Required roles")
    attributes: Optional[Dict[str, Any]] = Field(
        None, description="Required attributes"
    )
    conditions: Optional[List[PolicyCondition]] = Field(
        None, description="Policy conditions"
    )
    operator: str = Field("AND", description="Logical operator for conditions")
    require_all: bool = Field(False, description="Whether all conditions must be met")

    @model_validator(mode="before")
    @classmethod
    def validate_policy_config(cls, values):
        """Validate that policy configuration is consistent."""
        policy_type = values.get("type")

        if policy_type == PolicyType.PERMISSION and not values.get("permission"):
            raise ValueError("Permission policy must specify a permission")

        if policy_type == PolicyType.ROLE and not values.get("roles"):
            raise ValueError("Role policy must specify roles")

        if policy_type == PolicyType.ATTRIBUTE and not values.get("attributes"):
            raise ValueError("Attribute policy must specify attributes")

        if policy_type == PolicyType.COMPLEX and not values.get("conditions"):
            raise ValueError("Complex policy must specify conditions")

        return values


class RouteConfig(BaseModel):
    """Route-level authentication configuration."""

    path: str = Field(..., description="Route path pattern")
    methods: List[str] = Field(
        default_factory=lambda: ["GET"], description="HTTP methods"
    )
    policy: Union[str, PolicyConfig] = Field(..., description="Access policy")
    require_fresh_auth: bool = Field(False, description="Require recent authentication")
    max_auth_age: Optional[str] = Field(None, description="Maximum authentication age")
    csrf_protection: bool = Field(False, description="Enable CSRF protection")
    content_validation: bool = Field(False, description="Enable content validation")
    audit: Optional[Dict[str, Any]] = Field(None, description="Audit configuration")
    context_extraction: Optional[Dict[str, str]] = Field(
        None, description="Context extraction rules"
    )


class RouterConfig(BaseModel):
    """Router-level authentication configuration."""

    name: str = Field(..., description="Router name")
    policies: Dict[str, Union[str, PolicyConfig]] = Field(
        default_factory=dict, description="Router policies"
    )
    ip_restrictions: Optional[Dict[str, List[str]]] = Field(
        None, description="IP-based restrictions"
    )
    time_restrictions: Optional[Dict[str, Any]] = Field(
        None, description="Time-based restrictions"
    )


class PermissionDef(BaseModel):
    """Permission definition."""

    permission: str = Field(..., description="Permission name")
    description: str = Field(..., description="Permission description")
    resource: str = Field(..., description="Resource this permission applies to")
    actions: List[str] = Field(..., description="Actions this permission allows")
    conditions: Optional[Dict[str, Any]] = Field(
        None, description="Additional conditions"
    )


class RoleDef(BaseModel):
    """Role definition."""

    name: str = Field(..., description="Role name")
    permissions: List[str] = Field(..., description="Permissions granted by this role")
    description: str = Field(..., description="Role description")
    inherits: Optional[List[str]] = Field(
        None, description="Parent roles to inherit from"
    )
    require_mfa: bool = Field(False, description="Whether this role requires MFA")


class AuditConfig(BaseModel):
    """Audit configuration."""

    events: Optional[List[str]] = Field(
        None, description="Events this extension will emit"
    )
    sensitive_operations: Optional[List[str]] = Field(
        None, description="Operations requiring detailed logging"
    )
    pii_fields: Optional[List[str]] = Field(None, description="PII fields to protect")
    retention: Optional[Dict[str, str]] = Field(None, description="Retention policies")


class PoliciesConfig(BaseModel):
    """Policies configuration."""

    default: str = Field("authenticated", description="Default access policy")
    custom_policies: Optional[Dict[str, PolicyConfig]] = Field(
        None, description="Custom policy definitions"
    )


class ExtensionAuthConfig(BaseModel):
    """Extension-specific authentication configuration."""

    policies: Optional[PoliciesConfig] = Field(None, description="Extension policies")
    routers: Optional[List[RouterConfig]] = Field(
        None, description="Router configurations"
    )
    routes: Optional[List[RouteConfig]] = Field(
        None, description="Route configurations"
    )
    permissions: Optional[List[PermissionDef]] = Field(
        None, description="Permission definitions"
    )
    roles: Optional[List[RoleDef]] = Field(None, description="Role definitions")
    audit: Optional[AuditConfig] = Field(None, description="Audit configuration")


# Update forward references
PolicyCondition.model_rebuild()
