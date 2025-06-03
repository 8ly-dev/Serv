# Database Integration System Implementation Plan

## Overview

This document outlines the comprehensive implementation plan for Serv's database integration framework. The system uses **Ommi as the required default ORM** and provides configurable database connections through `serv.config.yaml`, CLI management commands, and automatic dependency injection integration with Bevy 3.1 qualifiers support.

## Architecture Overview

### Core Design Principles

1. **Ommi-First**: Ommi is the required default ORM for all database operations
2. **Configuration-Driven**: All database connections defined in `serv.config.yaml`
3. **Multi-Database Support**: Multiple databases of the same type using Bevy 3.1 qualifiers
4. **Provider-Agnostic**: Support additional database providers through factory pattern
5. **Flexible Configuration**: Two configuration styles (nested settings vs flat parameters)
6. **Automatic DI Integration**: Database instances registered by factory return type with qualifiers
7. **Lifecycle Management**: Automatic connection/disconnection with app lifecycle
8. **CLI Management**: Commands for database setup, migrations, and management

### Directory Structure

```
serv/database/                       # Core database integration
├── __init__.py
├── manager.py                       # DatabaseManager class
├── factory.py                       # Factory loading and invocation
├── config.py                        # Configuration parsing and validation
├── lifecycle.py                     # Connection lifecycle management
├── cli.py                           # CLI commands for database operations
└── exceptions.py                    # Database-specific exceptions

serv/bundled/database/               # Bundled database providers
├── __init__.py
├── ommi/                           # Primary Ommi ORM provider (default)
│   ├── __init__.py
│   └── factory.py
├── sqlite/                          # Legacy SQLite provider (optional)
│   ├── __init__.py
│   └── factory.py
└── postgresql/                      # Legacy PostgreSQL provider (optional)
    ├── __init__.py
    └── factory.py
```

## Prerequisites

### Required Dependencies

Before implementing the database integration system, the following dependencies must be added to `pyproject.toml`:

```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "ommi>=1.0.0",  # Required: Default ORM
    "bevy>=3.1.0",  # Required: Qualifier support
]

[project.optional-dependencies]
database = [
    "asyncpg",      # Optional: PostgreSQL support
    "aiosqlite",    # Optional: Enhanced SQLite support
]
```

### Key Changes from Original Plan

1. **Ommi as Required Dependency**: Ommi is now a required dependency and the default ORM
2. **Bevy 3.1 Qualifiers**: Multiple databases of the same type using qualifiers
3. **Type-Based DI Registration**: Database instances registered by factory return type
4. **Ommi-First Examples**: All examples and documentation prioritize Ommi

## Phase 1: Core Database Infrastructure

### 1.1 Configuration Schema

**Location**: `serv/config.py` (extend existing)

**Configuration Format**:
```yaml
# serv.config.yaml
databases:
  # Primary: Ommi with PostgreSQL (default/recommended)
  primary:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "postgresql://user:pass@localhost/mydb"
    pool_size: 10
    qualifier: "primary"  # Bevy 3.1 qualifier for DI
  
  # Secondary: Ommi with SQLite for local data
  local:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "sqlite:///local.db"
    qualifier: "local"    # Bevy 3.1 qualifier for DI
    
  # Authentication: Ommi with SQLite
  auth:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "sqlite:///auth.db"
    qualifier: "auth"     # Bevy 3.1 qualifier for DI
    
  # Testing: Ommi in-memory SQLite
  test:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "sqlite:///:memory:"
    qualifier: "test"     # Bevy 3.1 qualifier for DI
      
  # Optional: Redis cache (non-Ommi example)
  cache:
    provider: "redis_provider:create_redis"
    host: "localhost"
    port: 6379
    db: 0
    qualifier: "cache"    # Bevy 3.1 qualifier for DI
```

