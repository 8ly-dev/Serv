"""
CLI command handlers.

This module contains all the command handlers for the Serv CLI.
"""

import importlib
import importlib.util
import json
import logging
import os
import sys
from inspect import isclass
from pathlib import Path

import jinja2
import uvicorn
import yaml

from serv.app import App
from serv.config import DEFAULT_CONFIG_FILE, import_from_string

from .utils import (
    prompt_user,
    to_pascal_case,
    to_snake_case,
)

logger = logging.getLogger("serv")


def _should_prompt_interactively(args_ns):
    """Check if we should prompt the user interactively."""
    # Don't prompt if non-interactive mode is enabled
    if getattr(args_ns, "non_interactive", False):
        return False

    # Don't prompt if stdin is not available (like in tests or CI)
    try:
        import sys

        # Check if stdin is a TTY and can actually be read from
        if not sys.stdin.isatty():
            return False

        # Additional check: try to see if stdin is readable
        # In subprocess environments with capture_output=True, stdin might be closed
        if sys.stdin.closed:
            return False

        # Check if we're in a testing environment
        if hasattr(sys, "_getframe"):
            # Look for pytest in the call stack
            frame = sys._getframe()
            while frame:
                if "pytest" in str(frame.f_code.co_filename):
                    return False
                frame = frame.f_back

        return True
    except (AttributeError, OSError):
        return False


def _detect_plugin_context(plugin_arg=None):
    """Detect which plugin to operate on based on context and arguments.

    Returns:
        tuple: (plugin_name, plugin_dir_path) or (None, None) if not found
    """
    if plugin_arg:
        # Plugin explicitly specified
        plugins_dir = Path.cwd() / "plugins"
        plugin_dir = plugins_dir / plugin_arg
        if plugin_dir.exists() and (plugin_dir / "plugin.yaml").exists():
            return plugin_arg, plugin_dir
        else:
            logger.error(f"Plugin '{plugin_arg}' not found in plugins directory")
            return None, None

    # Check if we're in a plugin directory (has plugin.yaml)
    if (Path.cwd() / "plugin.yaml").exists():
        return Path.cwd().name, Path.cwd()

    # Check if there's only one plugin in the plugins directory
    plugins_dir = Path.cwd() / "plugins"
    if plugins_dir.exists():
        plugin_dirs = [
            d
            for d in plugins_dir.iterdir()
            if d.is_dir()
            and (d / "plugin.yaml").exists()
            and not d.name.startswith("_")
        ]
        if len(plugin_dirs) == 1:
            plugin_dir = plugin_dirs[0]
            return plugin_dir.name, plugin_dir

    return None, None


def _update_plugin_config(plugin_dir, component_type, component_name, entry_path):
    """Update the plugin.yaml file to include the new component.

    Args:
        plugin_dir: Path to the plugin directory
        component_type: Type of component ('listeners', 'middleware', 'routers')
        component_name: Name of the component
        entry_path: Entry path for the component
    """
    plugin_yaml_path = plugin_dir / "plugin.yaml"

    try:
        with open(plugin_yaml_path) as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Error reading plugin config '{plugin_yaml_path}': {e}")
        return False

    # Initialize the component section if it doesn't exist
    if component_type not in config:
        config[component_type] = []

    # Add the new component
    if component_type == "listeners":
        config[component_type].append(entry_path)
    elif component_type == "middleware":
        config[component_type].append({"entry": entry_path})
    elif component_type == "routers":
        # For routes, we need to add to a router configuration
        if isinstance(entry_path, dict):
            # New format with router name and path
            router_name = entry_path.get("router_name", "main_router")
            route_path = entry_path.get("path", f"/{component_name}")
            handler = entry_path.get("handler")

            # Find existing router or create new one
            target_router = None
            for router in config[component_type]:
                if router.get("name") == router_name:
                    target_router = router
                    break

            if not target_router:
                # Create new router
                target_router = {"name": router_name, "routes": []}
                config[component_type].append(target_router)

            # Add route to the target router
            if "routes" not in target_router:
                target_router["routes"] = []

            target_router["routes"].append({"path": route_path, "handler": handler})
        else:
            # Legacy format - add to first router or create default
            if not config[component_type]:
                config[component_type] = [{"name": "main_router", "routes": []}]

            # Add route to the first router
            config[component_type][0]["routes"].append(
                {"path": f"/{component_name}", "handler": entry_path}
            )

    try:
        with open(plugin_yaml_path, "w") as f:
            yaml.dump(config, f, sort_keys=False, indent=2, default_flow_style=False)
        return True
    except Exception as e:
        logger.error(f"Error writing plugin config '{plugin_yaml_path}': {e}")
        return False


def handle_init_command(args_ns):
    """Handles the 'init' command to create serv.config.yaml."""
    logger.debug("Init command started.")
    config_path = Path.cwd() / DEFAULT_CONFIG_FILE

    if config_path.exists() and not args_ns.force:
        overwrite_prompt = prompt_user(
            f"'{config_path.name}' already exists in '{Path.cwd()}'. Overwrite? (yes/no)",
            "no",
        )
        if overwrite_prompt is None or overwrite_prompt.lower() != "yes":
            print("Initialization cancelled by user.")
            return

    # For non-interactive mode, use default values
    if getattr(args_ns, "non_interactive", False) or (
        args_ns.force and config_path.exists()
    ):
        site_name = "My Serv Site"
        site_description = "A new website powered by Serv"
    else:
        site_name = prompt_user("Enter site name", "My Serv Site") or "My Serv Site"
        site_description = (
            prompt_user("Enter site description", "A new website powered by Serv")
            or "A new website powered by Serv"
        )

    # Load and render the config template
    try:
        template_dir = (
            Path(importlib.util.find_spec("serv.cli").submodule_search_locations[0])
            / "scaffolding"
        )
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
        template = env.get_template("config_yaml.template")

        config_context = {
            "site_name": site_name,
            "site_description": site_description,
        }

        config_content_str = template.render(**config_context)
    except Exception as e_template:
        logger.error(f"Error loading config_yaml.template: {e_template}")
        return

    try:
        with open(config_path, "w") as f:
            f.write(config_content_str)

        print(f"Successfully created '{config_path}'.")
        print("You can now configure your plugins in this file.")
    except OSError as e:
        logger.error(f"Error writing config file '{config_path}': {e}")


