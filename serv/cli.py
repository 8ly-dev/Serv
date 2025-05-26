import argparse
import os
import sys
import importlib
import asyncio
from inspect import isclass
from pathlib import Path
import yaml  # PyYAML
import logging
import uvicorn
import re

from serv.config import DEFAULT_CONFIG_FILE, ServConfigError, import_from_string # Keep DEFAULT_CONFIG_FILE and ServConfigError
from serv.app import App # Updated App import
from serv.plugins import Plugin, search_for_plugin_directory # For generated plugin file

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

# --- Helper: Plugin Identifier Resolution --- # This might need App context if plugins are only known by App
# For now, assume it can work standalone for CLI enable/disable which modify config file directly.

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
    config_path = Path.cwd() / DEFAULT_CONFIG_FILE

    if config_path.exists() and not args_ns.force:
        overwrite_prompt = prompt_user(f"'{config_path.name}' already exists in '{Path.cwd()}'. Overwrite? (yes/no)", "no")
        if overwrite_prompt is None or overwrite_prompt.lower() != 'yes':
            print("Initialization cancelled by user.")
            return
    
    # For non-interactive mode, use default values
    if getattr(args_ns, 'non_interactive', False) or (args_ns.force and config_path.exists()):
        site_name = "My Serv Site"
        site_description = "A new website powered by Serv"
    else:
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
#   - plugin: my_plugin  # Directory name in plugin_dir or dot notation (bundled.plugins.welcome)
#     settings:  # Optional settings override for the plugin
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
            # Use a ServConfig structure for clarity, even if dumping parts
            initial_site_info = config_content["site_info"]
            initial_plugins: list = []
            initial_middleware: list = []
            
            yaml.dump({"site_info": initial_site_info}, f, sort_keys=False, indent=2, default_flow_style=False)
            f.write(yaml_plugins_comment)
            yaml.dump({"plugins": initial_plugins}, f, sort_keys=False, indent=2, default_flow_style=False)
            f.write(yaml_middleware_comment)
            yaml.dump({"middleware": initial_middleware}, f, sort_keys=False, indent=2, default_flow_style=False)

        print(f"Successfully created '{config_path}'.")
        print("You can now configure your plugins and middleware in this file.")
    except IOError as e:
        logger.error(f"Error writing config file '{config_path}': {e}")


def handle_create_plugin_command(args_ns):
    """Handles the 'create-plugin' command."""
    logger.debug("Create plugin command started.")

    # For non-interactive mode (--force), use default values
    if getattr(args_ns, 'force', False) and getattr(args_ns, 'non_interactive', False):
        plugin_name_human = "Test Plugin"
        plugin_author = "Test Author"
        plugin_description = "A test plugin for Serv"
        plugin_version = "1.0.0"
    else:
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
        print(f"To use it, add its entry path to your '{DEFAULT_CONFIG_FILE}':")
        print(f"  - entry: {plugin_entry_path}")
        print(f"    config: {{}} # Optional config")

    except IOError as e:
        logger.error(f"Error writing '{plugin_py_path}': {e}")


