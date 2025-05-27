# Serv: Your Next-Generation ASGI Web Framework 🚀

!!! warning "Pre-Release Software"
    **Serv is currently in a pre-release state and is NOT recommended for production use at this time. APIs are subject to change.**

**Tired of boilerplate? Craving flexibility? Say hello to Serv!**

Serv is a powerful and intuitive ASGI web framework for Python, designed for ultimate extensibility while being opinionated only when necessary. It aims to make building web applications and APIs a breeze, even allowing you to construct entire sites with out-of-the-box extensions, minimizing the need to write custom code.

## ✨ Key Features

- **🚀 ASGI Native**: Built from the ground up for asynchronous Python
- **🔧 Extensible & Minimally Opinionated**: Designed for flexibility, providing guidance where it counts
- **⚡ Codeless Site Building**: Includes out-of-the-box extensions to get sites up and running quickly
- **💉 Dependency Injection**: Leverages `bevy` for clean, testable code
- **🔌 Extension Architecture**: Easily extend and customize framework behavior beyond the defaults
- **🛡️ Middleware Support**: Integrate custom processing steps into the request/response lifecycle
- **🗺️ Flexible Routing**: Define routes with ease using functions or classes
- **🚨 Comprehensive Error Handling**: Robust mechanisms for managing exceptions
- **📡 Event System**: Emit and listen to events throughout the application lifecycle

## Quick Example

Creating a Serv app is incredibly simple with the CLI! Here's how to build a "Hello World" app in under a minute:

```bash
# Create a new Serv application
serv create app

# Create a hello extension
serv create extension --name hello

# Add a route
serv create route --name hello --path /hello --extension hello

# Enable the extension
serv extension enable hello

# Launch your app
serv launch
```

That's it! Your app will be running at `http://localhost:8000/hello`

Want to add more routes? Just use the CLI:

```bash
# Add a route with path parameters
serv create route --name greet --path "/greet/{name}"
```

## Architecture Overview

Serv is built around several core concepts:

### 🏗️ Extension System
Everything in Serv is a extension. Routes, middleware, and even core functionality are implemented as extensions, making the framework incredibly modular and extensible.

### 💉 Dependency Injection
Using the `bevy` library, Serv provides powerful dependency injection capabilities that make your code clean, testable, and maintainable.

### 🔄 Event-Driven
Serv uses an event system that allows extensions to respond to application lifecycle events, enabling loose coupling between components.

### 🛣️ Flexible Routing
Support for both functional and class-based routing, with automatic parameter injection and multiple response types.

## Getting Started

Ready to dive in? Check out our comprehensive guides:

- **[Installation](getting-started/installation.md)** - Get Serv installed and ready to go
- **[Quick Start](getting-started/quick-start.md)** - Build your first app in minutes
- **[Your First App](getting-started/first-app.md)** - A detailed walkthrough of creating a complete application
- **[Configuration](getting-started/configuration.md)** - Learn how to configure Serv for your needs

## Community & Support

- **🌐 Website**: [getserv.ing](https://getserv.ing)
- **📦 PyPI Package**: [`getserving`](https://pypi.org/project/getserving/)
- **🐛 Issues**: Report bugs and request features on [GitHub](https://github.com/8ly-dev/Serv)
- **💬 Discussions**: Join the community discussions on [GitHub](https://github.com/8ly-dev/Serv/discussions)

## License

Serv is licensed under the **MIT License**. 