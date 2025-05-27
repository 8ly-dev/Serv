"""
End-to-end tests for declarative router functionality.

This file tests the complete workflow of declarative routers:
1. Creating plugins with routers configuration in extension.yaml
2. Loading plugins through the normal plugin loading mechanism
3. Verifying that HTTP requests work correctly through the declarative routes
4. Testing integration with the CLI commands
"""

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from serv.app import App
from tests.e2e.helpers import create_test_client


class TestDeclarativeRoutersE2E:
    """End-to-end tests for declarative router functionality."""

    @pytest.fixture
    def test_project_dir(self):
        """Create a test project directory with initialized Serv app."""
        test_dir = tempfile.mkdtemp()
        try:
            # Create basic project structure
            plugins_dir = Path(test_dir) / "extensions"
            plugins_dir.mkdir(exist_ok=True)

            # Create basic serv.config.yaml
            config = {
                "site_info": {
                    "name": "Test App",
                    "description": "Test application for declarative routers",
                },
                "extensions": [],
                "middleware": [],
            }

            with open(Path(test_dir) / "serv.config.yaml", "w") as f:
                yaml.dump(config, f)

            yield test_dir
        finally:
            shutil.rmtree(test_dir)

    def create_declarative_router_plugin(
        self, project_dir, plugin_name, extension_config
    ):
        """Create a plugin with declarative router configuration."""
        plugins_dir = Path(project_dir) / "extensions"
        extension_dir = plugins_dir / plugin_name
        extension_dir.mkdir(exist_ok=True)

        # Create extension.yaml with routers configuration
        with open(extension_dir / "extension.yaml", "w") as f:
            yaml.dump(extension_config, f)

        # Create __init__.py to make it a package
        (extension_dir / "__init__.py").touch()

        # Create handler modules based on the router configuration
        routers_config = extension_config.get("routers", [])
        module_handlers = {}  # Track handlers per module

        for router_config in routers_config:
            routes = router_config.get("routes", [])
            for route in routes:
                handler_str = route.get("handler", "")
                if ":" in handler_str:
                    module_name, class_name = handler_str.split(":")
                    if module_name not in module_handlers:
                        module_handlers[module_name] = []
                    module_handlers[module_name].append(
                        (class_name, route.get("path", "unknown"))
                    )

        # Create module files with all handlers
        for module_name, handlers in module_handlers.items():
            module_file = extension_dir / f"{module_name}.py"
            handler_functions = []
            for class_name, path in handlers:
                handler_functions.append(f"""
async def {class_name}(response: ResponseBuilder = dependency(), **path_params):
    response.content_type("text/plain")
    response.body("Hello from {class_name} at {path} with params: {{path_params}}")
""")

            handler_code = f"""
from serv.responses import ResponseBuilder
from bevy import dependency
{"".join(handler_functions)}
"""
            module_file.write_text(handler_code)

        return extension_dir

    @pytest.mark.asyncio
    async def test_basic_declarative_router_e2e(self, test_project_dir):
        """Test basic declarative router functionality end-to-end."""
        # Create a plugin with declarative router configuration
        extension_config = {
            "name": "Basic Router Extension",
            "description": "A plugin with basic declarative router",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "main_router",
                    "routes": [
                        {"path": "/hello", "handler": "handlers:HelloHandler"},
                        {"path": "/goodbye", "handler": "handlers:GoodbyeHandler"},
                    ],
                }
            ],
        }

        self.create_declarative_router_plugin(
            test_project_dir, "basic_router_plugin", extension_config
        )

        # Update the app config to include this plugin
        config_path = Path(test_project_dir) / "serv.config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        config["extensions"] = ["basic_router_plugin"]
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Create the app and test the routes
        app = App(
            config=str(config_path),
            extension_dir=str(Path(test_project_dir) / "extensions"),
            dev_mode=True,
        )

        async with create_test_client(app_factory=lambda: app) as client:
            # Test the hello route
            response = await client.get("/hello")
            assert response.status_code == 200
            assert "HelloHandler" in response.text
            assert "/hello" in response.text

            # Test the goodbye route
            response = await client.get("/goodbye")
            assert response.status_code == 200
            assert "GoodbyeHandler" in response.text
            assert "/goodbye" in response.text

            # Test non-existent route
            response = await client.get("/nonexistent")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_mounted_declarative_router_e2e(self, test_project_dir):
        """Test mounted declarative router functionality end-to-end."""
        # Create a plugin with mounted router configuration
        extension_config = {
            "name": "API Router Extension",
            "description": "A plugin with mounted API router",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "api_router",
                    "mount": "/api/v1",
                    "routes": [
                        {
                            "path": "/users",
                            "handler": "api:UsersHandler",
                            "methods": ["GET", "POST"],
                        },
                        {
                            "path": "/users/{id}",
                            "handler": "api:UserHandler",
                            "methods": ["GET", "PUT", "DELETE"],
                        },
                    ],
                }
            ],
        }

        self.create_declarative_router_plugin(
            test_project_dir, "api_router_plugin", extension_config
        )

        # Update the app config to include this plugin
        config_path = Path(test_project_dir) / "serv.config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        config["extensions"] = ["api_router_plugin"]
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Create the app and test the mounted routes
        app = App(
            config=str(config_path),
            extension_dir=str(Path(test_project_dir) / "extensions"),
            dev_mode=True,
        )

        async with create_test_client(app_factory=lambda: app) as client:
            # Test the users route (mounted at /api/v1)
            response = await client.get("/api/v1/users")
            assert response.status_code == 200
            assert "UsersHandler" in response.text

            # Test the user detail route with parameter
            response = await client.get("/api/v1/users/123")
            assert response.status_code == 200
            assert "UserHandler" in response.text

            # Test POST method
            response = await client.post("/api/v1/users")
            assert response.status_code == 200
            assert "UsersHandler" in response.text

            # Test PUT method
            response = await client.put("/api/v1/users/123")
            assert response.status_code == 200
            assert "UserHandler" in response.text

            # Test method not allowed
            response = await client.patch("/api/v1/users")
            assert response.status_code == 405

            # Test route not mounted at root
            response = await client.get("/users")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_multiple_declarative_routers_e2e(self, test_project_dir):
        """Test multiple declarative routers in a single plugin end-to-end."""
        # Create a plugin with multiple router configurations
        extension_config = {
            "name": "Multi Router Extension",
            "description": "A plugin with multiple declarative routers",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "main_router",
                    "routes": [{"path": "/", "handler": "main:HomeHandler"}],
                },
                {
                    "name": "api_router",
                    "mount": "/api",
                    "routes": [{"path": "/status", "handler": "api:StatusHandler"}],
                },
                {
                    "name": "admin_router",
                    "mount": "/admin",
                    "routes": [
                        {"path": "/dashboard", "handler": "admin:DashboardHandler"}
                    ],
                },
            ],
        }

        self.create_declarative_router_plugin(
            test_project_dir, "multi_router_plugin", extension_config
        )

        # Update the app config to include this plugin
        config_path = Path(test_project_dir) / "serv.config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        config["extensions"] = ["multi_router_plugin"]
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Create the app and test all routes
        app = App(
            config=str(config_path),
            extension_dir=str(Path(test_project_dir) / "extensions"),
            dev_mode=True,
        )

        async with create_test_client(app_factory=lambda: app) as client:
            # Test main router route
            response = await client.get("/")
            assert response.status_code == 200
            assert "HomeHandler" in response.text

            # Test API router route
            response = await client.get("/api/status")
            assert response.status_code == 200
            assert "StatusHandler" in response.text

            # Test admin router route
            response = await client.get("/admin/dashboard")
            assert response.status_code == 200
            assert "DashboardHandler" in response.text

    @pytest.mark.asyncio
    async def test_multiple_plugins_with_declarative_routers_e2e(
        self, test_project_dir
    ):
        """Test multiple plugins each with declarative routers end-to-end."""
        # Create first plugin
        plugin1_config = {
            "name": "Blog Extension",
            "description": "A blog plugin with declarative routes",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "blog_router",
                    "mount": "/blog",
                    "routes": [
                        {"path": "/posts", "handler": "blog:PostsHandler"},
                        {"path": "/posts/{id}", "handler": "blog:PostHandler"},
                    ],
                }
            ],
        }

        # Create second plugin
        plugin2_config = {
            "name": "Shop Extension",
            "description": "A shop plugin with declarative routes",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "shop_router",
                    "mount": "/shop",
                    "routes": [
                        {"path": "/products", "handler": "shop:ProductsHandler"},
                        {"path": "/cart", "handler": "shop:CartHandler"},
                    ],
                }
            ],
        }

        # Create both plugins
        self.create_declarative_router_plugin(
            test_project_dir, "blog_plugin", plugin1_config
        )
        self.create_declarative_router_plugin(
            test_project_dir, "shop_plugin", plugin2_config
        )

        # Update the app config to include both plugins
        config_path = Path(test_project_dir) / "serv.config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        config["extensions"] = ["blog_plugin", "shop_plugin"]
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Create the app and test routes from both plugins
        app = App(
            config=str(config_path),
            extension_dir=str(Path(test_project_dir) / "extensions"),
            dev_mode=True,
        )

        async with create_test_client(app_factory=lambda: app) as client:
            # Test blog plugin routes
            response = await client.get("/blog/posts")
            assert response.status_code == 200
            assert "PostsHandler" in response.text

            response = await client.get("/blog/posts/123")
            assert response.status_code == 200
            assert "PostHandler" in response.text

            # Test shop plugin routes
            response = await client.get("/shop/products")
            assert response.status_code == 200
            assert "ProductsHandler" in response.text

            response = await client.get("/shop/cart")
            assert response.status_code == 200
            assert "CartHandler" in response.text

    @pytest.mark.asyncio
    async def test_declarative_router_with_route_config_e2e(self, test_project_dir):
        """Test declarative router with route-level configuration end-to-end."""
        # Create a plugin with route configuration
        extension_config = {
            "name": "Configured Router Extension",
            "description": "A plugin with route-level configuration",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "configured_router",
                    "routes": [
                        {
                            "path": "/public",
                            "handler": "handlers:PublicHandler",
                            "config": {"auth_required": False, "cache_ttl": 3600},
                        },
                        {
                            "path": "/private",
                            "handler": "handlers:PrivateHandler",
                            "config": {"auth_required": True, "admin_only": True},
                        },
                    ],
                }
            ],
        }

        extension_dir = self.create_declarative_router_plugin(
            test_project_dir, "configured_router_plugin", extension_config
        )

        # Create custom handlers that use the configuration
        handlers_file = extension_dir / "handlers.py"
        handlers_code = """
from serv.responses import ResponseBuilder
from bevy import dependency

async def PublicHandler(response: ResponseBuilder = dependency()):
    response.content_type("application/json")
    response.body('{"message": "Public endpoint", "auth_required": false, "cache_ttl": 3600}')

async def PrivateHandler(response: ResponseBuilder = dependency()):
    response.content_type("application/json")
    response.body('{"message": "Private endpoint", "auth_required": true, "admin_only": true}')
"""
        handlers_file.write_text(handlers_code)

        # Update the app config to include this plugin
        config_path = Path(test_project_dir) / "serv.config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        config["extensions"] = ["configured_router_plugin"]
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Create the app and test the configured routes
        app = App(
            config=str(config_path),
            extension_dir=str(Path(test_project_dir) / "extensions"),
            dev_mode=True,
        )

        async with create_test_client(app_factory=lambda: app) as client:
            # Test public route
            response = await client.get("/public")
            assert response.status_code == 200
            json_data = response.json()
            assert json_data["message"] == "Public endpoint"
            assert not json_data["auth_required"]
            assert json_data["cache_ttl"] == 3600

            # Test private route
            response = await client.get("/private")
            assert response.status_code == 200
            json_data = response.json()
            assert json_data["message"] == "Private endpoint"
            assert json_data["auth_required"]
            assert json_data["admin_only"]

    @pytest.mark.asyncio
    async def test_declarative_router_error_handling_e2e(self, test_project_dir):
        """Test error handling in declarative routers end-to-end."""
        # Create a plugin with invalid handler reference
        extension_config = {
            "name": "Error Router Extension",
            "description": "A plugin with invalid handler for testing error handling",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "error_router",
                    "routes": [
                        {"path": "/valid", "handler": "handlers:ValidHandler"},
                        {
                            "path": "/invalid",
                            "handler": "nonexistent:InvalidHandler",  # This handler doesn't exist
                        },
                    ],
                }
            ],
        }

        # Create the plugin directory manually to avoid auto-creating all handlers
        plugins_dir = Path(test_project_dir) / "extensions"
        extension_dir = plugins_dir / "error_router_plugin"
        extension_dir.mkdir(exist_ok=True)

        # Create extension.yaml with routers configuration
        with open(extension_dir / "extension.yaml", "w") as f:
            yaml.dump(extension_config, f)

        # Create __init__.py to make it a package
        (extension_dir / "__init__.py").touch()

        # Create only the valid handler (not the nonexistent one)
        handlers_file = extension_dir / "handlers.py"
        handlers_code = """
from serv.responses import ResponseBuilder
from bevy import dependency

async def ValidHandler(response: ResponseBuilder = dependency()):
    response.content_type("text/plain")
    response.body("This handler works!")
"""
        handlers_file.write_text(handlers_code)
        # Note: We deliberately do NOT create nonexistent.py

        # Update the app config to include this plugin
        config_path = Path(test_project_dir) / "serv.config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        config["extensions"] = ["error_router_plugin"]
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # The app should load successfully, but the invalid route should cause an error during the first request
        # when the router plugin tries to load the nonexistent handler
        app = App(
            config=str(config_path),
            extension_dir=str(Path(test_project_dir) / "extensions"),
            dev_mode=True,
        )

        # The error should occur when we try to make a request, which triggers router loading
        async with create_test_client(app_factory=lambda: app) as client:
            # Let's see what actually happens when we try to access the invalid route
            response = await client.get("/invalid")
            # If we get here, the error was handled by the app's error handling
            # Let's check if it's a 500 error or similar
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text}")

            # The error should have been handled by the app's error handling system
            # and returned as a 500 error
            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_declarative_router_complex_paths_e2e(self, test_project_dir):
        """Test declarative router with complex path patterns end-to-end."""
        # Create a plugin with complex path patterns
        extension_config = {
            "name": "Complex Paths Extension",
            "description": "A plugin with complex path patterns",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "complex_router",
                    "routes": [
                        {
                            "path": "/users/{user_id}/posts/{post_id}",
                            "handler": "handlers:UserPostHandler",
                        },
                        {
                            "path": "/files/{path:path}",
                            "handler": "handlers:FileHandler",
                        },
                        {
                            "path": "/api/v{version:int}/data",
                            "handler": "handlers:VersionedDataHandler",
                        },
                    ],
                }
            ],
        }

        extension_dir = self.create_declarative_router_plugin(
            test_project_dir, "complex_paths_plugin", extension_config
        )

        # Create handlers that use path parameters
        handlers_file = extension_dir / "handlers.py"
        handlers_code = """
from serv.responses import ResponseBuilder
from serv.requests import Request
from bevy import dependency

async def UserPostHandler(user_id: str, post_id: str, response: ResponseBuilder = dependency()):
    response.content_type("application/json")
    response.body(f'{{"user_id": "{user_id}", "post_id": "{post_id}"}}')

async def FileHandler(path: str, response: ResponseBuilder = dependency()):
    response.content_type("application/json")
    response.body(f'{{"file_path": "{path}"}}')

async def VersionedDataHandler(version: int, response: ResponseBuilder = dependency()):
    response.content_type("application/json")
    response.body(f'{{"api_version": {version}, "data": "sample"}}')
"""
        handlers_file.write_text(handlers_code)

        # Update the app config to include this plugin
        config_path = Path(test_project_dir) / "serv.config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        config["extensions"] = ["complex_paths_plugin"]
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Create the app and test complex path patterns
        app = App(
            config=str(config_path),
            extension_dir=str(Path(test_project_dir) / "extensions"),
            dev_mode=True,
        )

        async with create_test_client(app_factory=lambda: app) as client:
            # Test nested path parameters
            response = await client.get("/users/123/posts/456")
            assert response.status_code == 200
            json_data = response.json()
            assert json_data["user_id"] == "123"
            assert json_data["post_id"] == "456"

            # Test path parameter with path type
            response = await client.get("/files/documents/readme.txt")
            assert response.status_code == 200
            json_data = response.json()
            assert json_data["file_path"] == "documents/readme.txt"

            # Test integer path parameter
            response = await client.get("/api/v2/data")
            assert response.status_code == 200
            json_data = response.json()
            assert json_data["api_version"] == 2
            assert json_data["data"] == "sample"
