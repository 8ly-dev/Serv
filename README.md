# Serv: Your Next-Generation ASGI Web Framework 🚀

> [!WARNING]
> **Serv is currently in a pre-release state and is NOT recommended for production use at this time. APIs are subject to change.**

**Tired of boilerplate? Craving flexibility? Say hello to Serv!**

Serv is a powerful and intuitive ASGI web framework for Python, designed for ultimate extensibility while being opinionated only when necessary. It aims to make building web applications and APIs a breeze, even allowing you to construct entire sites with out-of-the-box plugins, minimizing the need to write custom code. With its modern architecture, first-class support for dependency injection, and a flexible plugin system, Serv empowers you to focus on your application's unique logic, not the plumbing.

## ✨ Features

*   **ASGI Native:** Built from the ground up for asynchronous Python.
*   **Extensible & Minimally Opinionated:** Designed for flexibility, providing guidance where it counts.
*   **Codeless Site Building:** Includes out-of-the-box plugins to get sites up and running quickly.
*   **Dependency Injection:** Leverages `bevy` for clean, testable code.
*   **Plugin Architecture:** Easily extend and customize framework behavior beyond the defaults.
*   **Middleware Support:** Integrate custom processing steps into the request/response lifecycle.
*   **Flexible Routing:** Define routes with ease.
*   **Comprehensive Error Handling:** Robust mechanisms for managing exceptions.
*   **Event System:** Emit and listen to events throughout the application lifecycle.

## 🔌 Plugin and Middleware System

Serv provides a robust plugin and middleware loader that makes extending your application easy:

### Configuration Layers

Serv uses a two-layer configuration approach:

1. **Application Configuration (`serv.config.yaml`)**: Defines which plugins are enabled and can override plugin settings.
2. **Plugin Configuration (`plugin.yaml`)**: Defines plugin metadata, entry points, middleware, and default settings.

### Plugin Structure

Plugins in Serv are packages that should have the following structure:

```
plugins/
  plugin_name/
    __init__.py
    main.py  # Contains your Plugin subclass
    plugin.yaml  # Metadata and configuration for your plugin
```

The `plugin.yaml` file should contain:

```yaml
name: My Plugin Name
description: What my plugin does
version: 0.1.0
author: Your Name
entry: plugin_name.main:PluginClass  # Main plugin entry point

# Default settings for the plugin
settings:
  option1: default_value
  option2: default_value

# Additional entry points provided by this plugin
entry_points:
  - entry: plugin_name.submodule:AnotherPluginClass
    config:
      ep_option: value

# Middleware provided by this plugin
middleware:
  - entry: plugin_name.middleware:MyMiddleware
    config:
      mw_option: value
```

The application's `serv.config.yaml` then enables plugins and can override settings:

```yaml
plugins:
  - plugin: my_plugin  # Directory name in plugins directory
    settings:  # Optional settings override
      option1: override_value
  - plugin: another.module.path  # Dot notation for module path
```

Import paths in `plugin.yaml` are relative to the plugin directory, so a file at the root of the plugin would be referenced as `file:Thing`, while a file in a subdirectory would be referenced as `directory.file:Thing`.

### Middleware Structure

Middleware in Serv follows a similar structure:

```
middleware/
  middleware_name/
    __init__.py
    main.py  # Contains your middleware factory function
```

Middleware are async iterators but using the `ServMiddleware` type abstracts that away making it much simpler to implement.

```python
class MyMiddleware(ServMiddleware):
    async def enter(self):
        # Code to run before request processing
        pass
        
    async def leave(self):
        # Code to run after request processing
        pass
        
    async def on_error(self, exc):
        # Code to run on error
        pass
```

### Loading Plugins and Middleware

You can specify plugin directories using the CLI:

```
python -m serv launch --plugin-dirs ./plugins --config ./serv.config.yaml
```

Or programmatically:

```python
from serv.app import App

# Create an app with custom plugin directory and config
app = App(
    config='./serv.config.yaml',
    plugin_dir='./plugins'
)
```

##  Quick Start

*(Coming Soon)*

## 🛠 Installation

*(Coming Soon)*

## 🚀 Usage

*(Coming Soon)*

## 🤝 Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request.

## 📄 License

Serv is licensed under the **MIT License**.
# Test comment for pre-commit
