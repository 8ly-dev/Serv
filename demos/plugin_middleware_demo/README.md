# Plugin and Middleware Demo

This demo shows how to use the plugin and middleware loader features of Serv.

## Features

- Demonstrates loading plugins from custom directories
- Shows how to load middleware from custom directories
- Includes a simple authentication plugin
- Includes a request logging middleware
- Demonstrates configuration through serv.config.yaml

## Directory Structure

```
plugin_middleware_demo/
├── README.md             # This file
├── serv.config.yaml      # Configuration file
├── plugins/              # Plugin directory
│   ├── __init__.py
│   ├── auth/             # Authentication plugin
│   │   ├── __init__.py
│   │   ├── main.py       # Plugin implementation
│   │   └── plugin.yaml   # Plugin metadata
│   └── routes/           # Routes plugin
│       ├── __init__.py
│       ├── main.py       # Plugin implementation
│       └── plugin.yaml   # Plugin metadata
└── middleware/           # Middleware directory
    ├── __init__.py
    └── logging/          # Logging middleware
        ├── __init__.py
        └── main.py       # Middleware implementation
```

## Running the Demo

From the project root directory:

```bash
# Navigate to the demo directory
cd demos/plugin_middleware_demo

# Run the demo with serv launch
serv launch

# Or, to validate without actually starting the server
serv launch --validate-only
```

Then visit http://localhost:8000 in your browser.

## API Endpoints

- `GET /` - Main demo page
- `GET /info` - Returns JSON information about the application
- `GET /protected` - Protected route requiring authentication

To test the protected route with authentication:

```bash
curl -H "Authorization: Basic dXNlcjpwYXNz" http://localhost:8000/protected
```

## How It Works

The application is structured as a set of plugins and middleware without any application code in the root directory. All the functionality is contained in the plugins and middleware directories.

The serv.config.yaml file specifies which plugins and middleware to load:

```yaml
plugins:
  - entry: plugins.auth.main:Auth
    config:
      enabled: true
      users:
        admin: "password123"  # In a real app, this would be hashed

  - entry: plugins.routes.main:Routes
    config: {}

middleware:
  - entry: middleware.logging.main:request_logger_middleware
    config:
      level: "DEBUG"
      log_headers: true
```

When you run `serv launch`, it:

1. Creates a Serv application
2. Loads the configuration from serv.config.yaml
3. Sets up the router
4. Loads all the plugins and middleware specified in the config
5. Starts the server

This demonstrates a clean, modular organization where all functionality is contained in plugins and middleware. 