**Configuration Validation**:
- Required fields: `provider` for each database
- Provider format: `module.path:factory_function`
- Settings can be nested object or flat parameters
- Optional `qualifier` field for Bevy 3.1 DI qualifiers (enables multiple databases of same type)
- Environment variable substitution support
- Ommi is the recommended provider for all database operations

### 1.2 DatabaseManager Class

**Location**: `serv/database/manager.py`

**Key Components**:
- Database configuration loading and validation
- Factory resolution and invocation
- Connection lifecycle management
- Dependency injection registration

```python
from typing import Dict, Any, Optional, Callable
from contextlib import AsyncExitStack
import inspect
from bevy import Container

class DatabaseManager:
    """
    Manages database connections defined in configuration.
    Handles factory loading, connection lifecycle, and DI registration.
    """
    
    def __init__(self, app_config: Dict[str, Any], container: Container):
        self.config = app_config.get('databases', {})
        self.container = container
        self.connections: Dict[str, Any] = {}
        self.exit_stack = AsyncExitStack()
    
    async def initialize_databases(self) -> None:
        """Initialize all configured database connections"""
        
    async def shutdown_databases(self) -> None:
        """Shutdown all database connections"""
        
    def register_with_di(self, name: str, connection: Any, qualifier: str | None = None) -> None:
        """Register database connection with dependency injection using Bevy 3.1 qualifiers"""
        
    async def create_connection(self, name: str, config: Dict[str, Any]) -> Any:
        """Create single database connection from config with qualifier support"""
```

### 1.3 Factory Loading System

**Location**: `serv/database/factory.py`

**Key Components**:
- Dynamic module and function loading
- Configuration style detection
- Parameter binding for factory functions
- Error handling for factory failures

```python
import importlib
import inspect
from typing import Dict, Any, Callable, Tuple

class FactoryLoader:
    """
    Loads and invokes database factory functions with configuration.
    Supports both nested settings and flat parameter styles.
    """
    
    @staticmethod
    def load_factory(provider: str) -> Callable:
        """Load factory function from module path"""
        module_path, function_name = provider.split(':')
        module = importlib.import_module(module_path)
        return getattr(module, function_name)
    
    @staticmethod
    def detect_config_style(config: Dict[str, Any]) -> str:
        """Detect whether config uses nested settings or flat parameters"""
        return "nested" if "settings" in config else "flat"
    
    @staticmethod
    async def invoke_factory(
        factory: Callable, 
        name: str, 
        config: Dict[str, Any]
    ) -> Any:
        """Invoke factory with appropriate parameter style"""
        
    @staticmethod
    def bind_flat_parameters(
        factory: Callable, 
        config: Dict[str, Any]
    ) -> Tuple[tuple, dict]:
        """Bind flat config parameters to factory signature"""
```

### 1.4 Lifecycle Management

**Location**: `serv/database/lifecycle.py`

**Key Components**:
- Connection initialization during app startup
- Graceful shutdown with proper cleanup
- Exit stack integration for resource management
- Error handling during lifecycle events

```python
from contextlib import AsyncExitStack
from typing import Any, Dict

class DatabaseLifecycle:
    """
    Manages database connection lifecycle within app context.
    Integrates with app startup/shutdown and exit stack management.
    """
    
    def __init__(self, manager: DatabaseManager, exit_stack: AsyncExitStack):
        self.manager = manager
        self.exit_stack = exit_stack
    
    async def startup_databases(self) -> None:
        """Initialize databases during app startup"""
        
    async def shutdown_databases(self) -> None:
        """Cleanup databases during app shutdown"""
        
    def register_cleanup(self, connection: Any) -> None:
        """Register connection cleanup with exit stack"""
```

## Phase 2: CLI Integration

### 2.1 Database CLI Commands

**Location**: `serv/database/cli.py` and extend `serv/cli/commands.py`

**New Commands**:
```bash
# Database management
serv database list                    # List configured databases
serv database status                  # Show connection status
serv database test <name>             # Test specific database connection
serv database test-all                # Test all database connections

# Database setup
serv database setup <name>            # Initialize specific database
serv database setup-all               # Initialize all databases
serv database reset <name>            # Reset specific database
serv database reset-all               # Reset all databases

# Configuration help
serv database config                  # Show example configurations
serv database providers               # List available providers
```

