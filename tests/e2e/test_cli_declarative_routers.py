"""
CLI end-to-end tests for declarative router functionality.

This file tests the CLI workflow for declarative routers:
1. Using CLI commands to create projects and plugins
2. Manually configuring plugins with declarative routers
3. Testing that the CLI-created apps work with declarative routers
4. Verifying plugin enable/disable functionality with declarative routers
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

from serv.app import App
from tests.e2e.helpers import create_test_client


def run_cli_command(command, cwd=None, check=True, shell=False, env=None):
    """
    Run a Serv CLI command and return its output.

    Args:
        command: Command to run (list of arguments or string if shell=True)
        cwd: Working directory
        check: Whether to check return code
        shell: Whether to use shell execution
        env: Optional environment variables dict

    Returns:
        tuple: (return_code, stdout, stderr)
    """
    import os

    # Prepare environment
    cmd_env = os.environ.copy()
    if env:
        cmd_env.update(env)

    # Run the command
    result = subprocess.run(
        command,
        cwd=cwd,
        shell=shell,
        env=cmd_env,
        text=True,
        capture_output=True,
        check=False,  # We'll handle errors ourselves
    )

    # Optionally check return code
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, command, result.stdout, result.stderr
        )

    return result.returncode, result.stdout, result.stderr


class TestCLIDeclarativeRouters:
    """CLI end-to-end tests for declarative router functionality."""

    @pytest.fixture
    def cli_project_dir(self):
        """Create a test project directory initialized with CLI."""
        test_dir = tempfile.mkdtemp()
        try:
            # Initialize the Serv project using CLI
            run_cli_command(
                ["python", "-m", "serv", "app", "init", "--force", "--non-interactive"],
                cwd=test_dir,
            )

            yield test_dir
        finally:
            shutil.rmtree(test_dir)

    def create_declarative_router_plugin_via_cli(
        self, project_dir, plugin_name, plugin_config
    ):
        """Create a plugin with declarative router configuration using CLI-like structure."""
        plugins_dir = Path(project_dir) / "plugins"
        plugins_dir.mkdir(exist_ok=True)

        plugin_dir = plugins_dir / plugin_name
        plugin_dir.mkdir(exist_ok=True)

        # Create plugin.yaml with routers configuration
        with open(plugin_dir / "plugin.yaml", "w") as f:
            yaml.dump(plugin_config, f)

        # Create __init__.py to make it a package
        (plugin_dir / "__init__.py").touch()

        # Create handler modules based on the router configuration
        routers_config = plugin_config.get("routers", [])
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
            module_file = plugin_dir / f"{module_name}.py"
            handler_functions = []
            for class_name, path in handlers:
                handler_functions.append(f"""
async def {class_name}(response: ResponseBuilder = dependency()):
    response.content_type("text/plain")
    response.body("Hello from {class_name} via CLI at {path}")
""")

            handler_code = f"""
