"""Type analysis utilities for route handlers."""

from datetime import date, datetime
from types import NoneType, UnionType
from typing import Annotated, Any, Union, get_args, get_origin, get_type_hints


class AnnotationEvaluationError(Exception):
    """Raised when user-provided type annotations cannot be evaluated.

    This indicates a bug in the user's code (invalid type annotations,
    missing imports, syntax errors, etc.) that needs immediate attention.
    """

    pass


def get_safe_type_hints(callable_obj, *, include_extras: bool = False) -> dict:
    """Safely extract type hints, wrapping annotation evaluation errors.

    Args:
        callable_obj: The callable or signature to extract type hints from
        include_extras: Whether to include typing.Annotated information

    Returns:
        Dictionary of parameter name to type annotation

    Raises:
        AnnotationEvaluationError: When user annotations cannot be evaluated
    """
    try:
        return get_type_hints(callable_obj, include_extras=include_extras)
    except (NameError, SyntaxError, ImportError, AttributeError, TypeError) as e:
        # These indicate problems with user-provided type annotations
        obj_name = getattr(callable_obj, "__name__", str(callable_obj))
        raise AnnotationEvaluationError(
            f"Failed to evaluate type annotations for {obj_name}: {e}"
        ) from e


def normalized_origin(annotation: Any) -> Any:
    """Get normalized origin type, handling UnionType vs Union differences."""
    origin = get_origin(annotation)
    if origin is UnionType:
        return Union
    return origin


def is_optional(annotation: Any) -> bool:
    """Check if a type annotation represents an optional value."""
    origin = normalized_origin(annotation)
    if origin is list:
        return True
    if origin is Union and NoneType in get_args(annotation):
        return True
    return False


def extract_annotated_info(annotation: Any) -> tuple[Any, Any] | tuple[None, None]:
    """Extract base type and metadata from Annotated types.

    Returns:
        Tuple of (base_type, metadata) or (None, None) if not Annotated
    """
    if get_origin(annotation) is Annotated:
        annotation_args = get_args(annotation)
        if len(annotation_args) >= 2:
            return annotation_args[0], annotation_args[1]

    return None, None


def is_subclass_safe(obj: Any, class_or_tuple: type | tuple[type, ...]) -> bool:
    """Safely check if obj is a subclass, handling non-type objects."""
    try:
        return isinstance(obj, type) and issubclass(obj, class_or_tuple)
    except TypeError:
        return False


def _datetime_validator(x: str) -> bool:
    """Validate datetime string format."""
    try:
        datetime.strptime(x, "%Y-%m-%d %H:%M:%S")
        return True
    except ValueError:
        return False


def _date_validator(x: str) -> bool:
    """Validate date string format."""
    try:
        datetime.strptime(x, "%Y-%m-%d")
        return True
    except ValueError:
        return False


# Type validators for string values
STRING_VALUE_TYPE_VALIDATORS = {
    int: str.isdigit,
    float: lambda x: x.replace(".", "").isdigit(),
    bool: lambda x: x.lower() in {"true", "false", "yes", "no", "1", "0"},
    datetime: _datetime_validator,
    date: _date_validator,
}


def is_valid_type(value: Any, allowed_types: list[type]) -> bool:
    """Check if a value is valid for any of the allowed types."""
    for allowed_type in allowed_types:
        if allowed_type is type(None):
            continue

        if allowed_type not in STRING_VALUE_TYPE_VALIDATORS:
            return True

        if STRING_VALUE_TYPE_VALIDATORS[allowed_type](value):
            return True

    return False
