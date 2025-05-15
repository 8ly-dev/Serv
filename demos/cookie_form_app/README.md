# Serv Framework - Cookie Form Demo

This directory contains a demonstration of using forms, cookies, and conditional routing with the Serv web framework.

## Features Demonstrated

*   Handling HTML form submissions (POST requests).
*   Reading form data from the request body.
*   Setting and deleting HTTP cookies (`ResponseBuilder.set_cookie`, `ResponseBuilder.delete_cookie`).
*   Reading cookies from the `Request` object.
*   Conditional logic within a handler to dispatch to different `Router` instances based on the presence of a cookie.
*   Using multiple `Router` instances, each handling the same path (`/`) but for different application states (logged in vs. not logged in).
*   POST-Redirect-GET pattern for form submissions.
*   Basic HTML generation within handlers.

## Files

*   `main.py`: The Python script containing the Serv application, routers, handlers, and dispatch logic.
*   `README.md`: This file.

## How It Works

1.  When you first visit `/`, the `root_dispatcher` handler is invoked.
2.  It checks for a cookie named `"username"`.
3.  If the cookie is **not found**: 
    *   It dispatches the request to `form_router`.
    *   `form_router` (GET `/`): Displays an HTML form asking for your name.
4.  You submit the form (POST `/`):
    *   `root_dispatcher` again checks for the cookie (still not found initially for the POST).
    *   It dispatches to `form_router`.
    *   `form_router` (POST `/`): 
        *   Reads the `username` from the submitted form data.
        *   Sets a cookie named `"username"` with the value you provided.
        *   Redirects you back to `/` (using HTTP 303 See Other).
5.  After the redirect, you visit `/` again (GET):
    *   `root_dispatcher` checks for the `"username"` cookie.
    *   If the cookie is **found**:
        *   It dispatches the request to `welcome_router`.
        *   `welcome_router` (GET `/`): Reads the username from the cookie and displays a personalized welcome message along with a "Logout" button.
6.  You click "Logout" (POST `/logout`):
    *   The `logout_handler` (registered directly on the main `app`) is invoked.
    *   It deletes the `"username"` cookie.
    *   It redirects you back to `/`.
7.  After the logout redirect, visiting `/` will again show the name input form, as the cookie is now gone.

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