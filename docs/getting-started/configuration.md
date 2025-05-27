# Configuration

Serv uses a flexible configuration system based on YAML files. This guide covers how to configure your Serv applications effectively.

## Configuration Files

### Main Configuration File

The main configuration file is typically named `serv.config.yaml` and placed in your project root:

```yaml
# serv.config.yaml
extensions:
  - extension: auth
    settings:
      secret_key: "your-secret-key-here"
      token_expiry: 3600
  - extension: blog
    settings:
      posts_per_page: 10
      allow_comments: true
  - entry: external_package.extension:ExternalExtension
    config:
      api_url: "https://api.example.com"

middleware:
  - entry: my_middleware:LoggingMiddleware
    config:
      log_level: "INFO"

settings:
  debug: false
  host: "0.0.0.0"
  port: 8000
```

### Loading Configuration

Load configuration when creating your app:

```python
from serv import App

# Load from default location (./serv.config.yaml)
app = App()

# Load from custom location
app = App(config="./config/production.yaml")

# Load from multiple files (later files override earlier ones)
app = App(config=["./base.yaml", "./environment.yaml"])
```

## Extension Configuration

### Extension Settings

Configure extensions in the `extensions` section:

```yaml
extensions:
  - extension: auth  # Extension directory name
    settings:
      secret_key: "super-secret-key"
      algorithm: "HS256"
      token_expiry: 86400  # 24 hours
      
  - extension: database
    settings:
      url: "postgresql://user:pass@localhost/db"
      pool_size: 10
      echo: false
```

### External Extension Configuration

Load extensions from external packages:

```yaml
extensions:
  - entry: "my_package.auth:AuthExtension"
    config:
      provider: "oauth2"
      client_id: "your-client-id"
      
  - entry: "third_party_extension:MainExtension"
    config:
      api_key: "your-api-key"
```

### Extension-Specific Configuration Files

Extensions can have their own `extension.yaml` files with default settings:

```yaml
# extensions/auth/extension.yaml
name: Authentication Extension
description: Provides user authentication
version: 1.0.0
author: Your Name
entry: auth.main:AuthExtension

settings:
  secret_key: "default-secret"
  algorithm: "HS256"
  token_expiry: 3600
  require_email_verification: true
```

Application configuration can override these defaults:

```yaml
# serv.config.yaml
extensions:
  - extension: auth
    settings:
      secret_key: "production-secret"  # Overrides default
      token_expiry: 7200               # Overrides default
      # require_email_verification uses default (true)
```

## Environment-Specific Configuration

### Environment Variables

Use environment variables for sensitive or environment-specific settings:

```yaml
# serv.config.yaml
extensions:
  - extension: database
    settings:
      url: ${DATABASE_URL}
      
  - extension: auth
    settings:
      secret_key: ${JWT_SECRET_KEY}
      
settings:
  debug: ${DEBUG:false}  # Default to false if not set
  port: ${PORT:8000}     # Default to 8000 if not set
```

### Multiple Configuration Files

Organize configuration by environment:

```yaml
# base.yaml - Common settings
extensions:
  - extension: auth
    settings:
      algorithm: "HS256"
      token_expiry: 3600

settings:
  host: "0.0.0.0"
```

```yaml
# development.yaml - Development overrides
extensions:
  - extension: auth
    settings:
      secret_key: "dev-secret"

settings:
  debug: true
  port: 8000
```

```yaml
# production.yaml - Production overrides
extensions:
  - extension: auth
    settings:
      secret_key: ${JWT_SECRET_KEY}

settings:
  debug: false
  port: ${PORT:80}
```

Load configuration based on environment:

```python
import os
from serv import App

env = os.getenv("ENVIRONMENT", "development")
config_files = ["base.yaml", f"{env}.yaml"]

app = App(config=config_files)
```

## Application Settings

### Core Settings

Configure core application behavior:

