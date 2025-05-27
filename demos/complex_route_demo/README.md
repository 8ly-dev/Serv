# Serv Framework - Complex Route Demo

This directory demonstrates more advanced routing capabilities in Serv, including:

## Features Demonstrated

*   Class-based routes (inheriting from `serv.routes.Route`).
*   Using `Annotated` return types for responses (e.g., `Jinja2Response`, `HtmlResponse`).
*   Automatic request form data parsing into dataclasses (e.g., `serv.routes.Form`).
*   Organizing routes and handlers in separate files (`demo.py`).
*   Registering routes via a Extension (`plugins.py`).
*   Using Jinja2 templates for rendering HTML.
*   Running the application using Uvicorn with the factory pattern.

## Files

*   `main.py`: Entry point to run the demo application using Uvicorn.
*   `plugins.py`: Contains `DemoRoutesExtension` which registers the class-based routes.
*   `demo.py`: Defines the `HomeRoute` (using Jinja2) and `SubmitRoute` (processing a form).
*   `templates/home.html`: A Jinja2 template for the homepage, including a form.
*   `__init__.py`: Makes the demo directory a package if needed for imports.
*   `README.md`: This file.

## Prerequisites

Ensure Python 3.8+ and the Serv framework (including `bevy`) are installed. See the main project README or other demo READMEs for detailed installation instructions.
`uvicorn` is required to run this demo:

```bash
pip install uvicorn
```

## Running the Demo

1.  Navigate to the Serv project's root directory.
2.  Run the application:
    ```bash
    python demos/complex_route_demo/main.py
    ```
3.  The server will start (defaults to `http://127.0.0.1:8000`).
    You should see output like:
    ```
    Starting Serv complex route demo on http://127.0.0.1:8000 (dev_mode=True, factory)
    Access it at:
      http://127.0.0.1:8000/ (GET)
      http://127.0.0.1:8000/submit (POST via form on homepage)
    Press Ctrl+C to stop.
    ```
4.  Open a browser to `http://127.0.0.1:8000/`. You should see a form.
5.  Fill out and submit the form. You should see a confirmation page.

**Note:** As of the last check, there were runtime errors related to `Jinja2Response` context and `HtmlResponse` handling when using class-based routes. These might indicate issues in the Serv framework core that need addressing for this demo to function correctly.

## Stopping the Demo

Press `Ctrl+C` in the terminal. 