def handle_create_plugin_command(args_ns):
    """Handles the 'create plugin' command."""
    logger.debug("Create plugin command started.")

    # Get plugin name from args or prompt for it
    plugin_name_human = args_ns.name
    if not plugin_name_human:
        if _should_prompt_interactively(args_ns):
            plugin_name_human = prompt_user("Plugin name")
            if not plugin_name_human:
                logger.error("Plugin name is required.")
                return
        else:
            logger.error("Plugin name is required. Use --name to specify it.")
            return

    # For non-interactive mode, use default values
    if getattr(args_ns, "non_interactive", False):
        plugin_author = "Test Author"
        plugin_description = "A test plugin for Serv"
        plugin_version = "1.0.0"
    else:
        plugin_author = prompt_user("Author", "Your Name") or "Your Name"
        plugin_description = (
            prompt_user("Description", "A cool Serv plugin.") or "A cool Serv plugin."
        )
        plugin_version = prompt_user("Version", "0.1.0") or "0.1.0"

    plugin_dir_name = to_snake_case(plugin_name_human)
    if not plugin_dir_name:
        logger.error(
            f"Could not derive a valid module name from '{plugin_name_human}'. Please use alphanumeric characters."
        )
        return

    plugins_root_dir = Path.cwd() / "plugins"
    plugin_specific_dir = plugins_root_dir / plugin_dir_name

    if plugin_specific_dir.exists() and not getattr(args_ns, "force", False):
        print(
            f"Warning: Plugin directory '{plugin_specific_dir}' already exists. Files might be overwritten."
        )

    try:
        os.makedirs(plugin_specific_dir, exist_ok=True)
        (plugins_root_dir / "__init__.py").touch(exist_ok=True)
        (plugin_specific_dir / "__init__.py").touch(exist_ok=True)

    except OSError as e:
        logger.error(
            f"Error creating plugin directory structure '{plugin_specific_dir}': {e}"
        )
        return

    # Create plugin.yaml (without listeners - those will be added by create listener)
    plugin_yaml_path = plugin_specific_dir / "plugin.yaml"

    plugin_yaml_context = {
        "plugin_name": plugin_name_human,
        "plugin_version": plugin_version,
        "plugin_author": plugin_author,
        "plugin_description": plugin_description,
    }

    try:
        template_dir = (
            Path(importlib.util.find_spec("serv.cli").submodule_search_locations[0])
            / "scaffolding"
        )
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
        template = env.get_template("plugin_yaml.template")
        plugin_yaml_content_str = template.render(**plugin_yaml_context)
    except Exception as e_template:
        logger.error(f"Error loading plugin_yaml.template: {e_template}")
        return

    try:
        with open(plugin_yaml_path, "w") as f:
            f.write(plugin_yaml_content_str)
        print(f"Created '{plugin_yaml_path}'")
        print(
            f"Plugin '{plugin_name_human}' created successfully in '{plugin_specific_dir}'."
        )
        print("To add functionality, create listeners with:")
        print(
            f"  serv create listener --name <listener_name> --plugin {plugin_dir_name}"
        )
        print("To enable the plugin, run:")
        print(f"  serv plugin enable {plugin_dir_name}")

    except OSError as e:
        logger.error(f"Error writing '{plugin_yaml_path}': {e}")
        return


def handle_enable_plugin_command(args_ns):
    """Handles the 'enable-plugin' command."""
    plugin_identifier = args_ns.plugin_identifier
    logger.debug(f"Attempting to enable plugin: '{plugin_identifier}'...")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        logger.error(
            f"Configuration file '{config_path}' not found. Please run 'serv init' first."
        )
        return

    # Convert plugin identifier to directory name
    plugin_id = to_snake_case(plugin_identifier)
    plugin_name_human = plugin_identifier

    # Check if plugin directory exists
    plugins_dir = Path.cwd() / "plugins"
    plugin_yaml_path = plugins_dir / plugin_id / "plugin.yaml"

    if not plugin_yaml_path.exists():
        logger.error(
            f"Plugin '{plugin_identifier}' not found. Expected plugin.yaml at '{plugin_yaml_path}'."
        )
        return

    # Get human name from plugin.yaml
    try:
        with open(plugin_yaml_path) as f:
            plugin_meta = yaml.safe_load(f)
        if isinstance(plugin_meta, dict):
            plugin_name_human = plugin_meta.get("name", plugin_identifier)
    except Exception:
        plugin_name_human = plugin_identifier

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Error reading config file '{config_path}': {e}")
        return

    plugins = config.get("plugins", [])

    # Check if plugin is already enabled
    for plugin_entry in plugins:
        if isinstance(plugin_entry, dict):
            existing_plugin = plugin_entry.get("plugin")
        else:
            existing_plugin = plugin_entry

        if existing_plugin == plugin_id or existing_plugin == plugin_identifier:
            print(f"Plugin '{plugin_identifier}' is already enabled.")
            return

    # Add the plugin
    plugins.append({"plugin": plugin_id})
    config["plugins"] = plugins

    try:
        with open(config_path, "w") as f:
            yaml.dump(config, f, sort_keys=False, indent=2, default_flow_style=False)
        print(f"Plugin '{plugin_identifier}' enabled successfully.")
        if plugin_name_human and plugin_name_human != plugin_identifier:
            print(f"Human name: {plugin_name_human}")
    except Exception as e:
        logger.error(f"Error writing config file '{config_path}': {e}")