```yaml
settings:
  # Server settings
  host: "0.0.0.0"
  port: 8000
  
  # Development settings
  debug: true
  reload: true
  
  # Security settings
  allowed_hosts: ["localhost", "127.0.0.1", "myapp.com"]
  cors_origins: ["http://localhost:3000"]
  
  # Logging settings
  log_level: "INFO"
  log_format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Custom Settings

Add your own application-wide settings:

```yaml
settings:
  # Custom application settings
  app_name: "My Awesome App"
  version: "1.0.0"
  max_upload_size: 10485760  # 10MB
  cache_timeout: 300
  
  # Feature flags
  features:
    user_registration: true
    email_notifications: false
    analytics: true
```

Access custom settings in your code:

```python
from serv.config import get_config

config = get_config()
app_name = config.get('app_name', 'Default App')
max_upload = config.get('max_upload_size', 1048576)
```

## Middleware Configuration

### Global Middleware

Configure middleware that applies to all requests:

```yaml
middleware:
  - entry: "serv.middleware.cors:CORSMiddleware"
    config:
      allow_origins: ["*"]
      allow_methods: ["GET", "POST", "PUT", "DELETE"]
      allow_headers: ["*"]
      
  - entry: "my_middleware:LoggingMiddleware"
    config:
      log_requests: true
      log_responses: false
      
  - entry: "my_middleware:RateLimitMiddleware"
    config:
      requests_per_minute: 60
      burst_size: 10
```

### Extension-Provided Middleware

Extensions can register their own middleware:

```yaml
# In extension.yaml
middleware:
  - entry: "auth.middleware:AuthMiddleware"
    config:
      exempt_paths: ["/health", "/metrics"]
      
  - entry: "auth.middleware:SessionMiddleware"
    config:
      session_timeout: 1800
```

## Configuration Validation

### Schema Validation

Define schemas to validate your configuration:

```python
from serv.config import ConfigSchema
from typing import Optional

class AuthExtensionConfig(ConfigSchema):
    secret_key: str
    algorithm: str = "HS256"
    token_expiry: int = 3600
    require_email_verification: bool = True

class AuthExtension(Extension):
    def __init__(self):
        # Validate configuration against schema
        self.config = AuthExtensionConfig.from_config(self.get_config())
    
    async def on_app_startup(self):
        print(f"Auth extension starting with algorithm: {self.config.algorithm}")
```

### Required Settings

Mark settings as required:

```yaml
# extension.yaml
settings:
  secret_key: !required  # Must be provided
  algorithm: "HS256"     # Has default
  token_expiry: 3600     # Has default
```

## Configuration Best Practices

### 1. Use Environment Variables for Secrets

Never commit secrets to version control:

```yaml
# Good
extensions:
  - extension: auth
    settings:
      secret_key: ${JWT_SECRET_KEY}

# Bad - secret in config file
extensions:
  - extension: auth
    settings:
      secret_key: "super-secret-key-123"
```

### 2. Provide Sensible Defaults

Make your extensions work out of the box:

```yaml
# extension.yaml
settings:
  debug: false
  timeout: 30
  retries: 3
  cache_enabled: true
```

### 3. Document Configuration Options

Document all configuration options:

```yaml
# extension.yaml
name: My Extension
description: Does awesome things

settings:
  # Required: API key for external service
  api_key: !required
  
  # Optional: Request timeout in seconds (default: 30)
  timeout: 30
  
  # Optional: Number of retries on failure (default: 3)
  retries: 3
  
  # Optional: Enable caching (default: true)
  cache_enabled: true
```

### 4. Validate Configuration Early

Validate configuration at startup:

```python
class MyExtension(Extension):
    def __init__(self):
        config = self.get_config()
        
        # Validate required settings
        if not config.get('api_key'):
            raise ValueError("api_key is required")
        
        # Validate setting types and ranges
        timeout = config.get('timeout', 30)
        if not isinstance(timeout, int) or timeout <= 0:
            raise ValueError("timeout must be a positive integer")
        
        self.api_key = config['api_key']
        self.timeout = timeout
```

### 5. Use Configuration Layers

Organize configuration in layers:

1. **Extension defaults** (in `extension.yaml`)
2. **Application config** (in `serv.config.yaml`)
3. **Environment variables** (for deployment-specific values)
4. **Command-line arguments** (for runtime overrides)

```python
# Example of configuration precedence
import os
from serv import App

# 1. Start with extension defaults
# 2. Override with application config
app = App(config="serv.config.yaml")

