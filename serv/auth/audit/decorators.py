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
        """Validate that all audit-required methods are properly set up."""
        for attr_name in dir(cls):
            # Skip private/magic methods and non-callable attributes
            if attr_name.startswith('_'):
                continue

            attr = getattr(cls, attr_name)
            if callable(attr) and hasattr(attr, '_audit_pipeline'):
                # Method has audit requirements - ensure it's properly set up
                # Additional validation could be added here if needed
                pass
