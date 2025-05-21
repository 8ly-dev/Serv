import argparse
import os
import sys
import importlib
import asyncio
from inspect import isawaitable
from pathlib import Path
import yaml  # PyYAML
import logging
import uvicorn
import re
from bevy import dependency # For dependency injection

from serv.config import import_module_from_string, load_raw_config, setup_app_from_config, DEFAULT_CONFIG_FILE, import_from_string, ServConfigError
from serv.app import App as DefaultApp # Default app
from serv.plugins import Plugin, search_for_plugin_directory # For generated plugin file
from serv.loader import ServLoader


# Logging setup
logger = logging.getLogger("serv")
if not logger.hasHandlers():
    handler = logging.StreamHandler(sys.stdout)
    # Basic format, can be overridden by app's own logging config
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    if os.getenv("SERV_DEBUG"): # More verbose if SERV_DEBUG is set
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# --- Helper Functions ---

def to_pascal_case(name: str) -> str:
    """Converts a string to PascalCase."""
    name = name.replace('-', ' ').replace('_', ' ')
    parts = name.split(' ')
    processed_parts = []
    for part in parts:
        if not part:
            continue
        # Handle 'v' followed by digit, e.g., v2 -> V2
        if len(part) > 1 and part[0].lower() == 'v' and part[1:].isdigit():
            processed_parts.append('V' + part[1:])
        else:
            processed_parts.append(part.capitalize())
    return "".join(processed_parts)

def to_snake_case(name: str) -> str:
    """Converts a string to snake_case. Handles spaces, hyphens, and existing PascalCase/camelCase."""
    s = re.sub(r'[\s-]+', '_', name) # Replace spaces/hyphens with underscores
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', s) # Underscore before capital if followed by lowercase
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s).lower() # Underscore before capital if followed by lowercase/digit
    s = re.sub(r'_+', '_', s) # Consolidate multiple underscores
    s = s.strip('_') # Remove leading/trailing underscores
    return s

def prompt_user(text: str, default: str | None = None) -> str:
    """Prompts the user for input with an optional default value."""
    prompt_text = f"{text}"
    if default is not None:
        prompt_text += f" [{default}]"
    prompt_text += ": "

    while True:
        response = input(prompt_text).strip()
        if response:
            return response
        if default is not None:
            return default
        # Do not print error for empty if default is None, let it loop
        # Or, if input is truly required:
        # print("Input cannot be empty.")


# --- Helper: Plugin Identifier Resolution ---

def _resolve_plugin_module_string(identifier: str, project_root: Path) -> tuple[str | None, str | None]:
    """Resolves a plugin identifier to its module string and name.

    Args:
        identifier: The plugin identifier (simple name or full module.path:Class).
        project_root: The root directory of the project (usually CWD).

    Returns:
        A tuple (module_string, plugin_name_human) or (None, None) if not found.
        plugin_name_human is extracted from plugin.yaml if resolved via simple name.
    """
    plugins_dir = project_root / "plugins"
    if ":" in identifier:
        # Assume it's a direct module string. We don't have a simple name here.
        return identifier, None # No simple name to derive human name from, user provided full path

    # Simple name. Convert to snake_case for directory lookup.
    dir_name = to_snake_case(identifier)
    if not dir_name:
        logger.error(f"Could not derive a valid directory name from identifier '{identifier}'.")
        return None, None

    plugin_yaml_path = plugins_dir / dir_name / "plugin.yaml"

    if not plugin_yaml_path.exists():
        logger.warning(f"Plugin configuration '{plugin_yaml_path}' not found for simple name '{identifier}'.")
        logger.warning(f"Attempted to find it for directory '{dir_name}'. Ensure the plugin exists and the name is correct.")
        return None, None

    try:
        with open(plugin_yaml_path, 'r') as f:
            plugin_meta = yaml.safe_load(f)
        if not isinstance(plugin_meta, dict):
            logger.error(f"Invalid YAML format in '{plugin_yaml_path}'. Expected a dictionary.")
            return None, None

        entry_string = plugin_meta.get("entry")
        plugin_name_human = plugin_meta.get("name", identifier) # Fallback to identifier if name not in yaml

        if not entry_string:
            logger.error(f"'entry' key not found in '{plugin_yaml_path}'.")
            return None, None
        return entry_string, plugin_name_human
    except Exception as e:
        logger.error(f"Error reading or parsing '{plugin_yaml_path}': {e}")
        return None, None


