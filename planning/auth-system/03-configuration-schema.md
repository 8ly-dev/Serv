# Configuration Schema Design

## Overview

This document defines the configuration schema for the authentication system, including both the `serv.config.yaml` format and the `extension.yaml` policy configuration.

## serv.config.yaml Schema

### Complete Auth Configuration

```yaml
# Database configuration (follows Serv patterns)
databases:
  # Main application database
  primary:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "${DATABASE_URL:-sqlite:///app.db}"
    qualifier: "primary"
  
  # Dedicated authentication database
  auth:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "${AUTH_DATABASE_URL:-sqlite:///auth.db}"
    qualifier: "auth"

# Authentication and authorization configuration
auth:
  # Core authentication settings
  enabled: true
  
  # Provider configurations
  providers:
    # Credential provider configuration
    credential:
      provider: "database"  # database, memory, or import.path:Class
      config:
        database_qualifier: "auth"  # References databases.auth above
        password_hashing: "argon2"
        password_policy:
          min_length: 12
          require_uppercase: true
          require_lowercase: true
          require_numbers: true
          require_symbols: true
          max_age_days: 90
          history_count: 12
        token_settings:
          algorithm: "HS256"
          expiry: "24h"
          refresh_enabled: true
        # Multi-factor auth for future expansion
        # multi_factor:
        #   enabled: false
    
    # Session provider configuration  
    session:
      provider: "memory"  # database, memory, or import.path:Class
      config:
        default_duration: "8h"
        max_duration: "30d"
        inactivity_timeout: "2h"
        concurrent_sessions: 5
        session_fixation_protection: true
        secure_cookies: true
        same_site: "Strict"
        cleanup_interval: "1h"
    
    # User provider configuration
    user:
      provider: "database"  # database, memory, or import.path:Class
      config:
        database_qualifier: "auth"  # Uses same auth database
        username_field: "username"
        email_field: "email"
        auto_create_users: false
        default_roles: ["user"]
        user_activation: "email"
        profile_fields: ["first_name", "last_name", "department"]
    
    # Audit provider configuration
    audit:
      provider: "database"  # database, memory, or import.path:Class
      config:
        database_qualifier: "auth"  # Uses same auth database
        retention_days: 2555  # 7 years
        encryption_enabled: true
        encryption_key: "${AUDIT_ENCRYPTION_KEY}"
        real_time_alerts: true
        alert_endpoints: ["slack://security", "email://security@company.com"]
    
    # Policy provider configuration
    policy:
      provider: "rbac"  # rbac, or import.path:Class
      config:
        role_hierarchy: true
        permission_inheritance: true
        default_policy: "deny"
        cache_evaluations: true
        cache_duration: "5m"
  
  # Security settings
  security:
    # Future: Rate limiting (not implemented in initial version)
    # rate_limiting:
    #   enabled: false
    
    # Security headers
    headers:
      strict_transport_security: true
      content_security_policy: "default-src 'self'"
      x_frame_options: "DENY"
      x_content_type_options: "nosniff"
    
    # Password security
    password_security:
      breach_checking: true
      common_password_list: "top_10k"
      similarity_threshold: 0.8
    
    # Session security
    session_security:
      ip_validation: true
      user_agent_validation: true
      geo_blocking: false
      concurrent_login_limit: 3
  
  # Future integrations (not implemented in initial version)
  # integrations:
  #   oauth:
  #     enabled: false
  #   ldap:
  #     enabled: false
  #   saml:
  #     enabled: false
  
  # Development and testing
  development:
    mock_providers: false
    bypass_mfa: false
    debug_audit: false
    test_users:
      - username: "admin"
        password: "admin123"
        roles: ["admin"]
      - username: "user"
        password: "user123"
        roles: ["user"]
```

## extension.yaml Policy Configuration

### Route and Router Protection