**CLI Implementation**:
```python
import click
from typing import Optional

@click.group()
def database():
    """Database management commands"""
    pass

@database.command()
def list():
    """List all configured databases"""
    
@database.command()
@click.argument('name', required=False)
def status(name: Optional[str]):
    """Show database connection status"""
    
@database.command()
@click.argument('name')
def test(name: str):
    """Test specific database connection"""
    
@database.command()
def test_all():
    """Test all database connections"""
    
@database.command()
@click.argument('name')
def setup(name: str):
    """Initialize specific database"""
    
@database.command()
def setup_all():
    """Initialize all databases"""
```

### 2.2 Configuration Templates

**Location**: `serv/cli/scaffolding/database_configs.yaml`

**Template Examples**:
```yaml
# PRIMARY: Ommi PostgreSQL (recommended for production)
ommi_postgresql_primary:
  provider: "serv.bundled.database.ommi:create_ommi"
  connection_string: "${DATABASE_URL}"
  qualifier: "primary"
  pool_size: 10

# Ommi SQLite (recommended for development/local)
ommi_sqlite_local:
  provider: "serv.bundled.database.ommi:create_ommi"
  connection_string: "sqlite:///app.db"
  qualifier: "local"

# Ommi in-memory (recommended for testing)
ommi_test:
  provider: "serv.bundled.database.ommi:create_ommi"
  connection_string: "sqlite:///:memory:"
  qualifier: "test"

# Multiple Ommi instances example
ommi_auth:
  provider: "serv.bundled.database.ommi:create_ommi"
  connection_string: "sqlite:///auth.db"
  qualifier: "auth"

ommi_analytics:
  provider: "serv.bundled.database.ommi:create_ommi"
  connection_string: "postgresql://user:pass@analytics-host/analytics"
  qualifier: "analytics"

# OPTIONAL: Redis cache (non-ORM)
redis_cache:
  provider: "redis:Redis"
  host: "${REDIS_HOST:-localhost}"
  port: 6379
  db: 0
  qualifier: "cache"

# LEGACY: SQLAlchemy (use Ommi instead)
sqlalchemy_legacy:
  provider: "sqlalchemy:create_engine"
  settings:
    url: "${DATABASE_URL}"
    pool_size: 10
    echo: false
  qualifier: "legacy"
```

## Phase 3: Bundled Database Providers

**Note**: Ommi is the required default ORM. Legacy providers are provided for specific use cases only.

### 3.2 Legacy SQLite Provider (Optional)

**Location**: `serv/bundled/database/sqlite/factory.py`

**Note**: Use Ommi SQLite provider instead. This is provided for legacy compatibility only.

```python
import sqlite3
import aiosqlite
from typing import Optional, Dict, Any

async def create_connection(name: str, settings: Optional[Dict[str, Any]] = None) -> aiosqlite.Connection:
    """Create SQLite database connection"""
    config = settings or {}
    database = config.get('database', ':memory:')
    timeout = config.get('timeout', 20.0)
    
    connection = await aiosqlite.connect(database, timeout=timeout)
    
    # Register cleanup
    async def cleanup():
        await connection.close()
    connection._cleanup = cleanup
    
    return connection

async def create_memory(name: str) -> aiosqlite.Connection:
    """Create in-memory SQLite database"""
    return await create_connection(name, {"database": ":memory:"})
```

### 3.1 Ommi Provider (Default/Primary)

**Location**: `serv/bundled/database/ommi/factory.py`

**Features**:
- **Default ORM for Serv**: Required dependency, primary choice for all database operations
- Auto-detects database driver from connection string scheme
- Supports SQLite and PostgreSQL out of the box
- Flat configuration (no nested driver specification required)
- Multiple database instances using Bevy 3.1 qualifiers
- Proper error handling for unsupported schemes
- Seamless integration with Serv's DI system