# --- Command Handlers ---

def handle_init_command(args_ns):
    """Handles the 'init' command to create serv.config.yaml."""
    logger.debug("Init command started.")
    config_path = Path.cwd() / "serv.config.yaml"

    if config_path.exists() and not args_ns.force:
        overwrite_prompt = prompt_user(f"'{config_path.name}' already exists in '{Path.cwd()}'. Overwrite? (yes/no)", "no")
        if overwrite_prompt is None or overwrite_prompt.lower() != 'yes':
            print("Initialization cancelled by user.")
            return

    site_name = prompt_user("Enter site name", "My Serv Site") or "My Serv Site"
    site_description = prompt_user("Enter site description", "A new website powered by Serv") or "A new website powered by Serv"

    config_content = {
        "site_info": {
            "name": site_name,
            "description": site_description,
        },
        "plugins": [],
        "middleware": [],
    }

    yaml_header = f"""# Serv Configuration File
# Created by 'serv init'

# Site-wide information, accessible via app.site_info
# name: {site_name}
# description: {site_description}
# You can add other custom key-value pairs under site_info.

"""
    yaml_plugins_comment = """
# List of plugins to load.
# Plugins extend Serv's functionality.
# Use 'python -m serv create-plugin' to scaffold a new plugin.
# Example:
# plugins:
#   - entry: plugins.my_example_plugin.main:MyExamplePlugin
#     config: # Optional configuration for the plugin
#       some_setting: "value"
"""
    yaml_middleware_comment = """
# List of middleware to apply.
# Middleware process requests and responses globally.
# Example:
# middleware:
#   - entry: my_project.middleware:my_timing_middleware
#     config: # Optional configuration for the middleware
#       enabled: true
"""

    try:
        with open(config_path, "w") as f:
            f.write(yaml_header)
            yaml.dump({"site_info": config_content["site_info"]}, f, sort_keys=False, indent=2, default_flow_style=False)
            f.write(yaml_plugins_comment)
            yaml.dump({"plugins": config_content["plugins"]}, f, sort_keys=False, indent=2, default_flow_style=False)
            f.write(yaml_middleware_comment)
            yaml.dump({"middleware": config_content["middleware"]}, f, sort_keys=False, indent=2, default_flow_style=False)

        print(f"Successfully created '{config_path}'.")
        print("You can now configure your plugins and middleware in this file.")
    except IOError as e:
        logger.error(f"Error writing config file '{config_path}': {e}")


