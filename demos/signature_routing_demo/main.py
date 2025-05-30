#!/usr/bin/env python3
"""
Signature-Based Routing Demo

This demo showcases Serv's signature-based routing system using the modern
`serv launch` command with autoloaded extensions.

To run this demo:
    python main.py

Or directly with serv:
    serv launch

The demo showcases:
- Multiple handlers per HTTP method
- Parameter injection (Query, Header, Cookie)
- Authentication-based handler selection
- Form handling with automatic matching
- Handler scoring and selection

Visit http://127.0.0.1:8000/ after starting to see the demo!
"""

import os
import subprocess
import sys


def main():
    """Launch the signature routing demo using serv launch command"""
    print("🚀 Starting Serv Signature-Based Routing Demo")
    print("📍 Demo will be available at: http://127.0.0.1:8000/")
    print()
    print("✨ Features demonstrated:")
    print("  - Multiple GET handlers based on query parameters")
    print("  - Authentication-based handler selection")
    print("  - Automatic form matching and processing")
    print("  - Parameter injection (Query, Header, Cookie)")
    print()
    print("🔧 Using 'serv launch' with autoloaded extensions")
    print("📁 Extensions loaded from: ./extensions/")
    print()

    try:
        # Change to the demo directory
        demo_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(demo_dir)

        # Launch using serv command
        result = subprocess.run([sys.executable, "-m", "serv", "launch"], check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running serv launch: {e}")
        return e.returncode
    except FileNotFoundError:
        print("❌ Could not find 'serv' command. Make sure Serv is installed:")
        print("   pip install -e .")
        return 1
    except KeyboardInterrupt:
        print("\n👋 Demo stopped by user")
        return 0


if __name__ == "__main__":
    sys.exit(main())
