# Plugin and Middleware Demo

This demo shows how to use the plugin and middleware loader features of Serv.

## Features

- Demonstrates loading plugins from custom directories via `serv.config.yaml`.
- Shows how to load middleware from custom directories via `serv.config.yaml`.
- Includes a simple authentication plugin, a utility plugin, and a routes plugin.
- Includes a request logging middleware.
- Demonstrates configuration through `serv.config.yaml`.

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
│   │   └── plugin.yaml   # Plugin metadata (Note: serv.config.yaml is primary for loading)
│   ├── routes/           # Routes plugin
│   │   ├── __init__.py
│   │   ├── main.py       # Plugin implementation
│   │   └── plugin.yaml   # Plugin metadata
│   └── utils/            # Utility plugin
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
```

Then visit http://localhost:8000 in your browser.

**IMPORTANT NOTE:** As of the last check, this demo **does not run correctly** due to an issue in how `serv.app.App` currently loads plugins specified in `serv.config.yaml`. The `App._load_plugin_from_config` method incorrectly uses `Importer` with full module paths (e.g., `plugins.auth.main`) instead of simple package names. `Importer` is designed for discovery within a directory, while full paths should typically be handled by direct import mechanisms (like `import_from_string`). This results in plugins failing to load.

Additionally, the `plugins/auth/main.py:Auth` plugin uses a `configure(self, config)` method. The current `App` plugin loading mechanism primarily looks for `__init__(self, config=...)` or a `load_config(self, config)` method to pass configuration, so the `configure` method might not be called as intended.

If these issues in `serv.app.App` are resolved, the demo should showcase the intended plugin and middleware loading from configuration.

## API Endpoints (Intended)

- `GET /` - Main demo page
- `GET /info` - Returns JSON information about the application
- `GET /protected` - Protected route requiring authentication

To test the protected route with authentication (assuming the auth plugin loads and works):

```bash
curl -H "Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=" http://localhost:8000/protected
# (The base64 string is "admin:password123")
```

## How It Works (Intended Design)

The application is structured as a set of plugins and middleware.
All functionality is contained in the `plugins/` and `middleware/` directories.

The `serv.config.yaml` file specifies which plugins and middleware to load:

```yaml
plugins:
  - entry: plugins.auth.main:Auth
    config:
      enabled: true
      users:
        admin: "password123"
  - entry: plugins.utils.main:Utils
  - entry: plugins.routes.main:Routes

middleware:
  - entry: middleware.logging.main:request_logger_middleware
    config:
      level: "DEBUG"
```

When `serv launch` is run (and if `App` loads plugins correctly):

1.  A Serv `App` instance is created.
2.  It loads configuration from `serv.config.yaml` (because `serv launch` is run from this demo's directory).
3.  It attempts to load and configure all plugins and middleware specified in `serv.config.yaml`.
4.  Routes defined in `plugins.routes.main:Routes` would become active.
5.  Middleware like `request_logger_middleware` would process requests.
6.  The server starts, serving the application.

This demonstrates a modular organization where functionality is provided by plugins and middleware managed via external configuration. 