def handle_create_plugin_command(args_ns):
    """Handles the 'create-plugin' command."""
    logger.debug("Create plugin command started.")

    plugin_name_human = prompt_user("Plugin Name (e.g., 'My Awesome Plugin')")
    if not plugin_name_human:
        logger.error("Plugin name cannot be empty. Aborting.")
        return

    plugin_author = prompt_user("Author", "Your Name") or "Your Name"
    plugin_description = prompt_user("Description", "A cool Serv plugin.") or "A cool Serv plugin."
    plugin_version = prompt_user("Version", "0.1.0") or "0.1.0"

    class_name = to_pascal_case(plugin_name_human)
    module_base_name = to_snake_case(plugin_name_human)
    if not module_base_name:
        logger.error(f"Could not derive a valid module name from '{plugin_name_human}'. Please use alphanumeric characters.")
        return

    plugin_dir_name = module_base_name
    python_file_name = "main.py"

    plugins_root_dir = Path.cwd() / "plugins"
    plugin_specific_dir = plugins_root_dir / plugin_dir_name

    if plugin_specific_dir.exists() and not getattr(args_ns, 'force', False):
        print(f"Warning: Plugin directory '{plugin_specific_dir}' already exists. Files might be overwritten.")

    try:
        os.makedirs(plugin_specific_dir, exist_ok=True)
        (plugins_root_dir / "__init__.py").touch(exist_ok=True)
        (plugin_specific_dir / "__init__.py").touch(exist_ok=True)

    except OSError as e:
        logger.error(f"Error creating plugin directory structure '{plugin_specific_dir}': {e}")
        return

    # Create plugin.yaml
    plugin_yaml_path = plugin_specific_dir / "plugin.yaml"
    plugin_entry_path = f"plugins.{plugin_dir_name}.{python_file_name.replace('.py', '')}:{class_name}"

    plugin_yaml_context = {
        "plugin_name_human": plugin_name_human,
        "plugin_entry_path": plugin_entry_path,
        "plugin_version": plugin_version,
        "plugin_author": plugin_author,
        "plugin_description": plugin_description,
    }

    try:
        template_path = Path(importlib.util.find_spec("serv").submodule_search_locations[0]) / "scaffolding" / "plugin_yaml.template"
        with open(template_path, "r") as f_template:
            plugin_yaml_template_content = f_template.read()
    except Exception as e_template:
        logger.error(f"Error loading plugin_yaml.template: {e_template}")
        return

    plugin_yaml_content_str = plugin_yaml_template_content.format(**plugin_yaml_context)

    try:
        with open(plugin_yaml_path, "w") as f:
            f.write(plugin_yaml_content_str)
        print(f"Created '{plugin_yaml_path}'")
    except IOError as e:
        logger.error(f"Error writing '{plugin_yaml_path}': {e}")
        return

    # Create main.py (plugin Python file)
    plugin_py_path = plugin_specific_dir / python_file_name

    plugin_py_context = {
        "class_name": class_name,
        "module_base_name": module_base_name,
    }

    try:
        template_path = Path(importlib.util.find_spec("serv").submodule_search_locations[0]) / "scaffolding" / "plugin_main_py.template"
        with open(template_path, "r") as f_template:
            plugin_py_template_content = f_template.read()
    except Exception as e_template:
        logger.error(f"Error loading plugin_main_py.template: {e_template}")
        return

    plugin_py_content_str = plugin_py_template_content.format(**plugin_py_context)

    try:
        with open(plugin_py_path, "w") as f:
            f.write(plugin_py_content_str)
        print(f"Created '{plugin_py_path}'")
        print(f"Plugin '{plugin_name_human}' created successfully in '{plugin_specific_dir}'.")
        print(f"To use it, add its entry path to your 'serv.config.yaml':")
        print(f"  - entry: {plugin_entry_path}")
        print(f"    config: {{}} # Optional config")

    except IOError as e:
        logger.error(f"Error writing '{plugin_py_path}': {e}")


def handle_enable_plugin_command(args_ns):
    """Handles the 'enable-plugin' command."""
    plugin_identifier = args_ns.plugin_identifier
    logger.debug(f"Attempting to enable plugin: '{plugin_identifier}'...")

    config_path = Path.cwd() / "serv.config.yaml"
    if not config_path.exists():
        logger.error(f"Configuration file '{config_path}' not found. Please run 'serv app init' first.")
        return

    module_string, plugin_name_human = _resolve_plugin_module_string(plugin_identifier, Path.cwd())
    name_to_log = plugin_name_human or module_string

    if not module_string:
        logger.error(f"Could not resolve plugin '{plugin_identifier}'. Enable command aborted.")
        return

    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f) or {}
        if not isinstance(config_data, dict):
            logger.error(f"Invalid YAML format in '{config_path}'. Expected a dictionary. Aborting.")
            return

        plugins_list = config_data.get("plugins", [])
        if not isinstance(plugins_list, list):
            logger.error(f"'plugins' section in '{config_path}' is not a list. Aborting.")
            return

        found = False
        for plugin_entry in plugins_list:
            if isinstance(plugin_entry, dict) and plugin_entry.get("entry") == module_string:
                print(f"Plugin '{name_to_log}' ({module_string}) is already enabled.")
                found = True
                break

        if not found:
            plugins_list.append({"entry": module_string, "config": {}})
            config_data["plugins"] = plugins_list

            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, sort_keys=False, indent=2, default_flow_style=False)
            print(f"Plugin '{name_to_log}' ({module_string}) enabled successfully.")
            print(f"It has been added to '{config_path}'.")

    except Exception as e:
        logger.error(f"Error enabling plugin '{name_to_log}': {e}", exc_info=logger.level == logging.DEBUG)