def handle_disable_plugin_command(args_ns):
    """Handles the 'disable-plugin' command."""
    plugin_identifier = args_ns.plugin_identifier
    logger.debug(f"Attempting to disable plugin: '{plugin_identifier}'...")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        logger.error(
            f"Configuration file '{config_path}' not found. Please run 'serv init' first."
        )
        return

    # Convert plugin identifier to directory name
    plugin_id = to_snake_case(plugin_identifier)
    plugin_name_human = plugin_identifier

    # Check if plugin directory exists and get human name
    plugins_dir = Path.cwd() / "plugins"
    plugin_yaml_path = plugins_dir / plugin_id / "plugin.yaml"

    if plugin_yaml_path.exists():
        try:
            with open(plugin_yaml_path) as f:
                plugin_meta = yaml.safe_load(f)
            if isinstance(plugin_meta, dict):
                plugin_name_human = plugin_meta.get("name", plugin_identifier)
        except Exception:
            plugin_name_human = plugin_identifier

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Error reading config file '{config_path}': {e}")
        return

    plugins = config.get("plugins", [])
    original_count = len(plugins)

    # Remove the plugin
    plugins = [
        p
        for p in plugins
        if (
            (
                isinstance(p, dict)
                and p.get("plugin") not in [plugin_id, plugin_identifier]
            )
            or (isinstance(p, str) and p not in [plugin_id, plugin_identifier])
        )
    ]

    if len(plugins) == original_count:
        print(f"Plugin '{plugin_identifier}' was not found in the configuration.")
        return

    config["plugins"] = plugins

    try:
        with open(config_path, "w") as f:
            yaml.dump(config, f, sort_keys=False, indent=2, default_flow_style=False)
        print(f"Plugin '{plugin_identifier}' disabled successfully.")
        if plugin_name_human and plugin_name_human != plugin_identifier:
            print(f"Human name: {plugin_name_human}")
    except Exception as e:
        logger.error(f"Error writing config file '{config_path}': {e}")