```yaml
# Extension metadata
name: "Blog Extension"
description: "A simple blog management system"
version: "1.0.0"

# Authentication and authorization configuration
auth:
  # Global extension policies
  policies:
    # Default access policy for this extension
    default: "authenticated"  # "public", "authenticated", "admin", "custom:policy_name"
    
    # Custom policy definitions
    custom_policies:
      blog_author:
        description: "User must be the author of the blog post"
        type: "permission_check"
        permissions: ["write:blog"]
        conditions:
          resource_owner: true
      
      premium_content:
        description: "User must have premium subscription"
        type: "attribute_check"
        attributes:
          subscription_type: "premium"
      
      admin_only:
        description: "Administrative access only"
        type: "role_check"
        roles: ["admin", "moderator"]
        require_mfa: true
  
  # Router-level protection
  routers:
    - name: "blog_router"
      policies:
        default: "authenticated"
        routes:
          "/admin/*": "admin_only"
          "/premium/*": "premium_content"
          "/author/*": "blog_author"
      
      # IP restrictions
      ip_restrictions:
        admin_routes: ["192.168.1.0/24", "10.0.0.0/8"]
      
      # Time-based restrictions
      time_restrictions:
        maintenance_window:
          start: "02:00"
          end: "04:00"
          timezone: "UTC"
          exempt_roles: ["admin"]
  
  # Route-level protection
  routes:
    # Public routes (override default)
    - path: "/blog/posts"
      methods: ["GET"]
      policy: "public"
    
    - path: "/blog/search"
      methods: ["GET"]
      policy: "public"
    
    # Protected routes
    - path: "/blog/posts"
      methods: ["POST", "PUT", "DELETE"]
      policy: "blog_author"
      audit:
        events: ["content.create", "content.modify", "content.delete"]
        sensitive_data: true
    
    - path: "/blog/admin/*"
      methods: ["*"]
      policy: "admin_only"
      require_fresh_auth: true  # Require recent authentication
      max_auth_age: "30m"
    
    # Custom policy route
    - path: "/blog/posts/{post_id}/edit"
      methods: ["GET", "POST"]
      policy: "custom:blog_author"
      context_extraction:
        post_id: "path"
        user_id: "session"
      
      # Additional security
      csrf_protection: true
      content_validation: true
  
  # Permission definitions for this extension
  permissions:
    - permission: "read:blog"
      description: "Read blog posts and comments"
      resource: "blog"
      actions: ["read", "list"]
    
    - permission: "write:blog"
      description: "Create and edit own blog posts"
      resource: "blog"
      actions: ["create", "update"]
      conditions:
        owner_only: true
    
    - permission: "moderate:blog"
      description: "Moderate blog content"
      resource: "blog"
      actions: ["update", "delete", "moderate"]
    
    - permission: "admin:blog"
      description: "Full blog administration"
      resource: "blog"
      actions: ["*"]
  
  # Role definitions
  roles:
    - name: "blog_reader"
      permissions: ["read:blog"]
      description: "Can read blog content"
    
    - name: "blog_author"
      permissions: ["read:blog", "write:blog"]
      description: "Can read and write blog content"
    
    - name: "blog_moderator"
      permissions: ["read:blog", "write:blog", "moderate:blog"]
      description: "Can moderate blog content"
      inherits: ["blog_author"]
    
    - name: "blog_admin"
      permissions: ["admin:blog"]
      description: "Full blog administration"
      inherits: ["blog_moderator"]
      require_mfa: true
  
  # Audit configuration for this extension
  audit:
    # Events this extension will emit
    events:
      - "blog.post.create"
      - "blog.post.update"
      - "blog.post.delete"
      - "blog.comment.create"
      - "blog.comment.moderate"
    
    # High-risk operations requiring detailed logging
    sensitive_operations:
      - "blog.post.delete"
      - "blog.user.ban"
      - "blog.content.moderate"
    
    # PII fields to protect in audit logs
    pii_fields: ["user_email", "user_ip", "user_agent"]
    
    # Retention for extension-specific events
    retention:
      standard: "1y"
      sensitive: "7y"
      pii: "2y"

# Backwards compatibility with non-auth extensions
middleware:
  - name: "auth_middleware"
    priority: 100
    config:
      enforce_policies: true
      redirect_unauthorized: "/login"
      error_pages:
        401: "/errors/unauthorized"
        403: "/errors/forbidden"
```

## Policy Expression Language

### Simple Policy Expressions

