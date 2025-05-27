import asyncio

from bevy import dependency

from serv.app import App
from serv.extensions import Listener
from serv.responses import ResponseBuilder
from serv.routing import Router

# Define a handler for the root path


async def homepage(response: ResponseBuilder = dependency()):
    response.content_type("text/plain")
    response.body("Hello from Serv! This is the basic demo.")


# Define another handler for an /about path
async def about_page(response: ResponseBuilder = dependency()):
    response.content_type("text/html")
    response.body(
        "<h1>About Us</h1><p>This is a simple demo of the Serv framework.</p>"
    )


class BasicAppExtension(Listener):
    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        router.add_route("/", homepage)
        router.add_route("/about", about_page)


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
