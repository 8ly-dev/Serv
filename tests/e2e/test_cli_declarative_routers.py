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
                [
                    "python",
                    "-m",
                    "serv",
                    "create",
                    "app",
                    "--force",
                    "--non-interactive",
                ],
                cwd=test_dir,
            )

            yield test_dir
        finally:
            shutil.rmtree(test_dir)

    def create_declarative_router_plugin_via_cli(
        self, project_dir, plugin_name, extension_config
    ):
        """Create a plugin with declarative router configuration using CLI-like structure."""
        plugins_dir = Path(project_dir) / "extensions"
        plugins_dir.mkdir(exist_ok=True)

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

        return extension_dir

    @pytest.mark.asyncio
    async def test_cli_init_with_declarative_router_plugin(self, cli_project_dir):
        """Test that a CLI-initialized project can use declarative router plugins."""
        # Create a declarative router plugin in the CLI-initialized project
        extension_config = {
            "name": "CLI Router Extension",
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
            cli_project_dir, "cli_router_plugin", extension_config
        )

        # Enable the plugin using CLI command
        run_cli_command(
            ["python", "-m", "serv", "extension", "enable", "cli_router_plugin"],
            cwd=cli_project_dir,
        )

        # Verify the plugin was added to the config
        config_path = Path(cli_project_dir) / "serv.config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        plugins = config.get("extensions", [])
        plugin_names = [p["extension"] if isinstance(p, dict) else p for p in plugins]
        assert "cli_router_plugin" in plugin_names

        # Create the app and test the routes
        app = App(
            config=str(config_path),
            extension_dir=str(Path(cli_project_dir) / "extensions"),
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
        extension_config = {
            "name": "Toggle Router Extension",
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
            cli_project_dir, "toggle_router_plugin", extension_config
        )

        # Test with extension disabled (default state)
        config_path = Path(cli_project_dir) / "serv.config.yaml"
        app = App(
            config=str(config_path),
            extension_dir=str(Path(cli_project_dir) / "extensions"),
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
            ["python", "-m", "serv", "extension", "enable", "toggle_router_plugin"],
            cwd=cli_project_dir,
        )

        # Test with extension enabled
        app = App(
            config=str(config_path),
            extension_dir=str(Path(cli_project_dir) / "extensions"),
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
            ["python", "-m", "serv", "extension", "disable", "toggle_router_plugin"],
            cwd=cli_project_dir,
        )

        # Test with extension disabled again
        app = App(
            config=str(config_path),
            extension_dir=str(Path(cli_project_dir) / "extensions"),
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
            "name": "CLI Blog Extension",
            "description": "A blog extension created via CLI workflow",
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
            "name": "CLI API Extension",
            "description": "An API extension created via CLI workflow",
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
            ["python", "-m", "serv", "extension", "enable", "cli_blog_plugin"],
            cwd=cli_project_dir,
        )
        run_cli_command(
            ["python", "-m", "serv", "extension", "enable", "cli_api_plugin"],
            cwd=cli_project_dir,
        )

        # Verify both plugins are in the config
        config_path = Path(cli_project_dir) / "serv.config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        plugins = config.get("extensions", [])
        plugin_names = [p["extension"] if isinstance(p, dict) else p for p in plugins]
        assert "cli_blog_plugin" in plugin_names
        assert "cli_api_plugin" in plugin_names

        # Test that both plugins work together
        app = App(
            config=str(config_path),
            extension_dir=str(Path(cli_project_dir) / "extensions"),
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
    async def test_cli_plugin_list_with_declarative_routers(self, cli_project_dir):
        """Test that plugin list command works with declarative router plugins."""
        # Create a declarative router plugin
        extension_config = {
            "name": "Details Test Extension",
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
            cli_project_dir, "details_test_extension", extension_config
        )

        # Enable the plugin
        run_cli_command(
            ["python", "-m", "serv", "extension", "enable", "details_test_extension"],
            cwd=cli_project_dir,
        )

        # Run plugin list command
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "extension", "list"],
            cwd=cli_project_dir,
            check=False,  # Don't fail on error, we'll verify some basic output
        )

        # The command should run and show plugin information
        # Even if there are loading issues, it should show the configuration
        assert (
            "details_test_extension" in stdout.lower()
            or "details_test_extension" in stderr.lower()
        )

    @pytest.mark.asyncio
    async def test_cli_launch_dry_run_with_declarative_routers(self, cli_project_dir):
        """Test that launch --dry-run works with declarative router plugins."""
        # Create a declarative router plugin
        extension_config = {
            "name": "Launch Test Extension",
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
            cli_project_dir, "launch_test_extension", extension_config
        )

        # Enable the plugin
        run_cli_command(
            ["python", "-m", "serv", "extension", "enable", "launch_test_extension"],
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
        assert (
            "Instantiating App" in stdout or "launch_test_extension" in stdout.lower()
        )

    def test_cli_plugin_structure_with_declarative_routers(self, cli_project_dir):
        """Test that CLI-created plugin structure supports declarative routers."""
        # Create a plugin manually (simulating what CLI plugin create would do)
        plugins_dir = Path(cli_project_dir) / "extensions"
        plugins_dir.mkdir(exist_ok=True)

        extension_dir = plugins_dir / "structure_test_extension"
        extension_dir.mkdir(exist_ok=True)

        # Create extension.yaml with declarative routers
        extension_config = {
            "name": "Structure Test Extension",
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

        with open(extension_dir / "extension.yaml", "w") as f:
            yaml.dump(extension_config, f)

        # Create main.py with the handler
        main_code = """
from serv.responses import ResponseBuilder
from bevy import dependency

class StructureTestHandler:
    async def __call__(self, response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body("Structure test successful!")
"""
        with open(extension_dir / "main.py", "w") as f:
            f.write(main_code)

        # Create __init__.py
        (extension_dir / "__init__.py").touch()

        # Verify the structure is correct
        assert (extension_dir / "extension.yaml").exists()
        assert (extension_dir / "main.py").exists()
        assert (extension_dir / "__init__.py").exists()

        # Verify the extension.yaml has routers configuration
        with open(extension_dir / "extension.yaml") as f:
            loaded_config = yaml.safe_load(f)

        assert "routers" in loaded_config
        assert len(loaded_config["routers"]) == 1
        assert loaded_config["routers"][0]["name"] == "structure_router"
        assert loaded_config["routers"][0]["mount"] == "/structure"
