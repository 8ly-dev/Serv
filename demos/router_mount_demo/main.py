from typing import Annotated, Any

from bevy import dependency

from serv.app import App
from serv.extensions import Listener, on
from serv.routes import GetRequest, Jinja2Response, JsonResponse, Route, handle
from serv.routing import Router


# Define API Route classes for different resources
class UsersAPI(Route):
    @handle.GET
    async def list_all(
        self, request: GetRequest
    ) -> Annotated[dict[str, Any], JsonResponse]:
        users = [{"id": 1, "name": "John Doe"}, {"id": 2, "name": "Jane Smith"}]
        return {"users": users}

    @handle.GET
    async def get_one(
        self, request: GetRequest, id: str
    ) -> Annotated[dict[str, Any], JsonResponse]:
        return {"id": int(id), "name": f"User {id}"}


class ArticlesAPI(Route):
    @handle.GET
    async def list_all(
        self, request: GetRequest
    ) -> Annotated[dict[str, Any], JsonResponse]:
        articles = [
            {"id": 1, "title": "Getting Started with Serv"},
            {"id": 2, "title": "Advanced Routing in Serv"},
        ]
        return {"articles": articles}

    @handle.GET
    async def get_one(
        self, request: GetRequest, id: str
    ) -> Annotated[dict[str, Any], JsonResponse]:
        return {"id": int(id), "title": f"Article {id}"}


# Define frontend routes
class HomePage(Route):
    @handle.GET
    async def on_get(
        self, request: GetRequest
    ) -> Annotated[tuple[str, dict[str, Any]], Jinja2Response]:
        return "home.html", {"request": request}


class AboutPage(Route):
    @handle.GET
    async def on_get(
        self, request: GetRequest
    ) -> Annotated[tuple[str, dict[str, Any]], Jinja2Response]:
        return "about.html", {"request": request}


# Define Admin Handlers
async def admin_dashboard_handler(
    request: GetRequest,
) -> Annotated[tuple[str, dict[str, Any]], Jinja2Response]:
    return "admin/dashboard.html", {"request": request}


async def admin_users_handler(
    request: GetRequest,
) -> Annotated[tuple[str, dict[str, Any]], Jinja2Response]:
    return "admin/users.html", {"request": request}


class MountDemoExtension(Listener):
    def __init__(self):
        super().__init__()
        self.main_router = Router()
        api_router = Router()
        api_v1_router = Router()
        admin_router = Router()
        about_router = Router()

        api_v1_router.add_route("/users", UsersAPI)
        api_v1_router.add_route("/users/{id}", UsersAPI)
        api_v1_router.add_route("/articles", ArticlesAPI)
        api_v1_router.add_route("/articles/{id}", ArticlesAPI)

        api_router.mount("/v1", api_v1_router)

        admin_router.add_route("/", admin_dashboard_handler, methods=["GET"])
        admin_router.add_route("/users", admin_users_handler, methods=["GET"])
        about_router.add_route("/", AboutPage)
        self.main_router.add_route("/", HomePage)

        self.main_router.mount("/api", api_router)
        self.main_router.mount("/admin", admin_router)
        self.main_router.mount("/about", about_router)

    @on("app.request.begin")
    async def setup_router(self, router: Router = dependency()):
        router.add_router(self.main_router)


# Create the app
app = App(dev_mode=True)
app.add_extension(MountDemoExtension())  # Add the plugin instance

# Start the app
if __name__ == "__main__":
    import uvicorn

    print("Starting Serv Router Mount Demo on http://127.0.0.1:8000")
    print("Access it at:")
    print("  http://127.0.0.1:8000/")
    print("  http://127.0.0.1:8000/about")
    print("  http://127.0.0.1:8000/admin")
    print("  http://127.0.0.1:8000/api/v1/users")
    print("  http://127.0.0.1:8000/api/v1/users/{id}")
    print("Press Ctrl+C to stop.")
    uvicorn.run(app, host="127.0.0.1", port=8000)