def handle_list_plugin_command(args_ns):
    """Handles the 'list plugin' command."""
    logger.debug("List plugin command started.")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE

    if args_ns.available:
        # Show all available plugins in the plugins directory
        plugins_dir = Path.cwd() / "plugins"
        if not plugins_dir.exists():
            print("No plugins directory found.")
            return

        available_plugins = []
        for plugin_dir in plugins_dir.iterdir():
            if (
                plugin_dir.is_dir()
                and not plugin_dir.name.startswith("_")
                and (plugin_dir / "plugin.yaml").exists()
            ):
                try:
                    with open(plugin_dir / "plugin.yaml") as f:
                        plugin_meta = yaml.safe_load(f) or {}

                    plugin_name = plugin_meta.get("name", plugin_dir.name)
                    plugin_version = plugin_meta.get("version", "Unknown")
                    plugin_description = plugin_meta.get(
                        "description", "No description"
                    )

                    available_plugins.append(
                        {
                            "dir_name": plugin_dir.name,
                            "name": plugin_name,
                            "version": plugin_version,
                            "description": plugin_description,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Error reading plugin metadata for '{plugin_dir.name}': {e}"
                    )
                    available_plugins.append(
                        {
                            "dir_name": plugin_dir.name,
                            "name": plugin_dir.name,
                            "version": "Unknown",
                            "description": "Error reading metadata",
                        }
                    )

        if not available_plugins:
            print("No plugins found in the plugins directory.")
            return

        print(f"Available plugins ({len(available_plugins)}):")
        for plugin in available_plugins:
            print(f"  • {plugin['name']} (v{plugin['version']}) [{plugin['dir_name']}]")
            print(f"    {plugin['description']}")
    else:
        # Show enabled plugins from config
        if not config_path.exists():
            print(f"Configuration file '{config_path}' not found.")
            print("Run 'serv app init' to create a configuration file.")
            return

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error reading config file '{config_path}': {e}")
            return

        plugins = config.get("plugins", [])

        if not plugins:
            print("No plugins are currently enabled.")
            print("Use 'serv plugin enable <plugin>' to enable a plugin.")
            return

        print(f"Enabled plugins ({len(plugins)}):")
        for plugin_entry in plugins:
            if isinstance(plugin_entry, dict):
                plugin_id = plugin_entry.get("plugin", "Unknown")
                plugin_config = plugin_entry.get("config", {})
                config_info = " (with config)" if plugin_config else ""
            else:
                plugin_id = plugin_entry
                config_info = ""

            # Try to get human-readable name from plugin metadata
            plugin_name = plugin_id
            plugin_version = "Unknown"

            # Check if this is a directory-based plugin
            plugins_dir = Path.cwd() / "plugins"
            if plugins_dir.exists():
                # Extract directory name from plugin_id (handle both simple names and module paths)
                if ":" in plugin_id:
                    # Full module path like "test_plugin.test_plugin:TestPlugin"
                    module_path = plugin_id.split(":")[0]
                    dir_name = module_path.split(".")[0]
                else:
                    # Simple name or just module path
                    dir_name = plugin_id.split(".")[0]

                # Try to find the plugin directory
                plugin_dir = plugins_dir / dir_name
                if (
                    plugin_dir.exists()
                    and plugin_dir.is_dir()
                    and (plugin_dir / "plugin.yaml").exists()
                ):
                    try:
                        with open(plugin_dir / "plugin.yaml") as f:
                            plugin_meta = yaml.safe_load(f) or {}
                        plugin_name = plugin_meta.get("name", plugin_id)
                        plugin_version = plugin_meta.get("version", "Unknown")
                    except Exception:
                        pass

            print(f"  • {plugin_name} (v{plugin_version}) [{plugin_id}]{config_info}")


def handle_validate_plugin_command(args_ns):
    """Handles the 'plugin validate' command."""
    logger.debug("Plugin validate command started.")

    plugins_dir = Path.cwd() / "plugins"
    if not plugins_dir.exists():
        print("❌ No plugins directory found.")
        return False

    # Determine which plugins to validate
    if args_ns.plugin_identifier and not args_ns.all:
        # Validate specific plugin
        plugin_dirs = []
        plugin_dir = plugins_dir / args_ns.plugin_identifier
        if plugin_dir.exists() and plugin_dir.is_dir():
            plugin_dirs = [plugin_dir]
        else:
            print(f"❌ Plugin '{args_ns.plugin_identifier}' not found.")
            return False
    else:
        # Validate all plugins
        plugin_dirs = [
            d
            for d in plugins_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        ]

    if not plugin_dirs:
        print("ℹ️  No plugins found to validate.")
        return True

    print(f"=== Validating {len(plugin_dirs)} Plugin(s) ===")

    total_issues = 0

    for plugin_dir in plugin_dirs:
        print(f"\n🔍 Validating plugin: {plugin_dir.name}")
        issues = 0

        # Check for plugin.yaml
        plugin_yaml = plugin_dir / "plugin.yaml"
        if not plugin_yaml.exists():
            print("❌ Missing plugin.yaml")
            issues += 1
        else:
            try:
                with open(plugin_yaml) as f:
                    plugin_config = yaml.safe_load(f)

                if not plugin_config:
                    print("❌ plugin.yaml is empty")
                    issues += 1
                else:
                    print("✅ plugin.yaml is valid YAML")

                    # Check required fields
                    required_fields = ["name", "version"]
                    for field in required_fields:
                        if field not in plugin_config:
                            print(f"❌ Missing required field: {field}")
                            issues += 1
                        else:
                            print(f"✅ Has required field: {field}")

                    # Check optional but recommended fields
                    recommended_fields = ["description", "author"]
                    for field in recommended_fields:
                        if field not in plugin_config:
                            print(f"⚠️  Missing recommended field: {field}")
                        else:
                            print(f"✅ Has recommended field: {field}")

                    # Validate version format
                    version = plugin_config.get("version", "")
                    if (
                        version
                        and not version.replace(".", "")
                        .replace("-", "")
                        .replace("_", "")
                        .isalnum()
                    ):
                        print(f"⚠️  Version format may be invalid: {version}")

            except yaml.YAMLError as e:
                print(f"❌ plugin.yaml contains invalid YAML: {e}")
                issues += 1
            except Exception as e:
                print(f"❌ Error reading plugin.yaml: {e}")
                issues += 1

        # Check for __init__.py
        init_file = plugin_dir / "__init__.py"
        if not init_file.exists():
            print("⚠️  Missing __init__.py (recommended for Python packages)")
        else:
            print("✅ Has __init__.py")

        # Check for Python files
        py_files = list(plugin_dir.glob("*.py"))
        if not py_files:
            print("❌ No Python files found")
            issues += 1
        else:
            print(f"✅ Found {len(py_files)} Python file(s)")

            # Check for main plugin file (matching directory name)
            expected_main_file = plugin_dir / f"{plugin_dir.name}.py"
            if expected_main_file.exists():
                print(f"✅ Has main plugin file: {expected_main_file.name}")
            else:
                print(f"⚠️  No main plugin file found (expected: {plugin_dir.name}.py)")

        # Check for common issues
        if (plugin_dir / "main.py").exists() and not expected_main_file.exists():
            print(
                f"⚠️  Found main.py but expected {plugin_dir.name}.py (consider renaming)"
            )

        # Try to import the plugin (basic syntax check)
        if py_files:
            try:
                # This is a basic check - we're not actually importing to avoid side effects
                for py_file in py_files:
                    with open(py_file) as f:
                        content = f.read()

                    # Basic syntax check
                    try:
                        compile(content, str(py_file), "exec")
                        print(f"✅ {py_file.name} has valid Python syntax")
                    except SyntaxError as e:
                        print(f"❌ {py_file.name} has syntax error: {e}")
                        issues += 1

            except Exception as e:
                print(f"⚠️  Could not perform syntax check: {e}")

        if issues == 0:
            print(f"🎉 Plugin '{plugin_dir.name}' validation passed!")
        else:
            print(f"⚠️  Plugin '{plugin_dir.name}' has {issues} issue(s)")

        total_issues += issues

    print("\n=== Validation Summary ===")
    if total_issues == 0:
        print("🎉 All plugins passed validation!")
    else:
        print(f"⚠️  Found {total_issues} total issue(s) across all plugins")

    return total_issues == 0


def _get_configured_app(app_module_str: str | None, args_ns) -> App:
    """Get a configured App instance."""
    if app_module_str:
        try:
            app_class = import_from_string(app_module_str)
            if not isclass(app_class) or not issubclass(app_class, App):
                raise ValueError(f"'{app_module_str}' is not a valid App class")
        except Exception as e:
            logger.error(f"Error importing app class '{app_module_str}': {e}")
            raise
    else:
        app_class = App

    # Create app instance with CLI arguments
    app_kwargs = {}

    if hasattr(args_ns, "config") and args_ns.config:
        app_kwargs["config_file"] = args_ns.config

    if hasattr(args_ns, "plugin_dirs") and args_ns.plugin_dirs:
        app_kwargs["plugin_dir"] = args_ns.plugin_dirs
    else:
        # Default to ./plugins directory if it exists
        default_plugin_dir = Path.cwd() / "plugins"
        if default_plugin_dir.exists():
            app_kwargs["plugin_dir"] = str(default_plugin_dir)

    if hasattr(args_ns, "dev") and args_ns.dev:
        app_kwargs["dev_mode"] = True

    try:
        logger.info(
            f"Instantiating App ({app_class.__name__}) with arguments: {app_kwargs}"
        )
        app = app_class(**app_kwargs)
        return app
    except Exception as e:
        logger.error(f"Error creating app instance: {e}")
        raise


def handle_create_listener_command(args_ns):
    """Handles the 'create listener' command."""
    logger.debug("Create listener command started.")

    # Get listener name from args or prompt for it
    component_name = args_ns.name
    if not component_name:
        if _should_prompt_interactively(args_ns):
            component_name = prompt_user("Listener name")
            if not component_name:
                logger.error("Listener name is required.")
                return
        else:
            logger.error("Listener name is required. Use --name to specify it.")
            return
    plugin_name, plugin_dir = _detect_plugin_context(args_ns.plugin)

    if not plugin_name:
        if args_ns.plugin:
            logger.error(f"Plugin '{args_ns.plugin}' not found.")
            return
        elif _should_prompt_interactively(args_ns):
            # Interactive prompt for plugin
            plugins_dir = Path.cwd() / "plugins"
            if plugins_dir.exists():
                available_plugins = [
                    d.name
                    for d in plugins_dir.iterdir()
                    if d.is_dir()
                    and (d / "plugin.yaml").exists()
                    and not d.name.startswith("_")
                ]
                if available_plugins:
                    print("Available plugins:")
                    for i, plugin in enumerate(available_plugins, 1):
                        print(f"  {i}. {plugin}")
                    plugin_choice = prompt_user("Select plugin (name or number)")
                    if plugin_choice and plugin_choice.isdigit():
                        idx = int(plugin_choice) - 1
                        if 0 <= idx < len(available_plugins):
                            plugin_name = available_plugins[idx]
                            plugin_dir = plugins_dir / plugin_name
                    elif plugin_choice in available_plugins:
                        plugin_name = plugin_choice
                        plugin_dir = plugins_dir / plugin_name

            if not plugin_name:
                logger.error("No plugin specified and none could be auto-detected.")
                return
        else:
            logger.error("No plugin specified and none could be auto-detected.")
            return

    class_name = to_pascal_case(component_name)
    file_name = f"listener_{to_snake_case(component_name)}.py"
    file_path = plugin_dir / file_name

    if file_path.exists() and not args_ns.force:
        print(f"Warning: File '{file_path}' already exists. Use --force to overwrite.")
        return

    # Create the listener file
    context = {
        "class_name": class_name,
        "listener_name": component_name,
        "route_path": to_snake_case(component_name),
        "handler_name": f"handle_{to_snake_case(component_name)}",
    }

    try:
        template_dir = (
            Path(importlib.util.find_spec("serv.cli").submodule_search_locations[0])
            / "scaffolding"
        )
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
        template = env.get_template("listener_main_py.template")
        content = template.render(**context)

        with open(file_path, "w") as f:
            f.write(content)

        print(f"Created '{file_path}'")

        # Update plugin config
        entry_path = f"{file_name[:-3]}:{class_name}"
        if _update_plugin_config(plugin_dir, "listeners", component_name, entry_path):
            print("Added listener to plugin configuration")

        print(
            f"Listener '{component_name}' created successfully in plugin '{plugin_name}'."
        )

    except Exception as e:
        logger.error(f"Error creating listener: {e}")


def handle_create_route_command(args_ns):
    """Handles the 'create route' command."""
    logger.debug("Create route command started.")

    # Get route name from args or prompt for it
    component_name = args_ns.name
    if not component_name:
        if _should_prompt_interactively(args_ns):
            component_name = prompt_user("Route name")
            if not component_name:
                logger.error("Route name is required.")
                return
        else:
            logger.error("Route name is required. Use --name to specify it.")
            return
    plugin_name, plugin_dir = _detect_plugin_context(args_ns.plugin)

    if not plugin_name:
        if args_ns.plugin:
            logger.error(f"Plugin '{args_ns.plugin}' not found.")
            return
        elif _should_prompt_interactively(args_ns):
            # Interactive prompt for plugin
            plugins_dir = Path.cwd() / "plugins"
            if plugins_dir.exists():
                available_plugins = [
                    d.name
                    for d in plugins_dir.iterdir()
                    if d.is_dir()
                    and (d / "plugin.yaml").exists()
                    and not d.name.startswith("_")
                ]
                if available_plugins:
                    print("Available plugins:")
                    for i, plugin in enumerate(available_plugins, 1):
                        print(f"  {i}. {plugin}")
                    plugin_choice = prompt_user("Select plugin (name or number)")
                    if plugin_choice and plugin_choice.isdigit():
                        idx = int(plugin_choice) - 1
                        if 0 <= idx < len(available_plugins):
                            plugin_name = available_plugins[idx]
                            plugin_dir = plugins_dir / plugin_name
                    elif plugin_choice in available_plugins:
                        plugin_name = plugin_choice
                        plugin_dir = plugins_dir / plugin_name

            if not plugin_name:
                logger.error("No plugin specified and none could be auto-detected.")
                return
        else:
            logger.error("No plugin specified and none could be auto-detected.")
            return

    # Get route path
    route_path = args_ns.path
    if not route_path:
        default_path = f"/{to_snake_case(component_name)}"
        if _should_prompt_interactively(args_ns):
            route_path = prompt_user("Route path", default_path) or default_path
        else:
            route_path = default_path

    # Ensure path starts with /
    if not route_path.startswith("/"):
        route_path = "/" + route_path

    # Get router name
    router_name = args_ns.router
    if not router_name:
        # Check existing routers in plugin config
        plugin_yaml_path = plugin_dir / "plugin.yaml"
        existing_routers = []

        if plugin_yaml_path.exists():
            try:
                with open(plugin_yaml_path) as f:
                    plugin_config = yaml.safe_load(f) or {}

                routers = plugin_config.get("routers", [])
                existing_routers = [
                    router.get("name") for router in routers if router.get("name")
                ]
            except Exception:
                pass

        if _should_prompt_interactively(args_ns):
            if existing_routers:
                print("Existing routers:")
                for i, router in enumerate(existing_routers, 1):
                    print(f"  {i}. {router}")
                print(f"  {len(existing_routers) + 1}. Create new router")

                router_choice = prompt_user("Select router (name or number)", "1")
                if router_choice and router_choice.isdigit():
                    idx = int(router_choice) - 1
                    if 0 <= idx < len(existing_routers):
                        router_name = existing_routers[idx]
                    elif idx == len(existing_routers):
                        router_name = (
                            prompt_user("New router name", "main_router")
                            or "main_router"
                        )
                elif router_choice in existing_routers:
                    router_name = router_choice
                else:
                    router_name = router_choice or "main_router"
            else:
                router_name = prompt_user("Router name", "main_router") or "main_router"
        else:
            # Non-interactive mode, use default
            router_name = "main_router"

    class_name = to_pascal_case(component_name)
    file_name = f"route_{to_snake_case(component_name)}.py"
    file_path = plugin_dir / file_name

    if file_path.exists() and not args_ns.force:
        print(f"Warning: File '{file_path}' already exists. Use --force to overwrite.")
        return

    # Create the route file
    context = {
        "class_name": class_name,
        "route_name": component_name,
        "route_path": route_path,
    }

    try:
        template_dir = (
            Path(importlib.util.find_spec("serv.cli").submodule_search_locations[0])
            / "scaffolding"
        )
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
        template = env.get_template("route_main_py.template")
        content = template.render(**context)

        with open(file_path, "w") as f:
            f.write(content)

        print(f"Created '{file_path}'")

        # Update plugin config with router name and path
        entry_path = f"{file_name[:-3]}:{class_name}"
        route_config = {
            "path": route_path,
            "handler": entry_path,
            "router_name": router_name,
            "component_name": component_name,
        }

        if _update_plugin_config(plugin_dir, "routers", component_name, route_config):
            print(f"Added route to router '{router_name}' in plugin configuration")

        print(
            f"Route '{component_name}' created successfully in plugin '{plugin_name}' at path '{route_path}'."
        )

    except Exception as e:
        logger.error(f"Error creating route: {e}")


def handle_create_middleware_command(args_ns):
    """Handles the 'create middleware' command."""
    logger.debug("Create middleware command started.")

    # Get middleware name from args or prompt for it
    component_name = args_ns.name
    if not component_name:
        if _should_prompt_interactively(args_ns):
            component_name = prompt_user("Middleware name")
            if not component_name:
                logger.error("Middleware name is required.")
                return
        else:
            logger.error("Middleware name is required. Use --name to specify it.")
            return
    plugin_name, plugin_dir = _detect_plugin_context(args_ns.plugin)

    if not plugin_name:
        if args_ns.plugin:
            logger.error(f"Plugin '{args_ns.plugin}' not found.")
            return
        elif _should_prompt_interactively(args_ns):
            # Interactive prompt for plugin
            plugins_dir = Path.cwd() / "plugins"
            if plugins_dir.exists():
                available_plugins = [
                    d.name
                    for d in plugins_dir.iterdir()
                    if d.is_dir()
                    and (d / "plugin.yaml").exists()
                    and not d.name.startswith("_")
                ]
                if available_plugins:
                    print("Available plugins:")
                    for i, plugin in enumerate(available_plugins, 1):
                        print(f"  {i}. {plugin}")
                    plugin_choice = prompt_user("Select plugin (name or number)")
                    if plugin_choice and plugin_choice.isdigit():
                        idx = int(plugin_choice) - 1
                        if 0 <= idx < len(available_plugins):
                            plugin_name = available_plugins[idx]
                            plugin_dir = plugins_dir / plugin_name
                    elif plugin_choice in available_plugins:
                        plugin_name = plugin_choice
                        plugin_dir = plugins_dir / plugin_name

            if not plugin_name:
                logger.error("No plugin specified and none could be auto-detected.")
                return
        else:
            logger.error("No plugin specified and none could be auto-detected.")
            return

    middleware_name = to_snake_case(component_name)
    file_name = f"middleware_{middleware_name}.py"
    file_path = plugin_dir / file_name

    if file_path.exists() and not args_ns.force:
        print(f"Warning: File '{file_path}' already exists. Use --force to overwrite.")
        return

    # Get middleware description
    default_description = (
        f"Middleware for {component_name.replace('_', ' ')} functionality."
    )
    if _should_prompt_interactively(args_ns):
        middleware_description = (
            prompt_user("Middleware description", default_description)
            or default_description
        )
    else:
        middleware_description = default_description

    # Create the middleware file
    context = {
        "middleware_name": middleware_name,
        "middleware_description": middleware_description,
    }

    try:
        template_dir = (
            Path(importlib.util.find_spec("serv.cli").submodule_search_locations[0])
            / "scaffolding"
        )
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
        template = env.get_template("middleware_main_py.template")
        content = template.render(**context)

        with open(file_path, "w") as f:
            f.write(content)

        print(f"Created '{file_path}'")

        # Update plugin config
        entry_path = f"{file_name[:-3]}:{middleware_name}_middleware"
        if _update_plugin_config(plugin_dir, "middleware", component_name, entry_path):
            print("Added middleware to plugin configuration")

        print(
            f"Middleware '{component_name}' created successfully in plugin '{plugin_name}'."
        )

    except Exception as e:
        logger.error(f"Error creating middleware: {e}")


async def handle_launch_command(args_ns):
    """Handles the 'launch' command."""
    logger.debug("Launch command started.")

    try:
        app = _get_configured_app(args_ns.app, args_ns)

        if args_ns.dry_run:
            print("=== Dry Run Mode ===")
            print("Application loaded successfully. Server would start with:")
            print(f"  Host: {args_ns.host}")
            print(f"  Port: {args_ns.port}")
            print(f"  Reload: {args_ns.reload}")
            print(f"  Workers: {args_ns.workers}")
            return

        # Configure uvicorn
        uvicorn_config = {
            "app": app,
            "host": args_ns.host,
            "port": args_ns.port,
            "reload": args_ns.reload,
            "workers": args_ns.workers
            if not args_ns.reload
            else 1,  # Reload doesn't work with multiple workers
        }

        if args_ns.factory:
            # If factory mode, we need to pass the app as a string
            if args_ns.app:
                uvicorn_config["app"] = args_ns.app
            else:
                uvicorn_config["app"] = "serv.app:App"

        logger.info(f"Starting Serv application on {args_ns.host}:{args_ns.port}")

        # Start the server
        server = uvicorn.Server(uvicorn.Config(**uvicorn_config))
        await server.serve()

    except KeyboardInterrupt:
        # This should be handled by the main CLI, but just in case
        logger.info("Server shutdown requested")
        raise
    except Exception as e:
        logger.error(f"Error launching application: {e}")
        sys.exit(1)


async def handle_dev_command(args_ns):
    """Handles the 'dev' command for enhanced development server."""
    logger.debug("Dev command started.")

    try:
        print("🚀 Starting Serv development server...")
        print("📝 Development mode features:")
        print("   • Auto-reload enabled (unless --no-reload)")
        print("   • Enhanced error reporting")
        print("   • Development mode enabled")

        app = _get_configured_app(args_ns.app, args_ns)

        # Force development mode
        if hasattr(app, "dev_mode"):
            app.dev_mode = True

        # Configure uvicorn for development
        reload = not args_ns.no_reload
        uvicorn_config = {
            "app": app,
            "host": args_ns.host,
            "port": args_ns.port,
            "reload": reload,
            "workers": 1
            if reload
            else args_ns.workers,  # Reload doesn't work with multiple workers
            "log_level": "debug",
            "access_log": True,
        }

        logger.info(f"Starting development server on {args_ns.host}:{args_ns.port}")
        if reload:
            print("🔄 Auto-reload is enabled - files will be watched for changes")
        else:
            print("⚠️  Auto-reload is disabled")

        # Start the server
        server = uvicorn.Server(uvicorn.Config(**uvicorn_config))
        await server.serve()

    except KeyboardInterrupt:
        # This should be handled by the main CLI, but just in case
        logger.info("Development server shutdown requested")
        raise
    except Exception as e:
        logger.error(f"Error starting development server: {e}")
        sys.exit(1)


def handle_test_command(args_ns):
    """Handles the 'test' command."""
    logger.debug("Test command started.")

    # Check if pytest is available
    try:
        import pytest
    except ImportError:
        print("❌ pytest is not installed. Install it with: pip install pytest")
        return False

    print("🧪 Running tests...")

    # Build pytest command
    pytest_args = []

    # Determine what to test
    if args_ns.test_path:
        pytest_args.append(args_ns.test_path)
    elif args_ns.plugins:
        # Look for plugin tests
        plugins_dir = Path.cwd() / "plugins"
        if plugins_dir.exists():
            plugin_test_paths = []
            for plugin_dir in plugins_dir.iterdir():
                if plugin_dir.is_dir() and not plugin_dir.name.startswith("_"):
                    test_files = list(plugin_dir.glob("test_*.py")) + list(
                        plugin_dir.glob("*_test.py")
                    )
                    if test_files:
                        plugin_test_paths.extend(str(f) for f in test_files)

            if plugin_test_paths:
                pytest_args.extend(plugin_test_paths)
                print(f"📦 Found {len(plugin_test_paths)} plugin test files")
            else:
                print("ℹ️  No plugin tests found")
                return True
        else:
            print("⚠️  No plugins directory found")
            return True
    elif args_ns.e2e:
        # Run e2e tests
        e2e_dir = Path.cwd() / "tests" / "e2e"
        if e2e_dir.exists():
            pytest_args.append(str(e2e_dir))
            print("🌐 Running end-to-end tests")
        else:
            print("⚠️  No e2e tests directory found")
            return True
    else:
        # Run all tests
        test_dir = Path.cwd() / "tests"
        if test_dir.exists():
            pytest_args.append(str(test_dir))
            print("🔍 Running all tests")
        else:
            print("⚠️  No tests directory found")
            return True

    # Add coverage if requested
    if args_ns.coverage:
        try:
            import importlib.util

            if importlib.util.find_spec("pytest_cov") is not None:
                pytest_args.extend(
                    ["--cov=.", "--cov-report=html", "--cov-report=term"]
                )
                print("📊 Coverage reporting enabled")
            else:
                print("⚠️  pytest-cov not installed, skipping coverage reporting")
        except ImportError:
            print(
                "⚠️  pytest-cov not installed, skipping coverage. Install with: pip install pytest-cov"
            )

    # Add verbose if requested
    if args_ns.verbose:
        pytest_args.append("-v")

    # Run pytest
    try:
        print(f"Running: pytest {' '.join(pytest_args)}")
        exit_code = pytest.main(pytest_args)

        if exit_code == 0:
            print("✅ All tests passed!")
        else:
            print(f"❌ Tests failed with exit code {exit_code}")

        return exit_code == 0

    except Exception as e:
        logger.error(f"Error running tests: {e}")
        return False


def handle_shell_command(args_ns):
    """Handles the 'shell' command."""
    logger.debug("Shell command started.")

    print("🐍 Starting interactive Python shell...")

    # Prepare the shell environment
    shell_locals = {"__name__": "__console__", "__doc__": None}

    if not args_ns.no_startup:
        try:
            print("📦 Loading Serv app context...")
            app = _get_configured_app(args_ns.app, args_ns)
            shell_locals.update(
                {
                    "app": app,
                    "serv": importlib.import_module("serv"),
                    "Path": Path,
                    "yaml": yaml,
                }
            )

            # Add plugins to shell context
            if hasattr(app, "_plugins"):
                all_plugins = []
                for plugin_list in app._plugins.values():
                    all_plugins.extend(plugin_list)
                shell_locals["plugins"] = all_plugins
                print(f"🔌 Loaded {len(all_plugins)} plugins into context")

            print("✅ App context loaded successfully")
            print("Available objects: app, serv, plugins, Path, yaml")

        except Exception as e:
            logger.warning(f"Could not load app context: {e}")
            print("⚠️  App context not available, starting basic shell")

    # Try to use IPython if available and requested
    if args_ns.ipython:
        try:
            from IPython import start_ipython

            print("🎨 Starting IPython shell...")
            start_ipython(argv=[], user_ns=shell_locals)
            return
        except ImportError:
            print("⚠️  IPython not available, falling back to standard shell")

    # Use standard Python shell
    import code

    print("🐍 Starting Python shell...")
    print("Type 'exit()' or Ctrl+D to exit")

    shell = code.InteractiveConsole(locals=shell_locals)
    shell.interact(banner="")


def _get_config_value(config, key):
    """Get a nested configuration value using dot notation."""
    keys = key.split(".")
    value = config

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return None

    return value


def _set_config_value(config, key, value):
    """Set a nested configuration value using dot notation."""
    keys = key.split(".")
    current = config

    # Navigate to the parent of the target key
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        elif not isinstance(current[k], dict):
            raise ValueError(f"Cannot set nested value: '{k}' is not a dictionary")
        current = current[k]

    # Set the final value
    current[keys[-1]] = value


def handle_config_show_command(args_ns):
    """Handles the 'config show' command."""
    logger.debug("Config show command started.")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        print(f"❌ Configuration file '{config_path}' not found")
        print("   Run 'serv app init' to create a configuration file")
        return False

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)

        if not config:
            print("❌ Configuration file is empty")
            return False

        print(f"📄 Configuration from '{config_path}':")
        print("=" * 50)

        if args_ns.format == "json":
            print(json.dumps(config, indent=2, default=str))
        else:
            print(
                yaml.dump(config, sort_keys=False, indent=2, default_flow_style=False)
            )

        return True

    except Exception as e:
        logger.error(f"Error reading configuration: {e}")
        print(f"❌ Error reading configuration: {e}")
        return False


