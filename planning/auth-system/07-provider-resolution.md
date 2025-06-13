# Provider Resolution and Implementation Selection

## Overview

This document explains how the authentication system determines which concrete provider implementations to use based on configuration, and how the dependency injection container is populated with the correct instances using standardized `module:Class` import format.

## Provider Resolution Strategy

### 1. Configuration-Driven Factory Pattern

```python
# serv/auth/factory.py
from typing import Dict, Type, Any
from abc import ABC, abstractmethod
import importlib

class ProviderFactory(ABC):
    """Base factory for creating provider instances."""
    
    @abstractmethod
    def create(self, config: Dict[str, Any], container: Container) -> Any:
        """Create provider instance from configuration."""
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate provider configuration."""
        pass

class CredentialProviderFactory(ProviderFactory):
    """Factory for credential providers."""
    
    # Registry of bundled implementations using standard import format
    _bundled_implementations: Dict[str, str] = {
        "memory": "serv.bundled.auth.memory.credential:MemoryCredentialProvider",
        "database": "serv.bundled.auth.database.credential:DatabaseCredentialProvider", 
        "redis": "serv.bundled.auth.redis.credential:RedisCredentialProvider",
        "ldap": "serv.bundled.auth.ldap.credential:LdapCredentialProvider",
        "oauth": "serv.bundled.auth.oauth.credential:OAuthCredentialProvider"
    }
    
    # Registry for external/extension providers
    _external_implementations: Dict[str, str] = {}
    
    def create(self, config: Dict[str, Any], container: Container) -> CredentialProvider:
        provider_type = config.get("type")
        provider_class = config.get("class")  # Direct class specification
        
        if provider_class:
            # Direct class import for external providers
            return self._create_from_import_string(provider_class, config, container)
        elif provider_type in self._bundled_implementations:
            # Bundled implementation
            import_string = self._bundled_implementations[provider_type]
            return self._create_from_import_string(import_string, config, container)
        elif provider_type in self._external_implementations:
            # Registered external implementation
            import_string = self._external_implementations[provider_type]
            return self._create_from_import_string(import_string, config, container)
        else:
            raise ConfigurationError(f"Unknown credential provider: {provider_type}")
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        provider_type = config.get("type")
        provider_class = config.get("class")
        
        if not provider_type and not provider_class:
            return False
        
        # Get import string
        if provider_class:
            import_string = provider_class
        elif provider_type in self._bundled_implementations:
            import_string = self._bundled_implementations[provider_type]
        elif provider_type in self._external_implementations:
            import_string = self._external_implementations[provider_type]
        else:
            return False
        
        # Validate that the class can be imported and is correct type
        return self._validate_import_string(import_string, CredentialProvider)
    
    def _create_from_import_string(self, import_string: str, config: Dict[str, Any], container: Container):
        """Create provider from import string in format 'module.path:Class'."""
        try:
            module_path, class_name = import_string.split(":", 1)
            module = importlib.import_module(module_path)
            provider_class = getattr(module, class_name)
            
            provider_config = config.get("config", {})
            return provider_class(provider_config, container)
            
        except (ValueError, ImportError, AttributeError) as e:
            raise ConfigurationError(f"Cannot import provider '{import_string}': {e}")
    
    def _validate_import_string(self, import_string: str, expected_base_class: type) -> bool:
        """Validate that an import string points to a valid provider class."""
        try:
            module_path, class_name = import_string.split(":", 1)
            module = importlib.import_module(module_path)
            provider_class = getattr(module, class_name)
            
            # Check if it's a subclass of the expected base class
            return issubclass(provider_class, expected_base_class)
            
        except (ValueError, ImportError, AttributeError, TypeError):
            return False
    
```

### 2. Auth System Bootstrap