def handle_disable_plugin_command(args_ns):
    """Handles the 'disable-plugin' command."""
    plugin_identifier = args_ns.plugin_identifier
    logger.debug(f"Attempting to disable plugin: '{plugin_identifier}'...")

    config_path = Path.cwd() / "serv.config.yaml"
    if not config_path.exists():
        logger.error(f"Configuration file '{config_path}' not found. Cannot disable plugin.")
        return

    module_string, plugin_name_human = _resolve_plugin_module_string(plugin_identifier, Path.cwd())
    name_to_log = plugin_name_human or module_string

    if not module_string:
        logger.error(f"Could not resolve plugin '{plugin_identifier}'. Disable command aborted.")
        return

    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        if not config_data or not isinstance(config_data, dict):
            print(f"Warning: Configuration file '{config_path}' is empty or invalid. Cannot disable plugin.")
            return

        plugins_list = config_data.get("plugins", [])
        if not isinstance(plugins_list, list):
            logger.error(f"'plugins' section in '{config_path}' is not a list. Aborting.")
            return

        original_count = len(plugins_list)
        updated_plugins_list = [p for p in plugins_list if not (isinstance(p, dict) and p.get("entry") == module_string)]

        if len(updated_plugins_list) < original_count:
            config_data["plugins"] = updated_plugins_list
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, sort_keys=False, indent=2, default_flow_style=False)
            print(f"Plugin '{name_to_log}' ({module_string}) disabled successfully.")
            print(f"It has been removed from '{config_path}'.")
        else:
            print(f"Plugin '{name_to_log}' ({module_string}) was not found in the enabled plugins list in '{config_path}'.")

    except Exception as e:
        logger.error(f"Error disabling plugin '{name_to_log}': {e}", exc_info=logger.level == logging.DEBUG)


def handle_enable_middleware_command(args_ns):
    """Handles the 'enable-middleware' command."""
    middleware_entry_string = args_ns.middleware_entry_string
    logger.debug(f"Attempting to enable middleware: '{middleware_entry_string}'...")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        logger.error(f"Configuration file '{config_path}' not found. Please run 'serv app init' first.")
        return

    if ":" not in middleware_entry_string:
        logger.error(f"Invalid middleware entry string format: '{middleware_entry_string}'. Expected 'module.path:CallableName'.")
        return

    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f) or {}
        if not isinstance(config_data, dict):
            logger.error(f"Invalid YAML format in '{config_path}'. Expected a dictionary. Aborting.")
            return

        middlewares_list = config_data.get("middleware", [])
        if not isinstance(middlewares_list, list):
            logger.error(f"'middleware' section in '{config_path}' is not a list. Aborting.")
            return

        found = False
        for mw_entry in middlewares_list:
            if isinstance(mw_entry, dict) and mw_entry.get("entry") == middleware_entry_string:
                print(f"Middleware '{middleware_entry_string}' is already enabled.")
                found = True
                break

        if not found:
            middlewares_list.append({"entry": middleware_entry_string, "config": {}})
            config_data["middleware"] = middlewares_list

            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, sort_keys=False, indent=2, default_flow_style=False)
            print(f"Middleware '{middleware_entry_string}' enabled successfully.")
            print(f"It has been added to '{config_path}'.")

    except Exception as e:
        logger.error(f"Error enabling middleware '{middleware_entry_string}': {e}", exc_info=logger.level == logging.DEBUG)


def handle_disable_middleware_command(args_ns):
    """Handles the 'disable-middleware' command."""
    middleware_entry_string = args_ns.middleware_entry_string
    logger.debug(f"Attempting to disable middleware: '{middleware_entry_string}'...")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        logger.error(f"Configuration file '{config_path}' not found. Cannot disable middleware.")
        return

    if ":" not in middleware_entry_string:
        logger.error(f"Invalid middleware entry string format for disable: '{middleware_entry_string}'. Expected 'module.path:CallableName'.")
        return

    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        if not config_data or not isinstance(config_data, dict):
            print(f"Warning: Configuration file '{config_path}' is empty or invalid. Cannot disable middleware.")
            return

        middlewares_list = config_data.get("middleware", [])
        if not isinstance(middlewares_list, list):
            logger.error(f"'middleware' section in '{config_path}' is not a list. Aborting.")
            return

        original_count = len(middlewares_list)
        updated_middlewares_list = [
            mw for mw in middlewares_list
            if not (isinstance(mw, dict) and mw.get("entry") == middleware_entry_string)
        ]

        if len(updated_middlewares_list) < original_count:
            config_data["middleware"] = updated_middlewares_list
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, sort_keys=False, indent=2, default_flow_style=False)
            print(f"Middleware '{middleware_entry_string}' disabled successfully.")
            print(f"It has been removed from '{config_path}'.")
        else:
            print(f"Middleware '{middleware_entry_string}' was not found in the enabled middleware list in '{config_path}'.")

    except Exception as e:
        logger.error(f"Error disabling middleware '{middleware_entry_string}': {e}", exc_info=logger.level == logging.DEBUG)