**Driver Auto-Detection**:
- `sqlite://` → SQLiteDriver
- `postgresql://` → PostgreSQLDriver  
- Extensible for additional drivers
- In-memory SQLite support for testing

```python
from ommi import Ommi
from ommi.ext.drivers.sqlite import SQLiteDriver
from ommi.ext.drivers.postgresql import PostgreSQLDriver
from typing import Dict, Any, Optional

async def create_ommi(
    name: str, 
    connection_string: str = 'sqlite:///:memory:',
    qualifier: str | None = None,
    **kwargs
) -> Ommi:
    """Create Ommi database instance with auto-detected driver (PRIMARY FACTORY)"""
    
    # Auto-detect driver from connection string scheme
    if connection_string.startswith('sqlite'):
        driver = SQLiteDriver.connect(connection_string, **kwargs)
    elif connection_string.startswith('postgresql'):
        driver = PostgreSQLDriver.connect(connection_string, **kwargs)
    else:
        # Extract scheme for error message
        scheme = connection_string.split('://')[0] if '://' in connection_string else connection_string
        raise ValueError(f"Unsupported database scheme: {scheme}")
    
    # Create Ommi instance
    ommi_instance = Ommi(driver)
    await ommi_instance.__aenter__()
    
    # Register cleanup
    async def cleanup():
        await ommi_instance.__aexit__(None, None, None)
    ommi_instance._cleanup = cleanup
    
    return ommi_instance

# Convenience factories for common configurations
async def create_ommi_sqlite(
    name: str,
    database_path: str = ":memory:",
    qualifier: str | None = None,
    **kwargs
) -> Ommi:
    """Create Ommi instance with SQLite database"""
    connection_string = f"sqlite:///{database_path}"
    return await create_ommi(name, connection_string, qualifier, **kwargs)

async def create_ommi_postgresql(
    name: str,
    host: str = "localhost",
    port: int = 5432,
    database: str = "postgres",
    username: str = "postgres",
    password: str = "",
    qualifier: str | None = None,
    **kwargs
) -> Ommi:
    """Create Ommi instance with PostgreSQL database"""
    connection_string = f"postgresql://{username}:{password}@{host}:{port}/{database}"
    return await create_ommi(name, connection_string, qualifier, **kwargs)

# Backward compatibility
async def create_ommi_nested(name: str, settings: Optional[Dict[str, Any]] = None) -> Ommi:
    """Create Ommi instance with nested settings (backward compatibility)"""
    config = settings or {}
    connection_string = config.get('connection_string', 'sqlite:///:memory:')
    qualifier = config.get('qualifier')
    
    # Forward to the main factory with auto-detection
    return await create_ommi(name, connection_string, qualifier, **{k: v for k, v in config.items() if k not in ['connection_string', 'qualifier']})
```

### 3.3 Legacy SQLAlchemy Provider (Optional)

**Location**: Example external package integration

**Note**: Use Ommi provider instead. This is provided for legacy compatibility only.

```python
# Example: serv_sqlalchemy package
import sqlalchemy.ext.asyncio as sa_async
from typing import Dict, Any, Optional

async def create_engine(name: str, settings: Optional[Dict[str, Any]] = None) -> sa_async.AsyncEngine:
    """Create SQLAlchemy async engine"""
    config = settings or {}
    url = config.get('url', 'sqlite:///:memory:')
    pool_size = config.get('pool_size', 5)
    echo = config.get('echo', False)
    
    engine = sa_async.create_async_engine(
        url,
        pool_size=pool_size,
        echo=echo
    )
    
    # Register cleanup
    async def cleanup():
        await engine.dispose()
    engine._cleanup = cleanup
    
    return engine

# Flat parameter style binding
async def create_engine_flat(
    name: str,
    url: str = 'sqlite:///:memory:',
    pool_size: int = 5,
    echo: bool = False
) -> sa_async.AsyncEngine:
    """Create SQLAlchemy engine with flat parameters"""
    engine = sa_async.create_async_engine(
        url,
        pool_size=pool_size,
        echo=echo
    )
    
    async def cleanup():
        await engine.dispose()
    engine._cleanup = cleanup
    
    return engine
```

