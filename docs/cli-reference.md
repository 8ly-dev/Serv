# CLI Reference

The Serv CLI provides a comprehensive set of commands for managing your web applications, extensions, and development workflow. This reference covers all available commands with detailed examples and usage patterns.

## Installation and Setup

The Serv CLI is available when you install the Serv framework:

```bash
pip install getserving
```

Verify the installation:

```bash
serv --version
```

## Global Options

All Serv commands support these global options:

| Option | Description | Example |
|--------|-------------|---------|
| `--version` | Show version information | `serv --version` |
| `--debug` | Enable debug logging | `serv --debug launch` |
| `--dev` | Enable development mode | `serv --dev launch` |
| `--app`, `-a` | Custom application class | `serv -a myapp.core:CustomApp launch` |
| `--config`, `-c` | Path to config file | `serv -c config/prod.yaml launch` |
| `--extension-dirs` | Extension directory path | `serv --extension-dirs ./custom-extensions launch` |

## Application Management

## Development Server

### `serv launch`

Launch the Serv application server.

**Usage:**
```bash
serv launch [--host HOST] [--port PORT] [--reload] [--no-reload] [--workers N] [--factory] [--dry-run]
```

**Options:**
- `--host`: Bind socket to this host (default: 127.0.0.1)
- `--port`, `-p`: Bind socket to this port (default: 8000)
- `--reload`: Enable auto-reload
- `--no-reload`: Disable auto-reload (overrides --dev mode default)
- `--workers`, `-w`: Number of worker processes (default: 1)
- `--factory`: Treat app as factory function
- `--dry-run`: Load app but don't start server

**Examples:**

```bash
# Basic launch
serv launch

# Custom host and port
serv launch --host 0.0.0.0 --port 3000

# Production with multiple workers
serv launch --workers 4 --host 0.0.0.0 --port 8000

# Development mode with enhanced features
serv --dev launch

# Development mode with auto-reload disabled
serv --dev launch --no-reload

# Dry run to test configuration
serv launch --dry-run
```

**Development Mode (--dev flag):**

The global `--dev` flag enables enhanced development features:

- 🔄 Auto-reload enabled by default (unless `--no-reload` is specified)
- 📝 Enhanced error reporting with full tracebacks
- 🐛 Debug logging automatically enabled
- ⚡ Development-optimized uvicorn settings

```bash
# Start development server
serv --dev launch

# Development mode on custom port
serv --dev launch --port 3000

# Development mode without auto-reload
serv --dev launch --no-reload

# Development mode on all interfaces
serv --dev launch --host 0.0.0.0
```

## Testing

### `serv test`

Run tests for your application and extensions.

**Usage:**
```bash
serv test [--extensions] [--e2e] [--coverage] [--verbose] [test_path]
```

**Options:**
- `--extensions`: Run extension tests only
- `--e2e`: Run end-to-end tests only
- `--coverage`: Generate coverage report
- `--verbose`, `-v`: Verbose test output
- `test_path`: Specific test file or directory

**Examples:**

```bash
# Run all tests
serv test

# Run only extension tests
serv test --extensions

# Run only e2e tests
serv test --e2e

# Run with coverage report
serv test --coverage

# Run specific test file
serv test tests/test_auth.py

# Verbose output with coverage
serv test --verbose --coverage
```

**Example output:**
```
🧪 Running tests...
🔍 Running all tests
Running: pytest tests/
📊 Coverage reporting enabled
✅ All tests passed!

Coverage Report:
Name                 Stmts   Miss  Cover
----------------------------------------
serv/app.py            45      2    96%
extensions/auth.py        23      0   100%
----------------------------------------
TOTAL                  68      2    97%
```

### `serv shell`

Start an interactive Python shell with your application context loaded.

**Usage:**
```bash
serv shell [--ipython] [--no-startup]
```

**Options:**
- `--ipython`: Use IPython if available
- `--no-startup`: Skip loading app context