def handle_create_middleware_command(args_ns):
    """Handles the 'create-middleware' command."""
    logger.debug("Creating a new Serv middleware...")

    mw_name_human = prompt_user("Middleware Name (e.g., 'Request Logger')")
    if not mw_name_human:
        logger.error("Middleware name cannot be empty. Aborting.")
        return

    mw_description = prompt_user("Description", f"A middleware for {mw_name_human}.") or f"A middleware for {mw_name_human}."

    class_name_base = to_pascal_case(mw_name_human)
    package_dir_name = to_snake_case(mw_name_human)
    python_main_file_name = "main.py"

    if not package_dir_name:
        logger.error(f"Could not derive a valid directory name from '{mw_name_human}'. Please use alphanumeric characters.")
        return

    middleware_class_name = f"{class_name_base}Middleware"

    middleware_root_dir = Path.cwd() / "middleware"
    middleware_package_dir = middleware_root_dir / package_dir_name
    middleware_py_path = middleware_package_dir / python_main_file_name

    try:
        os.makedirs(middleware_package_dir, exist_ok=True)
        (middleware_root_dir / "__init__.py").touch(exist_ok=True)
        (middleware_package_dir / "__init__.py").touch(exist_ok=True)
    except OSError as e:
        logger.error(f"Error creating middleware directory structure '{middleware_package_dir}': {e}")
        return

    middleware_py_context = {
        "mw_description": mw_description,
        "middleware_class_name": middleware_class_name,
        "mw_name_human": mw_name_human,
    }

    try:
        template_path = Path(importlib.util.find_spec("serv").submodule_search_locations[0]) / "scaffolding" / "middleware_main_py.template"
        with open(template_path, "r") as f_template:
            middleware_py_template_content = f_template.read()
    except Exception as e_template:
        logger.error(f"Error loading middleware_main_py.template: {e_template}")
        return

    middleware_py_content_str = middleware_py_template_content.format(**middleware_py_context)

    try:
        with open(middleware_py_path, "w") as f:
            f.write(middleware_py_content_str)
        print(f"Created middleware file: '{middleware_py_path}'")

        entry_path_to_suggest = f"middleware.{package_dir_name}.{python_main_file_name.replace('.py', '')}:{middleware_class_name}"
        print(f"Middleware '{mw_name_human}' created successfully in '{middleware_package_dir}'.")
        print(f"To use it, add its entry path to your 'serv.config.yaml' under the 'middleware' section:")
        print(f"  - entry: {entry_path_to_suggest}")
        print(f"    config: {{}} # Optional: Add any config key-value pairs here")
        print(f"Then run: serv middleware enable {entry_path_to_suggest}")

    except IOError as e:
        logger.error(f"Error writing middleware file '{middleware_py_path}': {e}")