```python
# serv/auth/bootstrap.py
from bevy import Container
from serv.auth.config import AuthConfig
from serv.auth.factory import (
    CredentialProviderFactory,
    SessionProviderFactory,
    UserProviderFactory,
    AuditProviderFactory,
    PolicyProviderFactory
)

class AuthSystemBootstrap:
    """Bootstraps the authentication system from configuration."""
    
    def __init__(self, config: AuthConfig):
        self.config = config
        self.factories = {
            "credential": CredentialProviderFactory(),
            "session": SessionProviderFactory(),
            "user": UserProviderFactory(),
            "audit": AuditProviderFactory(),
            "policy": PolicyProviderFactory()
        }
    
    async def setup_providers(self, container: Container) -> None:
        """Set up all auth providers in the container."""
        
        # Create providers in dependency order
        audit_provider = await self._create_audit_provider(container)
        credential_provider = await self._create_credential_provider(container)
        session_provider = await self._create_session_provider(container)
        user_provider = await self._create_user_provider(container)
        policy_provider = await self._create_policy_provider(container)
        
        # Create main auth provider
        from serv.bundled.auth.auth import StandardAuthProvider
        auth_provider = StandardAuthProvider(
            credential_provider=credential_provider,
            session_provider=session_provider,
            user_provider=user_provider,
            audit_provider=audit_provider
        )
        
        # Register all providers in container
        container.add(AuditProvider, audit_provider)
        container.add(CredentialProvider, credential_provider)
        container.add(SessionProvider, session_provider)
        container.add(UserProvider, user_provider)
        container.add(PolicyProvider, policy_provider)
        container.add(AuthProvider, auth_provider)
        
        # Create and register policy engine
        from serv.auth.core.policy import PolicyEngine
        policy_engine = PolicyEngine(policy_provider, auth_provider, audit_provider)
        container.add(PolicyEngine, policy_engine)
        
        # Set up database models if using database providers
        await self._setup_database_models(container)
    
    async def _create_credential_provider(self, container: Container) -> CredentialProvider:
        """Create credential provider from configuration."""
        config = self.config.providers.credential
        factory = self.factories["credential"]
        
        if not factory.validate_config(config.model_dump()):
            raise ConfigurationError("Invalid credential provider configuration")
        
        return factory.create(config.model_dump(), container)
    
    async def _setup_database_models(self, container: Container) -> None:
        """Set up database models for auth providers that need them."""
        # Check if any providers are using database
        database_qualifiers = set()
        
        for provider_config in [
            self.config.providers.credential,
            self.config.providers.session,
            self.config.providers.user,
            self.config.providers.audit
        ]:
            if provider_config.type == "database":
                qualifier = provider_config.config.get("database_qualifier")
                if qualifier:
                    database_qualifiers.add(qualifier)
        
        # Set up models for each database
        for qualifier in database_qualifiers:
            try:
                from bevy import Options
                from ommi import Ommi
                from serv.bundled.auth.database.models import auth_collection
                
                db = container.get(Ommi, Options(qualifier=qualifier))
                await db.use_models(auth_collection)
            except Exception as e:
                raise ConfigurationError(f"Failed to setup auth models for database '{qualifier}': {e}")
    
    # Similar methods for other providers...
```

### 3. Configuration Examples

```yaml
# serv.config.yaml - Different provider combinations

# Option 1: Bundled providers by type name
auth:
  enabled: true
  providers:
    credential:
      provider: "database"  # → serv.bundled.auth.database.credential:DatabaseCredentialProvider
      config:
        database_qualifier: "auth"
    
    session:
      provider: "memory"    # → serv.bundled.auth.memory.session:MemorySessionProvider
      config:
        default_duration: "8h"
    
    user:
      provider: "database"  # → serv.bundled.auth.database.user:DatabaseUserProvider
      config:
        database_qualifier: "auth"
    
    audit:
      provider: "database"  # → serv.bundled.auth.database.audit:DatabaseAuditProvider
      config:
        database_qualifier: "auth"

---
# Option 2: Direct class specification (bundled and external)
auth:
  enabled: true
  providers:
    credential:
      provider: "serv.bundled.auth.database.credential:DatabaseCredentialProvider"
      config:
        database_qualifier: "auth"
    
    session:
      provider: "redis_cluster_session.provider:RedisClusterSessionProvider"  # External package
      config:
        nodes: ["redis1:6379", "redis2:6379", "redis3:6379"]
    
    user:
      provider: "serv_auth_okta.providers:OktaUserProvider"  # External package
      config:
        domain: "company.okta.com"
        api_token: "${OKTA_API_TOKEN}"
    
    audit:
      provider: "elasticsearch_audit.provider:ElasticsearchAuditProvider"  # External package
      config:
        endpoint: "https://elasticsearch.company.com"

---
# Option 3: Mixed approach
auth:
  enabled: true
  providers:
    credential:
      provider: "database"  # Bundled shorthand
      config:
        database_qualifier: "auth"
    
    session:
      provider: "memory"    # Bundled shorthand
      config:
        default_duration: "1h"
    
    user:
      provider: "my_company.auth.providers:CustomActiveDirectoryUserProvider"  # Custom
      config:
        domain: "company.local"
    
    audit:
      provider: "database"  # Bundled shorthand
      config:
        database_qualifier: "auth"

---
# Development configuration
auth:
  enabled: true
  providers:
    # All in-memory for testing
    credential:
      provider: "memory"
      config:
        password_min_length: 8
    
    session:
      provider: "memory"
      config:
        default_duration: "1h"
    
    user:
      provider: "memory"
      config:
        auto_create_users: true
    
    audit:
      provider: "serv.bundled.auth.file.audit:FileAuditProvider"
      config:
        log_file: "/tmp/auth_audit.log"
```