```yaml
# String-based policies (simple)
policy: "public"                    # Anyone can access
policy: "authenticated"             # Must be logged in
policy: "admin"                     # Must have admin role
policy: "custom:my_policy"          # Custom policy function

# Permission-based policies
policy:
  type: "permission"
  permission: "read:posts"

# Role-based policies  
policy:
  type: "role"
  roles: ["admin", "moderator"]
  require_all: false  # OR operation (default), true = AND operation

# Attribute-based policies
policy:
  type: "attribute"
  attributes:
    department: "engineering"
    clearance_level: ">=secret"

# Complex policies with conditions
policy:
  type: "complex"
  conditions:
    - type: "permission"
      permission: "write:posts"
    - type: "attribute"
      attributes:
        is_verified: true
    - type: "context"
      conditions:
        resource_owner: true
        time_of_day: "business_hours"
  operator: "AND"  # AND, OR, NOT
```

## Configuration Validation Schema

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from enum import Enum

class ProviderSpec(str):
    """Provider specification - either simple name or import.path:Class"""
    pass

class PolicyType(str, Enum):
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    PERMISSION = "permission"
    ROLE = "role"
    ATTRIBUTE = "attribute"
    COMPLEX = "complex"
    CUSTOM = "custom"

class AuthConfig(BaseModel):
    enabled: bool = True
    providers: 'ProvidersConfig'
    security: Optional['SecurityConfig'] = None
    integrations: Optional['IntegrationsConfig'] = None
    development: Optional['DevelopmentConfig'] = None

class ProvidersConfig(BaseModel):
    credential: 'ProviderConfig'
    session: 'ProviderConfig'
    user: 'ProviderConfig'
    audit: 'ProviderConfig'
    policy: 'ProviderConfig'

class ProviderConfig(BaseModel):
    provider: ProviderSpec
    config: Dict[str, Any]

class ExtensionAuthConfig(BaseModel):
    policies: Optional['PoliciesConfig'] = None
    routers: Optional[List['RouterConfig']] = None
    routes: Optional[List['RouteConfig']] = None
    permissions: Optional[List['PermissionDef']] = None
    roles: Optional[List['RoleDef']] = None
    audit: Optional['AuditConfig'] = None

class PolicyConfig(BaseModel):
    type: PolicyType
    permission: Optional[str] = None
    roles: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None
    conditions: Optional[List['PolicyCondition']] = None
    operator: Optional[str] = "AND"

# ... additional validation models
```

## Environment Variable Integration

```yaml
# Environment variable substitution patterns
auth:
  providers:
    credential:
      config:
        # Direct substitution
        encryption_key: "${AUTH_ENCRYPTION_KEY}"
        
        # With defaults
        password_policy:
          min_length: "${PASSWORD_MIN_LENGTH:-12}"
        
        # Required variables (will fail if not set)
        database_url: "${DATABASE_URL:?Database URL is required}"
        
        # Complex substitution
        redis_url: "${REDIS_PROTOCOL:-redis}://${REDIS_HOST:-localhost}:${REDIS_PORT:-6379}/${REDIS_DB:-0}"
```

## Configuration Loading and Validation

```python
class AuthConfigLoader:
    """Loads and validates authentication configuration."""
    
    @staticmethod
    def load_config(config_path: Path) -> AuthConfig:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
        
        # Environment variable substitution
        processed_config = AuthConfigLoader._substitute_env_vars(raw_config)
        
        # Validation
        try:
            return AuthConfig(**processed_config.get('auth', {}))
        except ValidationError as e:
            raise ConfigurationError(f"Invalid auth configuration: {e}")
    
    @staticmethod
    def load_extension_auth_config(extension_yaml: Path) -> ExtensionAuthConfig:
        """Load extension-specific auth configuration."""
        # Similar loading logic for extension.yaml files
        pass
```

This configuration schema provides:
- **Comprehensive Coverage**: All aspects of authentication/authorization
- **Flexibility**: Multiple provider types and integration options  
- **Validation**: Strong typing and validation rules
- **Environment Integration**: Secure handling of secrets
- **Extension Support**: Granular policy control per extension
- **Backwards Compatibility**: Works with existing extensions