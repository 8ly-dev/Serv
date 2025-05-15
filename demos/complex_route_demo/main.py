import sys
import pathlib

# Add project root to sys.path
# Assumes this script is in demos/complex_route_demo
# Project root is two levels up from this script's directory
project_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from serv import App
# Router is no longer directly used in main.py for route definition
from plugins import DemoRoutesPlugin 
# HomeRoute and SubmitRoute are used by the plugin, not directly here

app = App()

# Instantiate and register the plugin
# Assuming App has an `add_plugin` method or similar mechanism
# for Bevy to pick up the plugin and its dependencies.
app.add_plugin(DemoRoutesPlugin()) 

if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("Uvicorn is not installed. Please install it with: pip install uvicorn")
        print("You might also need bevy: pip install bevy")
    else:
        print("Starting Serv complex route demo on http://127.0.0.1:8000")
        print("Access it at:")
        print("  http://127.0.0.1:8000/")
        print("  http://127.0.0.1:8000/about")
        print("Press Ctrl+C to stop.")
        uvicorn.run(app, host="127.0.0.1", port=8000) 
    