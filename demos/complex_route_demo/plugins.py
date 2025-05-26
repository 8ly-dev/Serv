from bevy import dependency
from demo import (  # Assuming HomeRoute and SubmitRoute are in demo.py
    HomeRoute,
    SubmitRoute,
)

from serv.plugins import Plugin
from serv.routing import Router


class DemoRoutesPlugin(Plugin):
    def on_app_request_begin(self, router: Router = dependency()):
        """This method will be called by Bevy/Serv, injecting the Router.
        Alternatively, this could be an event handler if Serv uses an event system
        for plugin initialization phases.
        """
        router.add_route("/", HomeRoute)
        router.add_route("/submit", SubmitRoute)
        print(
            f"INFO: Demo routes registered with router {id(router)}"
        )  # For debugging/confirmation
