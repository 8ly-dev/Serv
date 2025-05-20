import pytest
from typing import Dict, Any
from serv.routing import Router
from serv.routes import GetRequest, Route


# Mock handlers for testing
async def user_handler(**kwargs):
    return f"User: {kwargs.get('id')}"

async def post_handler(**kwargs):
    return f"Post: {kwargs.get('post_id')}, Comment: {kwargs.get('comment_id')}"

async def profile_handler(**kwargs):
    return "Profile"

async def api_handler(**kwargs):
    return "API Root"


# Mock Route classes
class UserProfileRoute(Route):
    async def show_profile(self, request: GetRequest):
        return

class ArticleRoute(Route):
    async def show_article(self, request: GetRequest):
        return


def test_url_for_basic():
    router = Router()
    router.add_route("/user/{id}", user_handler, methods=["GET"])
    
    url = router.url_for(user_handler, id=123)
    assert url == "/user/123"


def test_url_for_multiple_params():
    router = Router()
    router.add_route("/posts/{post_id}/comments/{comment_id}", post_handler, methods=["GET"])
    
    url = router.url_for(post_handler, post_id=456, comment_id="abc")
    assert url == "/posts/456/comments/abc"


def test_url_for_mounted_router():
    main_router = Router()
    api_router = Router()
    
    api_router.add_route("/users/{id}", user_handler, methods=["GET"])
    main_router.mount("/api", api_router)
    
    url = main_router.url_for(user_handler, id=789)
    assert url == "/api/users/789"


def test_url_for_nested_mounted_routers():
    main_router = Router()
    api_router = Router()
    users_router = Router()
    
    users_router.add_route("/{id}/profile", profile_handler, methods=["GET"])
    api_router.mount("/users", users_router)
    main_router.mount("/api", api_router)
    
    url = main_router.url_for(profile_handler, id=321)
    assert url == "/api/users/321/profile"


def test_url_for_sub_router():
    main_router = Router()
    sub_router = Router()
    
    sub_router.add_route("/profile", profile_handler, methods=["GET"])
    main_router.add_router(sub_router)
    
    url = main_router.url_for(profile_handler)
    assert url == "/profile"


def test_url_for_missing_param():
    router = Router()
    router.add_route("/user/{id}", user_handler, methods=["GET"])
    
    with pytest.raises(ValueError, match="Missing required path parameter: id"):
        router.url_for(user_handler)


def test_url_for_handler_not_found():
    router = Router()
    router.add_route("/profile", profile_handler, methods=["GET"])
    
    with pytest.raises(ValueError, match="Handler user_handler not found in any router"):
        router.url_for(user_handler)


def test_url_for_route_class():
    router = Router()

    # Simulate what happens when Route class is registered
    router.add_route("/users/{username}", UserProfileRoute)

    
    # When we have the route instance's __call__ method
    url = router.url_for(UserProfileRoute, username="johndoe")
    assert url == "/users/johndoe"


def test_url_for_route_class_in_mounted_router():
    main_router = Router()
    api_router = Router()
    
    # Add a Route class to the API router
    api_router.add_route("/articles/{slug}", ArticleRoute)
    
    # Mount the API router
    main_router.mount("/api", api_router)
    
    # Get the URL using the Route class
    url = main_router.url_for(ArticleRoute, slug="getting-started")
    assert url == "/api/articles/getting-started"


# This test isn't really well-designed because our lookup logic doesn't directly support 
# looking up individual methods on the Route class yet, but just ensuring we can store 
# and access the route class URL and its instance still.
def test_url_for_route_instance_method():
    router = Router()
    
    # Register the Route class
    router.add_route("/products/{product_id}", ArticleRoute)
    
    # Create an instance of the route class
    route_instance = ArticleRoute()
    
    # Try to get the URL using the original class
    url = router.url_for(ArticleRoute, product_id="abcd-1234")
    assert url == "/products/abcd-1234" 