## Phase 4: App Integration

### 4.1 App Class Extensions

**Location**: `serv/app.py` (extend existing)

**Integration Points**:
- Database manager initialization during app creation
- Database connections during app startup
- Cleanup registration with app exit stack
- Dependency injection registration

```python
# Additions to existing App class
from serv.database import DatabaseManager

class App:
    def __init__(self, config_path: Optional[str] = None, dev_mode: bool = False):
        # ... existing initialization ...
        
        # Database manager
        self.database_manager = DatabaseManager(self.config, self.container)
    
    async def startup(self):
        # ... existing startup logic ...
        
        # Initialize databases
        await self.database_manager.initialize_databases()
    
    async def shutdown(self):
        # ... existing shutdown logic ...
        
        # Shutdown databases
        await self.database_manager.shutdown_databases()
```

### 4.2 Dependency Injection Integration

**Location**: `serv/injectors.py` (extend existing)

**Database Injection with Bevy 3.1 Qualifiers**:
```python
from bevy import Container
from typing import Any
from ommi import Ommi

def register_databases(container: Container, connections: Dict[str, Any], configs: Dict[str, Dict]) -> None:
    """Register database connections with DI container using factory return types and qualifiers"""
    for name, connection in connections.items():
        config = configs[name]
        qualifier = config.get('qualifier', name)
        
        # Register by factory return type with qualifier
        # This allows multiple instances of the same type (e.g., multiple Ommi instances)
        container.instance(
            connection,
            type_hint=type(connection),
            qualifier=qualifier
        )

# Usage in routes with Bevy 3.1 qualifiers
from bevy import dependency
from ommi import Ommi

class MyRoute(Route):
    async def handle_get(
        self,
        request: GetRequest,
        # Inject Ommi instances by qualifier
        primary_db: Ommi = dependency(qualifier="primary"),
        auth_db: Ommi = dependency(qualifier="auth"),
        local_db: Ommi = dependency(qualifier="local"),
    ):
        # Use databases
        user = await primary_db.find(User.id == 1).one.or_none()
        auth_token = await auth_db.find(Token.user_id == user.id).one.or_none()
        settings = await local_db.find(UserSettings.user_id == user.id).one.or_none()
```

## Phase 5: Configuration and Validation

### 5.1 Configuration Schema Validation

**Location**: `serv/database/config.py`

```python
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum

class ConfigStyle(Enum):
    NESTED = "nested"
    FLAT = "flat"

@dataclass
class DatabaseConfig:
    name: str
    provider: str
    style: ConfigStyle
    settings: Dict[str, Any]

class DatabaseConfigValidator:
    """Validates database configuration entries"""
    
    @staticmethod
    def validate_databases_config(config: Dict[str, Any]) -> List[DatabaseConfig]:
        """Validate and parse databases configuration"""
        
    @staticmethod
    def validate_provider_format(provider: str) -> bool:
        """Validate provider format (module.path:function)"""
        
    @staticmethod
    def check_provider_exists(provider: str) -> bool:
        """Check if provider module and function exist"""
```

### 5.2 Environment Variable Support

**Location**: `serv/config.py` (extend existing)

**Variable Substitution**:
```yaml
databases:
  production:
    provider: "sqlalchemy:create_engine"
    settings:
      url: "${DATABASE_URL}"  # Required environment variable
      pool_size: "${DB_POOL_SIZE:-10}"  # Optional with default
      echo: "${DEBUG:-false}"
```

## Phase 6: Error Handling and Diagnostics

### 6.1 Database Exceptions

**Location**: `serv/database/exceptions.py`

