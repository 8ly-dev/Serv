"""
CLI utility functions.

This module contains helper functions used across the CLI commands.
"""

import logging
import re
from pathlib import Path

import yaml

logger = logging.getLogger("serv")


def to_pascal_case(name: str) -> str:
    """Converts a string to PascalCase."""
    name = name.replace("-", " ").replace("_", " ")
    parts = name.split(" ")
    processed_parts = []
    for part in parts:
        if not part:
            continue
        # Handle 'v' followed by digit, e.g., v2 -> V2
        if len(part) > 1 and part[0].lower() == "v" and part[1:].isdigit():
            processed_parts.append("V" + part[1:])
        else:
            processed_parts.append(part.capitalize())
    return "".join(processed_parts)


def to_snake_case(name: str) -> str:
    """Converts a string to snake_case. Handles spaces, hyphens, and existing PascalCase/camelCase."""
    s = re.sub(r"[\s-]+", "_", name)  # Replace spaces/hyphens with underscores
    s = re.sub(
        r"(.)([A-Z][a-z]+)", r"\1_\2", s
    )  # Underscore before capital if followed by lowercase
    s = re.sub(
        r"([a-z0-9])([A-Z])", r"\1_\2", s
    ).lower()  # Underscore before capital if followed by lowercase/digit
    s = re.sub(r"_+", "_", s)  # Consolidate multiple underscores
    s = s.strip("_")  # Remove leading/trailing underscores
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


def resolve_plugin_module_string(
    identifier: str, project_root: Path
) -> tuple[str | None, str | None]:
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
        return (
            identifier,
            None,
        )  # No simple name to derive human name from, user provided full path

    # Simple name. Convert to snake_case for directory lookup.
    dir_name = to_snake_case(identifier)
    if not dir_name:
        logger.error(
            f"Could not derive a valid directory name from identifier '{identifier}'."
        )
        return None, None

    plugin_yaml_path = plugins_dir / dir_name / "plugin.yaml"

    if not plugin_yaml_path.exists():
        logger.warning(
            f"Plugin configuration '{plugin_yaml_path}' not found for simple name '{identifier}'."
        )
        logger.warning(
            f"Attempted to find it for directory '{dir_name}'. Ensure the plugin exists and the name is correct."
        )
        return None, None

    try:
        with open(plugin_yaml_path) as f:
            plugin_meta = yaml.safe_load(f)
        if not isinstance(plugin_meta, dict):
            logger.error(
                f"Invalid YAML format in '{plugin_yaml_path}'. Expected a dictionary."
            )
            return None, None

        entry_string = plugin_meta.get("entry")
        plugin_name_human = plugin_meta.get(
            "name", identifier
        )  # Fallback to identifier if name not in yaml

        if not entry_string:
            logger.error(f"'entry' key not found in '{plugin_yaml_path}'.")
            return None, None
        return entry_string, plugin_name_human
    except Exception as e:
        logger.error(f"Error reading or parsing '{plugin_yaml_path}': {e}")
        return None, None