def handle_app_details_command(args_ns):
    """Handles the 'app details' command to display loaded configuration."""
    logger.debug("Displaying application configuration details...")

    config_path_to_load = getattr(args_ns, 'config', None)

    try:
        raw_config = load_raw_config(config_path_to_load)
        effective_config_path_str = config_path_to_load or os.getenv("SERV_CONFIG_PATH") or DEFAULT_CONFIG_FILE
        effective_config_path = Path(effective_config_path_str).resolve()

        if not raw_config and not effective_config_path.exists():
            logger.info(f"No configuration file found at expected paths (checked: '{effective_config_path}', env var, default). Nothing to display.")
            print(f"No configuration file loaded. Searched at: {effective_config_path}")
            if not config_path_to_load:
                 print(f"You can create one with 'serv app init'.")
            return

        if not raw_config and effective_config_path.exists():
            logger.info(f"Configuration file '{effective_config_path}' was found but is empty or invalid. Nothing to display.")
            print(f"Configuration file loaded: {effective_config_path} (but it's empty or invalid)")
            return

        print(f"\n--- Configuration Details ---")
        print(f"Configuration file: {effective_config_path}")

        local_plugin_names_map = {}
        plugins_root_dir = Path.cwd() / "plugins"
        if plugins_root_dir.is_dir():
            for plugin_dir_item in plugins_root_dir.iterdir():
                if plugin_dir_item.is_dir():
                    plugin_yaml_path = plugin_dir_item / "plugin.yaml"
                    if plugin_yaml_path.is_file():
                        try:
                            with open(plugin_yaml_path, 'r') as f_yaml:
                                meta = yaml.safe_load(f_yaml)
                            if isinstance(meta, dict):
                                module_str = meta.get("entry")
                                human_name = meta.get("name")
                                if module_str and human_name:
                                    local_plugin_names_map[module_str] = human_name
                        except Exception as e_scan:
                            logger.debug(f"Error scanning {plugin_yaml_path} for plugin name mapping: {e_scan}")

        print("\n[Site Information]")
        site_info = raw_config.get("site_info")
        if site_info and isinstance(site_info, dict):
            for key, value in site_info.items():
                print(f"  {key}: {value}")
        elif site_info is not None:
             print(f"  Site info is present but not in the expected format: {site_info}")
        else:
            print("  (No site information configured)")

        print("\n[Plugins]")
        plugins = raw_config.get("plugins", [])
        if plugins:
            for i, plugin_entry in enumerate(plugins):
                if isinstance(plugin_entry, dict):
                    entry = plugin_entry.get("entry")
                    if not entry:
                        print(f"  - Plugin {i+1}: <Entry path not specified in serv.config.yaml>")
                        continue
                    try:
                        module_import_path = entry.split(":")[0]
                        module = import_module_from_string(module_import_path)
                        plugin_path = search_for_plugin_directory(Path(module.__file__))
                        plugin_settings = load_raw_config(plugin_path / "plugin.yaml")

                        plugin_path_resolved = plugin_path.resolve()
                        plugin_path_string = str(plugin_path_resolved)

                        print(f"  - {plugin_settings.get('name')}")
                        print(f"    - Entry: {entry}")
                        print(f"    - Path: {plugin_path_string}")
                    except ServConfigError as e_import:
                        print(f"  - Plugin entry: {entry}")
                        print(f"    - Error: Could not load/inspect plugin. {e_import}")
                    except Exception as e_generic:
                        print(f"  - Plugin entry: {entry}")
                        print(f"    - Error: An unexpected error occurred while inspecting plugin: {e_generic}")

                    plugin_config_value = plugin_entry.get("config")
                    if isinstance(plugin_config_value, dict):
                        if plugin_config_value:
                            print(f"    - Config:")
                            for key, value in plugin_config_value.items():
                                print(f"        - {key}: {value}")
                        else:
                            print("    - Config: (No config settings)")
                    elif plugin_config_value is None:
                        print("    - (No specific configuration provided)")
                    else:
                        print(f"    - Config: <Invalid format: {plugin_config_value}>")
                else:
                    print(f"  - Plugin {i+1}: <Invalid entry format: {plugin_entry}>")
        else:
            print("  (No plugins configured)")

        print("\n[Middleware]")
        middlewares = raw_config.get("middleware", [])
        if middlewares:
            for i, mw_entry in enumerate(middlewares):
                if isinstance(mw_entry, dict):
                    module = mw_entry.get("entry", "<Module not specified>")
                    print(f"  - {module}")
                    mw_config_value = mw_entry.get("config")
                    if isinstance(mw_config_value, dict):
                        if mw_config_value:
                            for key, value in mw_config_value.items():
                                print(f"    - {key}: {value}")
                        else:
                            print("    - Config: No Settings")
                    elif mw_config_value is None:
                        print("    - (No specific configuration provided)")
                    else:
                        print(f"    - Config: <Invalid format: {mw_config_value}>")
                else:
                    print(f"  - Middleware {i+1}: <Invalid entry format: {mw_entry}>")
        else:
            print("  (No middleware configured)")

        print("\n--------------------------------------------------")

    except ServConfigError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Error loading configuration: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while displaying app details: {e}", exc_info=logger.level == logging.DEBUG)
        print(f"An unexpected error occurred: {e}")