def handle_enable_plugin_command(args_ns):
    """Handles the 'enable-plugin' command."""
    plugin_identifier = args_ns.plugin_identifier
    logger.debug(f"Attempting to enable plugin: '{plugin_identifier}'...")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        logger.error(f"Configuration file '{config_path}' not found. Please run 'serv init' first.")
        return

    # Check if identifier is a dot-notation path or a simple name
    if ":" in plugin_identifier:
        # Dot notation with class - extract just the module path without class
        plugin_id = plugin_identifier.split(":")[0]
        plugin_name_human = plugin_identifier  # We don't have a human name when using direct dot notation
    else:
        # Simple name or dot notation without class
        plugin_id = plugin_identifier
        module_string, plugin_name_human = _resolve_plugin_module_string(plugin_identifier, Path.cwd())
        name_to_log = plugin_name_human or plugin_identifier

    if ":" in plugin_identifier and not plugin_id:
        logger.error(f"Invalid plugin identifier format: '{plugin_identifier}'. Use a directory name or dot notation.")
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

        # Check for existing plugin entries
        found = False
        for plugin_entry in plugins_list:
            if isinstance(plugin_entry, dict) and plugin_entry.get("plugin") == plugin_id:
                print(f"Plugin '{plugin_id}' is already enabled.")
                found = True
                break
            # For backward compatibility, also check entry format
            elif isinstance(plugin_entry, dict) and plugin_entry.get("entry") == plugin_id:
                print(f"Plugin '{plugin_id}' is already enabled (in old format). Consider updating to new format.")
                found = True
                break

        if not found:
            # Add plugin with new format
            plugins_list.append({"plugin": plugin_id, "settings": {}})
            config_data["plugins"] = plugins_list

            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, sort_keys=False, indent=2, default_flow_style=False)
            print(f"Plugin '{plugin_id}' enabled successfully.")
            print(f"It has been added to '{config_path}'.")

    except Exception as e:
        logger.error(f"Error enabling plugin '{plugin_id}': {e}", exc_info=logger.level == logging.DEBUG)


def handle_disable_plugin_command(args_ns):
    """Handles the 'disable-plugin' command."""
    plugin_identifier = args_ns.plugin_identifier
    logger.debug(f"Attempting to disable plugin: '{plugin_identifier}'...")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        logger.error(f"Configuration file '{config_path}' not found. Cannot disable plugin.")
        return

    # Check if identifier is a dot-notation path or a simple name
    if ":" in plugin_identifier:
        # Dot notation with class - extract just the module path without class
        plugin_id = plugin_identifier.split(":")[0]
    else:
        # Simple name or dot notation without class
        plugin_id = plugin_identifier
        # Try to resolve for better error messages, but don't require it for disabling
        module_string, plugin_name_human = _resolve_plugin_module_string(plugin_identifier, Path.cwd())

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
        
        # Check both plugin and entry fields for backward compatibility
        updated_plugins_list = [
            p for p in plugins_list 
            if not (isinstance(p, dict) and (
                p.get("plugin") == plugin_id or 
                p.get("entry") == plugin_id
            ))
        ]

        if len(updated_plugins_list) < original_count:
            config_data["plugins"] = updated_plugins_list
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, sort_keys=False, indent=2, default_flow_style=False)
            print(f"Plugin '{plugin_id}' disabled successfully.")
            print(f"It has been removed from '{config_path}'.")
        else:
            print(f"Plugin '{plugin_id}' was not found in the enabled plugins list in '{config_path}'.")

    except Exception as e:
        logger.error(f"Error disabling plugin '{plugin_id}': {e}", exc_info=logger.level == logging.DEBUG)


def handle_enable_middleware_command(args_ns):
    """Handles the 'enable-middleware' command."""
    middleware_entry_string = args_ns.middleware_identifier
    logger.debug(f"Attempting to enable middleware: '{middleware_entry_string}'...")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        logger.error(f"Configuration file '{config_path}' not found. Please run 'serv init' first.")
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
    middleware_entry_string = args_ns.middleware_identifier
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
        print(f"To use it, add its entry path to your '{DEFAULT_CONFIG_FILE}' under the 'middleware' section:")
        print(f"  - entry: {entry_path_to_suggest}")
        print(f"    config: {{}} # Optional: Add any config key-value pairs here")
        print(f"Then run: serv enable-middleware {entry_path_to_suggest}")

    except IOError as e:
        logger.error(f"Error writing middleware file '{middleware_py_path}': {e}")


