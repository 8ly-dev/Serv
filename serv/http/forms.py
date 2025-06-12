"""Form processing utilities for HTTP requests."""

import io
from dataclasses import dataclass
from datetime import date, datetime
from inspect import get_annotations
from types import NoneType, UnionType
from typing import Any, Union, get_args, get_origin

# NoneType is imported from types above


@dataclass
class FileUpload:
    """Represents an uploaded file from a multipart form.

    Attributes:
        filename: Original filename from the client, if provided
        content_type: MIME type of the uploaded file
        headers: Additional headers from the multipart section
        file: File-like object containing the uploaded data
    """

    filename: str | None
    content_type: str | None
    headers: dict[str, str]
    file: io.IOBase

    async def read(self) -> bytes:
        """Read the entire content of the uploaded file."""
        return self.file.read()

    async def seek(self, offset: int) -> int:
        """Seek to a specific position in the file."""
        return self.file.seek(offset)

    async def close(self) -> None:
        """Close the file handle."""
        return self.file.close()


def normalized_origin(annotation: Any) -> Any:
    """Normalize type annotation origin for consistent handling.

    Args:
        annotation: Type annotation to normalize

    Returns:
        Normalized type origin
    """
    origin = get_origin(annotation)
    if origin is UnionType:
        return Union
    return origin


def is_optional(annotation: Any) -> bool:
    """Check if a type annotation represents an optional field.

    Args:
        annotation: Type annotation to check

    Returns:
        True if the annotation is optional (Union with None or list)
    """
    origin = normalized_origin(annotation)
    if origin is list:
        return True

    if origin is Union and NoneType in get_args(annotation):
        return True

    return False


def _datetime_validator(x: str) -> bool:
    """Validate if a string can be parsed as a datetime."""
    try:
        datetime.strptime(x, "%Y-%m-%d %H:%M:%S")
        return True
    except ValueError:
        return False


def _date_validator(x: str) -> bool:
    """Validate if a string can be parsed as a date."""
    try:
        datetime.strptime(x, "%Y-%m-%d")
        return True
    except ValueError:
        return False


# Mapping of types to their string validation functions
string_value_type_validators = {
    int: str.isdigit,
    float: lambda x: x.replace(".", "").isdigit(),
    bool: lambda x: x.lower() in {"true", "false", "yes", "no", "1", "0"},
    datetime: _datetime_validator,
    date: _date_validator,
}


def _is_valid_type(value: Any, allowed_types: list[type]) -> bool:
    """Check if a value matches one of the allowed types.

    Args:
        value: Value to validate
        allowed_types: List of allowed types

    Returns:
        True if the value matches one of the allowed types
    """
    for allowed_type in allowed_types:
        if allowed_type is type(None):
            continue

        if allowed_type not in string_value_type_validators:
            return True

        if string_value_type_validators[allowed_type](value):
            return True

    return False


class Form:
    """Base class for defining form models with automatic validation.

    Form classes define the expected structure and types of form data.
    They provide validation and type checking capabilities for HTTP form submissions.

    Attributes:
        __form_method__: HTTP method this form accepts (defaults to "POST")

    Examples:
        Basic form definition:

        ```python
        from serv.http.forms import Form

        class ContactForm(Form):
            name: str
            email: str
            message: str
            newsletter: bool = False  # Optional field
        ```

        Form with custom method:

        ```python
        class SearchForm(Form):
            __form_method__ = "GET"

            query: str
            category: str | None = None
        ```
    """

    __form_method__ = "POST"

    @classmethod
    def matches_form_data(cls, form_data: dict[str, Any]) -> bool:
        """Check if form data matches this form's structure and types.

        Args:
            form_data: Dictionary of form field names to values

        Returns:
            True if the form data is valid for this form class
        """
        annotations = get_annotations(cls)

        allowed_keys = set(annotations.keys())
        required_keys = {
            key for key, value in annotations.items() if not is_optional(value)
        }

        form_data_keys = set(form_data.keys())
        has_missing_required_keys = required_keys - form_data_keys
        has_extra_keys = form_data_keys > allowed_keys
        if has_missing_required_keys or has_extra_keys:
            return False  # Form data keys do not match the expected keys

        for key, value in annotations.items():
            optional = key not in required_keys
            if key not in form_data and not optional:
                return False

            allowed_types = get_args(value)
            if not allowed_types:
                allowed_types = [value]

            if get_origin(value) is list and not all(
                _is_valid_type(item, allowed_types) for item in form_data[key]
            ):
                return False

            if key in form_data and not _is_valid_type(
                form_data[key][0], allowed_types
            ):
                return False

        return True  # All fields match


__all__ = [
    "FileUpload",
    "Form",
    "normalized_origin",
    "is_optional",
    "string_value_type_validators",
    "_is_valid_type",
    "_datetime_validator",
    "_date_validator",
]
