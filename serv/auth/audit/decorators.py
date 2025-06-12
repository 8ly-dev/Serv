"""Audit enforcement decorators and base classes."""




class AuditEnforced:
    """Base class for audit-enforced classes.

    Classes that inherit from this will have audit requirements
    enforced automatically using __init_subclass__.
    """

    def __init_subclass__(cls, **kwargs):
        """Validate audit requirements when subclass is created."""
        super().__init_subclass__(**kwargs)

        # Validate that all methods with audit requirements are properly decorated
        cls._validate_audit_methods()

    @classmethod
    def _validate_audit_methods(cls):
        """Validate that all audit-required methods are properly set up.

        Ensures that subclasses cannot override or weaken audit requirements
        from parent classes, which would create security vulnerabilities.
        """
        for attr_name in dir(cls):
            # Skip private/magic methods and non-callable attributes
            if attr_name.startswith('_'):
                continue

            attr = getattr(cls, attr_name)
            if callable(attr) and hasattr(attr, '_audit_pipeline'):
                # Method has audit requirements - validate against parent classes
                cls._validate_audit_requirement_inheritance(attr_name, attr)

    @classmethod
    def _validate_audit_requirement_inheritance(cls, method_name: str, method: callable):
        """Validate that method doesn't override parent audit requirements.

        Args:
            method_name: Name of the method being validated
            method: The method object with audit requirements

        Raises:
            AuditError: If method attempts to override parent audit requirements
        """
        from ..exceptions import AuditError

        current_requirement = getattr(method, '_audit_pipeline', None)
        if not current_requirement:
            return

        # Check all parent classes in MRO (excluding current class)
        for parent_cls in cls.__mro__[1:]:
            if not hasattr(parent_cls, method_name):
                continue

            parent_method = getattr(parent_cls, method_name)
            if not callable(parent_method):
                continue

            parent_requirement = getattr(parent_method, '_audit_pipeline', None)
            if not parent_requirement:
                continue

            # Found a parent with audit requirements for this method
            if current_requirement != parent_requirement:
                raise AuditError(
                    f"Class {cls.__name__} cannot override audit requirements for method '{method_name}'. "
                    f"Parent class {parent_cls.__name__} requires {parent_requirement}, "
                    f"but {cls.__name__} specifies {current_requirement}. "
                    f"Audit requirements must be identical in inheritance hierarchies to prevent security bypasses."
                )

            # Found matching requirement, stop checking (first match wins)
            break
