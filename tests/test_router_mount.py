import pytest

from serv.exceptions import HTTPMethodNotAllowedException
from serv.routing import Router


# Mock handlers for testing
async def root_handler(**kwargs):
    return "Root Handler"


async def api_users_handler(**kwargs):
    return "API Users Handler"


async def api_posts_handler(**kwargs):
    return f"API Posts Handler with ID: {kwargs.get('id', 'none')}"


async def admin_handler(**kwargs):
    return "Admin Handler"


def test_mount_router_basic_functionality():
    # Create the routers
    main_router = Router()
    api_router = Router()
    admin_router = Router()

    # Set up routes in the API router
    api_router.add_route("/users", api_users_handler, methods=["GET"])
    api_router.add_route("/posts/{id}", api_posts_handler, methods=["GET"])

    # Set up routes in the admin router
    admin_router.add_route("/", admin_handler, methods=["GET"])

    # Set up routes in the main router
    main_router.add_route("/", root_handler, methods=["GET"])

    # Mount the API router at /api
    main_router.mount("/api", api_router)

    # Mount the admin router at /admin
    main_router.mount("/admin", admin_router)

    # Test main router routes
    handler, params, settings = main_router.resolve_route("/", "GET")
    assert handler == root_handler
    assert params == {}
    assert settings == {}

    # Test mounted API router routes
    handler, params, settings = main_router.resolve_route("/api/users", "GET")
    assert handler == api_users_handler
    assert params == {}
    assert settings == {}

    handler, params, settings = main_router.resolve_route("/api/posts/123", "GET")
    assert handler == api_posts_handler
    assert params == {"id": "123"}
    assert settings == {}

    # Test mounted admin router routes
    handler, params, settings = main_router.resolve_route("/admin", "GET")
    assert handler == admin_handler
    assert params == {}
    assert settings == {}

    # Test non-existent route
    assert main_router.resolve_route("/nonexistent", "GET") is None


def test_mount_router_method_not_allowed():
    main_router = Router()
    api_router = Router()

    api_router.add_route("/users", api_users_handler, methods=["GET"])
    main_router.mount("/api", api_router)

    # Test method not allowed
    with pytest.raises(HTTPMethodNotAllowedException) as exc_info:
        main_router.resolve_route("/api/users", "POST")

    assert "Method POST not allowed for /api/users" in str(exc_info.value)
    assert "GET" in exc_info.value.allowed_methods


def test_mount_router_nested():
    main_router = Router()
    api_router = Router()
    user_router = Router()

    # Set up nested routes
    user_router.add_route("/profile", api_users_handler, methods=["GET"])
    api_router.mount("/users", user_router)
    main_router.mount("/api", api_router)

    # Test deeply nested route
    handler, params, settings = main_router.resolve_route("/api/users/profile", "GET")
    assert handler == api_users_handler
    assert params == {}
    assert settings == {}


def test_mount_router_path_normalization():
    main_router = Router()
    api_router = Router()

    api_router.add_route("/users", api_users_handler, methods=["GET"])

    # Test with different path formats
    main_router.mount("api", api_router)  # Without leading slash
    handler, params, settings = main_router.resolve_route("/api/users", "GET")
    assert handler == api_users_handler

    main_router = Router()
    main_router.mount("/api/", api_router)  # With trailing slash
    handler, params, settings = main_router.resolve_route("/api/users", "GET")
    assert handler == api_users_handler
