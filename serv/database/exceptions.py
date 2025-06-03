"""Database-specific exceptions for Serv."""


class DatabaseError(Exception):
    """Base exception for database operations."""

    pass


class DatabaseConfigurationError(DatabaseError):
    """Configuration-related database errors."""

    pass


class DatabaseConnectionError(DatabaseError):
    """Connection-related database errors."""

    pass


class DatabaseFactoryError(DatabaseError):
    """Factory loading/invocation errors."""

    pass


class DatabaseLifecycleError(DatabaseError):
    """Lifecycle management errors."""

    pass
