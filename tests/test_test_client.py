"""Tests for the create_test_app_client function."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from serv.test_client import create_test_app_client


@pytest.mark.asyncio
async def test_create_test_app_client_basic():
    """Test basic functionality of create_test_app_client."""
    # Create a temporary config file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_path = temp_path / "serv.config.yaml"

        # Write a minimal config
        config_content = """site_info:
  name: "Test App"
  description: "Test application"

extensions: []
"""
        config_path.write_text(config_content)

        # Test the client
        async with create_test_app_client(config_path) as client:
            assert client is not None
            # Try to make a request - should get 404 since no extensions configured and welcome is mocked
            response = await client.get("/")
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_test_app_client_dev_mode():
    """Test create_test_app_client with dev mode enabled."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_path = temp_path / "serv.config.yaml"

        config_content = """site_info:
  name: "Test App Dev"
  description: "Test application in dev mode"

extensions: []
"""
        config_path.write_text(config_content)

        async with create_test_app_client(config_path, dev=True) as client:
            assert client is not None
            response = await client.get("/")
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_test_app_client_dry_run():
    """Test create_test_app_client with dry run mode."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_path = temp_path / "serv.config.yaml"

        config_content = """site_info:
  name: "Test App Dry Run"
  description: "Test application in dry run mode"

extensions: []
"""
        config_path.write_text(config_content)

        # In dry run mode, client should be None
        async with create_test_app_client(config_path, dry_run=True) as client:
            assert client is None


@pytest.mark.asyncio
async def test_create_test_app_client_with_custom_extension_dir():
    """Test create_test_app_client with custom extension directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_path = temp_path / "serv.config.yaml"

        # Create a custom extensions directory
        extensions_dir = temp_path / "my_extensions"
        extensions_dir.mkdir()

        config_content = """site_info:
  name: "Test App Custom Extensions"
  description: "Test application with custom extension directory"

extensions: []
"""
        config_path.write_text(config_content)

        async with create_test_app_client(
            config_path, extension_dirs=str(extensions_dir)
        ) as client:
            assert client is not None
            response = await client.get("/")
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_test_app_client_path_types():
    """Test create_test_app_client accepts both Path and string for config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_path = temp_path / "serv.config.yaml"

        config_content = """site_info:
  name: "Test App Path Types"
  description: "Test path parameter types"

extensions: []
"""
        config_path.write_text(config_content)

        # Test with Path object
        async with create_test_app_client(config_path) as client:
            assert client is not None
            response = await client.get("/")
            assert response.status_code == 404

        # Test with string path
        async with create_test_app_client(str(config_path)) as client:
            assert client is not None
            response = await client.get("/")
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_test_app_client_no_lifespan():
    """Test create_test_app_client with lifespan disabled."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_path = temp_path / "serv.config.yaml"

        config_content = """site_info:
  name: "Test App No Lifespan"
  description: "Test application without lifespan events"

extensions: []
"""
        config_path.write_text(config_content)

        async with create_test_app_client(config_path, use_lifespan=False) as client:
            assert client is not None
            response = await client.get("/")
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_test_app_client_custom_base_url():
    """Test create_test_app_client with custom base URL."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_path = temp_path / "serv.config.yaml"

        config_content = """site_info:
  name: "Test App Custom URL"
  description: "Test application with custom base URL"

extensions: []
"""
        config_path.write_text(config_content)

        custom_base_url = "http://custom.test"
        async with create_test_app_client(
            config_path, base_url=custom_base_url
        ) as client:
            assert client is not None
            assert str(client.base_url) == custom_base_url
            response = await client.get("/")
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_test_app_client_error_handling():
    """Test create_test_app_client error handling with invalid config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_path = temp_path / "invalid.yaml"

        # Write invalid YAML to trigger an error
        config_path.write_text("invalid: yaml: content: [")

        # Should raise an exception for invalid YAML
        with pytest.raises(Exception):
            async with create_test_app_client(config_path) as client:
                pass
