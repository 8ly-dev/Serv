# CLI Reference

The Serv CLI provides a comprehensive set of commands for managing your web applications, plugins, and development workflow. This reference covers all available commands with detailed examples and usage patterns.

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
| `--app`, `-a` | Custom application class | `serv -a myapp.core:CustomApp launch` |
| `--config`, `-c` | Path to config file | `serv -c config/prod.yaml launch` |
| `--plugin-dirs` | Plugin directory path | `serv --plugin-dirs ./custom-plugins launch` |

## Application Management

## Development Server

### `serv launch`

Launch the production Serv application server.

**Usage:**
```bash
serv launch [--host HOST] [--port PORT] [--reload] [--workers N] [--factory] [--dry-run] [--dev]
```

**Options:**
- `--host`: Bind socket to this host (default: 127.0.0.1)
- `--port`, `-p`: Bind socket to this port (default: 8000)
- `--reload`: Enable auto-reload
- `--workers`, `-w`: Number of worker processes (default: 1)
- `--factory`: Treat app as factory function
- `--dry-run`: Load app but don't start server
- `--dev`: Enable development mode

**Examples:**

```bash
# Basic launch
serv launch

# Custom host and port
serv launch --host 0.0.0.0 --port 3000

# Production with multiple workers
serv launch --workers 4 --host 0.0.0.0 --port 8000

# Development mode with auto-reload
serv launch --dev --reload

# Dry run to test configuration
serv launch --dry-run
```

### `serv dev`

Start an enhanced development server with debugging features.

**Usage:**
```bash
serv dev [--host HOST] [--port PORT] [--no-reload] [--workers N]
```

**Options:**
- `--host`: Bind socket to this host (default: 127.0.0.1)
- `--port`, `-p`: Bind socket to this port (default: 8000)
- `--no-reload`: Disable auto-reload (enabled by default)
- `--workers`, `-w`: Number of worker processes (default: 1)

**Examples:**

```bash
# Start development server
serv dev

# Custom port with auto-reload
serv dev --port 3000

# Disable auto-reload
serv dev --no-reload

# Development server on all interfaces
serv dev --host 0.0.0.0
```

**Development features:**
- 🔄 Auto-reload enabled by default
- 📝 Enhanced error reporting
- 🐛 Debug logging
- ⚡ Fast restart on file changes

## Testing

### `serv test`

Run tests for your application and plugins.

**Usage:**
```bash
serv test [--plugins] [--e2e] [--coverage] [--verbose] [test_path]
```

**Options:**
- `--plugins`: Run plugin tests only
- `--e2e`: Run end-to-end tests only
- `--coverage`: Generate coverage report
- `--verbose`, `-v`: Verbose test output
- `test_path`: Specific test file or directory

**Examples:**

```bash
# Run all tests
serv test

# Run only plugin tests
serv test --plugins

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
plugins/auth.py        23      0   100%
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
- `plugins`: List of loaded plugins
- `Path`: pathlib.Path class
- `yaml`: PyYAML module

**Example session:**
```python
🐍 Starting interactive Python shell...
📦 Loading Serv app context...
🔌 Loaded 3 plugins into context
✅ App context loaded successfully
Available objects: app, serv, plugins, Path, yaml

>>> app.site_info
{'name': 'My Awesome Website', 'description': 'A modern web application'}
>>> len(plugins)
3
>>> plugins[0].name
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
plugins:
- plugin: user_management
- plugin: api_router
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
✅ Has required field: plugins
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

# Get first plugin
serv config get plugins.0.plugin

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

## Plugin Management

### `serv plugin list`

List available and enabled plugins.

**Usage:**
```bash
serv plugin list [--available]
```

**Options:**
- `--available`: Show all available plugins (default shows enabled)

**Examples:**

```bash
# List enabled plugins
serv plugin list

# List all available plugins
serv plugin list --available
```

**Example output:**
```
Enabled plugins (2):
  • User Management (v1.0.0) [user_management]
  • API Router (v2.1.0) [api_router] (with config)

Available plugins (4):
  • User Management (v1.0.0) [user_management]
    User authentication and management system
  • API Router (v2.1.0) [api_router]
    RESTful API routing and middleware
  • Blog Engine (v1.5.0) [blog_engine]
    Simple blog functionality
  • Admin Panel (v0.9.0) [admin_panel]
    Administrative interface
```

### `serv plugin enable`

Enable a plugin in your application.

**Usage:**
```bash
serv plugin enable <plugin_identifier>
```

**Examples:**

```bash
# Enable by directory name
serv plugin enable user_management

# Enable plugin with different name
serv plugin enable blog_engine
```

**Example output:**
```
Plugin 'user_management' enabled successfully.
Human name: User Management
```

### `serv plugin disable`

Disable a plugin in your application.

**Usage:**
```bash
serv plugin disable <plugin_identifier>
```

