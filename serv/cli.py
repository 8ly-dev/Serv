"""
Serv CLI - Legacy entry point.

This module provides backward compatibility by importing the main function
from the new modular CLI structure.
"""

from serv.cli.main import main

# For backward compatibility, expose the main function directly
__all__ = ["main"]

if __name__ == "__main__":
    main()
