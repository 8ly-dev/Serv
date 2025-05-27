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
    """Converts a string to PascalCase.

    Transforms various naming conventions (snake_case, kebab-case, space-separated)
    into PascalCase format commonly used for class names.

    Args:
        name: Input string to convert.

    Returns:
        String converted to PascalCase.

    Examples:
        ```python
        to_pascal_case("user_profile")     # "UserProfile"
        to_pascal_case("api-handler")      # "ApiHandler"
        to_pascal_case("my extension")        # "MyExtension"
        to_pascal_case("v2_api")          # "V2Api"
        ```
    """
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
    """Converts a string to snake_case.

    Handles spaces, hyphens, and existing PascalCase/camelCase conversions.
    Commonly used for file names, directory names, and Python identifiers.

    Args:
        name: Input string to convert.

    Returns:
        String converted to snake_case.

    Examples:
        ```python
        to_snake_case("UserProfile")       # "user_profile"
        to_snake_case("API-Handler")       # "api_handler"
        to_snake_case("my extension name")    # "my_extension_name"
        to_snake_case("XMLHttpRequest")    # "xml_http_request"
        ```
    """
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
    """Prompts the user for input with an optional default value.

    Displays a prompt to the user and waits for input. If a default value is
    provided, it will be used when the user presses Enter without typing anything.

    Args:
        text: The prompt text to display to the user.
        default: Optional default value to use if user provides no input.

    Returns:
        The user's input string, or the default value if no input was provided.

    Examples:
        ```python
        name = prompt_user("Enter your name")
        port = prompt_user("Enter port", default="8000")
        confirm = prompt_user("Continue? (y/n)", default="y")
        ```
    """
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


def resolve_extension_module_string(
    identifier: str, project_root: Path
) -> tuple[str | None, str | None]:
    """Resolves a extension identifier to its module string and name.

    Args:
        identifier: The extension identifier (simple name or full module.path:Class).
        project_root: The root directory of the project (usually CWD).

    Returns:
        A tuple (module_string, extension_name_human) or (None, None) if not found.
        extension_name_human is extracted from extension.yaml if resolved via simple name.
    """
    extensions_dir = project_root / "extensions"
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

    extension_yaml_path = extensions_dir / dir_name / "extension.yaml"

    if not extension_yaml_path.exists():
        logger.warning(
            f"Extension configuration '{extension_yaml_path}' not found for simple name '{identifier}'."
        )
        logger.warning(
            f"Attempted to find it for directory '{dir_name}'. Ensure the extension exists and the name is correct."
        )
        return None, None

    try:
        with open(extension_yaml_path) as f:
            extension_meta = yaml.safe_load(f)
        if not isinstance(extension_meta, dict):
            logger.error(
                f"Invalid YAML format in '{extension_yaml_path}'. Expected a dictionary."
            )
            return None, None

        entry_string = extension_meta.get("entry")
        extension_name_human = extension_meta.get(
            "name", identifier
        )  # Fallback to identifier if name not in yaml

        if not entry_string:
            logger.error(f"'entry' key not found in '{extension_yaml_path}'.")
            return None, None
        return entry_string, extension_name_human
    except Exception as e:
        logger.error(f"Error reading or parsing '{extension_yaml_path}': {e}")
        return None, None
