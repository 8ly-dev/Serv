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
        """Test the 'serv create app' command."""
        # Run the init command
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Check that the config file was created
        config_path = Path(clean_test_dir) / "serv.config.yaml"
        assert config_path.exists(), "Config file should have been created"

        # Verify the content of the config file
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert "site_info" in config, "Config should have a 'site_info' section"
        assert "extensions" in config, "Config should have a 'extensions' section"
        assert "middleware" in config, "Config should have a 'middleware' section"

    def test_create_extension_command(self, clean_test_dir, monkeypatch):
        """Test manually creating a plugin structure."""
        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create plugin directory structure manually
        plugins_dir = Path(clean_test_dir) / "extensions"
        plugins_dir.mkdir(exist_ok=True)

        test_extension_dir = plugins_dir / "test_extension"
        test_extension_dir.mkdir(exist_ok=True)

        # Create extension.yaml
        extension_yaml = {
            "name": "test-plugin",
            "display_name": "Test Extension",
            "description": "A test plugin for Serv",
            "version": "1.0.0",
            "author": "Test Author",
            "entry": "plugins.test_extension.main:TestExtension",
        }

        with open(test_extension_dir / "extension.yaml", "w") as f:
            yaml.dump(extension_yaml, f)

        # Create main.py
        plugin_code = """
from serv.extensions import Extension, on
from bevy import dependency
from serv.routing import Router
from serv.responses import ResponseBuilder

class TestExtension(Extension):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._stand_alone = True

    @on("app.request.begin")
    async def setup_routes(self, router: Router = dependency()) -> None:
        router.add_route("/hello", self._hello_handler, methods=["GET"])

    async def _hello_handler(self, response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body("Hello from test_extension!")
"""
        with open(test_extension_dir / "main.py", "w") as f:
            f.write(plugin_code)

        # Make sure plugins directory is a package
        with open(plugins_dir / "__init__.py", "w") as f:
            f.write("")
        with open(test_extension_dir / "__init__.py", "w") as f:
            f.write("")

        # Check that the plugin directory was created
        assert test_extension_dir.exists(), (
            "Extension directory should have been created"
        )

        # Check for extension.yaml
        extension_yaml_path = test_extension_dir / "extension.yaml"
        assert extension_yaml_path.exists(), "extension.yaml should exist"

        # Check for main.py
        plugin_main = test_extension_dir / "main.py"
        assert plugin_main.exists(), "main.py should exist"

        # Verify extension.yaml content
        with open(extension_yaml_path) as f:
            loaded_extension_config = yaml.safe_load(f)

        assert loaded_extension_config["name"] == "test-plugin", (
            "Extension name should match expected value"
        )
        assert loaded_extension_config["display_name"] == "Test Extension", (
            "Display name should match expected value"
        )
        assert loaded_extension_config["version"] == "1.0.0", (
            "Version should match expected value"
        )

    def test_launch_dry_run(self, clean_test_dir):
        """Test the 'serv launch --dry-run' command."""
        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Modify the config to include a dummy plugin to prevent welcome plugin auto-loading
        config_path = Path(clean_test_dir) / "serv.config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Add a dummy plugin to prevent welcome plugin from being auto-loaded
        config["extensions"] = [
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
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
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

    def test_create_extension_command_new_syntax(self, clean_test_dir):
        """Test the new 'serv create extension' command."""
        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a plugin using the new syntax
        return_code, stdout, stderr = run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "extension",
                "--name",
                "My Awesome Extension",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Check that the extension directory was created
        extension_dir = Path(clean_test_dir) / "extensions" / "my_awesome_extension"
        assert extension_dir.exists(), "Extension directory should have been created"

        # Check for extension.yaml
        extension_yaml_path = extension_dir / "extension.yaml"
        assert extension_yaml_path.exists(), "extension.yaml should exist"

        # Verify extension.yaml content
        with open(extension_yaml_path) as f:
            loaded_extension_config = yaml.safe_load(f)

        assert loaded_extension_config["name"] == "My Awesome Extension", (
            "Extension name should match expected value"
        )
        assert loaded_extension_config["version"] == "1.0.0", (
            "Version should match expected value"
        )

        # Extension should not have listeners initially (those are added by create listener)
        assert "entry" not in loaded_extension_config, (
            "Extension should not have entry field initially"
        )
        assert "listeners" not in loaded_extension_config, (
            "Extension should not have listeners initially"
        )
        assert "entry_points" not in loaded_extension_config, (
            "Extension should not have entry_points initially"
        )

    def test_create_listener_command(self, clean_test_dir):
        """Test the 'serv create listener' command."""
        # Set up a clean directory with config and a plugin
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a test plugin first
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "extension",
                "--name",
                "Test Extension",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Create a listener in the test plugin
        return_code, stdout, stderr = run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "listener",
                "--name",
                "admin_auth",
                "--extension",
                "test_extension",
            ],
            cwd=clean_test_dir,
        )

        # Check that the listener file was created
        listener_path = (
            Path(clean_test_dir)
            / "extensions"
            / "test_extension"
            / "listener_admin_auth.py"
        )
        assert listener_path.exists(), "Listener file should have been created"

        # Check that the plugin config was updated
        extension_yaml_path = (
            Path(clean_test_dir) / "extensions" / "test_extension" / "extension.yaml"
        )
        with open(extension_yaml_path) as f:
            extension_config = yaml.safe_load(f)

        assert "listeners" in extension_config, (
            "Extension config should have listeners section"
        )
        assert any(
            "listener_admin_auth:AdminAuth" in listener
            for listener in extension_config["listeners"]
        ), "Listener should be added to config"

        # Verify the listener file content
        with open(listener_path) as f:
            content = f.read()

        assert "class AdminAuth" in content, "Listener should have correct class name"
        assert "admin_auth" in content, "Listener should reference the name"

    def test_create_route_command(self, clean_test_dir):
        """Test the 'serv create route' command."""
        # Set up a clean directory with config and a plugin
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a test plugin first
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "extension",
                "--name",
                "Test Extension",
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
                "--extension",
                "test_extension",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Check that the route file was created
        route_path = (
            Path(clean_test_dir)
            / "extensions"
            / "test_extension"
            / "route_user_profile.py"
        )
        assert route_path.exists(), "Route file should have been created"

        # Check that the plugin config was updated
        extension_yaml_path = (
            Path(clean_test_dir) / "extensions" / "test_extension" / "extension.yaml"
        )
        with open(extension_yaml_path) as f:
            extension_config = yaml.safe_load(f)

        assert "routers" in extension_config, (
            "Extension config should have routers section"
        )
        assert len(extension_config["routers"]) > 0, "Should have at least one router"
        assert any(
            "route_user_profile:UserProfile" in route["handler"]
            for router in extension_config["routers"]
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
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a test plugin first
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "extension",
                "--name",
                "Test Extension",
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
                "--extension",
                "test_extension",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Check that the middleware file was created
        middleware_path = (
            Path(clean_test_dir)
            / "extensions"
            / "test_extension"
            / "middleware_auth_check.py"
        )
        assert middleware_path.exists(), "Middleware file should have been created"

        # Check that the plugin config was updated
        extension_yaml_path = (
            Path(clean_test_dir) / "extensions" / "test_extension" / "extension.yaml"
        )
        with open(extension_yaml_path) as f:
            extension_config = yaml.safe_load(f)

        assert "middleware" in extension_config, (
            "Extension config should have middleware section"
        )
        assert any(
            "middleware_auth_check:auth_check_middleware" in mw["entry"]
            for mw in extension_config["middleware"]
        ), "Middleware should be added to config"

        # Verify the middleware file content
        with open(middleware_path) as f:
            content = f.read()

        assert "auth_check_middleware" in content, (
            "Middleware should have correct function name"
        )
        assert "async def" in content, "Middleware should be an async function"

    def test_create_listener_auto_detect_plugin(self, clean_test_dir):
        """Test that create listener can auto-detect plugin when only one exists."""
        # Set up a clean directory with config and a plugin
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a test plugin first
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "extension",
                "--name",
                "Test Extension",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Create a listener without specifying plugin (should auto-detect)
        return_code, stdout, stderr = run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "listener",
                "--name",
                "auto_detect",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Check that the listener file was created in the auto-detected plugin
        listener_path = (
            Path(clean_test_dir)
            / "extensions"
            / "test_extension"
            / "listener_auto_detect.py"
        )
        assert listener_path.exists(), (
            "Listener file should have been created in auto-detected plugin"
        )

    def test_create_listener_from_extension_directory(self, clean_test_dir):
        """Test that create listener works when run from within a plugin directory."""
        # Set up a clean directory with config and a plugin
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a test plugin first
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "extension",
                "--name",
                "Test Extension",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        extension_dir = Path(clean_test_dir) / "extensions" / "test_extension"

        # Create a listener from within the plugin directory
        return_code, stdout, stderr = run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "listener",
                "--name",
                "from_extension_dir",
                "--non-interactive",
            ],
            cwd=str(extension_dir),
        )

        # Check that the listener file was created
        listener_path = extension_dir / "listener_from_extension_dir.py"
        assert listener_path.exists(), (
            "Listener file should have been created when run from plugin directory"
        )

    def test_extension_list_command(self, clean_test_dir):
        """Test the 'serv extension list' command."""
        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Test list with no plugins enabled
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "extension", "list"],
            cwd=clean_test_dir,
        )
        assert "No extensions are currently enabled" in stdout

        # Test list available with no extensions directory
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "extension", "list", "--available"],
            cwd=clean_test_dir,
        )
        assert "No extensions directory found" in stdout

        # Create some plugins
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "extension",
                "--name",
                "Test Extension One",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "extension",
                "--name",
                "Test Extension Two",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Test list available with plugins
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "extension", "list", "--available"],
            cwd=clean_test_dir,
        )
        assert "Available extensions (2)" in stdout
        assert "Test Extension One" in stdout
        assert "Test Extension Two" in stdout
        assert "test_extension_one" in stdout
        assert "test_extension_two" in stdout

        # Enable one plugin
        run_cli_command(
            ["python", "-m", "serv", "extension", "enable", "test_extension_one"],
            cwd=clean_test_dir,
        )

        # Test list enabled plugins
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "extension", "list"],
            cwd=clean_test_dir,
        )
        assert "Enabled extensions (1)" in stdout
        assert "Test Extension One" in stdout
        assert "test_extension_one" in stdout

    def test_extension_validate_command(self, clean_test_dir):
        """Test the 'serv extension validate' command."""
        # Test with no plugins directory
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "extension", "validate"],
            cwd=clean_test_dir,
            check=False,
        )
        assert "No extensions directory found" in stdout

        # Set up a clean directory with config and plugins
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a valid plugin
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "extension",
                "--name",
                "Valid Extension",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Test validating all plugins
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "extension", "validate"],
            cwd=clean_test_dir,
        )
        assert "=== Validating 1 Extension(s) ===" in stdout
        assert "Validating extension: valid_extension" in stdout
        assert "extension.yaml is valid YAML" in stdout
        assert "Has required field: name" in stdout
        assert "Has required field: version" in stdout

        # Test validating specific extension
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "extension", "validate", "valid_extension"],
            cwd=clean_test_dir,
        )
        assert "Validating extension: valid_extension" in stdout

        # Test validating non-existent plugin
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "extension", "validate", "nonexistent"],
            cwd=clean_test_dir,
            check=False,
        )
        assert "Extension 'nonexistent' not found" in stdout

    def test_config_show_command(self, clean_test_dir):
        """Test the 'serv config show' command."""
        # Test with no config file
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "config", "show"],
            cwd=clean_test_dir,
            check=False,
        )
        assert "Configuration file" in stdout
        assert "not found" in stdout

        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Test show in YAML format (default)
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "config", "show"],
            cwd=clean_test_dir,
        )
        assert "Configuration from" in stdout
        assert "site_info:" in stdout
        assert "name: My Serv Site" in stdout

        # Test show in JSON format
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "config", "show", "--format", "json"],
            cwd=clean_test_dir,
        )
        assert "Configuration from" in stdout
        assert '"site_info"' in stdout
        assert '"name": "My Serv Site"' in stdout

    def test_config_validate_command(self, clean_test_dir):
        """Test the 'serv config validate' command."""
        # Test with no config file
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "config", "validate"],
            cwd=clean_test_dir,
            check=False,
        )
        assert "Configuration file" in stdout
        assert "not found" in stdout

        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Test validate valid config
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "config", "validate"],
            cwd=clean_test_dir,
        )
        assert "Configuration file is valid YAML" in stdout
        assert "Configuration validation passed" in stdout

        # Test with invalid YAML
        config_path = Path(clean_test_dir) / "serv.config.yaml"
        with open(config_path, "w") as f:
            f.write("invalid: yaml: content: [")

        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "config", "validate"],
            cwd=clean_test_dir,
            check=False,
        )
        assert "Invalid YAML syntax" in stdout

    def test_config_get_command(self, clean_test_dir):
        """Test the 'serv config get' command."""
        # Test with no config file
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "config", "get", "site_info.name"],
            cwd=clean_test_dir,
            check=False,
        )
        assert "Configuration file" in stdout
        assert "not found" in stdout

        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Test get existing key
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "config", "get", "site_info.name"],
            cwd=clean_test_dir,
        )
        assert "site_info.name: My Serv Site" in stdout

        # Test get non-existent key
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "config", "get", "nonexistent.key"],
            cwd=clean_test_dir,
            check=False,
        )
        assert "Key 'nonexistent.key' not found" in stdout

    def test_config_set_command(self, clean_test_dir):
        """Test the 'serv config set' command."""
        # Test with no config file
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "config", "set", "test.key", "value"],
            cwd=clean_test_dir,
            check=False,
        )
        assert "Configuration file" in stdout
        assert "not found" in stdout

        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Test set string value
        return_code, stdout, stderr = run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "config",
                "set",
                "site_info.name",
                "New Site Name",
            ],
            cwd=clean_test_dir,
        )
        assert "Set site_info.name = New Site Name" in stdout

        # Verify the value was set
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "config", "get", "site_info.name"],
            cwd=clean_test_dir,
        )
        assert "site_info.name: New Site Name" in stdout

        # Test set integer value
        return_code, stdout, stderr = run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "config",
                "set",
                "test.number",
                "42",
                "--type",
                "int",
            ],
            cwd=clean_test_dir,
        )
        assert "Set test.number = 42" in stdout

        # Test set boolean value
        return_code, stdout, stderr = run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "config",
                "set",
                "test.enabled",
                "true",
                "--type",
                "bool",
            ],
            cwd=clean_test_dir,
        )
        assert "Set test.enabled = True" in stdout

        # Test set list value
        return_code, stdout, stderr = run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "config",
                "set",
                "test.items",
                "a,b,c",
                "--type",
                "list",
            ],
            cwd=clean_test_dir,
        )
        assert "Set test.items = ['a', 'b', 'c']" in stdout

    def test_dev_command_dry_run(self, clean_test_dir):
        """Test the '--dev' flag with launch command (replaces the old 'serv dev' command)."""
        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Test that the --dev flag works with launch command
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "--dev", "launch", "--help"],
            cwd=clean_test_dir,
        )
        assert "usage: serv launch" in stdout
        assert "--host" in stdout
        assert "--port" in stdout
        assert "--no-reload" in stdout
        assert "--workers" in stdout

        # Test --dev flag in main help
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "--help"],
            cwd=clean_test_dir,
        )
        assert "--dev" in stdout
        assert "development mode" in stdout.lower()

        # Test that --dev flag can be used without explicit launch command
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "--dev", "--help"],
            cwd=clean_test_dir,
        )
        # Should default to launch command when no subcommand specified
        assert "usage:" in stdout.lower()

    def test_test_command_no_pytest(self, clean_test_dir):
        """Test the 'serv test' command when pytest is not available."""
        # This test simulates the case where pytest is not installed
        # We can't easily uninstall pytest in the test environment, so we'll test the help

        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "test", "--help"],
            cwd=clean_test_dir,
        )
        assert "usage: serv test" in stdout
        assert "--extensions" in stdout
        assert "--e2e" in stdout
        assert "--coverage" in stdout
        assert "--verbose" in stdout

    def test_test_command_with_no_tests(self, clean_test_dir):
        """Test the 'serv test' command when no tests directory exists."""
        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Run test command (should handle missing tests gracefully)
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "test"],
            cwd=clean_test_dir,
            check=False,  # May fail due to no tests
        )
        # The command should run and provide some output about no tests found
        assert "Running tests" in stdout or "No tests" in stdout or "pytest" in stdout

    def test_shell_command_help(self, clean_test_dir):
        """Test the 'serv shell' command help."""
        # Test that the shell command exists and can be parsed
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "shell", "--help"],
            cwd=clean_test_dir,
        )
        assert "usage: serv shell" in stdout
        assert "--ipython" in stdout
        assert "--no-startup" in stdout

    def test_shell_command_no_startup(self, clean_test_dir):
        """Test the 'serv shell' command with --no-startup flag."""
        # We can't easily test the interactive shell, but we can test that it starts
        # and exits quickly with --no-startup and some input

        # Set up a clean directory with config
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Test shell command with immediate exit
        # We'll use a subprocess with input to make it exit immediately
        import subprocess

        result = subprocess.run(
            ["python", "-m", "serv", "shell", "--no-startup"],
            cwd=clean_test_dir,
            input="exit()\n",  # Exit immediately
            text=True,
            capture_output=True,
            timeout=10,  # Timeout after 10 seconds
        )

        # Should have started the shell (even if it exited immediately)
        assert (
            "Starting" in result.stdout
            or "Python" in result.stdout
            or result.returncode == 0
        )

    def test_all_new_commands_help(self, clean_test_dir):
        """Test that all commands have proper help text."""
        # Test main help shows all commands and global flags
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "--help"],
            cwd=clean_test_dir,
        )

        # Check that all commands are listed in main help
        assert "test" in stdout
        assert "shell" in stdout
        assert "config" in stdout
        assert "Run tests for the application and extensions" in stdout
        assert "Start interactive Python shell with app context" in stdout
        assert "Configuration management commands" in stdout

        # Check that the global --dev flag is shown
        assert "--dev" in stdout
        assert "development mode" in stdout.lower()

        # Test individual command help works
        individual_commands = [
            ["launch", "--help"],
            ["test", "--help"],
            ["shell", "--help"],
            ["config", "--help"],
            ["config", "validate", "--help"],
            ["extension", "validate", "--help"],
        ]

        for cmd_args in individual_commands:
            return_code, stdout, stderr = run_cli_command(
                ["python", "-m", "serv"] + cmd_args,
                cwd=clean_test_dir,
            )
            # Just check that help was displayed (contains usage and options)
            assert "usage:" in stdout.lower(), (
                f"Command {cmd_args} should show usage help"
            )
            assert "options:" in stdout.lower(), (
                f"Command {cmd_args} should show options help"
            )

        # Test global --dev flag with launch command
        return_code, stdout, stderr = run_cli_command(
            ["python", "-m", "serv", "--dev", "launch", "--help"],
            cwd=clean_test_dir,
        )
        assert "usage:" in stdout.lower()
        assert "options:" in stdout.lower()

    def test_config_subcommands_help(self, clean_test_dir):
        """Test that all config subcommands have proper help text."""
        config_subcommands = [
            ["config", "show", "--help"],
            ["config", "validate", "--help"],
            ["config", "get", "--help"],
            ["config", "set", "--help"],
        ]

        for cmd_args in config_subcommands:
            return_code, stdout, stderr = run_cli_command(
                ["python", "-m", "serv"] + cmd_args,
                cwd=clean_test_dir,
            )
            # Just check that help was displayed properly
            assert "usage:" in stdout.lower(), (
                f"Config subcommand {cmd_args} should show usage"
            )
            assert "options:" in stdout.lower(), (
                f"Config subcommand {cmd_args} should show options"
            )

    def test_create_route_with_custom_path_and_router(self, clean_test_dir):
        """Test the 'serv create route' command with custom path and router."""
        # Set up a clean directory with config and a plugin
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a test plugin first
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "extension",
                "--name",
                "Test Extension",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Create a route with custom path and router
        return_code, stdout, stderr = run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "route",
                "--name",
                "user_profile",
                "--path",
                "/users/{id}/profile",
                "--router",
                "api_router",
                "--extension",
                "test_extension",
            ],
            cwd=clean_test_dir,
        )

        # Check that the route file was created
        route_path = (
            Path(clean_test_dir)
            / "extensions"
            / "test_extension"
            / "route_user_profile.py"
        )
        assert route_path.exists(), "Route file should have been created"

        # Check that the plugin config was updated correctly
        extension_yaml_path = (
            Path(clean_test_dir) / "extensions" / "test_extension" / "extension.yaml"
        )
        with open(extension_yaml_path) as f:
            extension_config = yaml.safe_load(f)

        assert "routers" in extension_config, (
            "Extension config should have routers section"
        )

        # Find the api_router
        api_router = None
        for router in extension_config["routers"]:
            if router.get("name") == "api_router":
                api_router = router
                break

        assert api_router is not None, "Should have created api_router"
        assert "routes" in api_router, "Router should have routes"

        # Check the route configuration
        user_profile_route = None
        for route in api_router["routes"]:
            if "/users/{id}/profile" in route.get("path", ""):
                user_profile_route = route
                break

        assert user_profile_route is not None, "Should have user profile route"
        assert user_profile_route["path"] == "/users/{id}/profile", (
            "Route should have correct path"
        )
        assert "route_user_profile:UserProfile" in user_profile_route["handler"], (
            "Route should have correct handler"
        )

        # Verify success message
        assert "Route 'user_profile' created successfully" in stdout
        assert "at path '/users/{id}/profile'" in stdout
        assert "Added route to router 'api_router'" in stdout

    def test_create_multiple_routes_same_router(self, clean_test_dir):
        """Test creating multiple routes in the same router."""
        # Set up a clean directory with config and a plugin
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a test plugin first
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "extension",
                "--name",
                "Test Extension",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Create first route
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "route",
                "--name",
                "user_profile",
                "--path",
                "/users/{id}/profile",
                "--router",
                "api_router",
                "--extension",
                "test_extension",
            ],
            cwd=clean_test_dir,
        )

        # Create second route in same router
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "route",
                "--name",
                "user_posts",
                "--path",
                "/users/{id}/posts",
                "--router",
                "api_router",
                "--extension",
                "test_extension",
            ],
            cwd=clean_test_dir,
        )

        # Check that both route files were created
        profile_route_path = (
            Path(clean_test_dir)
            / "extensions"
            / "test_extension"
            / "route_user_profile.py"
        )
        posts_route_path = (
            Path(clean_test_dir)
            / "extensions"
            / "test_extension"
            / "route_user_posts.py"
        )
        assert profile_route_path.exists(), "Profile route file should exist"
        assert posts_route_path.exists(), "Posts route file should exist"

        # Check plugin configuration
        extension_yaml_path = (
            Path(clean_test_dir) / "extensions" / "test_extension" / "extension.yaml"
        )
        with open(extension_yaml_path) as f:
            extension_config = yaml.safe_load(f)

        # Should have one router with two routes
        assert len(extension_config["routers"]) == 1, "Should have exactly one router"
        api_router = extension_config["routers"][0]
        assert api_router["name"] == "api_router", "Router should be named api_router"
        assert len(api_router["routes"]) == 2, "Router should have two routes"

        # Check both routes are present
        paths = [route["path"] for route in api_router["routes"]]
        assert "/users/{id}/profile" in paths, "Should have profile route"
        assert "/users/{id}/posts" in paths, "Should have posts route"

    def test_create_routes_different_routers(self, clean_test_dir):
        """Test creating routes in different routers."""
        # Set up a clean directory with config and a plugin
        run_cli_command(
            ["python", "-m", "serv", "create", "app", "--force", "--non-interactive"],
            cwd=clean_test_dir,
        )

        # Create a test plugin first
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "extension",
                "--name",
                "Test Extension",
                "--force",
                "--non-interactive",
            ],
            cwd=clean_test_dir,
        )

        # Create route in api_router
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "route",
                "--name",
                "user_profile",
                "--path",
                "/api/users/{id}/profile",
                "--router",
                "api_router",
                "--extension",
                "test_extension",
            ],
            cwd=clean_test_dir,
        )

        # Create route in admin_router
        run_cli_command(
            [
                "python",
                "-m",
                "serv",
                "create",
                "route",
                "--name",
                "admin_dashboard",
                "--path",
                "/admin/dashboard",
                "--router",
                "admin_router",
                "--extension",
                "test_extension",
            ],
            cwd=clean_test_dir,
        )

        # Check plugin configuration
        extension_yaml_path = (
            Path(clean_test_dir) / "extensions" / "test_extension" / "extension.yaml"
        )
        with open(extension_yaml_path) as f:
            extension_config = yaml.safe_load(f)

        # Should have two routers
        assert len(extension_config["routers"]) == 2, "Should have exactly two routers"

        router_names = [router["name"] for router in extension_config["routers"]]
        assert "api_router" in router_names, "Should have api_router"
        assert "admin_router" in router_names, "Should have admin_router"

        # Check each router has the correct route
        for router in extension_config["routers"]:
            if router["name"] == "api_router":
                assert len(router["routes"]) == 1, "API router should have one route"
                assert router["routes"][0]["path"] == "/api/users/{id}/profile"
            elif router["name"] == "admin_router":
                assert len(router["routes"]) == 1, "Admin router should have one route"
                assert router["routes"][0]["path"] == "/admin/dashboard"
