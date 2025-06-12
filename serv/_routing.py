"""Legacy routing exports for backward compatibility.

All routing functionality has been moved to serv.routing.router.
This module provides re-exports for backward compatibility.
"""

# Import from new router module and exceptions
from serv.routing.router import Router, RouteSettings, get_current_router
from serv.exceptions import HTTPNotFoundException

# Re-export for backward compatibility
__all__ = ["Router", "RouteSettings", "get_current_router", "HTTPNotFoundException"]