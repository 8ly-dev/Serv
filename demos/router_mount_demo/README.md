# Serv Framework - Router Mount Demo

This demo showcases how to structure a Serv application with multiple `Router` instances mounted at different paths, including nested mounts for API versioning.

## Features Demonstrated

*   Creating multiple `Router` instances.
*   Mounting routers at different base paths (`main_router.mount("/api", api_router)`).
*   Nested mounting (`api_router.mount("/v1", api_v1_router)`).
*   Class-based routes (`HomePage`, `AboutPage`, `UsersAPI`, `ArticlesAPI`) using `serv.routes.Route`.
*   Function-based handlers (`admin_dashboard_handler`, `admin_users_handler`).
*   Using `Annotated` return types with `Jinja2Response` and `JsonResponse`.
*   Serving HTML templates and JSON responses.
*   Organizing route setup within a `Extension`.

## Files

*   `main.py`: The main application script, sets up the app, plugin, and routers.
*   `templates/`: Directory containing HTML templates for the demo.
    *   `home.html`
    *   `about.html`
    *   `admin/dashboard.html`
    *   `admin/users.html`
*   `README.md`: This file.

## Prerequisites

*   Python 3.8+
*   Serv framework installed (e.g., `pip install -e .` from project root).
*   `uvicorn` (`pip install uvicorn`).

## Running the Demo

1.  Ensure you are in the root directory of the Serv project.
2.  Run the demo script directly:
    ```bash
    python demos/router_mount_demo/main.py
    ```
3.  The server will start (defaults to `http://127.0.0.1:8000`). You should see output indicating the server is running and listing accessible routes.

4.  Test the following endpoints in your browser or with `curl`:
    *   `http://127.0.0.1:8000/` (Homepage)
    *   `http://127.0.0.1:8000/about` (About Page)
    *   `http://127.0.0.1:8000/admin` (Admin Dashboard)
    *   `http://127.0.0.1:8000/admin/users` (Admin Users Page)
    *   `http://127.0.0.1:8000/api/v1/users` (Users API)
    *   `http://127.0.0.1:8000/api/v1/users/123` (Specific User API)
    *   `http://127.0.0.1:8000/api/v1/articles` (Articles API)
    *   `http://127.0.0.1:8000/api/v1/articles/456` (Specific Article API)

**Note on potential issues:** If you encounter an `ImportError` for `Template` or `JSON` from `serv.responses`, please ensure that `demos/router_mount_demo/main.py` uses `from serv.routes import Jinja2Response, JsonResponse` and that handlers return data suitable for these (e.g., `Annotated[Tuple[str, Dict], Jinja2Response]` or `Annotated[Dict, JsonResponse]`). The class-based routing features are sensitive to correct type hinting and response annotations.

## Stopping the Demo

Press `Ctrl+C` in the terminal where the script is running. 