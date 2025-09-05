import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from serving.config import Config
from serving.error_handler import ErrorHandler
from serving.serv import Serv, ThemingConfig


class TestThemingConfig:
    def test_theming_config_defaults(self):
        """Test that ThemingConfig has correct defaults."""
        config = ThemingConfig()
        assert config.error_templates is None
        assert config.default_error_template is None

    def test_theming_config_with_values(self):
        """Test ThemingConfig with custom values."""
        config = ThemingConfig(
            error_templates={"404": "errors/404.html", "500": "errors/500.html"},
            default_error_template="errors/default.html"
        )
        assert config.error_templates["404"] == "errors/404.html"
        assert config.error_templates["500"] == "errors/500.html"
        assert config.default_error_template == "errors/default.html"

    def test_theming_config_model_key(self):
        """Test that ThemingConfig has the correct model key."""
        assert ThemingConfig.__model_key__ == "theming"


class TestErrorHandler:
    def test_error_handler_initialization(self):
        """Test ErrorHandler initialization."""
        handler = ErrorHandler()
        assert handler.theming_config is None
        assert handler.custom_templates is None
        assert handler.fallback_templates is not None

    def test_error_handler_with_config(self):
        """Test ErrorHandler with theming config."""
        theming_config = ThemingConfig(
            error_templates={"404": "custom_404.html"},
            default_error_template="custom_error.html"
        )
        handler = ErrorHandler(theming_config=theming_config)
        assert handler.theming_config == theming_config

    def test_get_default_message(self):
        """Test default error messages."""
        handler = ErrorHandler()
        assert handler._get_default_message(404) == "Not Found"
        assert handler._get_default_message(401) == "Unauthorized"
        assert handler._get_default_message(500) == "Internal Server Error"
        assert handler._get_default_message(999) == "Error"  # Unknown code

    def test_render_error_fallback(self):
        """Test that fallback template is used when no config."""
        handler = ErrorHandler()
        
        # Mock request
        mock_request = MagicMock()
        mock_request.url.path = "/test"
        
        response = handler.render_error(mock_request, 404)
        
        # Should return HTMLResponse with fallback template
        assert response.status_code == 200  # Template response is always 200
        assert response.media_type == "text/html"

    def test_render_error_with_custom_message(self):
        """Test rendering with custom error message."""
        handler = ErrorHandler()
        
        mock_request = MagicMock()
        mock_request.url.path = "/test"
        
        response = handler.render_error(
            mock_request, 
            404, 
            error_message="Custom Not Found",
            details="The specific resource was not found"
        )
        
        assert response.status_code == 200


class TestServWithTheming:
    @pytest.fixture(autouse=True)
    def disable_auth(self):
        """Disable authentication for all tests."""
        with patch('serving.serv.Serv._configure_auth', MagicMock()):
            yield

    def test_serv_without_theming_config(self):
        """Test that Serv works without theming configuration."""
        yaml_content = """
environment: test
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serving.test.yaml"
            config_file.write_text(yaml_content)
            
            serv = Serv(working_directory=tmpdir, environment="test")
            
            # Should have error handler, theming config will have None values
            assert serv.error_handler is not None
            # When no theming config in YAML, DI creates default with None values
            assert serv.error_handler.theming_config.error_templates is None
            assert serv.error_handler.theming_config.default_error_template is None

    def test_serv_with_theming_config(self):
        """Test Serv with theming configuration."""
        yaml_content = """
environment: test
theming:
  error_templates:
    "404": "custom/404.html"
    "500": "custom/500.html"
  default_error_template: "custom/error.html"
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serving.test.yaml"
            config_file.write_text(yaml_content)
            
            # Create template directory
            templates_dir = Path(tmpdir) / "templates"
            templates_dir.mkdir()
            
            serv = Serv(working_directory=tmpdir, environment="test")
            
            # Should have error handler with theming config
            assert serv.error_handler is not None
            assert serv.error_handler.theming_config is not None
            assert serv.error_handler.theming_config.error_templates["404"] == "custom/404.html"
            assert serv.error_handler.theming_config.default_error_template == "custom/error.html"

    def test_serv_with_partial_theming_config(self):
        """Test Serv with partial theming configuration."""
        yaml_content = """
environment: test
theming:
  default_error_template: "errors/default.html"
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serving.test.yaml"
            config_file.write_text(yaml_content)
            
            serv = Serv(working_directory=tmpdir, environment="test")
            
            assert serv.error_handler.theming_config is not None
            assert serv.error_handler.theming_config.error_templates is None
            assert serv.error_handler.theming_config.default_error_template == "errors/default.html"

    def test_unauthorized_uses_error_handler(self):
        """Test that unauthorized responses use the error handler."""
        yaml_content = """
environment: test
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serving.test.yaml"
            config_file.write_text(yaml_content)
            
            serv = Serv(working_directory=tmpdir, environment="test")
            
            # Mock endpoint that will be wrapped
            async def test_endpoint():
                return "test"
            
            # Mock credential provider that denies access
            mock_credential_provider = MagicMock()
            mock_credential_provider.has_credentials.return_value = False
            
            # Mock route config with permissions
            mock_route_config = MagicMock()
            mock_route_config.permissions = {"admin"}
            
            wrapped = serv._wrap_endpoint(test_endpoint, mock_route_config)
            
            # Test that wrapped endpoint uses error handler
            mock_request = MagicMock()
            mock_request.path_params = {}
            
            with patch('serving.serv.get_container') as mock_get_container:
                mock_container = MagicMock()
                mock_container.get.return_value = mock_credential_provider
                mock_container.call.return_value = False
                mock_get_container.return_value = mock_container
                
                import asyncio
                response = asyncio.run(wrapped(mock_request))
                
                # Should return HTML response from error handler
                assert response.status_code == 200  # Template response
                assert response.media_type == "text/html"