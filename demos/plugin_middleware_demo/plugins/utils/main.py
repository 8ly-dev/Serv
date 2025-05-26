"""
Utility plugin for Serv demo
"""

import time

from serv.plugins import Plugin


class Utils(Plugin):
    """
    A utility plugin that provides shared functionality for other plugins
    """

    def __init__(self):
        """Initialize the utilities plugin."""
        self.start_time = time.time()

    def on_app_startup(self, app):
        """
        Called when the app starts up.

        Args:
            app: The Serv application instance
        """
        print("Utils plugin loaded!")

    def get_uptime(self) -> float:
        """Get the application uptime in seconds."""
        return time.time() - self.start_time

    def format_uptime(self) -> str:
        """Format the uptime as a human-readable string."""
        uptime = self.get_uptime()
        minutes, seconds = divmod(uptime, 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        elif minutes > 0:
            return f"{int(minutes)}m {int(seconds)}s"
        else:
            return f"{int(seconds)}s"