```python
class DatabaseError(Exception):
    """Base exception for database operations"""
    pass

class DatabaseConfigurationError(DatabaseError):
    """Configuration-related database errors"""
    pass

class DatabaseConnectionError(DatabaseError):
    """Connection-related database errors"""
    pass

class DatabaseFactoryError(DatabaseError):
    """Factory loading/invocation errors"""
    pass

class DatabaseLifecycleError(DatabaseError):
    """Lifecycle management errors"""
    pass
```

### 6.2 Diagnostic Tools

**Location**: `serv/database/diagnostics.py`

```python
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class DatabaseDiagnostic:
    name: str
    provider: str
    status: str
    error: Optional[str] = None
    connection_info: Optional[Dict[str, Any]] = None

class DatabaseDiagnostics:
    """Diagnostic tools for database connections"""
    
    async def test_connection(self, name: str, config: Dict[str, Any]) -> DatabaseDiagnostic:
        """Test single database connection"""
        
    async def test_all_connections(self) -> List[DatabaseDiagnostic]:
        """Test all configured database connections"""
        
    def generate_report(self, diagnostics: List[DatabaseDiagnostic]) -> str:
        """Generate human-readable diagnostic report"""
```

## Phase 7: Testing Strategy

### 7.1 Unit Tests

**Test Coverage**:
- Configuration parsing and validation
- Factory loading and invocation
- Parameter binding for both config styles
- Lifecycle management
- Dependency injection registration
- Error handling scenarios

**Location**: `tests/test_database/`

### 7.2 Integration Tests

**Test Scenarios**:
- Complete database initialization flow
- Multiple database configurations
- CLI command functionality
- Real database connections (SQLite, in-memory)
- App startup/shutdown with databases

### 7.3 Configuration Tests

**Test Cases**:
- Valid and invalid configuration formats
- Environment variable substitution
- Missing provider modules
- Factory function signature validation

## Implementation Sequence

### Week 1: Core Infrastructure
1. Create database manager and factory loader
2. Implement configuration parsing and validation
3. Add basic lifecycle management
4. Create core exception classes

### Week 2: App Integration
1. Integrate with App class startup/shutdown
2. Add dependency injection support
3. Implement exit stack integration
4. Create basic diagnostic tools

### Week 3: CLI Commands
1. Implement database CLI commands
2. Add configuration templates
3. Create database testing utilities
4. Add provider discovery tools

### Week 4: Bundled Providers
1. Create SQLite provider
2. Implement Ommi provider
3. Add example third-party integration
4. Create provider documentation

### Week 5: Testing and Documentation
1. Comprehensive unit tests
2. Integration testing
3. CLI testing
4. Documentation and examples

## Success Criteria

### Functional Requirements
- [ ] Configuration-driven database setup
- [ ] Support for both nested and flat parameter styles
- [ ] Automatic dependency injection registration
- [ ] Proper lifecycle management with cleanup
- [ ] CLI commands for database management
- [ ] Error handling and diagnostics
- [ ] Multiple database provider support

### Technical Requirements
- [ ] Factory pattern for provider extensibility
- [ ] Async/await support throughout
- [ ] Exit stack integration for resource cleanup
- [ ] Environment variable substitution
- [ ] Configuration validation and error reporting
- [ ] Type hints and proper documentation

### Developer Experience
- [ ] Clear configuration examples
- [ ] Helpful CLI commands
- [ ] Good error messages
- [ ] Easy provider development
- [ ] Simple DI integration
- [ ] Comprehensive testing utilities

## Configuration Examples

### Complete Example Configuration