**Examples:**

```bash
# Disable by directory name
serv plugin disable user_management

# Disable plugin with different name
serv plugin disable blog_engine
```

### `serv plugin validate`

Validate plugin structure and configuration.

**Usage:**
```bash
serv plugin validate [plugin_identifier] [--all]
```

**Options:**
- `--all`: Validate all plugins

**Examples:**

```bash
# Validate all plugins
serv plugin validate

# Validate specific plugin
serv plugin validate user_management

# Explicitly validate all
serv plugin validate --all
```

**Example output:**
```
=== Validating 2 Plugin(s) ===

🔍 Validating plugin: user_management
✅ plugin.yaml is valid YAML
✅ Has required field: name
✅ Has required field: version
✅ Has recommended field: description
✅ Has recommended field: author
✅ Has __init__.py
✅ Found 3 Python file(s)
✅ Has main plugin file: user_management.py
✅ user_management.py has valid Python syntax
🎉 Plugin 'user_management' validation passed!

=== Validation Summary ===
🎉 All plugins passed validation!
```

## Project and Plugin Development

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

### `serv create plugin`

Create a new plugin with proper structure.

**Usage:**
```bash
serv create plugin --name NAME [--force] [--non-interactive]
```

**Options:**
- `--name`: Name of the plugin (required)
- `--force`: Overwrite existing plugin
- `--non-interactive`: Use default values

**Examples:**

```bash
# Interactive plugin creation
serv create plugin --name "User Authentication"

# Non-interactive with defaults
serv create plugin --name "Blog Engine" --non-interactive

# Force overwrite existing
serv create plugin --name "API Router" --force
```

**Interactive prompts:**
```
Author [Your Name]: John Doe
Description [A cool Serv plugin.]: User authentication and management
Version [0.1.0]: 1.0.0
```

**Generated structure:**
```
plugins/
└── user_authentication/
    ├── __init__.py
    ├── plugin.yaml
    └── user_authentication.py
```

### `serv create route`

Create a new route handler in a plugin.

**Usage:**
```bash
serv create route --name NAME [--path PATH] [--router ROUTER] [--plugin PLUGIN] [--force]
```

**Options:**
- `--name`: Name of the route (required)
- `--path`: URL path for the route
- `--router`: Router name to add the route to
- `--plugin`: Plugin to add the route to (auto-detected if not provided)
- `--force`: Overwrite existing files

**Examples:**

```bash
# Basic route creation (interactive)
serv create route --name user_profile

# Specify everything explicitly
serv create route --name user_profile \
  --path "/users/{id}/profile" \
  --router api_router \
  --plugin user_management

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

**Generated plugin.yaml update:**
```yaml
routers:
- name: api_router
  routes:
  - path: /users/{id}/profile
    handler: route_user_profile:UserProfile
```

### `serv create entrypoint`

Create a new plugin entrypoint.

**Usage:**
```bash
serv create entrypoint --name NAME [--plugin PLUGIN] [--force]
```

**Examples:**

```bash
# Create entrypoint
serv create entrypoint --name admin_auth --plugin user_management

# Auto-detect plugin
serv create entrypoint --name email_sender
```

### `serv create middleware`

Create a new middleware component.

**Usage:**
```bash
serv create middleware --name NAME [--plugin PLUGIN] [--force]
```

**Examples:**

```bash
# Create middleware
serv create middleware --name auth_check --plugin user_management

# Rate limiting middleware
serv create middleware --name rate_limiter --plugin security
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

### Plugin Development Workflow

```bash
# 1. Create new project (if needed)
serv create app

# 2. Create plugin
serv create plugin --name "My Feature"

# 3. Add routes
serv create route --name feature_api --path "/api/feature" --router api_router

# 4. Add middleware
serv create middleware --name feature_auth

# 5. Validate plugin
serv plugin validate my_feature

# 6. Enable plugin
serv plugin enable my_feature

# 7. Test
serv test --plugins

# 8. Start development server
serv dev
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

**Plugin not loading:**
```bash
# Validate plugin structure
serv plugin validate my_plugin

# Check if plugin is enabled
serv plugin list

# Enable plugin
serv plugin enable my_plugin
```

**Application health check:**
```bash
# Check configuration
serv config validate

# Check plugins
serv plugin validate

# Check if app can be loaded
serv launch --dry-run
```

### Debug Mode

Enable debug logging for detailed information:

```bash
serv --debug dev
serv --debug config validate
serv --debug plugin validate
```

### Getting Help

```bash
# General help
serv --help

# Command-specific help
serv dev --help
serv create route --help
serv config set --help
```

## Environment Variables

Serv CLI respects these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `SERV_CONFIG` | Default config file path | `serv.config.yaml` |
| `SERV_PLUGIN_DIRS` | Default plugin directories | `./plugins` |
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
    
    - name: Validate plugins
      run: serv plugin validate
    
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