"""
Main CLI entry point.

This module contains the main function that orchestrates the CLI execution.
"""

import asyncio
import logging
import os
import sys

from .commands import handle_launch_command
from .parser import create_parser

# Logging setup
logger = logging.getLogger("serv")
if not logger.hasHandlers():
    handler = logging.StreamHandler(sys.stdout)
    # Basic format, can be overridden by app's own logging config
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    if os.getenv("SERV_DEBUG"):  # More verbose if SERV_DEBUG is set
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        )
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def main():
    """Main CLI entry point."""
    parser, launch_parser = create_parser()

    # Process args
    args_ns = parser.parse_args()

    if args_ns.debug or os.getenv("SERV_DEBUG"):
        os.environ["SERV_DEBUG"] = "1"
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")

    # Enable debug logging automatically in dev mode
    if hasattr(args_ns, "dev") and args_ns.dev:
        os.environ["SERV_DEBUG"] = "1"
        logger.setLevel(logging.DEBUG)
        logger.debug("Development mode enabled - debug logging activated.")

    current_args_to_use = args_ns

    if not hasattr(args_ns, "command") or args_ns.command is None:
        # No command specified, default to 'launch'
        non_command_cli_args = sys.argv[1:]
        logger.debug(
            f"No command specified. Defaulting to 'launch'. Using CLI args: {non_command_cli_args}"
        )
        try:
            launch_specific_args = launch_parser.parse_args(non_command_cli_args)
            # Propagate global arguments to launch command
            for global_arg_name in ["debug", "dev", "app", "config", "extension_dirs"]:
                if hasattr(args_ns, global_arg_name):
                    setattr(
                        launch_specific_args,
                        global_arg_name,
                        getattr(args_ns, global_arg_name),
                    )
            current_args_to_use = launch_specific_args
            current_args_to_use.func = handle_launch_command  # Ensure func is set
        except SystemExit:
            # If there's a parsing error, let's use the original args to show help
            parser.print_help()
            sys.exit(1)
    else:
        # Command was specified, propagate global --dev flag to the command's args
        if hasattr(args_ns, "dev") and args_ns.dev:
            current_args_to_use.dev = True

    if hasattr(current_args_to_use, "func"):
        # Use async if the handler is async
        handler = current_args_to_use.func
        if asyncio.iscoroutinefunction(handler):
            try:
                asyncio.run(handler(current_args_to_use))
            except KeyboardInterrupt:
                # Handle Ctrl+C gracefully
                print("\n🛑 Server stopped by user")
                sys.exit(0)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                sys.exit(1)
        else:
            try:
                handler(current_args_to_use)
            except KeyboardInterrupt:
                print("\n🛑 Operation stopped by user")
                sys.exit(0)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                sys.exit(1)
    else:
        # No command found, show help
        parser.print_help()


if __name__ == "__main__":
    main()
