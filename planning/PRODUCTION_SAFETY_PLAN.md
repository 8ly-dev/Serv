# Production Safety Plan

## Overview
Development settings in production are a major security risk. This plan outlines a comprehensive production safety system with environment detection, config validation, and CLI restrictions.

## 1. Environment Detection & Rules

### Environment Variable System
```bash
# Production detection (any of these marks production)
SERV_ENV=production
SERV_PRODUCTION=true
NODE_ENV=production  # Common convention

# Config file designation
SERV_PRODUCTION_CONFIGS="serv.config.yaml,production.yaml"  # Default: serv.config.yaml
```

### Production Safety Rules
1. **Config File Restrictions**: Only designated production configs allowed
2. **Development Feature Blocking**: Dev settings cause startup failure
3. **CLI Command Restrictions**: Dev-only commands blocked
4. **Validation on Startup**: Comprehensive production readiness checks

## 2. Config Loading API Design

### Current vs Proposed API

```python
# Current: Dict-based (unsafe)
raw_config = load_raw_config("serv.config.yaml")
auth_config = raw_config.get("auth", {})

# Proposed: Model-based (type-safe)
config = ServConfig.load_from_file("serv.config.yaml", production_mode=True)
auth_config = config.auth  # Validated AuthConfig instance
```

### New Config Models

```python
# Core config model
class ServConfig(BaseModel):
    site_info: SiteInfoConfig
    auth: Optional[AuthConfig] = None
    extensions: list[ExtensionConfig] = Field(default_factory=list)
    middleware: list[MiddlewareConfig] = Field(default_factory=list)
    databases: dict[str, DatabaseConfig] = Field(default_factory=dict)
    development: Optional[DevelopmentConfig] = None  # Stripped in production
    
    @classmethod
    def load_from_file(cls, path: Path, production_mode: bool = None) -> "ServConfig":
        """Load and validate config with production safety."""
        
    def strip_development_features(self) -> "ServConfig":
        """Return production-safe version with dev features removed."""
        
    def save_to_file(self, path: Path) -> None:
        """Save config to YAML file."""

# Development-specific config
class DevelopmentConfig(BaseModel):
    debug: bool = False
    auto_reload: bool = True
    mock_external_services: bool = False
    test_data_fixtures: list[str] = Field(default_factory=list)
    bypass_auth: bool = False  # DANGEROUS!
    expose_internal_apis: bool = False
    
    @field_validator("*")
    @classmethod
    def block_in_production(cls, v, info):
        if is_production_mode():
            raise ValueError(f"Development setting '{info.field_name}' not allowed in production")
        return v
```

## 3. Production Validation System

### Production Safety Validator

```python
class ProductionSafetyValidator:
    """Validates configuration for production readiness."""
    
    @classmethod
    def validate_config(cls, config: ServConfig, strict: bool = True) -> list[str]:
        """Return list of production safety violations."""
        violations = []
        
        # Check for development features
        if config.development is not None:
            violations.append("Development section must be removed in production")
            
        # Check auth development settings
        if config.auth and config.auth.development:
            if config.auth.development.mock_providers:
                violations.append("Mock auth providers not allowed in production")
            if config.auth.development.bypass_mfa:
                violations.append("MFA bypass not allowed in production")
                
        # Check dangerous auth settings
        if config.auth and config.auth.development:
            for user in config.auth.development.test_users:
                violations.append(f"Test user '{user.username}' not allowed in production")
                
        return violations
    
    @classmethod
    def strip_development_features(cls, config: ServConfig) -> ServConfig:
        """Return production-safe config with dev features stripped."""
        config_dict = config.model_dump()
        
        # Remove development sections
        config_dict.pop("development", None)
        if "auth" in config_dict and config_dict["auth"]:
            config_dict["auth"].pop("development", None)
            
        # Remove debug middleware
        config_dict["middleware"] = [
            m for m in config_dict["middleware"] 
            if not m.get("entry", "").startswith("debug_")
        ]
        
        return ServConfig(**config_dict)
```

