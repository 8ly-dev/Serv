"""Form handling utilities for Serv applications."""

from inspect import get_annotations
from typing import Any, get_args, get_origin

from .type_utils import is_optional, is_valid_type


class Form:
    """Base class for form handling."""

    __form_method__ = "POST"

    @classmethod
    def matches_form_data(cls, form_data: dict[str, Any]) -> bool:
        """Check if form data matches this form's structure."""
        annotations = get_annotations(cls)

        allowed_keys = set(annotations.keys())
        required_keys = {
            key for key, value in annotations.items() if not is_optional(value)
        }

        form_data_keys = set(form_data.keys())
        has_missing_required_keys = required_keys - form_data_keys
        has_extra_keys = form_data_keys > allowed_keys
        if has_missing_required_keys or has_extra_keys:
            return False

        for key, value in annotations.items():
            optional = key not in required_keys
            if key not in form_data and not optional:
                return False

            allowed_types = get_args(value)
            if not allowed_types:
                allowed_types = [value]

            if get_origin(value) is list and not all(
                is_valid_type(item, allowed_types) for item in form_data[key]
            ):
                return False

            if key in form_data and not is_valid_type(form_data[key][0], allowed_types):
                return False

        return True