def handle_app_details_command(args_ns):
    """Handles the 'app details' command to display loaded configuration."""
    logger.debug("Displaying application configuration details...")

    config_path_to_load_str = getattr(args_ns, 'config', None)
    plugin_dir_str = getattr(args_ns, 'plugin_dirs', None) # Get from args if specified
    dev_mode_flag = getattr(args_ns, 'dev', False)

    try:
        # Instantiate App to load and process configuration
        # Use default config file if none specified
        app_kwargs = {}
        if config_path_to_load_str is not None:
            app_kwargs['config'] = config_path_to_load_str
        if plugin_dir_str is not None:
            app_kwargs['plugin_dir'] = plugin_dir_str
        if dev_mode_flag:
            app_kwargs['dev_mode'] = dev_mode_flag
            
        app_instance = App(**app_kwargs)

        # Determine the effective config path
        if config_path_to_load_str:
            effective_config_path = Path(config_path_to_load_str).resolve()
        else:
            default_path = Path.cwd() / DEFAULT_CONFIG_FILE
            if default_path.exists():
                effective_config_path = default_path
            else:
                effective_config_path = "(No config file loaded)" # Or some indicator
        
        raw_app_config = app_instance._config

        if not raw_app_config.get("plugins") and not raw_app_config.get("middleware") and not raw_app_config.get("site_info"):
            if isinstance(effective_config_path, Path) and not effective_config_path.exists():
                 logger.info(f"No configuration file found at '{effective_config_path}'. Nothing to display.")
                 print(f"No configuration file found or loaded. Searched at: {effective_config_path}")
                 if not config_path_to_load_str:
                     print(f"You can create one with 'serv init'.")
                 return
            elif isinstance(effective_config_path, Path) and effective_config_path.exists():
                 logger.info(f"Configuration file '{effective_config_path}' was found but appears empty or yielded no Serv configuration. Nothing to display.")
                 print(f"Configuration file loaded: {effective_config_path} (but it appears effectively empty for Serv settings)")
                 return
            else: # No path, and empty config means no file was loaded
                logger.info(f"No configuration specified and default not found. Nothing to display.")
                print(f"No configuration file loaded (no path specified and default '{DEFAULT_CONFIG_FILE}' not found)." )
                if not config_path_to_load_str:
                     print(f"You can create one with 'serv init'.")
                return


        print(f"\n--- Configuration Details ---")
        config_display_path = str(effective_config_path) if isinstance(effective_config_path, Path) else str(effective_config_path)
        print(f"Configuration source: {config_display_path}")
        if app_instance._dev_mode:
            print(f"Development mode: Enabled")
        if hasattr(app_instance, '_plugin_loader') and app_instance._plugin_loader:
            print(f"Plugin directory: {app_instance._plugin_loader.directory}")

        print("\n[Site Information]")
        site_info = raw_app_config.get("site_info", {})
        if site_info:
            for key, value in site_info.items():
                print(f"  {key}: {value}")
        else:
            print("  (No site information configured)")

        print("\n[Plugins]")
        # Accessing app_instance._plugins which is Dict[Path, list[Plugin]]
        # The structure of _plugins might be Dict[Path, List[PluginInstance]]
        # We need to iterate through this and display info.
        # The raw config might be more direct for displaying what *was* in the YAML.
        
        configured_plugins_in_yaml = raw_app_config.get("plugins", [])
        if configured_plugins_in_yaml:
            print("  (As configured in YAML):")
            for i, plugin_entry_yaml in enumerate(configured_plugins_in_yaml):
                if isinstance(plugin_entry_yaml, dict):
                    entry_str = plugin_entry_yaml.get("entry", "<Entry not specified>")
                    print(f"    - Entry: {entry_str}")
                    plugin_cfg_yaml = plugin_entry_yaml.get("config")
                    if isinstance(plugin_cfg_yaml, dict):
                        if plugin_cfg_yaml:
                            print(f"      Config (from YAML):")
                            for key, value in plugin_cfg_yaml.items():
                                print(f"        - {key}: {value}")
                        else:
                            print("      Config (from YAML): (No config settings)")
                    elif plugin_cfg_yaml is None:
                         print("      Config (from YAML): (Not specified)")
                    else:
                        print(f"      Config (from YAML): <Invalid format: {plugin_cfg_yaml}>")
                else:
                    print(f"    - Invalid plugin entry format in YAML: {plugin_entry_yaml}")
            print("\n  (Loaded plugin instances):")
            if app_instance._plugins:
                 for plugin_path_key, plugin_instances_list in app_instance._plugins.items():
                    if not plugin_instances_list:
                        print(f"    - Path key '{plugin_path_key}': No plugins loaded.")
                        continue
                    print(f"    - From source/path key '{plugin_path_key}':")
                    for plugin_obj in plugin_instances_list:
                        plugin_name = getattr(plugin_obj, 'name', plugin_obj.__class__.__name__)
                        print(f"      - Instance: {plugin_name} ({plugin_obj.__class__.__module__}.{plugin_obj.__class__.__name__})")
                        # If plugins have their specific loaded config, display it too
                        # This requires plugin instances to store their config if needed for display
                        # For example: if hasattr(plugin_obj, 'loaded_config') and plugin_obj.loaded_config:
                        #    print(f"        Loaded Config: {plugin_obj.loaded_config}")
            else:
                print("    (No plugin instances currently loaded in the app object)")
        else:
            print("  (No plugins configured in YAML)")
            if app_instance._plugins:
                print("  (However, some plugin instances might be loaded programmatically - check app state if debugging)")

        print("\n[Middleware]")
        # Similar to plugins, display from raw_config and then what's loaded in App
        configured_middleware_in_yaml = raw_app_config.get("middleware", [])
        if configured_middleware_in_yaml:
            print("  (As configured in YAML):")
            for i, mw_entry_yaml in enumerate(configured_middleware_in_yaml):
                if isinstance(mw_entry_yaml, dict):
                    entry_str = mw_entry_yaml.get("entry", "<Entry not specified>")
                    print(f"    - Entry: {entry_str}")
                    mw_cfg_yaml = mw_entry_yaml.get("config")
                    if isinstance(mw_cfg_yaml, dict):
                        if mw_cfg_yaml:
                            print(f"      Config (from YAML):")
                            for key, value in mw_cfg_yaml.items():
                                print(f"        - {key}: {value}")
                        else:
                            print("      Config (from YAML): (No config settings)") 
                    elif mw_cfg_yaml is None:
                        print("      Config (from YAML): (Not specified)") 
                    else:
                        print(f"      Config (from YAML): <Invalid format: {mw_cfg_yaml}>")
                else:
                    print(f"    - Invalid middleware entry format in YAML: {mw_entry_yaml}")
            print("\n  (Loaded middleware handlers/factories):")
            if app_instance._middleware: # This is a list of Callable[[], AsyncIterator[None]]
                for i, mw_factory in enumerate(app_instance._middleware):
                    mw_name = getattr(mw_factory, '__name__', str(mw_factory))
                    # Trying to get module info is harder for factories unless they carry it.
                    print(f"    - Handler/Factory {i+1}: {mw_name}")
            else:
                print("    (No middleware handlers/factories currently loaded in the app object)")
        else:
            print("  (No middleware configured in YAML)")
            if app_instance._middleware:
                print("  (However, some middleware might be loaded programmatically - check app state if debugging)")


        print("\n--------------------------------------------------")

    except ServConfigError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Error loading configuration: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while displaying app details: {e}", exc_info=logger.level == logging.DEBUG)
        print(f"An unexpected error occurred: {e}")

