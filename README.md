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

### Plugin Structure

Plugins in Serv are packages that should have the following structure:

```
plugins/
  plugin_name/
    __init__.py
    main.py  # Contains your Plugin subclass
    plugin.yaml  # Metadata about your plugin
```

The `plugin.yaml` file should contain:

```yaml
name: My Plugin Name
description: What my plugin does
version: 0.1.0
author: Your Name
entry: plugins.plugin_name.main:PluginClass
```

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

You can specify plugin and middleware directories using the CLI:

```
python -m serv launch --plugin-dirs ./plugins,./custom_plugins --middleware-dirs ./middleware,./custom_middleware
```

Or programmatically:

```python
from serv.app import App
from serv.loader import ServLoader

# Create an app with custom plugin/middleware directories
app = App(
    plugin_dirs=['./plugins', './custom_plugins'],
    middleware_dirs=['./middleware', './custom_middleware']
)

# Load all available plugins and middleware
app.load_plugins()
app.load_middleware_packages()

# Or load specific ones
app.load_plugin('auth', namespace='plugins')
app.load_middleware('logging', namespace='middleware')
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
