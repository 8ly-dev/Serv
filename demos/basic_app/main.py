import asyncio
from typing import Annotated

from serv.app import App
from serv.extensions import Listener
from serv.responses import HtmlResponse, TextResponse
from serv.routes import Route
from serv.routing import Router


class HomeRoute(Route):
    """Modern Route class demonstrating signature-based routing"""

    async def handle_get(self) -> Annotated[str, TextResponse]:
        """Handle GET requests to homepage"""
        return "Hello from Serv! This is the updated basic demo using Route classes."


class AboutRoute(Route):
    """About page route"""

    async def handle_get(self) -> Annotated[str, HtmlResponse]:
        """Handle GET requests to about page"""
        return """
        <h1>About Us</h1>
        <p>This is a simple demo of the Serv framework using the new Route class system.</p>
        <p><a href="/">← Back to Home</a></p>
        
        <h2>What's New</h2>
        <ul>
            <li>Route classes instead of functions</li>
            <li>Signature-based method dispatch</li>
            <li>Type-annotated responses</li>
            <li>Automatic parameter injection</li>
        </ul>
        
        <p>Check out the <a href="../signature_routing_demo/">signature routing demo</a> for more advanced features!</p>
        """


class BasicAppExtension(Listener):
    async def on_app_request_begin(self, router: Router) -> None:
        router.add_route("/", HomeRoute)
        router.add_route("/about", AboutRoute)


# If the script is run directly, start the Uvicorn server
if __name__ == "__main__":

    async def main():
        try:
            import uvicorn
        except ImportError:
            print(
                "Uvicorn is not installed. Please install it with: pip install uvicorn"
            )
            return

        print("Starting Serv basic demo on http://127.0.0.1:8000")
        print("Press Ctrl+C to stop.")

        # Create an app instance inside the event loop
        app = App()
        app.add_extension(BasicAppExtension(stand_alone=True))

        # Configure and run Uvicorn with the same loop
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=8000,
            loop="asyncio",
        )
        server = uvicorn.Server(config)
        await server.serve()

    asyncio.run(main())
