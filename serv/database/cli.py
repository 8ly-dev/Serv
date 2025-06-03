"""Database CLI commands for Serv."""

import logging
from pathlib import Path

import yaml
from bevy import get_registry

from serv.config import DEFAULT_CONFIG_FILE, load_raw_config
from serv.database.manager import DatabaseManager

logger = logging.getLogger("serv.database")


def handle_database_list_command(args_ns):
    """Handles the 'database list' command."""
    logger.debug("Database list command started.")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        print(f"❌ Configuration file '{config_path}' not found")
        print("   Run 'serv create app' to create a configuration file")
        return False

    try:
        config = load_raw_config(config_path)
        databases = config.get("databases", {})

        if not databases:
            print("ℹ️  No databases configured")
            print(
                "   Add databases to your serv.config.yaml file or use 'serv database config' for examples"
            )
            return True

        print(f"📊 Configured databases ({len(databases)}):")
        print("=" * 50)

        for name, db_config in databases.items():
            provider = db_config.get("provider", "Unknown")
            qualifier = db_config.get("qualifier", name)
            connection_string = db_config.get("connection_string", "Not specified")

            # Mask credentials in connection string for display
            display_connection = _mask_credentials(connection_string)

            print(f"• {name}")
            print(f"  Provider: {provider}")
            print(f"  Qualifier: {qualifier}")
            print(f"  Connection: {display_connection}")
            print()

        return True

    except Exception as e:
        logger.error(f"Error listing databases: {e}")
        print(f"❌ Error listing databases: {e}")
        return False


def handle_database_status_command(args_ns):
    """Handles the 'database status' command."""
    logger.debug("Database status command started.")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        print(f"❌ Configuration file '{config_path}' not found")
        return False

    try:
        config = load_raw_config(config_path)
        databases = config.get("databases", {})

        if not databases:
            print("ℹ️  No databases configured")
            return True

        # Filter by specific database if provided
        if hasattr(args_ns, "name") and args_ns.name:
            if args_ns.name not in databases:
                print(f"❌ Database '{args_ns.name}' not found in configuration")
                return False
            databases = {args_ns.name: databases[args_ns.name]}

        print("🔍 Database Status:")
        print("=" * 50)

        for name, db_config in databases.items():
            print(f"Database: {name}")

            try:
                # Test connection creation (don't actually connect)
                provider = db_config.get("provider")
                if not provider:
                    print("  ❌ Missing provider")
                    continue

                from serv.database.factory import FactoryLoader

                FactoryLoader.load_factory(provider)
                print(f"  ✅ Provider loadable: {provider}")

                # Check configuration
                config_style = FactoryLoader.detect_config_style(db_config)
                print(f"  ℹ️  Config style: {config_style}")

                # Check for required fields
                if config_style == "nested":
                    settings = db_config.get("settings", {})
                    print(f"  ℹ️  Settings: {len(settings)} parameters")
                else:
                    flat_params = {
                        k: v
                        for k, v in db_config.items()
                        if k not in ["provider", "qualifier"]
                    }
                    print(f"  ℹ️  Parameters: {len(flat_params)} flat parameters")

                qualifier = db_config.get("qualifier", name)
                print(f"  ℹ️  Qualifier: {qualifier}")

            except Exception as e:
                print(f"  ❌ Configuration error: {e}")

            print()

        return True

    except Exception as e:
        logger.error(f"Error checking database status: {e}")
        print(f"❌ Error checking database status: {e}")
        return False


def handle_database_test_command(args_ns):
    """Handles the 'database test' command."""
    import asyncio

    return asyncio.run(_async_database_test_command(args_ns))


async def _async_database_test_command(args_ns):
    """Async implementation of database test command."""
    logger.debug("Database test command started.")

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        print(f"❌ Configuration file '{config_path}' not found")
        return False

    try:
        config = load_raw_config(config_path)
        databases = config.get("databases", {})

        if not databases:
            print("ℹ️  No databases configured")
            return True

        # Filter by specific database if provided
        test_databases = databases
        if hasattr(args_ns, "name") and args_ns.name:
            if args_ns.name not in databases:
                print(f"❌ Database '{args_ns.name}' not found in configuration")
                return False
            test_databases = {args_ns.name: databases[args_ns.name]}

        print("🧪 Testing database connections:")
        print("=" * 50)

        registry = get_registry()
        container = registry.create_container()
        db_manager = DatabaseManager(config, container)

        success_count = 0
        total_count = len(test_databases)

        for name, db_config in test_databases.items():
            print(f"Testing: {name}")

            try:
                # Attempt to create connection
                connection = await db_manager.create_connection(name, db_config)
                print("  ✅ Connection successful")

                # Clean up connection if it has cleanup method
                if hasattr(connection, "_cleanup"):
                    await connection._cleanup()
                elif hasattr(connection, "__aexit__"):
                    await connection.__aexit__(None, None, None)

                success_count += 1

            except Exception as e:
                print(f"  ❌ Connection failed: {e}")

            print()

        print(f"📊 Test Results: {success_count}/{total_count} successful")
        return success_count == total_count

    except Exception as e:
        logger.error(f"Error testing database connections: {e}")
        print(f"❌ Error testing database connections: {e}")
        return False


