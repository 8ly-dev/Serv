"""
CLI argument parser.

This module contains the argument parser setup for the Serv CLI.
"""

import argparse

from serv.config import DEFAULT_CONFIG_FILE

from .commands import (
    handle_app_details_command,
    handle_create_plugin_command,
    handle_disable_plugin_command,
    handle_enable_plugin_command,
    handle_init_command,
    handle_launch_command,
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

    # Plugin commands
    plugin_parser = subparsers.add_parser("plugin", help="Plugin management commands")
    plugin_subparsers = plugin_parser.add_subparsers(
        title="plugin commands",
        dest="plugin_command",
        required=True,
        help="Plugin command to execute",
    )

    # Plugin create command
    plugin_create_parser = plugin_subparsers.add_parser(
        "create", help="Create a new plugin"
    )
    plugin_create_parser.add_argument(
        "--force", action="store_true", help="Force overwrite of existing plugin"
    )
    plugin_create_parser.add_argument(
        "--non-interactive",
        action="store_true",
        dest="non_interactive",
        help="Non-interactive mode with default values (for testing)",
    )
    plugin_create_parser.set_defaults(func=handle_create_plugin_command)

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

    return parser, launch_parser
