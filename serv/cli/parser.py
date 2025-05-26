"""
CLI argument parser.

This module contains the argument parser setup for the Serv CLI.
"""

import argparse

from serv.config import DEFAULT_CONFIG_FILE

from .commands import (
    handle_app_check_command,
    handle_app_details_command,
    handle_config_get_command,
    handle_config_set_command,
    handle_config_show_command,
    handle_config_validate_command,
    handle_create_entrypoint_command,
    handle_create_middleware_command,
    handle_create_plugin_command,
    handle_create_route_command,
    handle_dev_command,
    handle_disable_plugin_command,
    handle_enable_plugin_command,
    handle_init_command,
    handle_launch_command,
    handle_list_plugin_command,
    handle_shell_command,
    handle_test_command,
    handle_validate_plugin_command,
)


def create_parser():
    """Create and configure the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="serv", description="Command-line interface for the Serv web framework."
    )
    serv_version = "0.1.0-dev"  # Placeholder

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {serv_version}"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging for Serv CLI and potentially the app.",
    )
    parser.add_argument(
        "--app",
        "-a",
        help='Custom application CLASS in the format "module.path:ClassName". If not provided, Serv\'s default App is'
        " used.",
        default=None,  # Default is to use serv.app.App
    )
    parser.add_argument(
        "--config",
        "-c",
        help=f"Path to config file. Default: ./{DEFAULT_CONFIG_FILE} or App default.",
        default=None,  # App will handle its default if this is None
    )
    parser.add_argument(
        "--plugin-dirs",  # Name changed for consistency, was plugin_dirs before
        help="Directory to search for plugins. Default: ./plugins or App default.",
        default=None,  # App will handle its default
    )

    # Subparsers for subcommands
    subparsers = parser.add_subparsers(
        title="commands", dest="command", required=False, help="Command to execute"
    )

    # Launch parser
    launch_parser = subparsers.add_parser("launch", help="Launch the Serv application.")
    launch_parser.add_argument(
        "--host",
        help="Bind socket to this host. Default: 127.0.0.1",
        default="127.0.0.1",
    )
    launch_parser.add_argument(
        "--port",
        "-p",
        type=int,
        help="Bind socket to this port. Default: 8000",
        default=8000,
    )
    launch_parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload."
    )
    launch_parser.add_argument(
        "--workers",
        "-w",
        type=int,
        help="Number of worker processes. Defaults to 1.",
        default=1,
    )
    launch_parser.add_argument(
        "--factory",
        action="store_true",
        help="Treat APP_MODULE as an application factory string (e.g., 'module:create_app').",
    )
    launch_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and configure the app and plugins but don't start the server.",
    )
    launch_parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable development mode for the application.",
    )
    launch_parser.set_defaults(func=handle_launch_command)

    # Dev parser
    dev_parser = subparsers.add_parser(
        "dev", help="Start development server with enhanced features."
    )
    dev_parser.add_argument(
        "--host",
        help="Bind socket to this host. Default: 127.0.0.1",
        default="127.0.0.1",
    )
    dev_parser.add_argument(
        "--port",
        "-p",
        type=int,
        help="Bind socket to this port. Default: 8000",
        default=8000,
    )
    dev_parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload (enabled by default in dev mode).",
    )
    dev_parser.add_argument(
        "--workers",
        "-w",
        type=int,
        help="Number of worker processes. Defaults to 1 (reload disabled with multiple workers).",
        default=1,
    )
    dev_parser.set_defaults(func=handle_dev_command)

    # Test parser
    test_parser = subparsers.add_parser(
        "test", help="Run tests for the application and plugins."
    )
    test_parser.add_argument(
        "--plugins", action="store_true", help="Run plugin tests only"
    )
    test_parser.add_argument(
        "--e2e", action="store_true", help="Run end-to-end tests only"
    )
    test_parser.add_argument(
        "--coverage", action="store_true", help="Generate coverage report"
    )
    test_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose test output"
    )
    test_parser.add_argument(
        "test_path", nargs="?", help="Specific test file or directory to run"
    )
    test_parser.set_defaults(func=handle_test_command)

    # Shell parser
    shell_parser = subparsers.add_parser(
        "shell", help="Start interactive Python shell with app context."
    )
    shell_parser.add_argument(
        "--ipython", action="store_true", help="Use IPython if available"
    )
    shell_parser.add_argument(
        "--no-startup", action="store_true", help="Skip loading app context"
    )
    shell_parser.set_defaults(func=handle_shell_command)

    # Config commands
    config_parser = subparsers.add_parser(
        "config", help="Configuration management commands"
    )
    config_subparsers = config_parser.add_subparsers(
        title="config commands",
        dest="config_command",
        required=True,
        help="Config command to execute",
    )

    # Config show command
    config_show_parser = config_subparsers.add_parser(
        "show", help="Display current configuration"
    )
    config_show_parser.add_argument(
        "--format", choices=["yaml", "json"], default="yaml", help="Output format"
    )
    config_show_parser.set_defaults(func=handle_config_show_command)

    # Config validate command
    config_validate_parser = config_subparsers.add_parser(
        "validate", help="Validate configuration file"
    )
    config_validate_parser.set_defaults(func=handle_config_validate_command)

    # Config get command
    config_get_parser = config_subparsers.add_parser(
        "get", help="Get configuration value"
    )
    config_get_parser.add_argument(
        "key", help="Configuration key (dot notation supported)"
    )
    config_get_parser.set_defaults(func=handle_config_get_command)

    # Config set command
    config_set_parser = config_subparsers.add_parser(
        "set", help="Set configuration value"
    )
    config_set_parser.add_argument(
        "key", help="Configuration key (dot notation supported)"
    )
    config_set_parser.add_argument("value", help="Configuration value")
    config_set_parser.add_argument(
        "--type",
        choices=["string", "int", "float", "bool", "list"],
        default="string",
        help="Value type",
    )
    config_set_parser.set_defaults(func=handle_config_set_command)

    # App commands
    app_parser = subparsers.add_parser("app", help="App management commands")
    app_subparsers = app_parser.add_subparsers(
        title="app commands",
        dest="app_command",
        required=True,
        help="App command to execute",
    )

    # App init command
    app_init_parser = app_subparsers.add_parser(
        "init", help="Initialize a new Serv project"
    )
    app_init_parser.add_argument(
        "--force", action="store_true", help="Force overwrite of existing config file"
    )
    app_init_parser.add_argument(
        "--non-interactive",
        action="store_true",
        dest="non_interactive",
        help="Non-interactive mode with default values (for testing)",
    )
    app_init_parser.set_defaults(func=handle_init_command)

    # App details command
    app_details_parser = app_subparsers.add_parser(
        "details", help="Display application configuration"
    )
    app_details_parser.set_defaults(func=handle_app_details_command)

    # App check command
    app_check_parser = app_subparsers.add_parser(
        "check", help="Validate application configuration and health"
    )
    app_check_parser.add_argument(
        "--config", action="store_true", help="Check configuration file only"
    )
    app_check_parser.add_argument(
        "--plugins", action="store_true", help="Check plugins only"
    )
    app_check_parser.add_argument(
        "--routes", action="store_true", help="Check routes only"
    )
    app_check_parser.set_defaults(func=handle_app_check_command)

    # Plugin commands
    plugin_parser = subparsers.add_parser("plugin", help="Plugin management commands")
    plugin_subparsers = plugin_parser.add_subparsers(
        title="plugin commands",
        dest="plugin_command",
        required=True,
        help="Plugin command to execute",
    )

    # Plugin enable command
    plugin_enable_parser = plugin_subparsers.add_parser(
        "enable", help="Enable a plugin"
    )
    plugin_enable_parser.add_argument(
        "plugin_identifier", help="Plugin identifier (directory name or module path)"
    )
    plugin_enable_parser.set_defaults(func=handle_enable_plugin_command)

    # Plugin disable command
    plugin_disable_parser = plugin_subparsers.add_parser(
        "disable", help="Disable a plugin"
    )
    plugin_disable_parser.add_argument(
        "plugin_identifier", help="Plugin identifier (directory name or module path)"
    )
    plugin_disable_parser.set_defaults(func=handle_disable_plugin_command)

    # Plugin list command
    plugin_list_parser = plugin_subparsers.add_parser(
        "list", help="List available and enabled plugins"
    )
    plugin_list_parser.add_argument(
        "--available",
        action="store_true",
        help="Show all available plugins (default shows enabled plugins)",
    )
    plugin_list_parser.set_defaults(func=handle_list_plugin_command)

    # Plugin validate command
    plugin_validate_parser = plugin_subparsers.add_parser(
        "validate", help="Validate plugin structure and configuration"
    )
    plugin_validate_parser.add_argument(
        "plugin_identifier",
        nargs="?",
        help="Plugin identifier (directory name or module path). If not provided, validates all plugins.",
    )
    plugin_validate_parser.add_argument(
        "--all", action="store_true", help="Validate all plugins"
    )
    plugin_validate_parser.set_defaults(func=handle_validate_plugin_command)

    # Create commands
    create_parser = subparsers.add_parser(
        "create", help="Create plugins and components"
    )
    create_subparsers = create_parser.add_subparsers(
        title="create commands",
        dest="create_command",
        required=True,
        help="Item to create",
    )

    # Create plugin command
    create_plugin_parser = create_subparsers.add_parser(
        "plugin", help="Create a new plugin"
    )
    create_plugin_parser.add_argument(
        "--name", required=True, help="Name of the plugin"
    )
    create_plugin_parser.add_argument(
        "--force", action="store_true", help="Force overwrite of existing plugin"
    )
    create_plugin_parser.add_argument(
        "--non-interactive",
        action="store_true",
        dest="non_interactive",
        help="Non-interactive mode with default values (for testing)",
    )
    create_plugin_parser.set_defaults(func=handle_create_plugin_command)

    # Create entrypoint command
    create_entrypoint_parser = create_subparsers.add_parser(
        "entrypoint", help="Create a new plugin entrypoint"
    )
    create_entrypoint_parser.add_argument(
        "--name", required=True, help="Name of the entrypoint"
    )
    create_entrypoint_parser.add_argument(
        "--plugin",
        help="Plugin to add the entrypoint to (auto-detected if not provided)",
    )
    create_entrypoint_parser.add_argument(
        "--force", action="store_true", help="Force overwrite of existing files"
    )
    create_entrypoint_parser.set_defaults(func=handle_create_entrypoint_command)

    # Create route command
    create_route_parser = create_subparsers.add_parser(
        "route", help="Create a new plugin route"
    )
    create_route_parser.add_argument("--name", required=True, help="Name of the route")
    create_route_parser.add_argument(
        "--path", help="URL path for the route (e.g., /users/{id}/profile)"
    )
    create_route_parser.add_argument("--router", help="Router name to add the route to")
    create_route_parser.add_argument(
        "--plugin", help="Plugin to add the route to (auto-detected if not provided)"
    )
    create_route_parser.add_argument(
        "--force", action="store_true", help="Force overwrite of existing files"
    )
    create_route_parser.set_defaults(func=handle_create_route_command)

    # Create middleware command
    create_middleware_parser = create_subparsers.add_parser(
        "middleware", help="Create a new plugin middleware"
    )
    create_middleware_parser.add_argument(
        "--name", required=True, help="Name of the middleware"
    )
    create_middleware_parser.add_argument(
        "--plugin",
        help="Plugin to add the middleware to (auto-detected if not provided)",
    )
    create_middleware_parser.add_argument(
        "--force", action="store_true", help="Force overwrite of existing files"
    )
    create_middleware_parser.set_defaults(func=handle_create_middleware_command)

    return parser, launch_parser
