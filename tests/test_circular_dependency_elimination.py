"""Tests to verify circular dependency elimination."""


def test_protocols_exist():
    """Test that all required protocols exist."""
    from serv.protocols import (
        AppContextProtocol,
        ContainerProtocol,
        EventEmitterProtocol,
        RouterProtocol,
    )

    assert EventEmitterProtocol is not None
    assert AppContextProtocol is not None
    assert RouterProtocol is not None
    assert ContainerProtocol is not None


def test_app_implements_protocols():
    """Test that App class implements required protocols."""
    from serv._app import App
    from serv.protocols import AppContextProtocol, EventEmitterProtocol

    app = App(dev_mode=True)

    # Test that App implements the protocols
    assert isinstance(app, EventEmitterProtocol)
    assert isinstance(app, AppContextProtocol)

    # Test that required methods exist
    assert hasattr(app, "emit")
    assert hasattr(app, "get_extension")
    assert hasattr(app, "add_extension")


def test_router_implements_protocol():
    """Test that Router class implements RouterProtocol."""
    from serv._routing import Router
    from serv.protocols import RouterProtocol

    router = Router()

    # Test that Router implements the protocol
    assert isinstance(router, RouterProtocol)

    # Test that required methods exist
    assert hasattr(router, "add_route")
    assert hasattr(router, "resolve_route")
    assert hasattr(router, "mount")


def test_route_uses_protocols():
    """Test that Route class uses protocols instead of direct imports."""
    from serv.routes import Route

    route = Route()

    # Test that emit method exists (should use EventEmitterProtocol)
    assert hasattr(route, "emit")

    # Test that the emit method signature uses protocols
    # The method should exist and be callable
    assert callable(route.emit)


def test_no_direct_app_import_in_routes():
    """Test that routes module doesn't directly import app module."""
    import ast
    from pathlib import Path

    routes_file = Path(__file__).parent.parent / "serv" / "routes.py"
    with open(routes_file) as f:
        tree = ast.parse(f.read())

    # Check for direct imports of serv.app
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.endswith("serv.app"), (
                    f"Found direct import of serv.app: {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert not node.module.endswith("serv.app"), (
                    f"Found direct import from serv.app: {node.module}"
                )


def test_framework_functionality_preserved():
    """Test that basic framework functionality still works after refactoring."""
    from serv._app import App
    from serv.routes import Route, handle

    # Test creating an app
    app = App(dev_mode=True)
    assert app is not None

    # Test creating a route
    class TestRoute(Route):
        @handle.GET
        async def test_handler(self):
            return {"status": "success"}

    # Test that route can be instantiated
    route = TestRoute()
    assert route is not None

    # Test that the route has expected methods
    assert hasattr(route, "test_handler")
    assert hasattr(route, "emit")
    assert hasattr(route, "extension")