## 4. CLI Integration

### Production-Safe Commands

```python
# New CLI commands
@cli.command()
@click.option("--target", default="production.yaml", help="Output production config file")
def convert_to_production(target: str):
    """Convert development config to production-ready config."""
    
@cli.command() 
def validate_production():
    """Validate current config for production readiness."""
    
@cli.command()
def production_check():
    """Comprehensive production readiness check."""

# Modified existing commands
@cli.command()
@click.option("--dev", is_flag=True, help="Enable development mode")
def launch(dev: bool):
    """Launch server with production safety checks."""
    if is_production_mode() and dev:
        raise click.ClickException("--dev flag not allowed in production environment")
```

### Development Command Blocking

```python
def require_development_mode(f):
    """Decorator to block commands in production."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if is_production_mode():
            raise click.ClickException(
                "This command is only available in development mode. "
                "Set SERV_ENV=development to enable."
            )
        return f(*args, **kwargs)
    return wrapper

@cli.command()
@require_development_mode
def shell():
    """Interactive shell (dev only)."""
    
@cli.command() 
@require_development_mode
def create_test_data():
    """Generate test data (dev only)."""
```

## 5. Implementation APIs

### Config Loading

```python
class ConfigLoader:
    @staticmethod
    def load_config(
        path: Optional[Path] = None, 
        production_mode: Optional[bool] = None
    ) -> ServConfig:
        """Load config with production safety."""
        
        if production_mode is None:
            production_mode = is_production_mode()
            
        if path is None:
            path = get_default_config_path(production_mode)
            
        # Validate config file is production-approved
        if production_mode and not is_production_config_file(path):
            raise ConfigurationError(
                f"Config file '{path}' not approved for production. "
                f"Approved files: {get_production_config_files()}"
            )
            
        raw_config = load_raw_config(path)
        config = ServConfig(**raw_config)
        
        # Production validation
        if production_mode:
            violations = ProductionSafetyValidator.validate_config(config)
            if violations:
                raise ConfigurationError(
                    f"Production safety violations:\n" + 
                    "\n".join(f"- {v}" for v in violations)
                )
                
        return config
```

### Environment Detection

```python
def is_production_mode() -> bool:
    """Detect if running in production mode."""
    return (
        os.getenv("SERV_ENV") == "production" or
        os.getenv("SERV_PRODUCTION", "").lower() in ("true", "1", "yes") or
        os.getenv("NODE_ENV") == "production"
    )

def get_production_config_files() -> list[str]:
    """Get list of approved production config files."""
    default = ["serv.config.yaml"]
    env_configs = os.getenv("SERV_PRODUCTION_CONFIGS", "")
    if env_configs:
        return [f.strip() for f in env_configs.split(",")]
    return default

def is_production_config_file(path: Path) -> bool:
    """Check if config file is approved for production."""
    approved = get_production_config_files()
    return path.name in approved or str(path) in approved
```

## 6. Migration Strategy

### Phase 1: Add Production Detection
1. Implement environment detection utilities
2. Add production mode parameter to existing functions
3. Maintain backward compatibility

### Phase 2: Add Config Models
1. Create ServConfig and related models
2. Add model-based loading alongside dict-based
3. Update auth system to use models

### Phase 3: Add Safety Validation
1. Implement ProductionSafetyValidator
2. Add validation to config loading
3. Block dangerous settings in production

### Phase 4: Add CLI Tools
1. Add production validation commands
2. Add dev-to-production conversion
3. Block dev commands in production

## Benefits

- **Security**: Prevents accidental deployment of dev settings
- **Compliance**: Clear separation between dev and production environments
- **Safety**: Multiple layers of validation and protection
- **Usability**: Easy conversion tools and clear error messages
- **Maintainability**: Type-safe config models and validation

## Implementation Priority

This should be implemented after completing the current auth system development to avoid scope creep and maintain focus on the core authentication functionality.