### 4. Provider Base Classes with Configuration Support

```python
# serv/bundled/auth/database/models.py
from dataclasses import dataclass
from typing import Annotated, Optional
from datetime import datetime
from ommi import ommi_model, Key
from ommi.models.collections import ModelCollection

# Auth-specific model collection
auth_collection = ModelCollection()

@ommi_model(collection=auth_collection)
@dataclass
class User:
    email: str
    username: str
    password_hash: str
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    id: Annotated[int, Key] = None

@ommi_model(collection=auth_collection)
@dataclass
class Session:
    user_id: int
    session_token: str
    expires_at: datetime
    created_at: datetime = None
    last_accessed_at: datetime = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    id: Annotated[int, Key] = None

@ommi_model(collection=auth_collection)
@dataclass
class AuditLog:
    user_id: Optional[int]
    event_type: str
    event_data: str  # JSON string
    ip_address: Optional[str]
    user_agent: Optional[str]
    timestamp: datetime = None
    id: Annotated[int, Key] = None

# serv/bundled/auth/database/credential.py
from bevy import Inject, Options
from ommi import Ommi

class DatabaseCredentialProvider(CredentialProvider):
    """Database-backed credential provider using Ommi."""
    
    def __init__(self, config: Dict[str, Any], container: Container):
        try:
            self.config = self._validate_and_parse_config(config)
            self.container = container
            self._db = None
            
            # Fail-fast: Test database connection at startup
            qualifier = self.config.get("database_qualifier")
            if not qualifier:
                raise ConfigurationError("database_qualifier is required for database credential provider")
            
            # Verify we can get the database instance
            test_db = container.get(Ommi, Options(qualifier=qualifier))
            if not test_db:
                raise ConfigurationError(f"Database with qualifier '{qualifier}' not found in container")
                
        except Exception as e:
            raise ConfigurationError(f"Failed to initialize database credential provider: {e}") from e
    
    @property 
    def db(self) -> Ommi:
        """Lazy-loaded database connection."""
        if self._db is None:
            qualifier = self.config["database_qualifier"]
            self._db = self.container.get(Ommi, Options(qualifier=qualifier))
        return self._db
    
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> bool:
        """Validate configuration for this provider."""
        required_fields = ["database_qualifier"]
        return all(field in config for field in required_fields)
    
    async def verify_credentials(self, email: str, password: str) -> Optional[User]:
        """Verify user credentials using Ommi."""
        user_result = await self.db.find(User.email == email).one()
        
        match user_result:
            case DBQueryResult.DBQuerySuccess(user):
                if self._verify_password(password, user.password_hash):
                    return user
                return None
            case DBQueryResult.DBQueryFailure(_):
                return None
```

## Key Benefits

### 1. **Standardized Import Format**
- Uses Python ecosystem standard `module:Class` format
- Same format for bundled and external providers
- Compatible with entry points and tooling

### 2. **Simple Configuration**
- Simple names for bundled providers
- Direct class imports for third-party providers
- Mixed configurations supported

### 3. **Validation & Error Handling**
- Configuration validated before provider creation
- Import validation ensures class compatibility
- Clear error messages for configuration issues

### 4. **Developer Experience**
```bash
# Install external provider
pip install my-custom-auth-provider

# Use in configuration with explicit import path
```

This approach provides a simple, explicit system for provider selection that loads only what is configured, while maintaining clean separation between configuration, implementation selection, and runtime usage.