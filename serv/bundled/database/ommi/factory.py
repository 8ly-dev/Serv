"""Ommi database provider factory functions."""

from typing import Any


def _import_ommi():
    """Lazy import Ommi to avoid circular import issues."""
    try:
        from ommi import Ommi

        return Ommi
    except ImportError as e:
        raise ImportError(
            "Ommi is not available. Please install with: uv add ommi"
        ) from e


def _import_sqlite_driver():
    """Lazy import SQLite driver."""
    try:
        from ommi.ext.drivers.sqlite import SQLiteDriver

        return SQLiteDriver
    except ImportError as e:
        raise ImportError(f"Ommi SQLite driver not available: {e}") from e


def _import_postgresql_driver():
    """Lazy import PostgreSQL driver."""
    try:
        from ommi.ext.drivers.postgresql import PostgreSQLDriver

        return PostgreSQLDriver
    except ImportError as e:
        raise ImportError(f"Ommi PostgreSQL driver not available: {e}") from e


async def create_ommi(
    name: str,
    connection_string: str = "sqlite:///:memory:",
    qualifier: str | None = None,
    **kwargs,
) -> Any:
    """Create Ommi database instance with auto-detected driver (PRIMARY FACTORY).

    Args:
        name: Database name
        connection_string: Database connection string
        qualifier: Optional qualifier for DI
        **kwargs: Additional driver parameters

    Returns:
        Configured Ommi instance

    Raises:
        ValueError: If database scheme is unsupported
    """
    Ommi = _import_ommi()

    # Auto-detect driver from connection string scheme
    if connection_string.startswith("sqlite"):
        SQLiteDriver = _import_sqlite_driver()
        from ommi.ext.drivers.sqlite.driver import SQLiteSettings
        
        # Extract database path from connection string
        # Format: sqlite:///path/to/db.db -> path/to/db.db
        if connection_string.startswith("sqlite:///"):
            database_path = connection_string[10:]  # Remove "sqlite:///"
        elif connection_string.startswith("sqlite://"):
            database_path = connection_string[9:]   # Remove "sqlite://"
        else:
            database_path = connection_string
        
        # Create SQLiteSettings with the database path
        settings = SQLiteSettings(database_path=database_path)
        driver = SQLiteDriver.connect(settings)
    elif connection_string.startswith("postgresql"):
        PostgreSQLDriver = _import_postgresql_driver()
        driver = PostgreSQLDriver.connect(connection_string, **kwargs)
    else:
        # Extract scheme for error message
        scheme = (
            connection_string.split("://")[0]
            if "://" in connection_string
            else connection_string
        )
        raise ValueError(f"Unsupported database scheme: {scheme}")

    # Create Ommi instance
    ommi_instance = Ommi(driver)
    await ommi_instance.__aenter__()

    # Register cleanup
    async def cleanup():
        await ommi_instance.__aexit__(None, None, None)

    ommi_instance._cleanup = cleanup

    return ommi_instance


async def create_ommi_sqlite(
    name: str, database_path: str = ":memory:", qualifier: str | None = None, **kwargs
) -> Any:
    """Create Ommi instance with SQLite database.

    Args:
        name: Database name
        database_path: Path to SQLite database file
        qualifier: Optional qualifier for DI
        **kwargs: Additional driver parameters

    Returns:
        Configured Ommi instance with SQLite
    """
    connection_string = f"sqlite:///{database_path}"
    return await create_ommi(name, connection_string, qualifier, **kwargs)


async def create_ommi_postgresql(
    name: str,
    host: str = "localhost",
    port: int = 5432,
    database: str = "postgres",
    username: str = "postgres",
    password: str = "",
    qualifier: str | None = None,
    **kwargs,
) -> Any:
    """Create Ommi instance with PostgreSQL database.

    Args:
        name: Database name
        host: PostgreSQL host
        port: PostgreSQL port
        database: Database name
        username: Username
        password: Password
        qualifier: Optional qualifier for DI
        **kwargs: Additional driver parameters

    Returns:
        Configured Ommi instance with PostgreSQL
    """
    connection_string = f"postgresql://{username}:{password}@{host}:{port}/{database}"
    return await create_ommi(name, connection_string, qualifier, **kwargs)


async def create_ommi_nested(name: str, settings: dict[str, Any] | None = None) -> Any:
    """Create Ommi instance with nested settings (backward compatibility).

    Args:
        name: Database name
        settings: Nested configuration dictionary

    Returns:
        Configured Ommi instance
    """
    config = settings or {}
    connection_string = config.get("connection_string", "sqlite:///:memory:")
    qualifier = config.get("qualifier")

    # Forward to the main factory with auto-detection
    return await create_ommi(
        name,
        connection_string,
        qualifier,
        **{
            k: v
            for k, v in config.items()
            if k not in ["connection_string", "qualifier"]
        },
    )