def _get_configured_app_factory(app_module_str: str, config_path_str: str | None, args=None):
    def factory():
        # Get the app and config path from the factory variables
        try:
            # Load config first
            app_obj = None
            raw_config = {}
            config_path = Path(config_path_str) if config_path_str else None
            
            if config_path and config_path.exists():
                raw_config = load_raw_config(config_path)
                if not raw_config or not isinstance(raw_config, dict):
                    print(f"Warning: Config file '{config_path}' is empty or not a valid YAML dictionary.")
                    raw_config = {}
            elif config_path_str:
                print(f"Warning: Config file '{config_path_str}' not found.")
            
            # Next, try to import the app module
            if app_module_str:
                print(f"Loading app from '{app_module_str}'...")
                try:
                    if ":" in app_module_str:
                        if getattr(args, 'factory', False):
                            # This is referring to a factory function
                            factory_callable = import_from_string(app_module_str)
                            app_obj = factory_callable()
                        else:
                            # This is a direct app instance
                            app_obj = import_from_string(app_module_str)
                    else:
                        # Basic module, assume app variable
                        module = importlib.import_module(app_module_str)
                        if hasattr(module, 'app'):
                            app_obj = module.app
                        else:
                            print(f"App module '{app_module_str}' imported, but no 'app' variable found. Please specify the full path to the app instance (e.g., 'module:app').")
                            return None
                except ImportError as e:
                    print(f"Error importing app from '{app_module_str}': {e}")
                    return None
            else:
                # No app module provided, create a default app
                app_obj = DefaultApp()
            
            # Apply Serv configuration to the app if it's a Serv app
            if app_obj and isinstance(app_obj, DefaultApp):
                # Create the loader with plugin and middleware directories from args
                plugin_dirs = getattr(args, 'plugin_dirs', ['./plugins'])
                middleware_dirs = getattr(args, 'middleware_dirs', ['./middleware'])
                loader = ServLoader(plugin_dirs=plugin_dirs, middleware_dirs=middleware_dirs)
                
                print(f"Configuring Serv app from '{config_path_str if config_path_str else 'default settings'}'...")
                if raw_config:
                    setup_app_from_config(app_obj, raw_config)
            else:
                print(f"Imported app '{app_module_str}' is not a Serv App instance. Skipping Serv config application.")
            
            return app_obj
        except Exception as e:
            print(f"Error configuring app: {e}")
            return None
    
    # Return the factory function
    return factory