**Examples:**

```bash
# Start shell with app context
serv shell

# Use IPython interface
serv shell --ipython

# Basic shell without app context
serv shell --no-startup
```

**Available objects in shell:**
- `app`: Your Serv application instance
- `serv`: The Serv module
- `extensions`: List of loaded extensions
- `Path`: pathlib.Path class
- `yaml`: PyYAML module

**Example session:**
```python
🐍 Starting interactive Python shell...
📦 Loading Serv app context...
🔌 Loaded 3 extensions into context
✅ App context loaded successfully
Available objects: app, serv, extensions, Path, yaml

>>> app.site_info
{'name': 'My Awesome Website', 'description': 'A modern web application'}
>>> len(extensions)
3
>>> extensions[0].name
'User Management'
```

## Configuration Management

### `serv config show`

Display your current configuration.

**Usage:**
```bash
serv config show [--format FORMAT]
```

**Options:**
- `--format`: Output format (yaml, json)

**Examples:**

```bash
# Show config in YAML format (default)
serv config show

# Show config in JSON format
serv config show --format json
```

**Example output:**
```yaml
📄 Configuration from 'serv.config.yaml':
==================================================
site_info:
  name: My Awesome Website
  description: A modern web application
extensions:
- extension: user_management
- extension: api_router
middleware:
- entry: cors_middleware
```

### `serv config validate`

Validate your configuration file syntax and structure.

**Usage:**
```bash
serv config validate
```

**Example output:**
```
✅ Configuration file is valid YAML
✅ Has required field: site_info
✅ Has required field: extensions
🎉 Configuration validation passed!
```

### `serv config get`

Get specific configuration values using dot notation.

**Usage:**
```bash
serv config get <key>
```

**Examples:**

```bash
# Get site name
serv config get site_info.name

# Get first extension
serv config get extensions.0.extension

# Get nested values
serv config get database.connection.host
```

**Example output:**
```
🔑 site_info.name: My Awesome Website
```

### `serv config set`

Set configuration values with automatic type conversion.

**Usage:**
```bash
serv config set <key> <value> [--type TYPE]
```

**Options:**
- `--type`: Value type (string, int, float, bool, list)

**Examples:**

```bash
# Set string value (default)
serv config set site_info.name "New Site Name"

# Set integer value
serv config set server.port 3000 --type int

# Set boolean value
serv config set debug.enabled true --type bool

# Set list value
serv config set allowed_hosts "localhost,127.0.0.1,example.com" --type list

# Set nested configuration
serv config set database.connection.timeout 30 --type int
```

## Extension Management

### `serv extension list`

List available and enabled extensions.

**Usage:**
```bash
serv extension list [--available]
```

**Options:**
- `--available`: Show all available extensions (default shows enabled)

**Examples:**

```bash
# List enabled extensions
serv extension list

# List all available extensions
serv extension list --available
```

**Example output:**
```
Enabled extensions (2):
  • User Management (v1.0.0) [user_management]
  • API Router (v2.1.0) [api_router] (with config)

Available extensions (4):
  • User Management (v1.0.0) [user_management]
    User authentication and management system
  • API Router (v2.1.0) [api_router]
    RESTful API routing and middleware
  • Blog Engine (v1.5.0) [blog_engine]
    Simple blog functionality
  • Admin Panel (v0.9.0) [admin_panel]
    Administrative interface
```

### `serv extension enable`

Enable a extension in your application.

**Usage:**
```bash
serv extension enable <extension_identifier>
```

**Examples:**

```bash
# Enable by directory name
serv extension enable user_management

# Enable extension with different name
serv extension enable blog_engine
```

**Example output:**
```
Extension 'user_management' enabled successfully.
Human name: User Management
```

### `serv extension disable`

Disable a extension in your application.

**Usage:**
```bash
serv extension disable <extension_identifier>
```

**Examples:**

```bash
# Disable by directory name
serv extension disable user_management

# Disable extension with different name
serv extension disable blog_engine
```

