#!/usr/bin/env python
"""CLI entry point for Serving framework."""

import argparse
import sys
import subprocess
import os
from serving.serv import ConfigurationError, Serv


def main():
    """Main CLI entry point for serving."""
    # Check if uvicorn is installed
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed.", file=sys.stderr)
        print("\nTo use the 'serv' command, install Serving with the server extra:", file=sys.stderr)
        print("  pip install serving[server]", file=sys.stderr)
        print("\nOr install uvicorn separately:", file=sys.stderr)
        print("  pip install uvicorn", file=sys.stderr)
        sys.exit(1)
    
    parser = argparse.ArgumentParser(
        description='Serving ASGI Framework CLI',
        usage='serv [options]',
        add_help=False  # We'll handle help manually to pass through uvicorn's help
    )
    
    # Serving-specific arguments
    parser.add_argument('-d', '--working-directory', dest='working_directory',
                        help='Working directory where config files are located')
    parser.add_argument('-e', '--env', dest='environment',
                        help='Environment name (e.g., dev, prod)')
    parser.add_argument('-h', '--help', action='store_true',
                        help='Show this help message')
    
    # Parse only known args, rest will be passed to uvicorn
    args, uvicorn_args = parser.parse_known_args()
    
    # Handle help
    if args.help:
        parser.print_help()
        print("\nAdditional options are passed to uvicorn. Run 'uvicorn --help' for more options.")
        sys.exit(0)

    # Validate that Serving config exists
    try:
        Serv.get_config_path(args.working_directory, args.environment)
    except ConfigurationError as e:
        print("SERVING CONFIG NOT FOUND")
        print()
        print(
            f"{e.config_filename} could not be found in {e.working_directory}. Please check that the working "
            f"directory and environment are set correctly."
        )
        sys.exit(1)
    
    # Build uvicorn command - always use serving.app:app
    cmd = ['uvicorn', 'serving.app:app']
    
    # Set environment variables for Serving to read
    env = os.environ.copy()
    
    if args.working_directory:
        # Change to the working directory so config files can be found
        os.chdir(args.working_directory)
    
    if args.environment:
        # Pass environment as env variable that the app will read
        env['SERV_ENVIRONMENT'] = args.environment
    
    # Add any additional uvicorn arguments
    cmd.extend(uvicorn_args)
    
    # If no host/port specified, add defaults
    if '--host' not in uvicorn_args and '-h' not in uvicorn_args:
        cmd.extend(['--host', '127.0.0.1'])
    if '--port' not in uvicorn_args and '-p' not in uvicorn_args:
        cmd.extend(['--port', '8000'])
    
    # Run uvicorn with the constructed command
    try:
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    main()