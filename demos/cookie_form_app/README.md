# Serv Framework - Cookie Form Demo

This directory contains a demonstration of using forms, cookies, and conditional routing with the Serv web framework.

## Features Demonstrated

*   Handling HTML form submissions (POST requests).
*   Reading form data from the request body using `request.form()`.
*   Setting and deleting HTTP cookies (`ResponseBuilder.set_cookie`, `ResponseBuilder.delete_cookie`).
*   Reading cookies using `Annotated[str, Cookie(...)]` in middleware.
*   Middleware (`cookie_based_router_middleware`) that dynamically adds pre-configured `Router` instances to the request's main router based on cookie presence.
*   Using multiple `Router` instances (`form_router`, `welcome_router`), each handling the same path (`/`) but for different application states (logged in vs. not logged in).
*   POST-Redirect-GET pattern for form submissions.
*   Basic HTML generation within handlers.
*   Using `App(dev_mode=True)` for more detailed error output during development (as used when testing this demo).

## Files

*   `main.py`: The Python script containing the Serv application, routers, handlers, and middleware.
*   `README.md`: This file.

## How It Works

1.  The `App` is initialized with `cookie_based_router_middleware`.
2.  When a request comes in (e.g., to `/`):
    *   The `cookie_based_router_middleware` is executed.
    *   It inspects the `"username"` cookie.
3.  If the cookie is **not found** (e.g., first visit, or after logout):
    *   The middleware adds `form_router` to the app's router for the current request.
    *   A GET request to `/` is then handled by `show_name_form_handler` from `form_router`, displaying an HTML form.
4.  You submit the form (e.g., `username=DemoUser`) via POST to `/`:
    *   The `cookie_based_router_middleware` runs (cookie still not present for this incoming POST).
    *   It adds `form_router`.
    *   The POST request to `/` is handled by `handle_name_submission_handler` from `form_router`:
        *   Reads the `username` from the submitted form data.
        *   Sets a cookie named `"username"` with the value you provided.
        *   Redirects you back to `/` (using HTTP 303 See Other).
5.  After the redirect, your browser makes a GET request to `/` (now with the `"username"` cookie):
    *   The `cookie_based_router_middleware` runs.
    *   It finds the `"username"` cookie.
    *   It adds `welcome_router` to the app's router for the current request.
    *   The GET request to `/` is handled by `show_welcome_message_handler` from `welcome_router`, displaying a personalized welcome message and a "Logout" button.
6.  You click "Logout" (POST `/logout`):
    *   The `cookie_based_router_middleware` runs (cookie is present).
    *   It adds `welcome_router`.
    *   The POST request to `/logout` is handled by `app_logout_handler` from `welcome_router`:
        *   It deletes the `"username"` cookie.
        *   It redirects you back to `/`.
7.  After the logout redirect, visiting `/` (GET) will again trigger the middleware, which won't find the cookie, and `form_router` will be used, showing the name input form.

## Prerequisites

Same as the basic demo:
*   Python 3.8+
*   Serv framework installed (e.g., `pip install -e .` from project root, or `PYTHONPATH` configured).
*   `uvicorn` and `bevy` installed (`pip install uvicorn bevy`).

## Running the Demo

1.  Navigate to the Serv project's root directory in your terminal.

2.  Run the demo application using Python:
    ```bash
    python demos/cookie_form_app/main.py
    ```

3.  The application will start on port `8001`:
    ```
    Starting Serv cookie_form_app demo on http://127.0.0.1:8001
    Access it at: http://127.0.0.1:8001/
    Press Ctrl+C to stop.
    ```

4.  Open your web browser and navigate to `http://127.0.0.1:8001/`.
    *   You should see the form asking for your name.
    *   Enter your name and submit.
    *   You should then see the welcome message with your name.
    *   Click "Logout".
    *   You should be returned to the name input form.

## Stopping the Demo

Press `Ctrl+C` in the terminal where the `main.py` script is running. 