def handle_config_validate_command(args_ns):
    """Handles the 'config validate' command."""
    logger.debug("Config validate command started.")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        print(f"❌ Configuration file '{config_path}' not found")
        return False

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)

        if not config:
            print("❌ Configuration file is empty")
            return False

        print("✅ Configuration file is valid YAML")

        # Basic structure validation
        issues = 0

        # Check required sections
        required_sections = ["site_info"]
        for section in required_sections:
            if section not in config:
                print(f"⚠️  Missing recommended section: {section}")
                issues += 1

        # Check site_info structure
        if "site_info" in config:
            site_info = config["site_info"]
            if not isinstance(site_info, dict):
                print("❌ 'site_info' must be a dictionary")
                issues += 1
            elif not site_info.get("name"):
                print("⚠️  Missing 'site_info.name'")
                issues += 1

        # Check plugins structure
        if "plugins" in config:
            plugins = config["plugins"]
            if not isinstance(plugins, list):
                print("❌ 'plugins' must be a list")
                issues += 1

        # Check middleware structure
        if "middleware" in config:
            middleware = config["middleware"]
            if not isinstance(middleware, list):
                print("❌ 'middleware' must be a list")
                issues += 1

        if issues == 0:
            print("🎉 Configuration validation passed!")
        else:
            print(f"⚠️  Found {issues} validation issue(s)")

        return issues == 0

    except yaml.YAMLError as e:
        print(f"❌ Invalid YAML syntax: {e}")
        return False
    except Exception as e:
        logger.error(f"Error validating configuration: {e}")
        print(f"❌ Error validating configuration: {e}")
        return False