def _get_configured_app(app_module_str: str | None, args_ns) -> App:
    """Helper to instantiate and configure the App object based on CLI args."""
    
    config_path = getattr(args_ns, 'config', None) # Path from --config, or None for default
    plugin_dir_path = getattr(args_ns, 'plugin_dirs', None) # Path from --plugin-dirs or None
    dev_mode_status = getattr(args_ns, 'dev', False)
    
    app_constructor_kwargs = {}
    if config_path is not None:
        app_constructor_kwargs['config'] = config_path
    if plugin_dir_path is not None:
        app_constructor_kwargs['plugin_dir'] = plugin_dir_path
    if dev_mode_status:
        app_constructor_kwargs['dev_mode'] = dev_mode_status

    # The app_module_str is for custom App *classes*, not instances directly from config.
    # If app_module_str is given, it means the user wants to use a *different App class*.
    if app_module_str:
        if ":" not in app_module_str:
            logger.error(f"App module string '{app_module_str}' must use colon notation (module.path:ClassName). Using default App.")
            app_class = App # Default serv.app.App
        else:
            try:
                logger.info(f"Loading custom App class from '{app_module_str}'...")
                app_class = import_from_string(app_module_str)
                if not isclass(app_class) or not issubclass(app_class, App):
                    logger.error(f"'{app_module_str}' did not resolve to a subclass of serv.app.App. Using default App.")
            except ServConfigError as e:
                logger.error(f"Error importing custom App class from '{app_module_str}': {e}. Using default App.")
                app_class = App # Fallback to default
    else:
        app_class = App # Default serv.app.App

    try:
        logger.info(f"Instantiating App ({app_class.__name__}) with arguments: {app_constructor_kwargs}")
        app_instance = app_class(**app_constructor_kwargs)
        logger.info("App instance created and configured.")
        return app_instance
    except ServConfigError as e:
        logger.error(f"Failed to configure and instantiate application: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred during app instantiation: {e}", exc_info=dev_mode_status)
        sys.exit(1)


