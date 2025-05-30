"""Welcome Extension - Default landing page for new Serv applications.

This module provides the built-in welcome extension that displays a friendly landing page
for new Serv applications. The extension is automatically enabled when no other extensions
are configured, providing immediate feedback that the application is running correctly.

The welcome extension demonstrates several key Serv concepts:
- Extension architecture and lifecycle hooks
- Route registration and handling
- Template rendering with Jinja2
- Conditional route registration to avoid conflicts

Components:
    WelcomeRoute: A simple route handler that renders the welcome template

The extension registers a GET route at the root path ("/") that displays a welcome page
with information about Serv, links to documentation, and getting started guidance.
It only registers the route if no other route is already handling the root path,
ensuring it doesn't interfere with user-defined routes.

Example:
    The welcome extension is automatically loaded when creating a new Serv app
    with no other extensions configured:

    ```python
    from serv import App

    # Creates app with welcome extension automatically enabled
    app = App()

    # Visit http://localhost:8000/ to see the welcome page
    ```

    To disable the welcome extension, simply configure other extensions:

    ```python
    # In serv.config.yaml:
    extensions:
      - name: "my_extension"
        entry: "extensions.my_extension:MyExtension"
    ```

Note:
    This extension is part of Serv's bundled extensions and is located in the
    serv.bundled.extensions.welcome package. It serves as both a useful default
    and an example of how to create Serv extensions.
"""

from typing import Annotated, Any  # Added Any for dict type hint

from serv.routes import GetRequest, Jinja2Response, Route, handle


class WelcomeRoute(Route):
    """Route handler for the welcome page.

    This route serves the default welcome page at the root path ("/") for new
    Serv applications. It renders a Jinja2 template that provides information
    about Serv, getting started guidance, and links to documentation.

    The route uses the Jinja2Response type annotation to automatically wrap
    the returned template name and context in a proper HTML response.

    Examples:
        ```python
        # Accessing the welcome page
        # GET / -> Renders welcome.html template
        ```

        The route can also be used as a reference for creating other
        template-based routes:

        ```python
        class MyRoute(Route):
            async def handle_get(self, request: GetRequest) -> Annotated[tuple[str, dict[str, Any]], Jinja2Response]:
                context = {"user": "John", "message": "Hello!"}
                return ("my_template.html", context)
        ```
    """

    @handle.GET
    async def show_welcome_page(
        self, _: GetRequest
    ) -> Annotated[tuple[str, dict[str, Any]], Jinja2Response]:
        """Handle GET requests to display the welcome page.

        Returns:
            A tuple containing the template name and context dictionary
            for rendering the welcome page.
        """
        # The Jinja2Response expects (template_name, context_dict)
        # The context dict is currently empty as the template is static.
        return ("welcome.html", {})
