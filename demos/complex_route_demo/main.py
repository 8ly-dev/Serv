import pathlib
import sys

from demos.complex_route_demo.plugins import DemoRoutesPlugin
from serv import App

# Add project root to sys.path
# Assumes this script is in demos/complex_route_demo
# Project root is two levels up from this script's directory
project_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# HomeRoute and SubmitRoute are used by the plugin, not directly here

_app_instance = None  # Keep instance at module level for factory


def app_factory():  # Renamed for clarity
    global _app_instance
    if _app_instance is None:
        # This will be called by Uvicorn, which should have a loop running.
        _app_instance = App(dev_mode=True)
        _app_instance.add_plugin(DemoRoutesPlugin(stand_alone=True))
    return _app_instance


if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("Uvicorn is not installed. Please install it with: pip install uvicorn")
        print("You might also need bevy: pip install bevy")
    else:
        print(
            "Starting Serv complex route demo on http://127.0.0.1:8000 (dev_mode=True, factory)"
        )
        print("Access it at:")
        print("  http://127.0.0.1:8000/ (GET)")
        print("  http://127.0.0.1:8000/submit (POST via form on homepage)")
        print("Press Ctrl+C to stop.")

        # Use the factory pattern. Uvicorn expects the import string or a callable that returns the app.
        # Passing the factory function directly.
        uvicorn.run(
            "main:app_factory", host="127.0.0.1", port=8000, factory=True, reload=False
        )  # Added reload=False for stability
