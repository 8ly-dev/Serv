"""
Test files related to routes.
"""
import asyncio
import pytest
from pathlib import Path
from httpx import AsyncClient
from bevy import dependency

from serv.app import App
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.plugins import Plugin
from serv.routing import Router
from serv.plugins.loader import PluginSpec
from tests.helpers import create_test_plugin_spec

class FileUploadTestPlugin(Plugin):
    def __init__(self):
        # Set up the plugin spec on the module before calling super().__init__()
        self._plugin_spec = create_test_plugin_spec(
            name="FileUploadTestPlugin",
            path=Path(__file__).parent
        )
        
        # Patch the module's __plugin_spec__ for testing BEFORE super().__init__()
        import sys
        module = sys.modules[self.__module__]
        module.__plugin_spec__ = self._plugin_spec
        
        super().__init__(stand_alone=True)
        self.plugin_registered_route = False
        self._stand_alone = True

    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        router.add_route("/upload", self.handle_upload)
        self.plugin_registered_route = True

    async def handle_upload(
        self, 
        request: Request = dependency(), 
        response: ResponseBuilder = dependency()
    ):
        """Handle file upload using function handler pattern"""
        try:
            # Check content type first
            content_type = request.headers.get("content-type", "")
            if not content_type or not ("multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type):
                response.set_status(400)
                response.content_type("text/plain")
                response.body("No file uploaded")
                return
                
            form_data = await request.form()
            
            # Check if form_data is empty or doesn't have the file field
            if not form_data or "file_upload" not in form_data:
                response.set_status(400)
                response.content_type("text/plain")
                response.body("No file uploaded")
                return

            file_upload_list = form_data["file_upload"]
            if not file_upload_list or not isinstance(file_upload_list, list):
                response.set_status(400)
                response.content_type("text/plain")
                response.body("Invalid file upload")
                return

            file_upload_dict = file_upload_list[0]  # Get first file
            if not isinstance(file_upload_dict, dict) or 'file' not in file_upload_dict:
                response.set_status(400)
                response.content_type("text/plain")
                response.body("Invalid file upload structure")
                return

            file_obj = file_upload_dict['file']
            content = file_obj.read()
            
            response_text = f"File: {file_upload_dict['filename']}\n"
            response_text += f"Content-Type: {file_upload_dict['content_type']}\n"
            response_text += f"Size: {len(content)} bytes\n"
            response_text += f"Content: {content.decode('utf-8') if len(content) < 100 else 'Large file'}"
            
            response.content_type("text/plain")
            response.body(response_text)

        except Exception as e:
            response.set_status(500)
            response.content_type("text/plain")
            response.body(f"Error processing upload: {str(e)}")

@pytest.mark.asyncio
async def test_file_upload_with_function_handler(app: App, client: AsyncClient):
    """Test file upload using the working function handler pattern"""
    plugin = FileUploadTestPlugin()
    app.add_plugin(plugin)

    files = {"file_upload": ("test.txt", b"Hello, World!", "text/plain")}
    
    response = await client.post("/upload", files=files)
    
    assert response.status_code == 200
    assert "File: test.txt" in response.text
    assert "Content-Type: text/plain" in response.text
    assert "Size: 13 bytes" in response.text
    assert "Content: Hello, World!" in response.text

@pytest.mark.asyncio
async def test_file_upload_no_file(app: App, client: AsyncClient):
    """Test file upload endpoint with no file"""
    plugin = FileUploadTestPlugin()
    app.add_plugin(plugin)

    response = await client.post("/upload")
    
    assert response.status_code == 400
    assert "No file uploaded" in response.text 