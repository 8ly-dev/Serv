"""
Routes plugin for Serv demo
"""

from bevy import dependency

# Import from the main module of the utils plugin
from plugins.utils.main import Utils
from serv.plugins import Plugin
from serv.responses import ResponseBuilder
from serv.routing import Router


class Routes(Plugin):
    """
    Plugin that sets up the routes for the demo application
    """

    def __init__(self):
        """Initialize the routes plugin."""
        self.utils = None

    def on_app_startup(self, app):
        """
        Set up the routes when the app starts up.

        Args:
            app: The Serv application instance
        """
        # Get the router
        router = app._container.get(Router)

        # Find the utils plugin instance from the loaded plugins
        for plugin in app._plugins:
            if isinstance(plugin, Utils):
                self.utils = plugin
                break

        if not self.utils:
            print(
                "Warning: Utils plugin not found. Uptime information will not be available."
            )

        # Register routes
        router.add_route("/", self.handle_index)
        router.add_route("/info", self.handle_info)
        router.add_route("/protected", self.handle_protected)
        router.add_route("/uptime", self.handle_uptime)

        print("Routes plugin loaded!")

    async def handle_index(
        self, request: Request = dependency(), response: ResponseBuilder = dependency()
    ):
        """Handle the index route."""
        uptime_info = (
            f"Server uptime: {self.utils.format_uptime()}"
            if self.utils
            else "Server uptime: Not available"
        )

        response.content_type("text/html")
        response.body(f"""
        <html>
            <head>
                <title>Serv Plugin and Middleware Demo</title>
                <style>
                    body {{
                        font-family: system-ui, sans-serif;
                        max-width: 800px;
                        margin: 20px auto;
                        padding: 20px;
                        line-height: 1.6;
                        color: #333;
                    }}
                    h1 {{
                        color: #0066cc;
                        border-bottom: 2px solid #eee;
                        padding-bottom: 10px;
                    }}
                    h2 {{
                        color: #0066cc;
                        margin-top: 30px;
                    }}
                    .card {{
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        padding: 20px;
                        margin: 20px 0;
                        background-color: #f9f9f9;
                    }}
                    code {{
                        background-color: #f0f0f0;
                        padding: 2px 4px;
                        border-radius: 4px;
                        font-family: monospace;
                    }}
                    .route {{
                        background-color: #e9f7fe;
                        border-left: 4px solid #0066cc;
                        padding: 10px 15px;
                        margin: 10px 0;
                    }}
                    .uptime-info {{
                        background-color: #f0f8ff;
                        padding: 10px;
                        border-radius: 4px;
                        margin: 20px 0;
                        text-align: center;
                        font-weight: bold;
                    }}
                </style>
            </head>
            <body>
                <h1>Serv Plugin and Middleware Demo</h1>

                <div class="uptime-info">
                    {uptime_info}
                </div>

                <p>This demo shows how to use plugins and middleware with Serv.</p>

                <div class="card">
                    <h2>Active Plugins</h2>
                    <p>The Authentication Plugin is active and will log all requests with an Authorization header.</p>
                    <p>Try making a request with <code>curl -H "Authorization: Basic dXNlcjpwYXNz" http://localhost:8000/</code></p>
                </div>

                <div class="card">
                    <h2>Plugin Imports</h2>
                    <p>This demo shows how one plugin can import another:</p>
                    <ul>
                        <li>The <strong>Routes Plugin</strong> imports and uses the <strong>Utils Plugin</strong></li>
                        <li>The Utils Plugin provides uptime information that the Routes Plugin displays</li>
                    </ul>
                </div>

                <div class="card">
                    <h2>Active Middleware</h2>
                    <p>The Request Logger middleware is active and will log all requests and responses.</p>
                    <p>Check your console to see the logs for each request.</p>
                </div>

                <div class="card">
                    <h2>Available Routes</h2>
                    <div class="route"><strong>GET /</strong> - This page</div>
                    <div class="route"><strong>GET /info</strong> - API endpoint that returns information about the application</div>
                    <div class="route"><strong>GET /protected</strong> - Route that requires authentication</div>
                    <div class="route"><strong>GET /uptime</strong> - Shows the current server uptime</div>
                </div>
            </body>
        </html>
        """)

    async def handle_info(
        self, request: Request = dependency(), response: ResponseBuilder = dependency()
    ):
        """Handle the info route."""
        uptime = self.utils.format_uptime() if self.utils else "Not available"

        response.content_type("application/json")
        response.body(f"""
        {{
            "name": "Plugin and Middleware Demo",
            "version": "0.1.0",
            "uptime": "{uptime}",
            "plugins": ["Authentication Plugin", "Utils Plugin", "Routes Plugin"],
            "middleware": ["Request Logger"],
            "routes": ["/", "/info", "/protected", "/uptime"]
        }}
        """)

    async def handle_protected(
        self, request: Request = dependency(), response: ResponseBuilder = dependency()
    ):
        """Handle the protected route."""
        if not request.headers.get("Authorization"):
            response.set_status(401)
            response.add_header("WWW-Authenticate", "Basic")
            response.content_type("text/plain")
            response.body("Authentication required")
            return

        # In a real app, we would verify the credentials here
        # For demo purposes, we'll just accept any Authorization header

        response.content_type("application/json")
        response.body("""
        {
            "message": "This is protected content",
            "status": "authenticated"
        }
        """)

    async def handle_uptime(
        self, request: Request = dependency(), response: ResponseBuilder = dependency()
    ):
        """Handle the uptime route."""
        if not self.utils:
            response.set_status(500)
            response.content_type("text/plain")
            response.body("Utils plugin not available")
            return

        uptime_sec = self.utils.get_uptime()
        uptime_formatted = self.utils.format_uptime()

        response.content_type("application/json")
        response.body(f"""
        {{
            "uptime_seconds": {uptime_sec:.1f},
            "uptime_formatted": "{uptime_formatted}"
        }}
        """)