async def handle_launch_command(args_ns):
    """Handles the 'launch' command to start the Uvicorn server."""
    app_module_str = args_ns.app
    app_target: any

    if args_ns.factory:
        app_target_factory = _get_configured_app_factory(app_module_str, args_ns.config, args_ns)
        app_target = app_target_factory
        logger.debug(f"Using application factory: '{app_module_str}' (via Serv wrapper factory).")
    else:
        if args_ns.reload:
            app_target_factory = _get_configured_app_factory(app_module_str, args_ns.config, args_ns)
            app_target = app_target_factory
            logger.debug(f"Running '{app_module_str}' with reload, using Serv's app factory for configuration.")
        else:
            try:
                temp_factory = _get_configured_app_factory(app_module_str, args_ns.config, args_ns)
                app_target = temp_factory()
                logger.debug(f"Running pre-configured app instance for '{app_module_str}'.")
            except Exception as e:
                logger.warning(f"Could not pre-load/configure '{app_module_str}', passing string to Uvicorn: {e}")
                app_target = app_module_str

    # If dry-run flag is set, exit after loading the app
    if args_ns.dry_run:
        print("App, config, plugins, and middleware loaded successfully.")
        print("\nDry run complete. Exiting without starting the server.")
        return

    uvicorn_log_level = "debug" if logger.level == logging.DEBUG else "info"
    num_workers = None
    if args_ns.workers is not None:
        if args_ns.workers == 0:
            num_workers = None
        elif args_ns.workers > 0:
            num_workers = args_ns.workers

    if args_ns.reload and num_workers is not None and num_workers > 1:
        logger.warning("Number of workers is ignored when reload is enabled. Using 1 worker.")
        if num_workers == 0:
            pass
        else:
             num_workers = 1

    try:
        # Configure Uvicorn with the loop
        config = uvicorn.Config(
            app_target,
            host=args_ns.host,
            port=args_ns.port,
            reload=args_ns.reload,
            workers=num_workers,
            log_level=uvicorn_log_level,
            loop="asyncio",  # Ensure Uvicorn uses the asyncio loop
        )
        server = uvicorn.Server(config)
        await server.serve()
    except ImportError as e:
        if app_module_str in str(e):
             logger.error(f"Error: App module '{app_module_str}' could not be found or imported.")
             logger.error("Please ensure it's a valid Python module string (e.g., 'my_app.main:app')")
             logger.error("and that the file exists and is in your Python path (e.g., run from project root).")
        else:
            logger.error(f"An import error occurred: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to run the Uvicorn server: {e}", exc_info=logger.level == logging.DEBUG)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        prog="serv",
        description="Command-line interface for the Serv web framework."
    )
    serv_version = "0.1.0-dev" # Placeholder

    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {serv_version}'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help="Enable debug logging for Serv CLI and potentially the app."
    )

    # Common parser for commands that use the application
    app_parent_parser = argparse.ArgumentParser(add_help=False)
    app_parent_parser.add_argument('--app', '-a',
                            help='Application module and app instance in the format "module.path:app_instance"',
                            default=None)
    app_parent_parser.add_argument('--config', '-c',
                            help=f'Path to config file. Default: {DEFAULT_CONFIG_FILE}',
                            default=DEFAULT_CONFIG_FILE)
    # Add plugin and middleware directory arguments
    app_parent_parser.add_argument('--plugin-dirs',
                            help='Comma-separated list of plugin directories to search',
                            default='./plugins')
    app_parent_parser.add_argument('--middleware-dirs', '-m',
                            help='Comma-separated list of middleware directories to search',
                            default='./middleware')
    
    # Subparsers for subcommands
    subparsers = parser.add_subparsers(title="commands", dest="command", required=False,
                                       help="Command to execute")
    
    # Launch parser
    launch_parser = subparsers.add_parser('launch', parents=[app_parent_parser], 
                                        help='Launch the Serv application.')
    launch_parser.add_argument('--host', 
                             help='Bind socket to this host. Default: 127.0.0.1',
                             default='127.0.0.1')
    launch_parser.add_argument('--port', '-p', type=int,
                             help='Bind socket to this port. Default: 8000',
                             default=8000)
    launch_parser.add_argument('--reload', action='store_true',
                             help='Enable auto-reload.')
    launch_parser.add_argument('--workers', '-w', type=int,
                             help='Number of worker processes. Defaults to 1.',
                             default=1)
    launch_parser.add_argument('--factory', action='store_true',
                             help="Treat APP_MODULE as an application factory string (e.g., 'module:create_app')."
    )
    launch_parser.add_argument('--dry-run', action='store_true',
                             help="Load and configure the app, plugins, and middleware but don't start the server."
    )
    # Important: Remove duplicate plugin/middleware args since they're inherited from app_parent_parser
    launch_parser.set_defaults(func=handle_launch_command)
    
    # ... existing subparsers ...
    
    # Process args
    args_ns = parser.parse_args()
    
    # Process comma-separated directory lists into actual lists
    if hasattr(args_ns, 'plugin_dirs') and isinstance(args_ns.plugin_dirs, str):
        args_ns.plugin_dirs = [d.strip() for d in args_ns.plugin_dirs.split(',') if d.strip()]
    
    if hasattr(args_ns, 'middleware_dirs') and isinstance(args_ns.middleware_dirs, str):
        args_ns.middleware_dirs = [d.strip() for d in args_ns.middleware_dirs.split(',') if d.strip()]
    
    if args_ns.debug or os.getenv("SERV_DEBUG"):
        os.environ["SERV_DEBUG"] = "1"
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")
    
    current_args_to_use = args_ns
    
    if not hasattr(args_ns, 'command') or args_ns.command is None:
        # No command specified, default to 'launch'
        non_command_cli_args = sys.argv[1:]
        logger.debug(f"No command specified. Defaulting to 'launch'. Using CLI args: {non_command_cli_args}")
        try:
            launch_specific_args = launch_parser.parse_args(non_command_cli_args)
            for global_arg_name in ['debug', 'version']:
                if hasattr(args_ns, global_arg_name):
                    setattr(launch_specific_args, global_arg_name, getattr(args_ns, global_arg_name))
            current_args_to_use = launch_specific_args
            current_args_to_use.func = handle_launch_command # Ensure func is set
        except SystemExit:
            # If there's a parsing error, let's use the original args to show help
            parser.print_help()
            sys.exit(1)
    
    if hasattr(current_args_to_use, 'func'):
        # Use async if the handler is async
        handler = current_args_to_use.func
        if asyncio.iscoroutinefunction(handler):
            asyncio.run(handler(current_args_to_use))
        else:
            handler(current_args_to_use)
    else:
        # No command found, show help
        parser.print_help()

if __name__ == "__main__":
    main()