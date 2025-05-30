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
import traceback
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


def _detect_extension_context(extension_arg=None):
    """Detect which extension to operate on based on context and arguments.

    Returns:
        tuple: (extension_name, extension_dir_path) or (None, None) if not found
    """
    if extension_arg:
        # Extension explicitly specified
        extensions_dir = Path.cwd() / "extensions"
        extension_dir = extensions_dir / extension_arg
        if extension_dir.exists() and (extension_dir / "extension.yaml").exists():
            return extension_arg, extension_dir
        else:
            logger.error(
                f"Extension '{extension_arg}' not found in extensions directory"
            )
            return None, None

    # Check if we're in a extension directory (has extension.yaml)
    if (Path.cwd() / "extension.yaml").exists():
        return Path.cwd().name, Path.cwd()

    # Check if there's only one extension in the extensions directory
    extensions_dir = Path.cwd() / "extensions"
    if extensions_dir.exists():
        extension_dirs = [
            d
            for d in extensions_dir.iterdir()
            if d.is_dir()
            and (d / "extension.yaml").exists()
            and not d.name.startswith("_")
        ]
        if len(extension_dirs) == 1:
            extension_dir = extension_dirs[0]
            return extension_dir.name, extension_dir

    return None, None


def _update_extension_config(extension_dir, component_type, component_name, entry_path):
    """Update the extension.yaml file to include the new component.

    Args:
        extension_dir: Path to the extension directory
        component_type: Type of component ('listeners', 'middleware', 'routers')
        component_name: Name of the component
        entry_path: Entry path for the component
    """
    extension_yaml_path = extension_dir / "extension.yaml"

    try:
        with open(extension_yaml_path) as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Error reading extension config '{extension_yaml_path}': {e}")
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
        with open(extension_yaml_path, "w") as f:
            yaml.dump(config, f, sort_keys=False, indent=2, default_flow_style=False)
        return True
    except Exception as e:
        logger.error(f"Error writing extension config '{extension_yaml_path}': {e}")
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
        print("You can now configure your extensions in this file.")
    except OSError as e:
        logger.error(f"Error writing config file '{config_path}': {e}")


def handle_create_extension_command(args_ns):
    """Handles the 'create extension' command."""
    logger.debug("Create extension command started.")

    # Get extension name from args or prompt for it
    extension_name_human = args_ns.name
    if not extension_name_human:
        if _should_prompt_interactively(args_ns):
            extension_name_human = prompt_user("Extension name")
            if not extension_name_human:
                logger.error("Extension name is required.")
                return
        else:
            logger.error("Extension name is required. Use --name to specify it.")
            return

    # For non-interactive mode, use default values
    if getattr(args_ns, "non_interactive", False):
        extension_author = "Test Author"
        extension_description = "A test extension for Serv"
        extension_version = "1.0.0"
    else:
        extension_author = prompt_user("Author", "Your Name") or "Your Name"
        extension_description = (
            prompt_user("Description", "A cool Serv extension.")
            or "A cool Serv extension."
        )
        extension_version = prompt_user("Version", "0.1.0") or "0.1.0"

    extension_dir_name = to_snake_case(extension_name_human)
    if not extension_dir_name:
        logger.error(
            f"Could not derive a valid module name from '{extension_name_human}'. Please use alphanumeric characters."
        )
        return

    extensions_root_dir = Path.cwd() / "extensions"
    extension_specific_dir = extensions_root_dir / extension_dir_name

    if extension_specific_dir.exists() and not getattr(args_ns, "force", False):
        print(
            f"Warning: Extension directory '{extension_specific_dir}' already exists. Files might be overwritten."
        )

    try:
        os.makedirs(extension_specific_dir, exist_ok=True)
        (extensions_root_dir / "__init__.py").touch(exist_ok=True)
        (extension_specific_dir / "__init__.py").touch(exist_ok=True)

    except OSError as e:
        logger.error(
            f"Error creating extension directory structure '{extension_specific_dir}': {e}"
        )
        return

    # Create extension.yaml (without listeners - those will be added by create listener)
    extension_yaml_path = extension_specific_dir / "extension.yaml"

    extension_yaml_context = {
        "extension_name": extension_name_human,
        "extension_version": extension_version,
        "extension_author": extension_author,
        "extension_description": extension_description,
    }

    try:
        template_dir = (
            Path(importlib.util.find_spec("serv.cli").submodule_search_locations[0])
            / "scaffolding"
        )
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
        template = env.get_template("extension_yaml.template")
        extension_yaml_content_str = template.render(**extension_yaml_context)
    except Exception as e_template:
        logger.error(f"Error loading extension_yaml.template: {e_template}")
        return

    try:
        with open(extension_yaml_path, "w") as f:
            f.write(extension_yaml_content_str)
        print(f"Created '{extension_yaml_path}'")
        print(
            f"Extension '{extension_name_human}' created successfully in '{extension_specific_dir}'."
        )
        print("To add functionality, create listeners with:")
        print(
            f"  serv create listener --name <listener_name> --extension {extension_dir_name}"
        )
        print("To enable the extension, run:")
        print(f"  serv extension enable {extension_dir_name}")

    except OSError as e:
        logger.error(f"Error writing '{extension_yaml_path}': {e}")
        return


