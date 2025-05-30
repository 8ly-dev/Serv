"""
Test files related to routes.
"""

from pathlib import Path
from typing import Annotated

import pytest
from bevy import dependency
from httpx import AsyncClient

from serv.app import App
from serv.extensions import Extension, on
from serv.requests import Request
from serv.routes import Route, TextResponse, handle
from serv.routing import Router
from tests.helpers import create_test_extension_spec


class FileUploadTestRoute(Route):
    """Handle file upload using Route class pattern"""

    @handle.POST
    async def post_handler(
        self, request: Request = dependency()
    ) -> Annotated[str, TextResponse]:
        from serv.exceptions import HTTPBadRequestException

        # Check content type first
        content_type = request.headers.get("content-type", "")
        if not content_type or not (
            "multipart/form-data" in content_type
            or "application/x-www-form-urlencoded" in content_type
        ):
            raise HTTPBadRequestException("No file uploaded")

        try:
            form_data = await request.form()
        except Exception:
            raise HTTPBadRequestException("Failed to parse form data") from None

        # Check if form_data is empty or doesn't have the file field
        if not form_data or "file_upload" not in form_data:
            raise HTTPBadRequestException("No file uploaded")

        file_upload_list = form_data["file_upload"]
        if not file_upload_list or not isinstance(file_upload_list, list):
            raise HTTPBadRequestException("Invalid file upload")

        file_upload_dict = file_upload_list[0]  # Get first file
        if not isinstance(file_upload_dict, dict) or "file" not in file_upload_dict:
            raise HTTPBadRequestException("Invalid file upload structure")

        try:
            file_obj = file_upload_dict["file"]
            content = file_obj.read()

            response_text = f"File: {file_upload_dict['filename']}\n"
            response_text += f"Content-Type: {file_upload_dict['content_type']}\n"
            response_text += f"Size: {len(content)} bytes\n"
            response_text += f"Content: {content.decode('utf-8') if len(content) < 100 else 'Large file'}"

            return response_text
        except Exception as e:
            from serv.exceptions import ServException

            raise ServException(f"Error processing upload: {str(e)}") from None


class FileUploadTestExtension(Extension):
    def __init__(self):
        # Set up the plugin spec on the module before calling super().__init__()
        self._extension_spec = create_test_extension_spec(
            name="FileUploadTestExtension", path=Path(__file__).parent
        )

        # Patch the module's __extension_spec__ for testing BEFORE super().__init__()
        import sys

        module = sys.modules[self.__module__]
        module.__extension_spec__ = self._extension_spec

        super().__init__(stand_alone=True)
        self.plugin_registered_route = False
        self._stand_alone = True

    @on("app.request.begin")
    async def setup_routes(self, router: Router = dependency()) -> None:
        router.add_route("/upload", FileUploadTestRoute)
        self.plugin_registered_route = True


@pytest.mark.asyncio
async def test_file_upload_with_route_handler(app: App, client: AsyncClient):
    """Test file upload using the Route class pattern"""
    plugin = FileUploadTestExtension()
    app.add_extension(plugin)

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
    plugin = FileUploadTestExtension()
    app.add_extension(plugin)

    response = await client.post("/upload")

    assert response.status_code == 400
    assert "No file uploaded" in response.text
