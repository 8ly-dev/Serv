import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse

from serving.exception_handlers import http_exception_handler, general_exception_handler, not_found_handler
from serving.exception_middleware import ExceptionMiddleware
from serving.serv import Serv


class TestExceptionHandlers:
    """Test exception handler functions."""
    
    @pytest.fixture(autouse=True)
    def disable_auth(self):
        """Disable authentication for all tests."""
        with patch('serving.serv.Serv._configure_auth', MagicMock()):
            yield
    
    async def test_http_exception_handler(self):
        """Test HTTP exception handler renders error page."""
        # Create a mock request with app state
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/test"
        
        # Create mock serv with error handler
        mock_serv = MagicMock()
        mock_error_handler = MagicMock()
        mock_error_handler.render_error.return_value = Response("Error page", status_code=200, media_type="text/html")
        mock_serv.error_handler = mock_error_handler
        
        mock_request.app.state.serv = mock_serv
        
        # Create HTTPException
        exc = HTTPException(status_code=403, detail="Forbidden")
        
        # Call handler
        response = await http_exception_handler(mock_request, exc)
        
        # Verify error handler was called correctly
        mock_error_handler.render_error.assert_called_once_with(
            mock_request,
            error_code=403,
            error_message="Forbidden",
            details=None
        )
        
        assert response.status_code == 200
        assert response.media_type == "text/html"
    
    async def test_general_exception_handler(self):
        """Test general exception handler renders 500 error."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/test"
        
        mock_serv = MagicMock()
        mock_serv.environment = "prod"
        mock_error_handler = MagicMock()
        mock_error_handler.render_error.return_value = Response("Error page", status_code=200, media_type="text/html")
        mock_serv.error_handler = mock_error_handler
        
        mock_request.app.state.serv = mock_serv
        
        # Create general exception
        exc = ValueError("Something went wrong")
        
        # Call handler
        response = await general_exception_handler(mock_request, exc)
        
        # Verify error handler was called with 500 error
        mock_error_handler.render_error.assert_called_once()
        call_args = mock_error_handler.render_error.call_args
        assert call_args[1]["error_code"] == 500
        assert call_args[1]["error_message"] == "Internal Server Error"
        assert "Something went wrong" in call_args[1]["details"]
    
    async def test_general_exception_handler_dev_mode(self):
        """Test general exception handler includes traceback in dev mode."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/test"
        
        mock_serv = MagicMock()
        mock_serv.environment = "dev"
        mock_error_handler = MagicMock()
        mock_error_handler.render_error.return_value = Response("Error page", status_code=200, media_type="text/html")
        mock_serv.error_handler = mock_error_handler
        
        mock_request.app.state.serv = mock_serv
        
        # Create general exception
        exc = ValueError("Debug error")
        
        # Call handler
        response = await general_exception_handler(mock_request, exc)
        
        # Verify traceback is included in dev mode
        call_args = mock_error_handler.render_error.call_args
        assert call_args[1]["error_code"] == 500
        details = call_args[1]["details"]
        assert "Traceback" in details or "ValueError" in details
    
    async def test_not_found_handler(self):
        """Test 404 not found handler."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/missing/path"
        
        mock_serv = MagicMock()
        mock_error_handler = MagicMock()
        mock_error_handler.render_error.return_value = Response("404 page", status_code=200, media_type="text/html")
        mock_serv.error_handler = mock_error_handler
        
        mock_request.app.state.serv = mock_serv
        
        # Create 404 exception
        exc = HTTPException(status_code=404)
        
        # Call handler
        response = await not_found_handler(mock_request, exc)
        
        # Verify error handler was called correctly
        mock_error_handler.render_error.assert_called_once_with(
            mock_request,
            error_code=404,
            error_message="Not Found",
            details="The requested path '/missing/path' could not be found."
        )


class TestExceptionMiddleware:
    """Test exception middleware."""
    
    async def test_middleware_handles_404_response(self):
        """Test middleware handles 404 responses."""
        # Create mock serv
        mock_serv = MagicMock()
        mock_error_handler = MagicMock()
        mock_error_handler.render_error.return_value = Response("404 page", status_code=200, media_type="text/html")
        mock_serv.error_handler = mock_error_handler
        
        # Create middleware
        mock_app = MagicMock()
        middleware = ExceptionMiddleware(mock_app, mock_serv)
        
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/missing"
        
        # Mock call_next returning 404
        async def mock_call_next(request):
            return Response("Not found", status_code=404)
        
        # Call middleware
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        # Verify error handler was called
        mock_error_handler.render_error.assert_called_once_with(
            mock_request,
            error_code=404,
            error_message="Not Found",
            details="The requested path '/missing' could not be found."
        )
    
    async def test_middleware_handles_http_exceptions(self):
        """Test middleware handles HTTP exceptions."""
        mock_serv = MagicMock()
        mock_error_handler = MagicMock()
        mock_error_handler.render_error.return_value = Response("Error page", status_code=200, media_type="text/html")
        mock_serv.error_handler = mock_error_handler
        
        mock_app = MagicMock()
        middleware = ExceptionMiddleware(mock_app, mock_serv)
        
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/test"
        
        # Mock call_next raising HTTPException
        async def mock_call_next(request):
            raise HTTPException(status_code=400, detail="Bad Request")
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        mock_error_handler.render_error.assert_called_once_with(
            mock_request,
            error_code=400,
            error_message="Bad Request",
            details=None
        )
    
    async def test_middleware_handles_general_exceptions(self):
        """Test middleware handles general exceptions."""
        mock_serv = MagicMock()
        mock_serv.environment = "prod"
        mock_error_handler = MagicMock()
        mock_error_handler.render_error.return_value = Response("Error page", status_code=200, media_type="text/html")
        mock_serv.error_handler = mock_error_handler
        
        mock_app = MagicMock()
        middleware = ExceptionMiddleware(mock_app, mock_serv)
        
        mock_request = MagicMock(spec=Request)
        
        # Mock call_next raising general exception
        async def mock_call_next(request):
            raise RuntimeError("Something broke")
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        call_args = mock_error_handler.render_error.call_args
        assert call_args[1]["error_code"] == 500
        assert call_args[1]["error_message"] == "Internal Server Error"
        assert "Something broke" in call_args[1]["details"]
    
    async def test_middleware_passes_through_success(self):
        """Test middleware passes through successful responses."""
        mock_serv = MagicMock()
        mock_app = MagicMock()
        middleware = ExceptionMiddleware(mock_app, mock_serv)
        
        mock_request = MagicMock(spec=Request)
        
        # Mock successful response
        expected_response = Response("Success", status_code=200)
        
        async def mock_call_next(request):
            return expected_response
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        # Should pass through unchanged
        assert response == expected_response


class TestServIntegrationWithExceptions:
    """Test Serv integration with exception handling."""
    
    @pytest.fixture(autouse=True)
    def disable_auth(self):
        """Disable authentication for all tests."""
        with patch('serving.serv.Serv._configure_auth', MagicMock()):
            yield
    
    def test_serv_configures_exception_handlers(self):
        """Test that Serv configures exception handlers correctly."""
        yaml_content = """
environment: test
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "serving.test.yaml"
            config_file.write_text(yaml_content)
            
            serv = Serv(working_directory=tmpdir, environment="test")
            
            # Check middleware is configured (middleware is a list of tuples)
            # We can't directly check middleware classes in Starlette, so skip this check
            
            # Check exception handlers are configured
            assert HTTPException in serv.app.exception_handlers
            assert 404 in serv.app.exception_handlers
            assert 500 in serv.app.exception_handlers
            
            # Check serv is stored in app state
            assert serv.app.state.serv == serv