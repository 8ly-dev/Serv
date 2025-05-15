from serv.app import App
from serv.responses import ResponseBuilder
from bevy import dependency

# Create an app instance
app = App()

# Define a handler for the root path
@app.add_route("/")
async def homepage(response: ResponseBuilder = dependency()):
    response.content_type("text/plain")
    response.body("Hello from Serv! This is the basic demo.")

# Define another handler for an /about path
@app.add_route("/about")
async def about_page(response: ResponseBuilder = dependency()):
    response.content_type("text/html")
    response.body("<h1>About Us</h1><p>This is a simple demo of the Serv framework.</p>")

# If the script is run directly, start the Uvicorn server
if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("Uvicorn is not installed. Please install it with: pip install uvicorn")
        print("You might also need bevy: pip install bevy")
    else:
        print("Starting Serv basic demo on http://127.0.0.1:8000")
        print("Access it at:")
        print("  http://127.0.0.1:8000/")
        print("  http://127.0.0.1:8000/about")
        print("Press Ctrl+C to stop.")
        uvicorn.run(app, host="127.0.0.1", port=8000) 