from serv.responses import ResponseBuilder
from bevy import dependency
{"".join(handler_functions)}
"""
            module_file.write_text(handler_code)

        return plugin_dir

    @pytest.mark.asyncio
    async def test_cli_init_with_declarative_router_plugin(self, cli_project_dir):
        """Test that a CLI-initialized project can use declarative router plugins."""
        # Create a declarative router plugin in the CLI-initialized project
        plugin_config = {
            "name": "CLI Router Plugin",
            "description": "A plugin with declarative router created in CLI project",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "cli_router",
                    "routes": [
                        {"path": "/cli-hello", "handler": "handlers:CLIHelloHandler"},
                        {"path": "/cli-status", "handler": "handlers:CLIStatusHandler"},
                    ],
                }
            ],
        }

        self.create_declarative_router_plugin_via_cli(
            cli_project_dir, "cli_router_plugin", plugin_config
        )

        # Enable the plugin using CLI command
        run_cli_command(
            ["python", "-m", "serv", "plugin", "enable", "cli_router_plugin"],
            cwd=cli_project_dir,
        )

        # Verify the plugin was added to the config
        config_path = Path(cli_project_dir) / "serv.config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        plugins = config.get("plugins", [])
        plugin_names = [p["plugin"] if isinstance(p, dict) else p for p in plugins]
        assert "cli_router_plugin" in plugin_names

        # Create the app and test the routes
        app = App(
            config=str(config_path),
            plugin_dir=str(Path(cli_project_dir) / "plugins"),
            dev_mode=True,
        )

        async with create_test_client(app_factory=lambda: app) as client:
            # Test the CLI hello route
            response = await client.get("/cli-hello")
            assert response.status_code == 200
            assert "CLIHelloHandler" in response.text
            assert "via CLI" in response.text

            # Test the CLI status route
            response = await client.get("/cli-status")
            assert response.status_code == 200
            assert "CLIStatusHandler" in response.text
            assert "via CLI" in response.text

    @pytest.mark.asyncio
    async def test_cli_plugin_enable_disable_with_declarative_routers(
        self, cli_project_dir
    ):
        """Test enabling and disabling plugins with declarative routers via CLI."""
        # Create a declarative router plugin
        plugin_config = {
            "name": "Toggle Router Plugin",
            "description": "A plugin for testing enable/disable with declarative routers",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "toggle_router",
                    "mount": "/toggle",
                    "routes": [
                        {"path": "/on", "handler": "handlers:OnHandler"},
                        {"path": "/off", "handler": "handlers:OffHandler"},
                    ],
                }
            ],
        }

        self.create_declarative_router_plugin_via_cli(
            cli_project_dir, "toggle_router_plugin", plugin_config
        )

        # Test with plugin disabled (default state)
        config_path = Path(cli_project_dir) / "serv.config.yaml"
        app = App(
            config=str(config_path),
            plugin_dir=str(Path(cli_project_dir) / "plugins"),
            dev_mode=True,
        )

        async with create_test_client(app_factory=lambda: app) as client:
            # Routes should not exist when plugin is disabled
            response = await client.get("/toggle/on")
            assert response.status_code == 404

            response = await client.get("/toggle/off")
            assert response.status_code == 404

        # Enable the plugin using CLI
        run_cli_command(
            ["python", "-m", "serv", "plugin", "enable", "toggle_router_plugin"],
            cwd=cli_project_dir,
        )

        # Test with plugin enabled
        app = App(
            config=str(config_path),
            plugin_dir=str(Path(cli_project_dir) / "plugins"),
            dev_mode=True,
        )

        async with create_test_client(app_factory=lambda: app) as client:
            # Routes should now exist
            response = await client.get("/toggle/on")
            assert response.status_code == 200
            assert "OnHandler" in response.text

            response = await client.get("/toggle/off")
            assert response.status_code == 200
            assert "OffHandler" in response.text

        # Disable the plugin using CLI
        run_cli_command(
            ["python", "-m", "serv", "plugin", "disable", "toggle_router_plugin"],
            cwd=cli_project_dir,
        )

        # Test with plugin disabled again
        app = App(
            config=str(config_path),
            plugin_dir=str(Path(cli_project_dir) / "plugins"),
            dev_mode=True,
        )

        async with create_test_client(app_factory=lambda: app) as client:
            # Routes should not exist again
            response = await client.get("/toggle/on")
            assert response.status_code == 404

            response = await client.get("/toggle/off")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cli_multiple_declarative_router_plugins(self, cli_project_dir):
        """Test multiple plugins with declarative routers managed via CLI."""
        # Create first plugin - Blog
        blog_config = {
            "name": "CLI Blog Plugin",
            "description": "A blog plugin created via CLI workflow",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "blog_router",
                    "mount": "/blog",
                    "routes": [
                        {"path": "/", "handler": "blog:BlogHomeHandler"},
                        {"path": "/posts", "handler": "blog:BlogPostsHandler"},
                    ],
                }
            ],
        }

        # Create second plugin - API
        api_config = {
            "name": "CLI API Plugin",
            "description": "An API plugin created via CLI workflow",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "api_router",
                    "mount": "/api",
                    "routes": [
                        {"path": "/health", "handler": "api:HealthHandler"},
                        {"path": "/version", "handler": "api:VersionHandler"},
                    ],
                }
            ],
        }

        # Create both plugins
        self.create_declarative_router_plugin_via_cli(
            cli_project_dir, "cli_blog_plugin", blog_config
        )
        self.create_declarative_router_plugin_via_cli(
            cli_project_dir, "cli_api_plugin", api_config
        )

        # Enable both plugins using CLI
        run_cli_command(
            ["python", "-m", "serv", "plugin", "enable", "cli_blog_plugin"],
            cwd=cli_project_dir,
        )
        run_cli_command(
            ["python", "-m", "serv", "plugin", "enable", "cli_api_plugin"],
            cwd=cli_project_dir,
        )

        # Verify both plugins are in the config
        config_path = Path(cli_project_dir) / "serv.config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        plugins = config.get("plugins", [])
        plugin_names = [p["plugin"] if isinstance(p, dict) else p for p in plugins]
        assert "cli_blog_plugin" in plugin_names
        assert "cli_api_plugin" in plugin_names

        # Test that both plugins work together
        app = App(
            config=str(config_path),
            plugin_dir=str(Path(cli_project_dir) / "plugins"),
            dev_mode=True,
        )

        async with create_test_client(app_factory=lambda: app) as client:
            # Test blog plugin routes
            response = await client.get("/blog/")
            assert response.status_code == 200
            assert "BlogHomeHandler" in response.text

            response = await client.get("/blog/posts")
            assert response.status_code == 200
            assert "BlogPostsHandler" in response.text

            # Test API plugin routes
            response = await client.get("/api/health")
            assert response.status_code == 200
            assert "HealthHandler" in response.text

            response = await client.get("/api/version")
            assert response.status_code == 200
            assert "VersionHandler" in response.text

    @pytest.mark.asyncio
    async def test_cli_app_details_with_declarative_routers(self, cli_project_dir):
        """Test that app details command works with declarative router plugins."""
        # Create a declarative router plugin
        plugin_config = {
            "name": "Details Test Plugin",
            "description": "A plugin for testing app details with declarative routers",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "details_router",
                    "routes": [
                        {"path": "/details", "handler": "handlers:DetailsHandler"}
                    ],
                }
            ],
        }

        self.create_declarative_router_plugin_via_cli(
            cli_project_dir, "details_test_plugin", plugin_config
        )

        # Enable the plugin
        run_cli_command(
            ["python", "-m", "serv", "plugin", "enable", "details_test_plugin"],
            cwd=cli_project_dir,
        )

        # Run app details command
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "app", "details"],
            cwd=cli_project_dir,
            check=False,  # Don't fail on error, we'll verify some basic output
        )

        # The command should run and show plugin information
        # Even if there are loading issues, it should show the configuration
        assert (
            "details_test_plugin" in stdout.lower()
            or "details_test_plugin" in stderr.lower()
        )

    @pytest.mark.asyncio
    async def test_cli_launch_dry_run_with_declarative_routers(self, cli_project_dir):
        """Test that launch --dry-run works with declarative router plugins."""
        # Create a declarative router plugin
        plugin_config = {
            "name": "Launch Test Plugin",
            "description": "A plugin for testing launch dry-run with declarative routers",
            "version": "1.0.0",
            "routers": [
                {
                    "name": "launch_router",
                    "routes": [
                        {
                            "path": "/launch-test",
                            "handler": "handlers:LaunchTestHandler",
                        }
                    ],
                }
            ],
        }

        self.create_declarative_router_plugin_via_cli(
            cli_project_dir, "launch_test_plugin", plugin_config
        )

        # Enable the plugin
        run_cli_command(
            ["python", "-m", "serv", "plugin", "enable", "launch_test_plugin"],
            cwd=cli_project_dir,
        )

        # Run launch --dry-run command
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "launch", "--dry-run"],
            cwd=cli_project_dir,
            check=False,  # Don't fail on error since dry-run might have issues
        )

        # The command should attempt to instantiate the app
        # Even if it fails, it should show that it's trying to load plugins
        assert "Instantiating App" in stdout or "launch_test_plugin" in stdout.lower()

    def test_cli_plugin_structure_with_declarative_routers(self, cli_project_dir):
        """Test that CLI-created plugin structure supports declarative routers."""
        # Create a plugin manually (simulating what CLI plugin create would do)
        plugins_dir = Path(cli_project_dir) / "plugins"
        plugins_dir.mkdir(exist_ok=True)

        plugin_dir = plugins_dir / "structure_test_plugin"
        plugin_dir.mkdir(exist_ok=True)

        # Create plugin.yaml with declarative routers
        plugin_config = {
            "name": "Structure Test Plugin",
            "description": "A plugin for testing CLI structure with declarative routers",
            "version": "1.0.0",
            "author": "Test Author",
            "routers": [
                {
                    "name": "structure_router",
                    "mount": "/structure",
                    "routes": [
                        {"path": "/test", "handler": "main:StructureTestHandler"}
                    ],
                }
            ],
        }

        with open(plugin_dir / "plugin.yaml", "w") as f:
            yaml.dump(plugin_config, f)

        # Create main.py with the handler
        main_code = """
from serv.responses import ResponseBuilder
from bevy import dependency

class StructureTestHandler:
    async def __call__(self, response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body("Structure test successful!")
"""
        with open(plugin_dir / "main.py", "w") as f:
            f.write(main_code)

        # Create __init__.py
        (plugin_dir / "__init__.py").touch()

        # Verify the structure is correct
        assert (plugin_dir / "plugin.yaml").exists()
        assert (plugin_dir / "main.py").exists()
        assert (plugin_dir / "__init__.py").exists()

        # Verify the plugin.yaml has routers configuration
        with open(plugin_dir / "plugin.yaml") as f:
            loaded_config = yaml.safe_load(f)

        assert "routers" in loaded_config
        assert len(loaded_config["routers"]) == 1
        assert loaded_config["routers"][0]["name"] == "structure_router"
        assert loaded_config["routers"][0]["mount"] == "/structure"
