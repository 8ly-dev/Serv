"""URL pattern matching and parameter extraction for Serv routing.

This module provides the core URL pattern matching functionality, supporting:
- Exact path matching
- Path parameters with type hints ({param}, {param:int}, {param:path})
- Embedded parameters in path segments (e.g., "v{version:int}")
- Multi-segment path parameters that consume remaining URL parts
"""

import re
from typing import Any


def match_path(request_path: str, path_pattern: str) -> dict[str, Any] | None:
    """Performs path matching against a pattern.

    Supports exact matches and path parameters with optional type hints.
    Supported types: {param}, {param:int}, {param:path}

    Args:
        request_path: The incoming request path to match
        path_pattern: The route pattern to match against

    Returns:
        A dict of path parameters if matched, else None.

    Examples:
        >>> match_path("/users/123", "/users/{user_id:int}")
        {"user_id": 123}

        >>> match_path("/files/docs/readme.txt", "/files/{path:path}")
        {"path": "docs/readme.txt"}

        >>> match_path("/api/v1/users", "/api/v{version:int}/users")
        {"version": 1}
    """
    pattern_parts = path_pattern.strip("/").split("/")
    request_parts = request_path.strip("/").split("/")

    # Handle special case for path type parameters that can consume multiple segments
    if any("{" in part and ":path}" in part for part in pattern_parts):
        return match_path_with_path_type(request_path, path_pattern)

    if len(pattern_parts) != len(request_parts):
        return None

    params = {}
    for p_part, r_part in zip(pattern_parts, request_parts, strict=False):
        if "{" in p_part and "}" in p_part:
            # Handle parameters that might be embedded in text (like "v{version:int}")
            result = match_segment_with_params(p_part, r_part)
            if result is None:
                return None
            params.update(result)
        elif p_part != r_part:
            return None

    return params


def match_segment_with_params(
    pattern_segment: str, request_segment: str
) -> dict[str, Any] | None:
    """Match a single path segment that may contain embedded parameters.

    Args:
        pattern_segment: Pattern segment like "v{version:int}" or "{user_id}"
        request_segment: Actual request segment like "v1" or "123"

    Returns:
        Dict of extracted parameters or None if no match

    Examples:
        >>> match_segment_with_params("v{version:int}", "v2")
        {"version": 2}

        >>> match_segment_with_params("{user_id:int}", "123")
        {"user_id": 123}
    """
    # Find all parameters in the pattern segment
    param_pattern = r"\{([^}]+)\}"
    params = {}

    # Build a regex pattern by replacing parameter placeholders
    regex_pattern = pattern_segment
    param_matches = re.finditer(param_pattern, pattern_segment)

    for match in reversed(list(param_matches)):  # Reverse to maintain indices
        param_spec = match.group(1)
        if ":" in param_spec:
            param_name, param_type = param_spec.split(":", 1)
            if param_type == "int":
                # Replace with regex for integers
                regex_pattern = (
                    regex_pattern[: match.start()]
                    + r"(\d+)"
                    + regex_pattern[match.end() :]
                )
            elif param_type == "path":
                # For path type in a segment, match everything
                regex_pattern = (
                    regex_pattern[: match.start()]
                    + r"(.+)"
                    + regex_pattern[match.end() :]
                )
            else:
                # Default to matching non-slash characters
                regex_pattern = (
                    regex_pattern[: match.start()]
                    + r"([^/]+)"
                    + regex_pattern[match.end() :]
                )
        else:
            # Simple parameter, match non-slash characters
            regex_pattern = (
                regex_pattern[: match.start()]
                + r"([^/]+)"
                + regex_pattern[match.end() :]
            )

    # Escape any remaining regex special characters in the pattern
    regex_pattern = regex_pattern.replace(".", r"\.")
    regex_pattern = "^" + regex_pattern + "$"

    # Try to match the request segment
    match = re.match(regex_pattern, request_segment)
    if not match:
        return None

    # Extract parameter values
    param_matches = list(re.finditer(param_pattern, pattern_segment))
    for i, param_match in enumerate(param_matches):
        param_spec = param_match.group(1)
        value = match.group(i + 1)

        if ":" in param_spec:
            param_name, param_type = param_spec.split(":", 1)
            try:
                if param_type == "int":
                    params[param_name] = int(value)
                elif param_type == "path":
                    params[param_name] = value
                else:
                    params[param_name] = value
            except ValueError:
                return None
        else:
            params[param_spec] = value

    return params


def match_path_with_path_type(
    request_path: str, path_pattern: str
) -> dict[str, Any] | None:
    """Handle path patterns with path type parameters that can consume multiple segments.

    Args:
        request_path: The incoming request path
        path_pattern: Pattern containing {param:path} parameters

    Returns:
        Dict of extracted parameters or None if no match

    Examples:
        >>> match_path_with_path_type("/files/docs/readme.txt", "/files/{path:path}")
        {"path": "docs/readme.txt"}

        >>> match_path_with_path_type("/api/v1/files/docs/readme.txt", "/api/v{version:int}/files/{path:path}")
        {"version": 1, "path": "docs/readme.txt"}
    """
    pattern_parts = path_pattern.strip("/").split("/")
    request_parts = request_path.strip("/").split("/")

    params = {}
    pattern_idx = 0
    request_idx = 0

    while pattern_idx < len(pattern_parts) and request_idx < len(request_parts):
        p_part = pattern_parts[pattern_idx]

        if p_part.startswith("{") and p_part.endswith("}"):
            param_spec = p_part[1:-1]
            if ":" in param_spec:
                param_name, param_type = param_spec.split(":", 1)
                if param_type == "path":
                    # Path type consumes remaining segments
                    remaining_pattern = len(pattern_parts) - pattern_idx - 1
                    if remaining_pattern == 0:
                        # This is the last part, consume all remaining request parts
                        path_value = "/".join(request_parts[request_idx:])
                        params[param_name] = path_value
                        return params
                    else:
                        # Calculate how many segments to consume
                        remaining_request = len(request_parts) - request_idx
                        segments_to_consume = remaining_request - remaining_pattern
                        if segments_to_consume < 1:
                            return None
                        path_value = "/".join(
                            request_parts[
                                request_idx : request_idx + segments_to_consume
                            ]
                        )
                        params[param_name] = path_value
                        request_idx += segments_to_consume
                elif param_type == "int":
                    try:
                        params[param_name] = int(request_parts[request_idx])
                    except ValueError:
                        return None
                    request_idx += 1
                else:
                    params[param_name] = request_parts[request_idx]
                    request_idx += 1
            else:
                params[param_spec] = request_parts[request_idx]
                request_idx += 1
        else:
            # Exact match required
            if p_part != request_parts[request_idx]:
                return None
            request_idx += 1

        pattern_idx += 1

    # Check if we consumed all parts
    if pattern_idx == len(pattern_parts) and request_idx == len(request_parts):
        return params

    return None