def handle_config_get_command(args_ns):
    """Handles the 'config get' command."""
    logger.debug("Config get command started.")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        print(f"❌ Configuration file '{config_path}' not found")
        return False

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)

        if not config:
            print("❌ Configuration file is empty")
            return False

        value = _get_config_value(config, args_ns.key)

        if value is None:
            print(f"❌ Key '{args_ns.key}' not found in configuration")
            return False

        print(f"🔑 {args_ns.key}: {value}")
        return True

    except Exception as e:
        logger.error(f"Error reading configuration: {e}")
        print(f"❌ Error reading configuration: {e}")
        return False


def handle_config_set_command(args_ns):
    """Handles the 'config set' command."""
    logger.debug("Config set command started.")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        print(f"❌ Configuration file '{config_path}' not found")
        print("   Run 'serv app init' to create a configuration file")
        return False

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        # Convert value to appropriate type
        value = args_ns.value
        if args_ns.type == "int":
            value = int(value)
        elif args_ns.type == "float":
            value = float(value)
        elif args_ns.type == "bool":
            value = value.lower() in ("true", "yes", "1", "on")
        elif args_ns.type == "list":
            # Simple comma-separated list
            value = [item.strip() for item in value.split(",")]

        # Set the value
        _set_config_value(config, args_ns.key, value)

        # Write back to file
        with open(config_path, "w") as f:
            yaml.dump(config, f, sort_keys=False, indent=2, default_flow_style=False)

        print(f"✅ Set {args_ns.key} = {value}")
        return True

    except ValueError as e:
        print(f"❌ Invalid value type: {e}")
        return False
    except Exception as e:
        logger.error(f"Error setting configuration: {e}")
        print(f"❌ Error setting configuration: {e}")
        return False
