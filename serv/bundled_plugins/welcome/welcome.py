from serv.routes import Route, GetRequest, Jinja2Response
from serv.plugins import Plugin
from serv.routing import Router # For type hinting
from bevy import dependency
from typing import Annotated, Any # Added Any for dict type hint

class WelcomeRoute(Route):
    async def handle_get(self, _: GetRequest) -> Annotated[tuple[str, dict[str, Any]], Jinja2Response]:
        # The Jinja2Response expects (template_name, context_dict)
        # The context dict is currently empty as the template is static.
        return ("welcome.html", {})

class WelcomePlugin(Plugin):
    """
    A simple plugin that registers the WelcomeRoute at the root path (/).
    """
    
    @dependency
    def get_router(self) -> Router:
        # This method is primarily for Bevy to satisfy the dependency in on_app_request_begin.
        # It might not be strictly necessary if Router is always in the container by then.
        # However, explicitly asking for it via a method can sometimes help Bevy's resolution.
        # Alternatively, on_app_request_begin can directly ask for Router = dependency().
        pass # Bevy will provide this

    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        """Registers the WelcomeRoute at '/' if no other route is already defined for it."""
        
        # Basic check: see if any route is already registered for GET on "/"
        # This is a simplification. A more robust router might offer a has_route(path, method) method.
        path_already_handled = False
        if hasattr(router, '_routes'): # Basic check if router has _routes attribute
            for path_pattern, methods, _ in router._routes:
                if path_pattern == "/":
                    if methods is None or "GET" in methods: # None means all methods
                        path_already_handled = True
                        break
        
        if not path_already_handled:
            print("INFO: WelcomePlugin registering WelcomeRoute at '/'.")
            router.add_route("/", WelcomeRoute)
        else:
            print("INFO: WelcomePlugin found existing route for '/'; WelcomeRoute not registered.") 