### `serv extension validate`

Validate extension structure and configuration.

**Usage:**
```bash
serv extension validate [extension_identifier] [--all]
```

**Options:**
- `--all`: Validate all extensions

**Examples:**

```bash
# Validate all extensions
serv extension validate

# Validate specific extension
serv extension validate user_management

# Explicitly validate all
serv extension validate --all
```

**Example output:**
```
=== Validating 2 Extension(s) ===

🔍 Validating extension: user_management
✅ extension.yaml is valid YAML
✅ Has required field: name
✅ Has required field: version
✅ Has recommended field: description
✅ Has recommended field: author
✅ Has __init__.py
✅ Found 3 Python file(s)
✅ Has main extension file: user_management.py
✅ user_management.py has valid Python syntax
🎉 Extension 'user_management' validation passed!

=== Validation Summary ===
🎉 All extensions passed validation!
```

## Project and Extension Development

### `serv create app`

Initialize a new Serv project with configuration files.

**Usage:**
```bash
serv create app [--force] [--non-interactive]
```

**Options:**
- `--force`: Overwrite existing configuration files
- `--non-interactive`: Use default values without prompts

**Examples:**

```bash
# Interactive initialization
serv create app

# Force overwrite existing config
serv create app --force

# Non-interactive with defaults (useful for scripts)
serv create app --non-interactive --force
```

**Interactive prompts:**
```
Enter site name [My Serv Site]: My Awesome Website
Enter site description [A new website powered by Serv]: A modern web application
```

**Generated files:**
- `serv.config.yaml` - Main configuration file

### `serv create extension`

Create a new extension with proper structure.

**Usage:**
```bash
serv create extension --name NAME [--force] [--non-interactive]
```

**Options:**
- `--name`: Name of the extension (required)
- `--force`: Overwrite existing extension
- `--non-interactive`: Use default values

**Examples:**

```bash
# Interactive extension creation
serv create extension --name "User Authentication"

# Non-interactive with defaults
serv create extension --name "Blog Engine" --non-interactive

# Force overwrite existing
serv create extension --name "API Router" --force
```

**Interactive prompts:**
```
Author [Your Name]: John Doe
Description [A cool Serv extension.]: User authentication and management
Version [0.1.0]: 1.0.0
```

**Generated structure:**
```
extensions/
└── user_authentication/
    ├── __init__.py
    ├── extension.yaml
    └── user_authentication.py
```

### `serv create route`

Create a new route handler in a extension.

**Usage:**
```bash
serv create route --name NAME [--path PATH] [--router ROUTER] [--extension PLUGIN] [--force]
```

**Options:**
- `--name`: Name of the route (required)
- `--path`: URL path for the route
- `--router`: Router name to add the route to
- `--extension`: Extension to add the route to (auto-detected if not provided)
- `--force`: Overwrite existing files

**Examples:**

```bash
# Basic route creation (interactive)
serv create route --name user_profile

# Specify everything explicitly
serv create route --name user_profile \
  --path "/users/{id}/profile" \
  --router api_router \
  --extension user_management

# Create API endpoint
serv create route --name create_post \
  --path "/api/v1/posts" \
  --router api_router

# Admin route
serv create route --name admin_dashboard \
  --path "/admin/dashboard" \
  --router admin_router
```

**Interactive prompts:**
```
Route path [/user_profile]: /users/{id}/profile
Existing routers:
  1. api_router
  2. admin_router
  3. Create new router
Select router (name or number) [1]: 1
```

**Generated extension.yaml update:**
```yaml
routers:
- name: api_router
  routes:
  - path: /users/{id}/profile
    handler: route_user_profile:UserProfile
```

### `serv create listener`

Create a new extension listener class.

**Usage:**
```bash
serv create listener --name NAME [--extension PLUGIN] [--force]
```

**Examples:**

