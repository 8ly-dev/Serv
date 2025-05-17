import argparse
import os
import sys
import importlib
from pathlib import Path
import yaml  # PyYAML
import logging
import uvicorn
import re
from bevy import dependency # For dependency injection

from serv.config import import_module_from_string, load_raw_config, setup_app_from_config, DEFAULT_CONFIG_FILE, import_from_string, ServConfigError
from serv.app import App as DefaultApp # Default app
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
    logger.info("Initializing Serv project...")
    config_path = Path.cwd() / "serv.config.yaml"

    if config_path.exists() and not args_ns.force:
        overwrite_prompt = prompt_user(f"'{config_path.name}' already exists in '{Path.cwd()}'. Overwrite? (yes/no)", "no")
        if overwrite_prompt is None or overwrite_prompt.lower() != 'yes': # prompt_user might return None if input is empty and no default
            logger.info("Initialization cancelled.")
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
#   - module: plugins.my_example_plugin.main:MyExamplePlugin
#     config: # Optional configuration for the plugin
#       some_setting: "value"
"""
    yaml_middleware_comment = """
# List of middleware to apply.
# Middleware process requests and responses globally.
# Example:
# middleware:
#   - module: my_project.middleware:my_timing_middleware
#     config: # Optional configuration for the middleware
#       enabled: true
"""

    try:
        with open(config_path, "w") as f:
            f.write(yaml_header)
            # Dump site_info
            yaml.dump({"site_info": config_content["site_info"]}, f, sort_keys=False, indent=2, default_flow_style=False)
            f.write(yaml_plugins_comment)
            yaml.dump({"plugins": config_content["plugins"]}, f, sort_keys=False, indent=2, default_flow_style=False)
            f.write(yaml_middleware_comment)
            yaml.dump({"middleware": config_content["middleware"]}, f, sort_keys=False, indent=2, default_flow_style=False)
            
        logger.info(f"Successfully created '{config_path}'.")
        logger.info("You can now configure your plugins and middleware in this file.")
        logger.info("Use 'python -m serv create-plugin' to scaffold a new plugin structure.")
        logger.info("Run your app with 'python -m serv run'.")
    except IOError as e:
        logger.error(f"Error writing config file '{config_path}': {e}")


def handle_create_plugin_command(args_ns):
    """Handles the 'create-plugin' command."""
    logger.info("Creating a new Serv plugin...")

    plugin_name_human = prompt_user("Plugin Name (e.g., 'My Awesome Plugin')")
    if not plugin_name_human: # Should be handled by prompt_user requiring input if no default
        logger.error("Plugin name cannot be empty. Aborting.")
        return

    plugin_author = prompt_user("Author", "Your Name") or "Your Name"
    plugin_description = prompt_user("Description", "A cool Serv plugin.") or "A cool Serv plugin."
    plugin_version = prompt_user("Version", "0.1.0") or "0.1.0"

    class_name = to_pascal_case(plugin_name_human)
    module_base_name = to_snake_case(plugin_name_human)
    if not module_base_name: # e.g. if plugin_name_human was just symbols
        logger.error(f"Could not derive a valid module name from '{plugin_name_human}'. Please use alphanumeric characters.")
        return
    
    plugin_dir_name = module_base_name
    python_file_name = "main.py"

    plugins_root_dir = Path.cwd() / "plugins"
    plugin_specific_dir = plugins_root_dir / plugin_dir_name

    if plugin_specific_dir.exists() and not getattr(args_ns, 'force', False): # Assuming a --force could be added
        logger.warning(f"Plugin directory '{plugin_specific_dir}' already exists. Files might be overwritten.")
        # Add a prompt here if not --force? For now, proceed.

    try:
        os.makedirs(plugin_specific_dir, exist_ok=True)
        # Create __init__.py in plugins_root_dir to make 'plugins' a package
        (plugins_root_dir / "__init__.py").touch(exist_ok=True)
        # Create __init__.py in plugin_specific_dir to make it a package
        (plugin_specific_dir / "__init__.py").touch(exist_ok=True)

    except OSError as e:
        logger.error(f"Error creating plugin directory structure '{plugin_specific_dir}': {e}")
        return

    # Create plugin.yaml
    plugin_yaml_path = plugin_specific_dir / "plugin.yaml"
    plugin_entry_path = f"plugins.{plugin_dir_name}.{python_file_name.replace('.py', '')}:{class_name}"
    
    # Prepare context for plugin.yaml template
    plugin_yaml_context = {
        "plugin_name_human": plugin_name_human,
        "plugin_entry_path": plugin_entry_path,
        "plugin_version": plugin_version,
        "plugin_author": plugin_author,
        "plugin_description": plugin_description,
    }
    
    # Load plugin.yaml template
    try:
        # Assuming serv is installed or PYTHONPATH is set to find serv.scaffolding
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
        logger.info(f"Created '{plugin_yaml_path}'")
    except IOError as e:
        logger.error(f"Error writing '{plugin_yaml_path}': {e}")
        return

    # Create main.py (plugin Python file)
    plugin_py_path = plugin_specific_dir / python_file_name
    
    # Prepare context for plugin_main_py.template
    plugin_py_context = {
        "class_name": class_name,
        "module_base_name": module_base_name,
        # Add any other variables needed by the template, e.g., plugin_name_human
    }

    # Load plugin_main_py.template
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
        logger.info(f"Created '{plugin_py_path}'")
        logger.info(f"Plugin '{plugin_name_human}' created successfully in '{plugin_specific_dir}'.")
        logger.info(f"To use it, add its entry path to your 'serv.config.yaml':")
        logger.info(f"  - entry: {plugin_entry_path}")
        logger.info(f"    config: {{}} # Optional config")

    except IOError as e:
        logger.error(f"Error writing '{plugin_py_path}': {e}")


def handle_enable_plugin_command(args_ns):
    """Handles the 'enable-plugin' command."""
    plugin_identifier = args_ns.plugin_identifier
    logger.info(f"Attempting to enable plugin: '{plugin_identifier}'...")

    config_path = Path.cwd() / "serv.config.yaml"
    if not config_path.exists():
        logger.error(f"Configuration file '{config_path}' not found. Please run 'serv app init' first.")
        return

    module_string, plugin_name_human = _resolve_plugin_module_string(plugin_identifier, Path.cwd())
    name_to_log = plugin_name_human or module_string # Use human name if available

    if not module_string:
        logger.error(f"Could not resolve plugin '{plugin_identifier}'. Enable command aborted.")
        return

    try:
        with open(config_path, 'r') as f:
            # Using SafeLoader is good, but for preserving comments/structure, ruamel.yaml would be better.
            # Sticking to PyYAML for now as it's an existing dependency.
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
                logger.info(f"Plugin '{name_to_log}' ({module_string}) is already enabled.")
                found = True
                break
        
        if not found:
            plugins_list.append({"entry": module_string, "config": {}})
            config_data["plugins"] = plugins_list
            
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, sort_keys=False, indent=2, default_flow_style=False)
            logger.info(f"Plugin '{name_to_log}' ({module_string}) enabled successfully.")
            logger.info(f"It has been added to '{config_path}'.")
        
    except Exception as e:
        logger.error(f"Error enabling plugin '{name_to_log}': {e}", exc_info=True)


def handle_disable_plugin_command(args_ns):
    """Handles the 'disable-plugin' command."""
    plugin_identifier = args_ns.plugin_identifier
    logger.info(f"Attempting to disable plugin: '{plugin_identifier}'...")

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
            logger.warning(f"Configuration file '{config_path}' is empty or invalid. Cannot disable plugin.")
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
            logger.info(f"Plugin '{name_to_log}' ({module_string}) disabled successfully.")
            logger.info(f"It has been removed from '{config_path}'.")
        else:
            logger.info(f"Plugin '{name_to_log}' ({module_string}) was not found in the enabled plugins list in '{config_path}'.")

    except Exception as e:
        logger.error(f"Error disabling plugin '{name_to_log}': {e}", exc_info=True)


def handle_enable_middleware_command(args_ns):
    """Handles the 'enable-middleware' command."""
    middleware_entry_string = args_ns.middleware_entry_string
    logger.info(f"Attempting to enable middleware: '{middleware_entry_string}'...")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        logger.error(f"Configuration file '{config_path}' not found. Please run 'serv app init' first.")
        return

    # Validate the entry string format basic check
    if ":" not in middleware_entry_string:
        logger.error(f"Invalid middleware entry string format: '{middleware_entry_string}'. Expected 'module.path:CallableName'.")
        return
        
    # We could try to import_from_string here to validate, but setup_app_from_config will do that eventually.
    # For enabling, we'll assume the user provides a correct string.

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
                logger.info(f"Middleware '{middleware_entry_string}' is already enabled.")
                found = True
                break
        
        if not found:
            middlewares_list.append({"entry": middleware_entry_string, "config": {}})
            config_data["middleware"] = middlewares_list
            
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, sort_keys=False, indent=2, default_flow_style=False)
            logger.info(f"Middleware '{middleware_entry_string}' enabled successfully.")
            logger.info(f"It has been added to '{config_path}'.")
        
    except Exception as e:
        logger.error(f"Error enabling middleware '{middleware_entry_string}': {e}", exc_info=True)


def handle_disable_middleware_command(args_ns):
    """Handles the 'disable-middleware' command."""
    middleware_entry_string = args_ns.middleware_entry_string
    logger.info(f"Attempting to disable middleware: '{middleware_entry_string}'...")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        logger.error(f"Configuration file '{config_path}' not found. Cannot disable middleware.")
        return

    if ":" not in middleware_entry_string: # Basic check, consistent with enable
        logger.error(f"Invalid middleware entry string format for disable: '{middleware_entry_string}'. Expected 'module.path:CallableName'.")
        return

    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        if not config_data or not isinstance(config_data, dict):
            logger.warning(f"Configuration file '{config_path}' is empty or invalid. Cannot disable middleware.")
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
            logger.info(f"Middleware '{middleware_entry_string}' disabled successfully.")
            logger.info(f"It has been removed from '{config_path}'.")
        else:
            logger.info(f"Middleware '{middleware_entry_string}' was not found in the enabled middleware list in '{config_path}'.")

    except Exception as e:
        logger.error(f"Error disabling middleware '{middleware_entry_string}': {e}", exc_info=True)


def handle_create_middleware_command(args_ns):
    """Handles the 'create-middleware' command."""
    logger.info("Creating a new Serv middleware...")

    mw_name_human = prompt_user("Middleware Name (e.g., 'Request Logger')")
    if not mw_name_human:
        logger.error("Middleware name cannot be empty. Aborting.")
        return
    
    mw_description = prompt_user("Description", f"A middleware for {mw_name_human}.") or f"A middleware for {mw_name_human}."

    class_name_base = to_pascal_case(mw_name_human)
    package_dir_name = to_snake_case(mw_name_human) # This will be the directory name for the package
    python_main_file_name = "main.py" # The main file within the package

    if not package_dir_name:
        logger.error(f"Could not derive a valid directory name from '{mw_name_human}'. Please use alphanumeric characters.")
        return

    middleware_class_name = f"{class_name_base}Middleware"
    # python_file_name = f"{package_dir_name}.py" # Old way, single file

    middleware_root_dir = Path.cwd() / "middleware"
    middleware_package_dir = middleware_root_dir / package_dir_name # Path to the new package directory
    middleware_py_path = middleware_package_dir / python_main_file_name # Path to main.py within the package

    try:
        os.makedirs(middleware_package_dir, exist_ok=True)
        (middleware_root_dir / "__init__.py").touch(exist_ok=True) # __init__.py in ./middleware/
        (middleware_package_dir / "__init__.py").touch(exist_ok=True) # __init__.py in ./middleware/<package_name>/
    except OSError as e:
        logger.error(f"Error creating middleware directory structure '{middleware_package_dir}': {e}")
        return

    # Create middleware Python file (main.py)
    # Prepare context for middleware_main_py.template
    middleware_py_context = {
        "mw_description": mw_description,
        "middleware_class_name": middleware_class_name,
        "mw_name_human": mw_name_human, # Potentially useful in the template
    }

    # Load middleware_main_py.template
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
        logger.info(f"Created middleware file: '{middleware_py_path}'")
        
        entry_path_to_suggest = f"middleware.{package_dir_name}.{python_main_file_name.replace('.py', '')}:{middleware_class_name}"
        logger.info(f"Middleware '{mw_name_human}' created successfully in '{middleware_package_dir}'.")
        logger.info(f"To use it, add its entry path to your 'serv.config.yaml' under the 'middleware' section:")
        logger.info(f"  - entry: {entry_path_to_suggest}")
        logger.info(f"    config: {{}} # Optional: Add any config key-value pairs here")
        logger.info(f"Then run: serv middleware enable {entry_path_to_suggest}")

    except IOError as e:
        logger.error(f"Error writing middleware file '{middleware_py_path}': {e}")


def handle_app_details_command(args_ns):
    """Handles the 'app details' command to display loaded configuration."""
    # Determine config path: use --config from args if provided, else default behavior of load_raw_config
    # The args_ns for 'app details' might not have a specific 'config' attribute unless we add it or make it global.
    # For now, let's assume load_raw_config(None) correctly uses its default search (env var, then DEFAULT_CONFIG_FILE)
    # If a global --config option is desired for all commands, argparse setup would need adjustment.
    # Let's assume for now that if `serv --config path app details` is used, args_ns would have `config`.
    # If not, load_raw_config(None) will use its internal default logic.
    
    config_path_to_load = getattr(args_ns, 'config', None) # Check if a global --config was parsed
    
    try:
        raw_config = load_raw_config(config_path_to_load)
        # load_raw_config now prints INFO if default is not found and returns {}. It raises error if specified path not found.
        # We need to know which path was actually attempted/loaded for accurate display.
        
        # Re-determine the path that load_raw_config would have used for display purposes
        # This duplicates some logic from load_raw_config but is for display only.
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

        print(f"Configuration file: {effective_config_path}")

        # Pre-scan local plugins to get their human-readable names mapped to module strings
        local_plugin_names_map = {}
        plugins_root_dir = Path.cwd() / "plugins"
        if plugins_root_dir.is_dir():
            for plugin_dir_item in plugins_root_dir.iterdir():
                if plugin_dir_item.is_dir(): # Iterate through potential plugin directories
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

        # Site Info
        print("\n[Site Information]")
        site_info = raw_config.get("site_info")
        if site_info and isinstance(site_info, dict):
            for key, value in site_info.items():
                print(f"  {key}: {value}")
        elif site_info is not None: # Present but not a dict
             print(f"  Site info is present but not in the expected format: {site_info}")
        else:
            print("  (No site information configured)")

        # Plugins
        print("\n[Plugins]")
        plugins = raw_config.get("plugins", [])
        if plugins:
            for i, plugin_entry in enumerate(plugins):
                if isinstance(plugin_entry, dict):
                    entry = plugin_entry.get("entry")
                    module_import_path = entry.split(":")[0]
                    module = import_module_from_string(module_import_path)
                    plugin_path = search_for_plugin_directory(Path(module.__file__))
                    plugin_settings = load_raw_config(plugin_path / "plugin.yaml")

                    plugin_path = plugin_path.resolve()
                    relative_paths = {
                        "[Bundled Plugins]": Path(__file__).parent / "bundled_plugins",
                        "[Python]": Path(sys.executable).parent,
                        ".": Path.cwd(),
                        "~": Path.home(),
                    }
                    for relative_name, relative_path in relative_paths.items():
                        if plugin_path.is_relative_to(relative_path):
                            plugin_path_string = f"{relative_name}/{plugin_path.relative_to(relative_path)}"
                            break

                    else:
                        plugin_path_string = str(plugin_path)


                    print(f"  - {plugin_settings.get('name')}")
                    print(f"    - Entry: {entry}")
                    print(f"    - Path: {plugin_path_string}")
                    
                    plugin_config_value = plugin_entry.get("config")
                    if isinstance(plugin_config_value, dict):
                        if plugin_config_value: # Non-empty dict
                            print(f"    - Config:")
                            for key, value in plugin_config_value.items():
                                print(f"        - {key}: {value}")
                        else: # Empty dict {}
                            print("    - Config: (No config settings)")
                    elif plugin_config_value is None: # 'config' key not present
                        print("    - (No specific configuration provided)")
                    else: # 'config' key present but not a dict (and not None)
                        print(f"    - Config: <Invalid format: {plugin_config_value}>")
                else:
                    print(f"  - Plugin {i+1}: <Invalid entry format: {plugin_entry}>")
        else:
            print("  (No plugins configured)")

        # Middleware
        print("\n[Middleware]")
        middlewares = raw_config.get("middleware", [])
        if middlewares:
            for i, mw_entry in enumerate(middlewares):
                if isinstance(mw_entry, dict):
                    # Middleware typically doesn't have a local plugin.yaml to scan for a human name in the same way.
                    # So, we will continue to display the module string directly for middleware.
                    module = mw_entry.get("entry", "<Module not specified>")
                    print(f"  - {module}")
                    mw_config_value = mw_entry.get("config")
                    if isinstance(mw_config_value, dict):
                        if mw_config_value: # Non-empty dict
                            for key, value in mw_config_value.items():
                                print(f"    - {key}: {value}")
                        else: # Empty dict {}
                            print("    - Config: No Settings")
                    elif mw_config_value is None: # 'config' key not present
                        print("    - (No specific configuration provided)")
                    else: # 'config' key present but not a dict (and not None)
                        print(f"    - Config: <Invalid format: {mw_config_value}>")
                else:
                    print(f"  - Middleware {i+1}: <Invalid entry format: {mw_entry}>")
        else:
            print("  (No middleware configured)")

    except ServConfigError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Error loading configuration: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while displaying app details: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}")

def _get_configured_app_factory(app_module_str: str, config_path_str: str | None):
    """
    Returns a factory function that Uvicorn can use.
    This factory imports/creates the app and applies Serv configuration.
    """
    def factory():
        logger.debug(f"App factory called for '{app_module_str}' with config '{config_path_str}'")
        app_obj = None
        try:
            # If it's the default app, instantiate it directly.
            if app_module_str == "serv.app:App":
                app_obj = DefaultApp()
            else: # Otherwise, import it (could be an instance or another factory)
                imported = import_from_string(app_module_str)
                if callable(imported) and not isinstance(imported, DefaultApp.__class__): # It's a factory function
                    logger.debug(f"Imported '{app_module_str}' is a callable factory. Calling it.")
                    app_obj = imported() 
                else: # It's an instance
                    app_obj = imported
            
            if app_obj is None:
                raise ImportError(f"Could not load app object from '{app_module_str}'")

            # Apply Serv configuration if it's a Serv App instance (or compatible)
            # This check helps avoid errors if app_obj is, e.g., a FastAPI app not meant for Serv's config.
            if isinstance(app_obj, DefaultApp) or (hasattr(app_obj, 'plugins_config') and hasattr(app_obj, 'router')):
                config_data = load_raw_config(config_path_str) # load_raw_config handles None path
                
                if config_data:
                    logger.info(f"Applying configuration from '{config_path_str or DEFAULT_CONFIG_FILE}' to '{app_module_str}'.")
                    setup_app_from_config(app_obj, config_data)
                else: # No config file found or it was empty
                    logger.info(f"No configuration file found or it's empty for '{app_module_str}'.")
                    # Load WelcomePlugin if default app and no config file was effectively used
                    if isinstance(app_obj, DefaultApp):
                        logger.info("Attempting to load bundled WelcomePlugin by default as no config file was used.")
                        try:
                            from serv.bundled_plugins.welcome import WelcomePlugin
                            welcome_plugin_instance = WelcomePlugin()
                            
                            # Manually set plugin_name and version if not done by Plugin base class
                            # These would normally come from plugin.yaml via PluginManager
                            if not hasattr(welcome_plugin_instance, 'name') or not welcome_plugin_instance.name:
                                 welcome_plugin_instance.name = "Serv Welcome Plugin (Bundled)"
                            if not hasattr(welcome_plugin_instance, 'version') or not welcome_plugin_instance.version:
                                 welcome_plugin_instance.version = "bundled"
                            
                            app_obj.add_plugin(welcome_plugin_instance)
                            logger.info(f"Successfully added '{welcome_plugin_instance.name}' to the application.")
                            
                            # Call on_app_startup manually as it's not going through the full plugin manager lifecycle
                            # that would normally call it after all plugins are loaded.
                            if hasattr(welcome_plugin_instance, 'on_app_startup'):
                                 welcome_plugin_instance.on_app_startup(app_obj)
                                 logger.info(f"Executed on_app_startup for '{welcome_plugin_instance.name}'.")

                        except ImportError as e:
                            logger.warning(f"Could not import bundled WelcomePlugin: {e}. Ensure it exists at serv.bundled_plugins.welcome")
                        except Exception as e:
                            logger.error(f"Error loading or starting bundled WelcomePlugin: {e}", exc_info=True)
            else:
                logger.info(f"Imported app '{app_module_str}' is not a Serv App instance. Skipping Serv config application.")

            return app_obj
            
        except ImportError:
            logger.error(f"Could not import app module '{app_module_str}'.", exc_info=True)
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error loading or configuring app '{app_module_str}' in factory: {e}", exc_info=True)
            sys.exit(1)
    return factory


def handle_launch_command(args_ns):
    """Handles the 'launch' command to start the Uvicorn server."""
    app_module_str = args_ns.app_module
    
    # Determine the application target for Uvicorn
    # Uvicorn's `factory` flag means app_target string is "module:factory_func_name"
    # If not using --factory, app_target can be an instance or "module:instance_name"
    
    app_target: any # Can be an app instance or a string path for uvicorn

    if args_ns.factory:
        # User specified --factory, app_module_str is "module:actual_user_factory"
        # We wrap this in our own factory to ensure Serv config can be applied if it's a Serv app.
        # However, the original intent of --factory might be for non-Serv apps too.
        # Let's use our factory to load *their* factory, then configure if Serv app.
        app_target_factory = _get_configured_app_factory(app_module_str, args_ns.config)
        app_target = app_target_factory # Pass our factory directly to uvicorn
        logger.info(f"Using application factory: '{app_module_str}' (via Serv wrapper factory).")
    else:
        # Not using --factory explicitly.
        # If --reload is used, Uvicorn needs a path string or a zero-argument callable (factory).
        # If not --reload, we can pass an instance.
        
        if args_ns.reload:
            # For reload, always use our factory that handles config loading.
            app_target_factory = _get_configured_app_factory(app_module_str, args_ns.config)
            app_target = app_target_factory
            logger.info(f"Running '{app_module_str}' with reload, using Serv's app factory for configuration.")
        else:
            # No reload, no --factory. We can try to load and configure the app instance directly.
            try:
                temp_factory = _get_configured_app_factory(app_module_str, args_ns.config)
                app_target = temp_factory() # Call our factory to get the configured instance
                logger.info(f"Running pre-configured app instance for '{app_module_str}'.")
            except Exception as e: # Fallback if direct instantiation/configuration fails
                logger.warning(f"Could not pre-load/configure '{app_module_str}', passing string to Uvicorn: {e}")
                app_target = app_module_str # Pass the string directly to Uvicorn

    uvicorn_log_level = "debug" if logger.level == logging.DEBUG else "info"

    # Handle workers: None for default (1 if not reload, N if reload based on CPU or 1)
    # 0 for uvicorn's auto.
    num_workers = None
    if args_ns.workers is not None: # User specified --workers
        if args_ns.workers == 0: # Auto
            num_workers = None # Uvicorn default based on reload/CPUs
        elif args_ns.workers > 0:
            num_workers = args_ns.workers
    # If args_ns.workers is default (1), and reload is False, num_workers will be 1.
    # If reload is True, uvicorn ignores workers > 1.

    if args_ns.reload and num_workers is not None and num_workers > 1:
        logger.warning("Number of workers is ignored when reload is enabled. Using 1 worker.")
        if num_workers == 0: # If user specified auto, let uvicorn handle it.
            pass # Uvicorn sets workers to 1 if reload=True
        else: # user specified > 1
             num_workers = 1


    try:
        uvicorn.run(
            app_target,
            host=args_ns.host,
            port=args_ns.port,
            reload=args_ns.reload,
            workers=num_workers,
            log_level=uvicorn_log_level,
            # The `factory` flag for uvicorn.run is about whether `app_target` string
            # itself points to a factory like "module:create_app".
            # If we pass a callable (our app_target_factory), uvicorn uses it directly.
            # So, uvicorn's own `factory` flag is not strictly needed if app_target is already a callable.
            # factory=args_ns.factory <--- this tells uvicorn if the STRING app_target is a factory
            # If app_target is already a callable, this is not needed.
        )
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
        description="Serv: A sleek, modern Python web framework CLI.",
        formatter_class=argparse.RawTextHelpFormatter # Preserves formatting in help messages
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

    # Top-level subparsers
    top_level_subparsers = parser.add_subparsers(title="Available command groups", dest="command_group")

    # --- App Command Group --- 
    app_parser = top_level_subparsers.add_parser(
        "app", 
        help="Manage your Serv application.",
        description="Commands for managing your Serv application."
    )
    app_subparsers = app_parser.add_subparsers(title="App commands", dest="app_command", required=True)
    
    # app init command
    app_init_parser = app_subparsers.add_parser(
        "init",
        help="Initialize a new Serv project (creates serv.config.yaml).",
        description="Guides you through creating a 'serv.config.yaml' file in your current directory."
    )
    app_init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite 'serv.config.yaml' if it already exists without prompting."
    )
    app_init_parser.set_defaults(func=handle_init_command)

    # app details command
    app_details_parser = app_subparsers.add_parser(
        "details",
        help="Display the application's loaded configuration from serv.config.yaml.",
        description="Loads and displays the contents of serv.config.yaml in a readable format."
    )
    # This command might also benefit from a --config option if we want to specify a different file
    # For now, it uses the same logic as `launch` (env var, default, or a future global --config)
    app_details_parser.set_defaults(func=handle_app_details_command)

    # --- Plugin Command Group --- 
    plugin_parser = top_level_subparsers.add_parser(
        "plugin", 
        help="Manage Serv plugins.",
        description="Commands for creating, enabling, and disabling Serv plugins."
    )
    plugin_subparsers = plugin_parser.add_subparsers(title="Plugin commands", dest="plugin_command", required=True)

    # plugin create command
    plugin_create_parser = plugin_subparsers.add_parser(
        "create",
        aliases=['new'],
        help="Create a new Serv plugin structure.",
        description="Scaffolds a new plugin directory with 'plugin.yaml' and a 'main.py' template."
    )
    plugin_create_parser.set_defaults(func=handle_create_plugin_command)

    # plugin enable command
    plugin_enable_parser = plugin_subparsers.add_parser(
        "enable",
        help="Enable a Serv plugin by adding it to serv.config.yaml.",
        description="Enables a plugin. Accepts a simple plugin name (found in ./plugins/) or a full module.path:Class string."
    )
    plugin_enable_parser.add_argument(
        "plugin_identifier",
        help="The name of the plugin in ./plugins/ (e.g., my_plugin) or full import string (e.g., mypackage.mod:MyPlugin)."
    )
    plugin_enable_parser.set_defaults(func=handle_enable_plugin_command)

    # plugin disable command
    plugin_disable_parser = plugin_subparsers.add_parser(
        "disable",
        help="Disable a Serv plugin by removing it from serv.config.yaml.",
        description="Disables a plugin. Accepts a simple plugin name (found in ./plugins/) or a full module.path:Class string."
    )
    plugin_disable_parser.add_argument(
        "plugin_identifier",
        help="The name of the plugin in ./plugins/ (e.g., my_plugin) or full import string (e.g., mypackage.mod:MyPlugin)."
    )
    plugin_disable_parser.set_defaults(func=handle_disable_plugin_command)

    # --- Middleware Command Group ---
    mw_parser = top_level_subparsers.add_parser(
        "middleware",
        help="Manage Serv middleware.",
        description="Commands for enabling and disabling Serv middleware."
    )
    mw_subparsers = mw_parser.add_subparsers(title="Middleware commands", dest="middleware_command", required=True)

    # middleware enable command
    mw_enable_parser = mw_subparsers.add_parser(
        "enable",
        help="Enable a Serv middleware by adding it to serv.config.yaml.",
        description="Enables a middleware. Expects a full module.path:CallableName string."
    )
    mw_enable_parser.add_argument(
        "middleware_entry_string",
        help="The full import string for the middleware (e.g., mypackage.mod:MyMiddlewareFactory)."
    )
    mw_enable_parser.set_defaults(func=handle_enable_middleware_command)

    # middleware disable command
    mw_disable_parser = mw_subparsers.add_parser(
        "disable",
        help="Disable a Serv middleware by removing it from serv.config.yaml.",
        description="Disables a middleware. Expects a full module.path:CallableName string."
    )
    mw_disable_parser.add_argument(
        "middleware_entry_string",
        help="The full import string for the middleware (e.g., mypackage.mod:MyMiddlewareFactory)."
    )
    mw_disable_parser.set_defaults(func=handle_disable_middleware_command)

    # middleware create command
    mw_create_parser = mw_subparsers.add_parser(
        "create",
        aliases=['new'],
        help="Create a new Serv middleware structure.",
        description="Scaffolds a new middleware Python file in the 'middleware' directory."
    )
    mw_create_parser.set_defaults(func=handle_create_middleware_command)
    
    # --- Launch Command --- 
    launch_parser = top_level_subparsers.add_parser(
        "launch",
        help="Launch the Serv development server (default command if none specified).",
        description="Starts a Uvicorn server for your Serv application."
    )
    launch_parser.add_argument(
        "app_module",
        nargs="?", 
        default="serv.app:App",
        help=("App to run, e.g., 'my_app.main:app' or 'my_project.app_factory:create_app'.\n"
              "Default: 'serv.app:App' (basic Serv instance).")
    )
    launch_parser.add_argument(
        "--host", default=os.getenv("SERV_HOST", "127.0.0.1"),
        help="Bind socket to this host. Default: 127.0.0.1 (or SERV_HOST env var)."
    )
    launch_parser.add_argument(
        "--port", type=int, default=int(os.getenv("SERV_PORT", "8000")),
        help="Bind socket to this port. Default: 8000 (or SERV_PORT env var)."
    )
    launch_parser.add_argument(
        "--reload", action="store_true", default=bool(os.getenv("SERV_RELOAD")),
        help="Enable auto-reload on code changes (or SERV_RELOAD env var)."
    )
    launch_parser.add_argument(
        "--workers", type=int, default=int(os.getenv("SERV_WORKERS", "1")) if os.getenv("SERV_WORKERS") else None,
        help="Number of worker processes. Default: 1. Use 0 for auto based on CPU count (Uvicorn default)."
    )
    launch_parser.add_argument(
        "--config", default=os.getenv("SERV_CONFIG_PATH"),
        help=("Path to Serv configuration file (serv.config.yaml).\n"
              f"Default: '{DEFAULT_CONFIG_FILE}' or 'serv.config.yaml' in CWD (or SERV_CONFIG_PATH env var).")
    )
    launch_parser.add_argument(
        "--factory", action="store_true", default=False,
        help="Treat APP_MODULE as an application factory string (e.g., 'module:create_app')."
    )
    launch_parser.set_defaults(func=handle_launch_command)
    
    args = parser.parse_args()

    if args.debug or os.getenv("SERV_DEBUG"):
        logger.setLevel(logging.DEBUG)
        for h in logger.handlers:
            h.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'))
        logger.debug("Debug logging enabled.")

    current_args_to_use = args

    if not hasattr(args, 'command_group') or args.command_group is None:
        # No command group specified, default to 'launch'
        # Reparse as if 'launch' was the command, preserving other args.
        non_command_cli_args = []
        skip_next = False
        for i, arg_val in enumerate(sys.argv[1:]):
            if skip_next:
                skip_next = False
                continue
            if arg_val in ["--version", "--debug"]:
                continue
            if arg_val in ["--help", "-h"] and i == 0 :
                 parser.print_help()
                 sys.exit(0)
            non_command_cli_args.append(arg_val)
            
        try:
            launch_specific_args = launch_parser.parse_args(non_command_cli_args)
            for global_arg_name in ['debug', 'version']:
                 if hasattr(args, global_arg_name):
                    setattr(launch_specific_args, global_arg_name, getattr(args, global_arg_name))
            current_args_to_use = launch_specific_args
            current_args_to_use.func = handle_launch_command # Ensure func is set
        except SystemExit:
            parser.print_help()
            sys.exit(1)
    
    # Dispatch to the appropriate handler function
    if hasattr(current_args_to_use, 'func') and callable(current_args_to_use.func):
        current_args_to_use.func(current_args_to_use)
    else:
        # If no func is set (e.g., 'serv app' or 'serv plugin' without subcommand),
        # print help for that command group.
        if hasattr(current_args_to_use, 'command_group'):
            if current_args_to_use.command_group == 'app':
                app_parser.print_help()
            elif current_args_to_use.command_group == 'plugin':
                plugin_parser.print_help()
            elif current_args_to_use.command_group == 'middleware':
                mw_parser.print_help()
            else: # Should not happen if command_group is one of the defined ones
                parser.print_help()
        else:
            parser.print_help() # Fallback to main help

if __name__ == "__main__":
    main() 