def handle_enable_extension_command(args_ns):
    """Handles the 'enable-extension' command."""
    extension_identifier = args_ns.extension_identifier
    logger.debug(f"Attempting to enable extension: '{extension_identifier}'...")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        logger.error(
            f"Configuration file '{config_path}' not found. Please run 'serv init' first."
        )
        return

    # Convert extension identifier to directory name
    extension_id = to_snake_case(extension_identifier)
    extension_name_human = extension_identifier

    # Check if extension directory exists
    extensions_dir = Path.cwd() / "extensions"
    extension_yaml_path = extensions_dir / extension_id / "extension.yaml"

    if not extension_yaml_path.exists():
        logger.error(
            f"Extension '{extension_identifier}' not found. Expected extension.yaml at '{extension_yaml_path}'."
        )
        return

    # Get human name from extension.yaml
    try:
        with open(extension_yaml_path) as f:
            extension_meta = yaml.safe_load(f)
        if isinstance(extension_meta, dict):
            extension_name_human = extension_meta.get("name", extension_identifier)
    except Exception:
        extension_name_human = extension_identifier

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Error reading config file '{config_path}': {e}")
        return

    extensions = config.get("extensions", [])

    # Check if extension is already enabled
    for extension_entry in extensions:
        if isinstance(extension_entry, dict):
            existing_extension = extension_entry.get("extension")
        else:
            existing_extension = extension_entry

        if (
            existing_extension == extension_id
            or existing_extension == extension_identifier
        ):
            print(f"Extension '{extension_identifier}' is already enabled.")
            return

    # Add the extension
    extensions.append({"extension": extension_id})
    config["extensions"] = extensions

    try:
        with open(config_path, "w") as f:
            yaml.dump(config, f, sort_keys=False, indent=2, default_flow_style=False)
        print(f"Extension '{extension_identifier}' enabled successfully.")
        if extension_name_human and extension_name_human != extension_identifier:
            print(f"Human name: {extension_name_human}")
    except Exception as e:
        logger.error(f"Error writing config file '{config_path}': {e}")


def handle_disable_extension_command(args_ns):
    """Handles the 'disable-extension' command."""
    extension_identifier = args_ns.extension_identifier
    logger.debug(f"Attempting to disable extension: '{extension_identifier}'...")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        logger.error(
            f"Configuration file '{config_path}' not found. Please run 'serv init' first."
        )
        return

    # Convert extension identifier to directory name
    extension_id = to_snake_case(extension_identifier)
    extension_name_human = extension_identifier

    # Check if extension directory exists and get human name
    extensions_dir = Path.cwd() / "extensions"
    extension_yaml_path = extensions_dir / extension_id / "extension.yaml"

    if extension_yaml_path.exists():
        try:
            with open(extension_yaml_path) as f:
                extension_meta = yaml.safe_load(f)
            if isinstance(extension_meta, dict):
                extension_name_human = extension_meta.get("name", extension_identifier)
        except Exception:
            extension_name_human = extension_identifier

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Error reading config file '{config_path}': {e}")
        return

    extensions = config.get("extensions", [])
    original_count = len(extensions)

    # Remove the extension
    extensions = [
        p
        for p in extensions
        if (
            (
                isinstance(p, dict)
                and p.get("extension") not in [extension_id, extension_identifier]
            )
            or (isinstance(p, str) and p not in [extension_id, extension_identifier])
        )
    ]

    if len(extensions) == original_count:
        print(f"Extension '{extension_identifier}' was not found in the configuration.")
        return

    config["extensions"] = extensions

    try:
        with open(config_path, "w") as f:
            yaml.dump(config, f, sort_keys=False, indent=2, default_flow_style=False)
        print(f"Extension '{extension_identifier}' disabled successfully.")
        if extension_name_human and extension_name_human != extension_identifier:
            print(f"Human name: {extension_name_human}")
    except Exception as e:
        logger.error(f"Error writing config file '{config_path}': {e}")


