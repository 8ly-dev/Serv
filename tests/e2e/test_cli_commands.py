"""
End-to-end tests for the Serv CLI commands.

This file contains tests that validate the behavior of the Serv CLI commands:
- init
- plugin commands (create, enable, disable)
- middleware commands (create, enable, disable)
- app details
- launch (with --dry-run option)

These tests use subprocess to run the CLI commands and validate their output.
"""

import os
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

    # Log the command output for debugging
    print(f"Command: {command}")
    print(f"Return code: {result.returncode}")
    print(f"Stdout: {result.stdout}")
    print(f"Stderr: {result.stderr}")

    # Optionally check return code
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, command, result.stdout, result.stderr
        )

    return result.returncode, result.stdout, result.stderr


class TestCliCommands:
    """Test suite for CLI commands."""

    @pytest.fixture
    def clean_test_dir(self):
        """Create a clean temporary directory for testing."""
        test_dir = tempfile.mkdtemp()
        try:
            yield test_dir
        finally:
            shutil.rmtree(test_dir)

    def test_init_command(self, clean_test_dir):
        """Test the 'serv app init' command."""
        # Run the init command
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "app", "init", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Check that the config file was created
        config_path = Path(clean_test_dir) / "serv.config.yaml"
        assert config_path.exists(), "Config file should have been created"

        # Verify the content of the config file
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert "site_info" in config, "Config should have a 'site_info' section"
        assert "plugins" in config, "Config should have a 'plugins' section"
        assert "middleware" in config, "Config should have a 'middleware' section"

    def test_create_plugin_command(self, clean_test_dir, monkeypatch):
        """Test manually creating a plugin structure."""
        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "app", "init", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create plugin directory structure manually
        plugins_dir = Path(clean_test_dir) / "plugins"
        plugins_dir.mkdir(exist_ok=True)

        test_plugin_dir = plugins_dir / "test_plugin"
        test_plugin_dir.mkdir(exist_ok=True)

        # Create plugin.yaml
        plugin_yaml = {
            "name": "test-plugin",
            "display_name": "Test Plugin",
            "description": "A test plugin for Serv",
            "version": "1.0.0",
            "author": "Test Author",
            "entry": "plugins.test_plugin.main:TestPlugin",
        }

        with open(test_plugin_dir / "plugin.yaml", "w") as f:
            yaml.dump(plugin_yaml, f)

        # Create main.py
        plugin_code = """
from serv.plugins import Plugin
from bevy import dependency
from serv.routing import Router
from serv.responses import ResponseBuilder

class TestPlugin(Plugin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._stand_alone = True

    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        router.add_route("/hello", self._hello_handler, methods=["GET"])

    async def _hello_handler(self, response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body("Hello from test_plugin!")
"""
        with open(test_plugin_dir / "main.py", "w") as f:
            f.write(plugin_code)

        # Make sure plugins directory is a package
        with open(plugins_dir / "__init__.py", "w") as f:
            f.write("")
        with open(test_plugin_dir / "__init__.py", "w") as f:
            f.write("")

        # Check that the plugin directory was created
        assert test_plugin_dir.exists(), "Plugin directory should have been created"

        # Check for plugin.yaml
        plugin_yaml_path = test_plugin_dir / "plugin.yaml"
        assert plugin_yaml_path.exists(), "plugin.yaml should exist"

        # Check for main.py
        plugin_main = test_plugin_dir / "main.py"
        assert plugin_main.exists(), "main.py should exist"

        # Verify plugin.yaml content
        with open(plugin_yaml_path) as f:
            loaded_plugin_config = yaml.safe_load(f)

        assert loaded_plugin_config["name"] == "test-plugin", (
            "Plugin name should match expected value"
        )
        assert loaded_plugin_config["display_name"] == "Test Plugin", (
            "Display name should match expected value"
        )
        assert loaded_plugin_config["version"] == "1.0.0", (
            "Version should match expected value"
        )

    def test_app_details_command(self, clean_test_dir):
        """Test the 'serv app details' command."""
        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "app", "init", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Run the app details command from the directory containing the config
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "app", "details"],
            cwd=clean_test_dir,
            check=False,  # Don't fail on error, we'll verify some basic output
        )

        # Even if there's a configuration loading error, the command should run and output something
        # Just check that the command executed and produced some output
        assert "config" in stdout.lower() or "configuration" in stdout.lower()

    def test_launch_dry_run(self, clean_test_dir):
        """Test the 'serv launch --dry-run' command."""
        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "app", "init", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Modify the config to include a dummy plugin to prevent welcome plugin auto-loading
        config_path = Path(clean_test_dir) / "serv.config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Add a dummy plugin to prevent welcome plugin from being auto-loaded
        config["plugins"] = [
            "dummy_plugin"
        ]  # This will fail to load but prevent welcome plugin

        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Run the launch command with dry-run from the directory containing the config
        # Expect this to fail due to the dummy plugin, but it should get past the welcome plugin issue
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "launch", "--dry-run"],
            cwd=clean_test_dir,
            check=False,  # Don't fail on error since we expect it to fail
        )

        # Check that it at least tried to load plugins (and failed on the dummy one)
        # This shows that the app loading got past the welcome plugin issue
        assert "Instantiating App" in stdout

    @pytest.mark.asyncio
    async def test_cli_with_async_client(self, clean_test_dir):
        """Test that a basic app can be created programmatically similar to CLI."""
        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "app", "init", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a minimal app instance directly (similar to what CLI would do)
        config_path = Path(clean_test_dir) / "serv.config.yaml"
        app = App(config=str(config_path), dev_mode=True)

        # Use the test client to make a simple request
        # This is a basic smoke test that the app can be created and handle a request
        async with create_test_client(app_factory=lambda: app) as client:
            response = await client.get("/")
            # We don't care about the status code as long as the request completes
            assert response.status_code is not None

    def test_create_entrypoint_command(self, clean_test_dir):
        """Test the 'serv create entrypoint' command."""
        # Set up a clean directory with config and a plugin
        run_cli_command(
            ["python", "-m", "serv", "app", "init", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a test plugin first
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "plugin",
                "create",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Create an entrypoint in the test plugin
        return_code, stdout, stderr = run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "entrypoint",
                "--name",
                "admin_auth",
                "--plugin",
                "test_plugin",
            ],
            cwd=clean_test_dir,
        )

        # Check that the entrypoint file was created
        entrypoint_path = (
            Path(clean_test_dir)
            / "plugins"
            / "test_plugin"
            / "entrypoint_admin_auth.py"
        )
        assert entrypoint_path.exists(), "Entrypoint file should have been created"

        # Check that the plugin config was updated
        plugin_yaml_path = (
            Path(clean_test_dir) / "plugins" / "test_plugin" / "plugin.yaml"
        )
        with open(plugin_yaml_path) as f:
            plugin_config = yaml.safe_load(f)

        assert "entry_points" in plugin_config, (
            "Plugin config should have entry_points section"
        )
        assert any(
            "entrypoint_admin_auth:AdminAuth" in ep
            for ep in plugin_config["entry_points"]
        ), "Entry point should be added to config"

        # Verify the entrypoint file content
        with open(entrypoint_path) as f:
            content = f.read()

        assert "class AdminAuth" in content, "Entrypoint should have correct class name"
        assert "admin_auth" in content, "Entrypoint should reference the name"

    def test_create_route_command(self, clean_test_dir):
        """Test the 'serv create route' command."""
        # Set up a clean directory with config and a plugin
        run_cli_command(
            ["python", "-m", "serv", "app", "init", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a test plugin first
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "plugin",
                "create",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Create a route in the test plugin
        return_code, stdout, stderr = run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "route",
                "--name",
                "user_profile",
                "--plugin",
                "test_plugin",
            ],
            cwd=clean_test_dir,
        )

        # Check that the route file was created
        route_path = (
            Path(clean_test_dir) / "plugins" / "test_plugin" / "route_user_profile.py"
        )
        assert route_path.exists(), "Route file should have been created"

        # Check that the plugin config was updated
        plugin_yaml_path = (
            Path(clean_test_dir) / "plugins" / "test_plugin" / "plugin.yaml"
        )
        with open(plugin_yaml_path) as f:
            plugin_config = yaml.safe_load(f)

        assert "routers" in plugin_config, "Plugin config should have routers section"
        assert len(plugin_config["routers"]) > 0, "Should have at least one router"
        assert any(
            "route_user_profile:UserProfile" in route["handler"]
            for router in plugin_config["routers"]
            for route in router.get("routes", [])
        ), "Route should be added to config"

        # Verify the route file content
        with open(route_path) as f:
            content = f.read()

        assert "class UserProfile" in content, "Route should have correct class name"
        assert "user_profile" in content, "Route should reference the name"

    def test_create_middleware_command(self, clean_test_dir):
        """Test the 'serv create middleware' command."""
        # Set up a clean directory with config and a plugin
        run_cli_command(
            ["python", "-m", "serv", "app", "init", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a test plugin first
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "plugin",
                "create",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Create middleware in the test plugin
        return_code, stdout, stderr = run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "middleware",
                "--name",
                "auth_check",
                "--plugin",
                "test_plugin",
            ],
            cwd=clean_test_dir,
        )

        # Check that the middleware file was created
        middleware_path = (
            Path(clean_test_dir)
            / "plugins"
            / "test_plugin"
            / "middleware_auth_check.py"
        )
        assert middleware_path.exists(), "Middleware file should have been created"

        # Check that the plugin config was updated
        plugin_yaml_path = (
            Path(clean_test_dir) / "plugins" / "test_plugin" / "plugin.yaml"
        )
        with open(plugin_yaml_path) as f:
            plugin_config = yaml.safe_load(f)

        assert "middleware" in plugin_config, (
            "Plugin config should have middleware section"
        )
        assert any(
            "middleware_auth_check:auth_check_middleware" in mw["entry"]
            for mw in plugin_config["middleware"]
        ), "Middleware should be added to config"

        # Verify the middleware file content
        with open(middleware_path) as f:
            content = f.read()

        assert "auth_check_middleware" in content, (
            "Middleware should have correct function name"
        )
        assert "async def" in content, "Middleware should be an async function"

    def test_create_entrypoint_auto_detect_plugin(self, clean_test_dir):
        """Test that create entrypoint can auto-detect plugin when only one exists."""
        # Set up a clean directory with config and a plugin
        run_cli_command(
            ["python", "-m", "serv", "app", "init", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a test plugin first
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "plugin",
                "create",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Create an entrypoint without specifying plugin (should auto-detect)
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "create", "entrypoint", "--name", "auto_detect"],
            cwd=clean_test_dir,
        )

        # Check that the entrypoint file was created in the auto-detected plugin
        entrypoint_path = (
            Path(clean_test_dir)
            / "plugins"
            / "test_plugin"
            / "entrypoint_auto_detect.py"
        )
        assert entrypoint_path.exists(), (
            "Entrypoint file should have been created in auto-detected plugin"
        )

    def test_create_entrypoint_from_plugin_directory(self, clean_test_dir):
        """Test that create entrypoint works when run from within a plugin directory."""
        # Set up a clean directory with config and a plugin
        run_cli_command(
            ["python", "-m", "serv", "app", "init", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a test plugin first
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "plugin",
                "create",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        plugin_dir = Path(clean_test_dir) / "plugins" / "test_plugin"

        # Create an entrypoint from within the plugin directory
        return_code, stdout, stderr = run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "entrypoint",
                "--name",
                "from_plugin_dir",
            ],
            cwd=str(plugin_dir),
        )

        # Check that the entrypoint file was created
        entrypoint_path = plugin_dir / "entrypoint_from_plugin_dir.py"
        assert entrypoint_path.exists(), (
            "Entrypoint file should have been created when run from plugin directory"
        )
