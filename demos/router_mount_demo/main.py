from serv.app import App
from serv.routing import Router
from serv.routes import Route, get
from serv.responses import Template, JSON
from typing import Dict, Any, List


# Define API Route classes for different resources
class UsersAPI(Route):
    @get("/")
    async def list_users(self) -> JSON:
        # Mock data for demonstration
        users = [
            {"id": 1, "name": "John Doe"},
            {"id": 2, "name": "Jane Smith"}
        ]
        return JSON({"users": users})
    
    @get("/{id}")
    async def get_user(self, id: str) -> JSON:
        # Mock data for demonstration
        return JSON({"id": int(id), "name": f"User {id}"})


class ArticlesAPI(Route):
    @get("/")
    async def list_articles(self) -> JSON:
        # Mock data for demonstration
        articles = [
            {"id": 1, "title": "Getting Started with Serv"},
            {"id": 2, "title": "Advanced Routing in Serv"}
        ]
        return JSON({"articles": articles})
    
    @get("/{id}")
    async def get_article(self, id: str) -> JSON:
        # Mock data for demonstration
        return JSON({"id": int(id), "title": f"Article {id}"})


# Define frontend routes
class HomePage(Route):
    @get("/")
    async def home(self) -> Template:
        return Template("home.html")


class AboutPage(Route):
    @get("/")
    async def about(self) -> Template:
        return Template("about.html")


# Create the app
app = App()

# Create routers for different sections of the app
main_router = Router()
api_router = Router()
api_v1_router = Router()
admin_router = Router()
about_router = Router()

# Set up API routes
api_v1_router.add_route("/users", UsersAPI)
api_v1_router.add_route("/articles", ArticlesAPI)

# Mount API v1 router to the API router
api_router.mount("/v1", api_v1_router)

# Set up admin routes (simplified for demo)
async def admin_dashboard_handler(**kwargs):
    return Template("admin/dashboard.html")

async def admin_users_handler(**kwargs):
    return Template("admin/users.html")

admin_router.add_route("/", admin_dashboard_handler, methods=["GET"])
admin_router.add_route("/users", admin_users_handler, methods=["GET"])

# Set up about route
about_router.add_route("/", AboutPage)

# Set up main routes
main_router.add_route("/", HomePage)

# Mount all specialized routers to the main router
main_router.mount("/api", api_router)  # Now /api/v1/users will work
main_router.mount("/admin", admin_router)  # Now /admin and /admin/users will work
main_router.mount("/about", about_router)  # Now /about will work

# Add the main router to the app
app.on_startup(lambda container: container.set(Router, main_router))

# Start the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000) 