async def handle_launch_command(args_ns):
    """Handles the 'launch' command to start the Uvicorn server."""
    app_module_str = args_ns.app # This is for a custom App CLASS, not an instance string for uvicorn
    
    # _get_configured_app now handles loading the App class and instantiating it with config
    app_target_instance = _get_configured_app(app_module_str, args_ns)

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
            app_target_instance, # Pass the app instance directly
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
        logger.error(f"Failed to run the Uvicorn server: {e}", exc_info=True)
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
    parser.add_argument(
        '--app', '-a',
        help='Custom application CLASS in the format "module.path:ClassName". If not provided, Serv\'s default App is'
             ' used.',
        default=None, # Default is to use serv.app.App
    )
    parser.add_argument(
        '--config', '-c',
        help=f'Path to config file. Default: ./{DEFAULT_CONFIG_FILE} or App default.',
        default=None # App will handle its default if this is None
    )
    parser.add_argument(
        '--plugin-dirs', # Name changed for consistency, was plugin_dirs before
        help='Directory to search for plugins. Default: ./plugins or App default.',
        default=None # App will handle its default
    )
    # No middleware_dirs needed at this top level, App handles its middleware sources via config

    # Subparsers for subcommands
    subparsers = parser.add_subparsers(title="commands", dest="command", required=False,
                                       help="Command to execute")
    
    # --- App Parent Parser --- (for commands that might need a configured app instance)
    # Some commands like 'init' or 'create-plugin' don't need a fully configured app instance.
    # Others like 'launch' or 'app details' do.
    # The global --config, --plugin-dirs, --dev args can be used by commands that build an App instance.

    # Create a parent parser for commands that operate on an app context
    # This helps avoid redefining --config, --plugin-dirs, --dev for each of them.
    # However, the current structure already puts these at the top level, which is fine.
    # Let's ensure launch_parser correctly inherits/uses them.

    # Launch parser
    # Remove app_parent_parser inheritance if its args are now global
    launch_parser = subparsers.add_parser('launch', #parents=[app_parent_parser], # app_parent_parser removed
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
    launch_parser.add_argument('--dev', action='store_true',
                             help="Enable development mode for the application."
    )
    # Important: Remove duplicate plugin/middleware args since they're inherited from app_parent_parser
    launch_parser.set_defaults(func=handle_launch_command)

    # App commands
    app_parser = subparsers.add_parser('app',
                                      help='App management commands')
    app_subparsers = app_parser.add_subparsers(title="app commands", dest="app_command", required=True,
                                             help="App command to execute")
    
    # App init command
    app_init_parser = app_subparsers.add_parser('init',
                                              help='Initialize a new Serv project')
    app_init_parser.add_argument('--force', action='store_true',
                               help='Force overwrite of existing config file')
    app_init_parser.add_argument('--non-interactive', action='store_true', dest='non_interactive',
                               help='Non-interactive mode with default values (for testing)')
    app_init_parser.set_defaults(func=handle_init_command)
    
    # App details command
    app_details_parser = app_subparsers.add_parser('details',
                                                 help='Display application configuration')
    app_details_parser.set_defaults(func=handle_app_details_command)
    
    # Plugin commands
    plugin_parser = subparsers.add_parser('plugin',
                                        help='Plugin management commands')
    plugin_subparsers = plugin_parser.add_subparsers(title="plugin commands", dest="plugin_command", required=True,
                                                   help="Plugin command to execute")
    
    # Plugin create command
    plugin_create_parser = plugin_subparsers.add_parser('create',
                                                      help='Create a new plugin')
    plugin_create_parser.add_argument('--force', action='store_true',
                                    help='Force overwrite of existing plugin')
    plugin_create_parser.add_argument('--non-interactive', action='store_true', dest='non_interactive',
                                    help='Non-interactive mode with default values (for testing)')
    plugin_create_parser.set_defaults(func=handle_create_plugin_command)
    
    # Plugin enable command
    plugin_enable_parser = plugin_subparsers.add_parser('enable',
                                                      help='Enable a plugin')
    plugin_enable_parser.add_argument('plugin_identifier',
                                    help='Plugin identifier (directory name or module path)')
    plugin_enable_parser.set_defaults(func=handle_enable_plugin_command)
    
    # Plugin disable command
    plugin_disable_parser = plugin_subparsers.add_parser('disable',
                                                       help='Disable a plugin')
    plugin_disable_parser.add_argument('plugin_identifier',
                                     help='Plugin identifier (directory name or module path)')
    plugin_disable_parser.set_defaults(func=handle_disable_plugin_command)
    
    # Middleware commands
    middleware_parser = subparsers.add_parser('middleware',
                                            help='Middleware management commands')
    middleware_subparsers = middleware_parser.add_subparsers(title="middleware commands", dest="middleware_command", required=True,
                                                           help="Middleware command to execute")
    
    # Middleware create command
    middleware_create_parser = middleware_subparsers.add_parser('create',
                                                              help='Create a new middleware')
    middleware_create_parser.add_argument('--force', action='store_true',
                                        help='Force overwrite of existing middleware')
    middleware_create_parser.set_defaults(func=handle_create_middleware_command)
    
    # Middleware enable command
    middleware_enable_parser = middleware_subparsers.add_parser('enable',
                                                              help='Enable a middleware')
    middleware_enable_parser.add_argument('middleware_identifier',
                                        help='Middleware identifier (file name without .py extension)')
    middleware_enable_parser.set_defaults(func=handle_enable_middleware_command)
    
    # Middleware disable command
    middleware_disable_parser = middleware_subparsers.add_parser('disable',
                                                               help='Disable a middleware')
    middleware_disable_parser.add_argument('middleware_identifier',
                                         help='Middleware identifier (file name without .py extension)')
    middleware_disable_parser.set_defaults(func=handle_disable_middleware_command)

    # ... existing subparsers ...

    # Process args
    args_ns = parser.parse_args()

    # Process comma-separated directory lists into actual lists
    # if hasattr(args_ns, 'plugin_dirs') and isinstance(args_ns.plugin_dirs, str):
    #     args_ns.plugin_dirs = [d.strip() for d in args_ns.plugin_dirs.split(',') if d.strip()]
    #
    # if hasattr(args_ns, 'middleware_dirs') and isinstance(args_ns.middleware_dirs, str):
    #     args_ns.middleware_dirs = [d.strip() for d in args_ns.middleware_dirs.split(',') if d.strip()]

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