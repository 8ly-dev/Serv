"""
Authentication plugin for Serv demo
"""

from typing import Any

from bevy import dependency

from serv.extensions import Listener
from serv.requests import Request
from serv.responses import ResponseBuilder


class Auth(Listener):
    """
    A basic authentication plugin for Serv.
    """

    def __init__(self):
        """Initialize the auth plugin."""
        self.users = {}
        self.enabled = True

    def configure(self, config: dict[str, Any]) -> None:
        """
        Configure the plugin with the provided configuration.

        Args:
            config: Extension configuration dictionary
        """
        self.users = config.get("users", {})
        self.enabled = config.get("enabled", True)

    def on_app_startup(self, app):
        """
        Called when the app starts up.

        Args:
            app: The Serv application instance
        """
        print("Auth plugin loaded!")

    async def on_request(
        self, request: Request = dependency(), response: ResponseBuilder = dependency()
    ):
        """
        Called for each request to check authentication.

        Args:
            request: The request object
            response: The response builder
        """
        if not self.enabled:
            return

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            return

        # In a real implementation, this would decode the Basic auth header
        # and check against the users dictionary
        print(f"Auth plugin checking request to {request.path}")