```yaml
# serv.config.yaml
databases:
  # Primary application database (Ommi + PostgreSQL)
  primary:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "${DATABASE_URL}"
    qualifier: "primary"
    pool_size: 10
      
  # Authentication database (Ommi + SQLite)
  auth:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "sqlite:///auth.db"
    qualifier: "auth"
    
  # Analytics database (Ommi + PostgreSQL)
  analytics:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "postgresql://user:pass@analytics-host/analytics"
    qualifier: "analytics"
    
  # Local development database (Ommi + SQLite)
  local:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "sqlite:///local.db"
    qualifier: "local"
    
  # Testing database (Ommi + in-memory SQLite)
  test:
    provider: "serv.bundled.database.ommi:create_ommi"
    connection_string: "sqlite:///:memory:"
    qualifier: "test"
    
  # Redis cache (non-ORM)
  cache:
    provider: "redis:Redis"
    host: "${REDIS_HOST:-localhost}"
    port: 6379
    db: 0
    decode_responses: true
    qualifier: "cache"
    
# Auth system integration with Ommi
auth:
  storage:
    backend: "serv.bundled.auth.storage.ommi_storage"
    config:
      database_qualifier: "auth"  # References databases.auth via qualifier
```

### Usage in Extensions

```python
# Extension using multiple Ommi databases with qualifiers
from serv.routes import Route
from serv.requests import GetRequest
from ommi import Ommi
from redis import Redis
from bevy import dependency

# Models (shared across databases)
class User:
    id: int
    name: str
    email: str

class AuthToken:
    user_id: int
    token: str
    expires_at: datetime

class AnalyticsEvent:
    user_id: int
    event_type: str
    timestamp: datetime

class DataRoute(Route):
    async def handle_get(
        self,
        request: GetRequest,
        # Multiple Ommi instances using Bevy 3.1 qualifiers
        primary_db: Ommi = dependency(qualifier="primary"),
        auth_db: Ommi = dependency(qualifier="auth"),
        analytics_db: Ommi = dependency(qualifier="analytics"),
        cache: Redis = dependency(qualifier="cache"),
    ):
        # Use primary database (PostgreSQL via Ommi)
        user = await primary_db.find(User.id == 1).one.or_none()
        if not user:
            return {"error": "User not found"}
            
        # Use auth database (SQLite via Ommi)
        token = await auth_db.find(AuthToken.user_id == user.id).one.or_none()
        
        # Use analytics database (PostgreSQL via Ommi)
        events = await analytics_db.find(AnalyticsEvent.user_id == user.id).limit(10).all()
        
        # Use cache (Redis)
        cache_key = f"user_data_{user.id}"
        cached_data = cache.get(cache_key)
        if not cached_data:
            cached_data = {"name": user.name, "email": user.email}
            cache.setex(cache_key, 3600, str(cached_data))
        
        return {
            "user": user,
            "auth_token": token,
            "recent_events": events,
            "cached_data": cached_data
        }
```

## Risk Assessment

### High Risk Items
- **Factory Loading**: Dynamic import security and error handling
- **Resource Cleanup**: Ensuring proper connection cleanup on app shutdown
- **Configuration Complexity**: Balancing flexibility with simplicity
- **Dependency Management**: Integration with existing DI system

### Mitigation Strategies
- Comprehensive factory validation and sandboxing
- Robust exit stack integration and testing
- Clear documentation and examples
- Extensive integration testing with real databases

## Dependencies and Blockers

### External Dependencies
- **Ommi ORM (REQUIRED)**: Primary database ORM, must be included in pyproject.toml
- **Bevy 3.1+ (REQUIRED)**: For qualifier-based dependency injection
- **Database drivers**: SQLite (built-in), PostgreSQL (optional)
- Configuration system enhancements
- CLI framework integration

### Internal Blockers
- App lifecycle hook system
- **Bevy 3.1 upgrade**: Required for qualifier support
- Configuration schema extensions
- Ommi integration testing

## Questions for Review

1. **Provider Security**: Should there be restrictions on which modules can be loaded as providers?

2. **Configuration Inheritance**: Should databases support configuration inheritance or templating?

3. **Migration Support**: Should the initial implementation include database migration utilities?

4. **Connection Pooling**: Should we provide built-in connection pooling abstractions?

5. **Health Checks**: Should databases automatically register health check endpoints?

6. **Monitoring**: Should we include built-in database performance monitoring?