# Serv Framework - Basic Demo

This directory contains a basic demonstration of the Serv web framework.

## Features Demonstrated

*   Basic application setup using `serv.app.App`.
*   Defining a simple `serv.plugins.Plugin`.
*   Adding routes within a plugin using `router.add_route()`.
*   Simple asynchronous request handlers.
*   Returning plain text and HTML responses using `serv.responses.ResponseBuilder`.
*   Dependency injection for `ResponseBuilder` and `Router` into handlers/plugin methods via `bevy.dependency()`.

## Files

*   `main.py`: The Python script containing the Serv application and example routes.
*   `README.md`: This file, providing instructions and information about the demo.

## Prerequisites

Before running the demo, ensure you have Python 3.8+ installed.

You will also need to install the Serv framework. If you are running this demo from within the Serv project's cloned repository, ensure the project is installed (e.g., in editable mode `pip install -e .`) or that your `PYTHONPATH` is configured to find the `serv` package.

Additionally, this demo uses `uvicorn` as the ASGI server and `bevy` for dependency injection. If they are not already installed as part of Serv's dependencies, you can install them via pip:

```bash
pip install uvicorn bevy
```

## Running the Demo

1.  Navigate to the Serv project's root directory in your terminal if you aren't there already.

2.  Run the demo application using Python:
    ```bash
    python demos/basic_app/main.py
    ```

3.  The application will start, and you should see output similar to:
    ```
    Starting Serv basic demo on http://127.0.0.1:8000
    Press Ctrl+C to stop.
    ```
    You can then access the application at:
    *   `http://127.0.0.1:8000/` to see the plain text homepage.
    *   `http://127.0.0.1:8000/about` to see the HTML about page.

## Stopping the Demo

To stop the server, press `Ctrl+C` in the terminal where the `main.py` script is running. 