# 3. Override with environment variables (handled automatically)
# 4. Override with command-line arguments
if os.getenv("DEBUG"):
    app.config['debug'] = True
```

## Dynamic Configuration

### Runtime Configuration Changes

Some settings can be changed at runtime:

```python
class ConfigurableExtension(Extension):
    def __init__(self):
        self.config = self.get_config()
        self.debug = self.config.get('debug', False)
    
    async def on_app_request_begin(self, router: Router = dependency()):
        # Add debug routes only if debug is enabled
        if self.debug:
            router.add_route("/debug/config", self.show_config)
    
    async def show_config(self, response: ResponseBuilder = dependency()):
        response.content_type("application/json")
        response.body(json.dumps(self.config, indent=2))
    
    def update_config(self, new_config: dict):
        """Update configuration at runtime"""
        self.config.update(new_config)
        self.debug = self.config.get('debug', False)
```

### Configuration Reloading

Implement configuration reloading for development:

```python
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigReloader(FileSystemEventHandler):
    def __init__(self, app: App):
        self.app = app
    
    def on_modified(self, event):
        if event.src_path.endswith('.yaml'):
            print("Configuration changed, reloading...")
            self.app.reload_config()

# In development mode
if app.config.get('debug'):
    observer = Observer()
    observer.schedule(ConfigReloader(app), path='.', recursive=False)
    observer.start()
```

## Configuration Examples

### Complete Application Configuration

```yaml
# serv.config.yaml
settings:
  app_name: "My Blog App"
  debug: ${DEBUG:false}
  host: ${HOST:0.0.0.0}
  port: ${PORT:8000}
  
  # Database settings
  database_url: ${DATABASE_URL:sqlite:///app.db}
  
  # Security settings
  secret_key: ${SECRET_KEY}
  allowed_hosts: 
    - "localhost"
    - "127.0.0.1"
    - ${DOMAIN:myapp.com}
  
  # Feature flags
  features:
    user_registration: true
    email_verification: ${EMAIL_VERIFICATION:false}
    analytics: ${ANALYTICS:false}

extensions:
  - extension: auth
    settings:
      secret_key: ${JWT_SECRET_KEY}
      token_expiry: ${TOKEN_EXPIRY:3600}
      
  - extension: blog
    settings:
      posts_per_page: ${POSTS_PER_PAGE:10}
      allow_comments: ${ALLOW_COMMENTS:true}
      
  - extension: email
    settings:
      smtp_host: ${SMTP_HOST:localhost}
      smtp_port: ${SMTP_PORT:587}
      smtp_user: ${SMTP_USER}
      smtp_password: ${SMTP_PASSWORD}

middleware:
  - entry: "serv.middleware.cors:CORSMiddleware"
    config:
      allow_origins: ${CORS_ORIGINS:["http://localhost:3000"]}
      
  - entry: "my_middleware:RateLimitMiddleware"
    config:
      requests_per_minute: ${RATE_LIMIT:60}
```

### Extension Configuration Template

```yaml
# extensions/my_extension/extension.yaml
name: My Extension
description: A sample extension demonstrating configuration
version: 1.0.0
author: Your Name
entry: my_extension.main:MyExtension

# Default settings (can be overridden in serv.config.yaml)
settings:
  # Required settings (must be provided by user)
  api_key: !required
  
  # Optional settings with defaults
  timeout: 30
  retries: 3
  debug: false
  
  # Complex settings
  cache:
    enabled: true
    ttl: 300
    max_size: 1000
  
  # List settings
  allowed_ips:
    - "127.0.0.1"
    - "::1"

# Additional entry points
entry_points:
  - entry: my_extension.admin:AdminExtension
    config:
      admin_path: "/admin"

# Middleware provided by this extension
middleware:
  - entry: my_extension.middleware:SecurityMiddleware
    config:
      check_csrf: true
      check_origin: true
```

## Next Steps

- **[Extensions](../guides/extensions.md)** - Learn how to create and configure extensions
- **[Middleware](../guides/middleware.md)** - Understand middleware configuration
- **[Deployment](../guides/deployment.md)** - Configure for production deployment
- **[Testing](../guides/testing.md)** - Test your configuration 