def handle_database_config_command(args_ns):
    """Handles the 'database config' command."""
    logger.debug("Database config command started.")

    print("📖 Database Configuration Examples:")
    print("=" * 50)

    # Try to load the template file
    try:
        import importlib.util

        template_dir = (
            Path(importlib.util.find_spec("serv.cli").submodule_search_locations[0])
            / "scaffolding"
        )
        template_path = template_dir / "database_configs.yaml"

        if template_path.exists():
            print(f"📄 Loading templates from: {template_path}")
            print("\n" + "=" * 50 + "\n")

            with open(template_path) as f:
                content = f.read()

            # Display the template file content
            print(content)

            print("\n" + "=" * 50)
            print("💡 Usage Instructions:")
            print(
                "1. Copy the relevant database configurations to your serv.config.yaml"
            )
            print("2. Place them under the 'databases:' section")
            print("3. Customize connection strings and parameters as needed")
            print("4. Set up environment variables for sensitive data")

        else:
            # Fallback to inline examples if template file not found
            _show_inline_database_examples()

    except Exception as e:
        logger.warning(f"Could not load database templates: {e}")
        # Fallback to inline examples
        _show_inline_database_examples()

    return True


def _show_inline_database_examples():
    """Show inline database configuration examples as fallback."""
    examples = {
        "Ommi with PostgreSQL (Recommended for Production)": {
            "primary": {
                "provider": "serv.bundled.database.ommi:create_ommi",
                "connection_string": "${DATABASE_URL}",
                "qualifier": "primary",
                "pool_size": 10,
            }
        },
        "Ommi with SQLite (Recommended for Development)": {
            "local": {
                "provider": "serv.bundled.database.ommi:create_ommi",
                "connection_string": "sqlite:///app.db",
                "qualifier": "local",
            }
        },
        "Ommi in-memory (Recommended for Testing)": {
            "test": {
                "provider": "serv.bundled.database.ommi:create_ommi",
                "connection_string": "sqlite:///:memory:",
                "qualifier": "test",
            }
        },
        "Multiple Ommi Instances": {
            "auth": {
                "provider": "serv.bundled.database.ommi:create_ommi",
                "connection_string": "sqlite:///auth.db",
                "qualifier": "auth",
            },
            "analytics": {
                "provider": "serv.bundled.database.ommi:create_ommi",
                "connection_string": "postgresql://user:pass@analytics-host/analytics",
                "qualifier": "analytics",
            },
        },
        "Nested Configuration Style": {
            "legacy": {
                "provider": "external_provider:create_engine",
                "settings": {"url": "${DATABASE_URL}", "pool_size": 10, "echo": False},
                "qualifier": "legacy",
            }
        },
    }

    for title, config in examples.items():
        print(f"\n# {title}")
        print("databases:")
        print(yaml.dump(config, indent=2, default_flow_style=False))

    print("\n💡 Environment Variables:")
    print(
        "Use ${VAR_NAME} or ${VAR_NAME:-default} for environment variable substitution"
    )
    print("\n📚 For more information, see the database integration documentation")


def handle_database_providers_command(args_ns):
    """Handles the 'database providers' command."""
    logger.debug("Database providers command started.")

    print("🔌 Available Database Providers:")
    print("=" * 50)

    providers = [
        {
            "name": "Ommi ORM (Default)",
            "provider": "serv.bundled.database.ommi:create_ommi",
            "description": "Primary ORM for Serv with auto-detected drivers",
            "schemes": ["sqlite://", "postgresql://"],
            "recommended": True,
        },
        {
            "name": "Ommi SQLite",
            "provider": "serv.bundled.database.ommi:create_ommi_sqlite",
            "description": "Ommi with SQLite database (convenience factory)",
            "schemes": ["sqlite://"],
            "recommended": True,
        },
        {
            "name": "Ommi PostgreSQL",
            "provider": "serv.bundled.database.ommi:create_ommi_postgresql",
            "description": "Ommi with PostgreSQL database (convenience factory)",
            "schemes": ["postgresql://"],
            "recommended": True,
        },
        {
            "name": "Ommi Nested",
            "provider": "serv.bundled.database.ommi:create_ommi_nested",
            "description": "Ommi with nested settings (backward compatibility)",
            "schemes": ["Various"],
            "recommended": False,
        },
    ]

    for provider in providers:
        status = "🌟 RECOMMENDED" if provider["recommended"] else "ℹ️  Available"
        print(f"\n{status}")
        print(f"Name: {provider['name']}")
        print(f"Provider: {provider['provider']}")
        print(f"Description: {provider['description']}")
        print(f"Supported schemes: {', '.join(provider['schemes'])}")

    print("\n💡 Custom Providers:")
    print("You can create custom providers by implementing factory functions")
    print("Format: 'module.path:factory_function'")
    print("\n📚 See the provider development documentation for more details")

    return True


def _mask_credentials(connection_string: str) -> str:
    """Mask credentials in connection string for display."""
    if "://" not in connection_string:
        return connection_string

    try:
        scheme, rest = connection_string.split("://", 1)

        if "@" in rest:
            # Has credentials
            credentials, host_part = rest.split("@", 1)
            if ":" in credentials:
                username, password = credentials.split(":", 1)
                masked_credentials = f"{username}:***"
            else:
                masked_credentials = f"{credentials}:***"
            return f"{scheme}://{masked_credentials}@{host_part}"
        else:
            # No credentials
            return connection_string
    except Exception:
        # If parsing fails, return as-is
        return connection_string