```bash
# Create listener
serv create listener --name admin_auth --extension user_management

# Auto-detect extension
serv create listener --name email_sender

# Force overwrite existing
serv create listener --name event_handler --force
```

### `serv create middleware`

Create a new middleware component.

**Usage:**
```bash
serv create middleware --name NAME [--extension PLUGIN] [--force]
```

**Examples:**

```bash
# Create middleware
serv create middleware --name auth_check --extension user_management

# Rate limiting middleware
serv create middleware --name rate_limiter --extension security
```

## Advanced Usage Patterns

### Multi-Environment Configuration

```bash
# Development
serv -c config/dev.yaml dev

# Staging
serv -c config/staging.yaml launch --host 0.0.0.0

# Production
serv -c config/prod.yaml launch --workers 4 --host 0.0.0.0
```

### Custom Application Classes

```bash
# Use custom app class
serv -a myproject.app:CustomApp launch

# With custom config
serv -a myproject.app:CustomApp -c custom.yaml dev
```

### Extension Development Workflow

```bash
# 1. Create new project (if needed)
serv create app

# 2. Create extension
serv create extension --name "My Feature"

# 3. Add listeners
serv create listener --name feature_handler

# 4. Add routes
serv create route --name feature_api --path "/api/feature" --router api_router

# 5. Add middleware
serv create middleware --name feature_auth

# 6. Validate extension
serv extension validate my_feature

# 7. Enable extension
serv extension enable my_feature

# 8. Test
serv test --extensions

# 9. Start development server
serv --dev launch
```

### Testing Workflow

```bash
# Run tests during development
serv test --verbose

# Check coverage
serv test --coverage

# Test specific components
serv test tests/test_auth.py --verbose

# Run e2e tests before deployment
serv test --e2e
```

### Configuration Management

```bash
# Check current config
serv config show

# Validate before deployment
serv config validate

# Update settings
serv config set debug.enabled false --type bool
serv config set server.workers 4 --type int

# Verify changes
serv config get debug.enabled
serv config get server.workers
```

## Troubleshooting

### Common Issues

**Configuration not found:**
```bash
# Check if config exists
serv config validate

# Create new config
serv create app
```

**Extension not loading:**
```bash
# Validate extension structure
serv extension validate my_extension

# Check if extension is enabled
serv extension list

# Enable extension
serv extension enable my_extension
```

**Application health check:**
```bash
# Check configuration
serv config validate

# Check extensions
serv extension validate

# Check if app can be loaded
serv launch --dry-run
```

### Debug Mode

Enable debug logging for detailed information:

```bash
serv --debug launch
serv --debug config validate
serv --debug extension validate
```

### Getting Help

```bash
# General help
serv --help

# Command-specific help
serv --dev launch --help
serv create route --help
serv config set --help
```

## Environment Variables

Serv CLI respects these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `SERV_CONFIG` | Default config file path | `serv.config.yaml` |
| `SERV_PLUGIN_DIRS` | Default extension directories | `./extensions` |
| `SERV_DEBUG` | Enable debug mode | `false` |

**Example:**
```bash
export SERV_CONFIG=config/production.yaml
export SERV_DEBUG=true
serv launch
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Serv Application CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    
    - name: Install dependencies
      run: |
        pip install serv
        pip install -r requirements.txt
    
    - name: Validate configuration
      run: serv config validate
    
    - name: Check application health
      run: serv app check
    
    - name: Validate extensions
      run: serv extension validate
    
    - name: Run tests with coverage
      run: serv test --coverage
    
    - name: Test application startup
      run: serv launch --dry-run
```

### Docker Integration

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .

RUN pip install serv
RUN pip install -r requirements.txt

# Validate configuration during build
RUN serv config validate
RUN serv app check

EXPOSE 8000
CMD ["serv", "launch", "--host", "0.0.0.0", "--workers", "4"]
```

This comprehensive CLI reference provides everything you need to effectively use Serv's command-line interface for development, testing, and deployment of your web applications. 