def handle_list_extension_command(args_ns):
    """Handles the 'list extension' command."""
    logger.debug("List extension command started.")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE

    if args_ns.available:
        # Show all available extensions in the extensions directory
        extensions_dir = Path.cwd() / "extensions"
        if not extensions_dir.exists():
            print("No extensions directory found.")
            return

        available_extensions = []
        for extension_dir in extensions_dir.iterdir():
            if (
                extension_dir.is_dir()
                and not extension_dir.name.startswith("_")
                and (extension_dir / "extension.yaml").exists()
            ):
                try:
                    with open(extension_dir / "extension.yaml") as f:
                        extension_meta = yaml.safe_load(f) or {}

                    extension_name = extension_meta.get("name", extension_dir.name)
                    extension_version = extension_meta.get("version", "Unknown")
                    extension_description = extension_meta.get(
                        "description", "No description"
                    )

                    available_extensions.append(
                        {
                            "dir_name": extension_dir.name,
                            "name": extension_name,
                            "version": extension_version,
                            "description": extension_description,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Error reading extension metadata for '{extension_dir.name}': {e}"
                    )
                    available_extensions.append(
                        {
                            "dir_name": extension_dir.name,
                            "name": extension_dir.name,
                            "version": "Unknown",
                            "description": "Error reading metadata",
                        }
                    )

        if not available_extensions:
            print("No extensions found in the extensions directory.")
            return

        print(f"Available extensions ({len(available_extensions)}):")
        for extension in available_extensions:
            print(
                f"  • {extension['name']} (v{extension['version']}) [{extension['dir_name']}]"
            )
            print(f"    {extension['description']}")
    else:
        # Show enabled extensions from config
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

        extensions = config.get("extensions", [])

        if not extensions:
            print("No extensions are currently enabled.")
            print("Use 'serv extension enable <extension>' to enable a extension.")
            return

        print(f"Enabled extensions ({len(extensions)}):")
        for extension_entry in extensions:
            if isinstance(extension_entry, dict):
                extension_id = extension_entry.get("extension", "Unknown")
                extension_config = extension_entry.get("config", {})
                config_info = " (with config)" if extension_config else ""
            else:
                extension_id = extension_entry
                config_info = ""

            # Try to get human-readable name from extension metadata
            extension_name = extension_id
            extension_version = "Unknown"

            # Check if this is a directory-based extension
            extensions_dir = Path.cwd() / "extensions"
            if extensions_dir.exists():
                # Extract directory name from extension_id (handle both simple names and module paths)
                if ":" in extension_id:
                    # Full module path like "test_extension.test_extension:TestExtension"
                    module_path = extension_id.split(":")[0]
                    dir_name = module_path.split(".")[0]
                else:
                    # Simple name or just module path
                    dir_name = extension_id.split(".")[0]

                # Try to find the extension directory
                extension_dir = extensions_dir / dir_name
                if (
                    extension_dir.exists()
                    and extension_dir.is_dir()
                    and (extension_dir / "extension.yaml").exists()
                ):
                    try:
                        with open(extension_dir / "extension.yaml") as f:
                            extension_meta = yaml.safe_load(f) or {}
                        extension_name = extension_meta.get("name", extension_id)
                        extension_version = extension_meta.get("version", "Unknown")
                    except Exception:
                        pass

            print(
                f"  • {extension_name} (v{extension_version}) [{extension_id}]{config_info}"
            )


def handle_validate_extension_command(args_ns):
    """Handles the 'extension validate' command."""
    logger.debug("Extension validate command started.")

    extensions_dir = Path.cwd() / "extensions"
    if not extensions_dir.exists():
        print("❌ No extensions directory found.")
        return False

    # Determine which extensions to validate
    if args_ns.extension_identifier and not args_ns.all:
        # Validate specific extension
        extension_dirs = []
        extension_dir = extensions_dir / args_ns.extension_identifier
        if extension_dir.exists() and extension_dir.is_dir():
            extension_dirs = [extension_dir]
        else:
            print(f"❌ Extension '{args_ns.extension_identifier}' not found.")
            return False
    else:
        # Validate all extensions
        extension_dirs = [
            d
            for d in extensions_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        ]

    if not extension_dirs:
        print("ℹ️  No extensions found to validate.")
        return True

    print(f"=== Validating {len(extension_dirs)} Extension(s) ===")

    total_issues = 0

    for extension_dir in extension_dirs:
        print(f"\n🔍 Validating extension: {extension_dir.name}")
        issues = 0

        # Check for extension.yaml
        extension_yaml = extension_dir / "extension.yaml"
        if not extension_yaml.exists():
            print("❌ Missing extension.yaml")
            issues += 1
        else:
            try:
                with open(extension_yaml) as f:
                    extension_config = yaml.safe_load(f)

                if not extension_config:
                    print("❌ extension.yaml is empty")
                    issues += 1
                else:
                    print("✅ extension.yaml is valid YAML")

                    # Check required fields
                    required_fields = ["name", "version"]
                    for field in required_fields:
                        if field not in extension_config:
                            print(f"❌ Missing required field: {field}")
                            issues += 1
                        else:
                            print(f"✅ Has required field: {field}")

                    # Check optional but recommended fields
                    recommended_fields = ["description", "author"]
                    for field in recommended_fields:
                        if field not in extension_config:
                            print(f"⚠️  Missing recommended field: {field}")
                        else:
                            print(f"✅ Has recommended field: {field}")

                    # Validate version format
                    version = extension_config.get("version", "")
                    if (
                        version
                        and not version.replace(".", "")
                        .replace("-", "")
                        .replace("_", "")
                        .isalnum()
                    ):
                        print(f"⚠️  Version format may be invalid: {version}")

            except yaml.YAMLError as e:
                print(f"❌ extension.yaml contains invalid YAML: {e}")
                issues += 1
            except Exception as e:
                print(f"❌ Error reading extension.yaml: {e}")
                issues += 1

        # Check for __init__.py
        init_file = extension_dir / "__init__.py"
        if not init_file.exists():
            print("⚠️  Missing __init__.py (recommended for Python packages)")
        else:
            print("✅ Has __init__.py")

        # Check for Python files
        py_files = list(extension_dir.glob("*.py"))
        if not py_files:
            print("❌ No Python files found")
            issues += 1
        else:
            print(f"✅ Found {len(py_files)} Python file(s)")

            # Check for main extension file (matching directory name)
            expected_main_file = extension_dir / f"{extension_dir.name}.py"
            if expected_main_file.exists():
                print(f"✅ Has main extension file: {expected_main_file.name}")
            else:
                print(
                    f"⚠️  No main extension file found (expected: {extension_dir.name}.py)"
                )

        # Check for common issues
        if (extension_dir / "main.py").exists() and not expected_main_file.exists():
            print(
                f"⚠️  Found main.py but expected {extension_dir.name}.py (consider renaming)"
            )

        # Try to import the extension (basic syntax check)
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
            print(f"🎉 Extension '{extension_dir.name}' validation passed!")
        else:
            print(f"⚠️  Extension '{extension_dir.name}' has {issues} issue(s)")

        total_issues += issues

    print("\n=== Validation Summary ===")
    if total_issues == 0:
        print("🎉 All extensions passed validation!")
    else:
        print(f"⚠️  Found {total_issues} total issue(s) across all extensions")

    return total_issues == 0


def _format_exception_group(exc: Exception, dev_mode: bool = False) -> str:
    """Format an ExceptionGroup with all sub-exceptions for better debugging.

    Args:
        exc: The exception to format (may or may not be an ExceptionGroup)
        dev_mode: Whether to include full tracebacks

    Returns:
        Formatted string with full exception details
    """
    if not isinstance(exc, ExceptionGroup):
        # Not an ExceptionGroup, format normally
        if dev_mode:
            return "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )
        else:
            return str(exc)

    # Format ExceptionGroup with all sub-exceptions
    lines = []
    lines.append(
        f"ExceptionGroup: {exc.message} ({len(exc.exceptions)} sub-exception{'s' if len(exc.exceptions) != 1 else ''})"
    )

    for i, sub_exc in enumerate(exc.exceptions, 1):
        lines.append(f"\n--- Sub-exception {i}/{len(exc.exceptions)} ---")
        lines.append(f"Type: {type(sub_exc).__name__}")
        lines.append(f"Message: {str(sub_exc)}")

        # Include exception notes if present (added by extension loader)
        # Notes are always shown as they provide valuable context without being too verbose
        if hasattr(sub_exc, "__notes__") and sub_exc.__notes__:
            lines.append("Notes:")
            for note in sub_exc.__notes__:
                lines.append(f"  {note}")

        if dev_mode:
            # Include full traceback for each sub-exception
            tb_lines = traceback.format_exception(
                type(sub_exc), sub_exc, sub_exc.__traceback__
            )
            lines.append("Traceback:")
            lines.extend(f"  {line.rstrip()}" for line in tb_lines)

        # Check for nested ExceptionGroups
        if isinstance(sub_exc, ExceptionGroup):
            lines.append("Nested ExceptionGroup:")
            nested_format = _format_exception_group(sub_exc, dev_mode)
            lines.extend(f"  {line}" for line in nested_format.split("\n"))

    return "\n".join(lines)


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

    if hasattr(args_ns, "extension_dirs") and args_ns.extension_dirs:
        app_kwargs["extension_dir"] = args_ns.extension_dirs
    else:
        # Default to ./extensions directory if it exists
        default_extension_dir = Path.cwd() / "extensions"
        if default_extension_dir.exists():
            app_kwargs["extension_dir"] = str(default_extension_dir)

    if hasattr(args_ns, "dev") and args_ns.dev:
        app_kwargs["dev_mode"] = True

    try:
        logger.info(
            f"Instantiating App ({app_class.__name__}) with arguments: {app_kwargs}"
        )
        app = app_class(**app_kwargs)
        return app
    except Exception as e:
        # Check if we're in development mode for enhanced error reporting
        dev_mode = getattr(args_ns, "dev", False) or app_kwargs.get("dev_mode", False)

        if isinstance(e, ExceptionGroup):
            # Format ExceptionGroup with all sub-exceptions
            formatted_error = _format_exception_group(e, dev_mode=dev_mode)
            logger.error(f"Error creating app instance:\n{formatted_error}")
        else:
            # Regular exception handling
            if dev_mode:
                logger.exception("Error creating app instance", exc_info=e)
            else:
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
    extension_name, extension_dir = _detect_extension_context(args_ns.extension)

    if not extension_name:
        if args_ns.extension:
            logger.error(f"Extension '{args_ns.extension}' not found.")
            return
        elif _should_prompt_interactively(args_ns):
            # Interactive prompt for extension
            extensions_dir = Path.cwd() / "extensions"
            if extensions_dir.exists():
                available_extensions = [
                    d.name
                    for d in extensions_dir.iterdir()
                    if d.is_dir()
                    and (d / "extension.yaml").exists()
                    and not d.name.startswith("_")
                ]
                if available_extensions:
                    print("Available extensions:")
                    for i, extension in enumerate(available_extensions, 1):
                        print(f"  {i}. {extension}")
                    extension_choice = prompt_user("Select extension (name or number)")
                    if extension_choice and extension_choice.isdigit():
                        idx = int(extension_choice) - 1
                        if 0 <= idx < len(available_extensions):
                            extension_name = available_extensions[idx]
                            extension_dir = extensions_dir / extension_name
                    elif extension_choice in available_extensions:
                        extension_name = extension_choice
                        extension_dir = extensions_dir / extension_name

            if not extension_name:
                logger.error("No extension specified and none could be auto-detected.")
                return
        else:
            logger.error("No extension specified and none could be auto-detected.")
            return

    class_name = to_pascal_case(component_name)
    file_name = f"listener_{to_snake_case(component_name)}.py"
    file_path = extension_dir / file_name

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

        # Update extension config
        entry_path = f"{file_name[:-3]}:{class_name}"
        if _update_extension_config(
            extension_dir, "listeners", component_name, entry_path
        ):
            print("Added listener to extension configuration")

        print(
            f"Listener '{component_name}' created successfully in extension '{extension_name}'."
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
    extension_name, extension_dir = _detect_extension_context(args_ns.extension)

    if not extension_name:
        if args_ns.extension:
            logger.error(f"Extension '{args_ns.extension}' not found.")
            return
        elif _should_prompt_interactively(args_ns):
            # Interactive prompt for extension
            extensions_dir = Path.cwd() / "extensions"
            if extensions_dir.exists():
                available_extensions = [
                    d.name
                    for d in extensions_dir.iterdir()
                    if d.is_dir()
                    and (d / "extension.yaml").exists()
                    and not d.name.startswith("_")
                ]
                if available_extensions:
                    print("Available extensions:")
                    for i, extension in enumerate(available_extensions, 1):
                        print(f"  {i}. {extension}")
                    extension_choice = prompt_user("Select extension (name or number)")
                    if extension_choice and extension_choice.isdigit():
                        idx = int(extension_choice) - 1
                        if 0 <= idx < len(available_extensions):
                            extension_name = available_extensions[idx]
                            extension_dir = extensions_dir / extension_name
                    elif extension_choice in available_extensions:
                        extension_name = extension_choice
                        extension_dir = extensions_dir / extension_name

            if not extension_name:
                logger.error("No extension specified and none could be auto-detected.")
                return
        else:
            logger.error("No extension specified and none could be auto-detected.")
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
        # Check existing routers in extension config
        extension_yaml_path = extension_dir / "extension.yaml"
        existing_routers = []

        if extension_yaml_path.exists():
            try:
                with open(extension_yaml_path) as f:
                    extension_config = yaml.safe_load(f) or {}

                routers = extension_config.get("routers", [])
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
    file_path = extension_dir / file_name

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

        # Update extension config with router name and path
        entry_path = f"{file_name[:-3]}:{class_name}"
        route_config = {
            "path": route_path,
            "handler": entry_path,
            "router_name": router_name,
            "component_name": component_name,
        }

        if _update_extension_config(
            extension_dir, "routers", component_name, route_config
        ):
            print(f"Added route to router '{router_name}' in extension configuration")

        print(
            f"Route '{component_name}' created successfully in extension '{extension_name}' at path '{route_path}'."
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
    extension_name, extension_dir = _detect_extension_context(args_ns.extension)

    if not extension_name:
        if args_ns.extension:
            logger.error(f"Extension '{args_ns.extension}' not found.")
            return
        elif _should_prompt_interactively(args_ns):
            # Interactive prompt for extension
            extensions_dir = Path.cwd() / "extensions"
            if extensions_dir.exists():
                available_extensions = [
                    d.name
                    for d in extensions_dir.iterdir()
                    if d.is_dir()
                    and (d / "extension.yaml").exists()
                    and not d.name.startswith("_")
                ]
                if available_extensions:
                    print("Available extensions:")
                    for i, extension in enumerate(available_extensions, 1):
                        print(f"  {i}. {extension}")
                    extension_choice = prompt_user("Select extension (name or number)")
                    if extension_choice and extension_choice.isdigit():
                        idx = int(extension_choice) - 1
                        if 0 <= idx < len(available_extensions):
                            extension_name = available_extensions[idx]
                            extension_dir = extensions_dir / extension_name
                    elif extension_choice in available_extensions:
                        extension_name = extension_choice
                        extension_dir = extensions_dir / extension_name

            if not extension_name:
                logger.error("No extension specified and none could be auto-detected.")
                return
        else:
            logger.error("No extension specified and none could be auto-detected.")
            return

    middleware_name = to_snake_case(component_name)
    file_name = f"middleware_{middleware_name}.py"
    file_path = extension_dir / file_name

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

        # Update extension config
        entry_path = f"{file_name[:-3]}:{middleware_name}_middleware"
        if _update_extension_config(
            extension_dir, "middleware", component_name, entry_path
        ):
            print("Added middleware to extension configuration")

        print(
            f"Middleware '{component_name}' created successfully in extension '{extension_name}'."
        )

    except Exception as e:
        logger.error(f"Error creating middleware: {e}")


async def handle_launch_command(args_ns):
    """Handles the 'launch' command."""
    logger.debug("Launch command started.")

    try:
        # Check if dev mode is enabled (global --dev flag)
        dev_mode = getattr(args_ns, "dev", False)

        if dev_mode:
            print("🚀 Starting Serv development server...")
            print("📝 Development mode features:")
            print("   • Auto-reload enabled (unless --no-reload)")
            print("   • Enhanced error reporting")
            print("   • Development mode enabled")

            # Set environment variables for better error reporting
            import os

            os.environ["PYTHONUNBUFFERED"] = "1"  # Ensure immediate output
            os.environ["PYTHONDONTWRITEBYTECODE"] = "1"  # Prevent .pyc files

        app = _get_configured_app(args_ns.app, args_ns)

        # Force development mode if --dev flag is set
        if dev_mode:
            app.dev_mode = True

        if args_ns.dry_run:
            print("=== Dry Run Mode ===")
            print("Application loaded successfully. Server would start with:")
            print(f"  Host: {args_ns.host}")
            print(f"  Port: {args_ns.port}")
            print(f"  Dev Mode: {dev_mode}")
            if dev_mode:
                reload_enabled = not getattr(args_ns, "no_reload", False)
                print(f"  Reload: {reload_enabled}")
            else:
                print(f"  Reload: {args_ns.reload}")
            print(f"  Workers: {args_ns.workers}")
            return

        # Determine reload setting
        if dev_mode:
            # In dev mode, auto-reload is enabled by default unless --no-reload is specified
            reload = not getattr(args_ns, "no_reload", False)
        else:
            # In normal mode, only reload if --reload is explicitly specified
            reload = args_ns.reload

        # Configure uvicorn
        uvicorn_config = {
            "app": app,
            "host": args_ns.host,
            "port": args_ns.port,
            "reload": reload,
            "workers": args_ns.workers
            if not reload
            else 1,  # Reload doesn't work with multiple workers
        }

        # Add dev mode specific configuration
        if dev_mode:
            uvicorn_config.update(
                {
                    "log_level": "debug",
                    "access_log": True,
                    "use_colors": True,
                    "server_header": False,  # Reduce noise in dev mode
                }
            )

        if args_ns.factory:
            # If factory mode, we need to pass the app as a string
            if args_ns.app:
                uvicorn_config["app"] = args_ns.app
            else:
                uvicorn_config["app"] = "serv.app:App"

        if dev_mode:
            logger.info(f"Starting development server on {args_ns.host}:{args_ns.port}")
            if reload:
                print("🔄 Auto-reload is enabled - files will be watched for changes")
            else:
                print("⚠️  Auto-reload is disabled")
        else:
            logger.info(f"Starting Serv application on {args_ns.host}:{args_ns.port}")

        # Start the server
        server = uvicorn.Server(uvicorn.Config(**uvicorn_config))
        await server.serve()

    except KeyboardInterrupt:
        # This should be handled by the main CLI, but just in case
        if dev_mode:
            logger.info("Development server shutdown requested")
        else:
            logger.info("Server shutdown requested")
        raise
    except Exception as e:
        # Enhanced error reporting for development mode
        if dev_mode and isinstance(e, ExceptionGroup):
            formatted_error = _format_exception_group(e, dev_mode=True)
            logger.error(f"Error starting development server:\n{formatted_error}")
        elif dev_mode:
            logger.exception("Error starting development server", exc_info=e)
        else:
            logger.error(f"Error launching application: {e}")
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
    elif args_ns.extensions:
        # Look for extension tests
        extensions_dir = Path.cwd() / "extensions"
        if extensions_dir.exists():
            extension_test_paths = []
            for extension_dir in extensions_dir.iterdir():
                if extension_dir.is_dir() and not extension_dir.name.startswith("_"):
                    test_files = list(extension_dir.glob("test_*.py")) + list(
                        extension_dir.glob("*_test.py")
                    )
                    if test_files:
                        extension_test_paths.extend(str(f) for f in test_files)

            if extension_test_paths:
                pytest_args.extend(extension_test_paths)
                print(f"📦 Found {len(extension_test_paths)} extension test files")
            else:
                print("ℹ️  No extension tests found")
                return True
        else:
            print("⚠️  No extensions directory found")
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

            # Add extensions to shell context
            if hasattr(app, "_extensions"):
                all_extensions = []
                for extension_list in app._extensions.values():
                    all_extensions.extend(extension_list)
                shell_locals["extensions"] = all_extensions
                print(f"🔌 Loaded {len(all_extensions)} extensions into context")

            print("✅ App context loaded successfully")
            print("Available objects: app, serv, extensions, Path, yaml")

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

        # Check extensions structure
        if "extensions" in config:
            extensions = config["extensions"]
            if not isinstance(extensions, list):
                print("❌ 'extensions' must be a list")
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
