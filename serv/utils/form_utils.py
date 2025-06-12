"""Form handling utilities for Serv applications."""

from inspect import get_annotations
from typing import Any, get_args, get_origin

from .type_utils import is_optional, is_valid_type


class Form:
    """Base class for form handling."""

    __form_method__ = "POST"

    # Security limits to prevent DoS attacks
    MAX_FORM_FIELDS = 1000
    MAX_LIST_ITEMS = 10000
    MAX_FIELD_SIZE = 1024 * 1024  # 1MB per field

    @classmethod
    def matches_form_data(cls, form_data: dict[str, Any]) -> bool:
        """Check if form data matches this form's structure."""
        # Validate form_data structure
        if not isinstance(form_data, dict):
            return False

        # Apply security limits
        if len(form_data) > cls.MAX_FORM_FIELDS:
            return False

        annotations = get_annotations(cls)

        allowed_keys = set(annotations.keys())
        required_keys = {
            key for key, value in annotations.items() if not is_optional(value)
        }

        form_data_keys = set(form_data.keys())
        has_missing_required_keys = required_keys - form_data_keys
        has_extra_keys = form_data_keys - allowed_keys  # Fixed: use subtraction, not comparison
        if has_missing_required_keys or has_extra_keys:
            return False

        for key, value in annotations.items():
            # Skip optional fields that aren't present (removed redundant check)
            if key not in form_data:
                continue

            field_data = form_data[key]

            # Apply field size limits
            if isinstance(field_data, str) and len(field_data) > cls.MAX_FIELD_SIZE:
                return False
            elif isinstance(field_data, list):
                if len(field_data) > cls.MAX_LIST_ITEMS:
                    return False
                # Check total size of list items
                total_size = sum(len(str(item)) for item in field_data)
                if total_size > cls.MAX_FIELD_SIZE:
                    return False

            allowed_types = get_args(value)
            if not allowed_types:
                allowed_types = [value]

            # Handle list types with bounds checking
            if get_origin(value) is list:
                if not isinstance(field_data, list):
                    return False
                if not all(is_valid_type(item, allowed_types) for item in field_data):
                    return False
            else:
                # Handle non-list types with bounds checking
                if isinstance(field_data, list):
                    if not field_data:  # Empty list
                        return False
                    # Use first item for validation
                    if not is_valid_type(field_data[0], allowed_types):
                        return False
                else:
                    # Direct value validation
                    if not is_valid_type(field_data, allowed_types):
                        return False

        return True
