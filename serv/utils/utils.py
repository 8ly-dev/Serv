"""Utility functions used throughout the Serv framework."""


def is_subclass_of(obj, parent_class: type) -> bool:
    """Check if obj is a type and a subclass of parent_class.

    This is a common pattern throughout the codebase for checking if an annotation
    or object represents a class that inherits from a specific parent class.

    Args:
        obj: The object to check (typically a type annotation)
        parent_class: The parent class to check inheritance against

    Returns:
        True if obj is a type and is a subclass of parent_class, False otherwise

    Examples:
        >>> is_subclass_of(str, object)
        True
        >>> is_subclass_of("not a type", object)
        False
        >>> is_subclass_of(int, str)
        False
    """
    return isinstance(obj, type) and issubclass(obj, parent_class)
