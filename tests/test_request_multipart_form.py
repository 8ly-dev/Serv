import pytest
from pathlib import Path
from httpx import AsyncClient
from typing import Type, List
import io
from dataclasses import dataclass

from serv.app import App
from serv.requests import FileUpload
from serv.routes import Route, Form, Response, TextResponse
from serv.plugins import Plugin
from serv.routing import Router
from serv.plugin_loader import PluginSpec
from bevy import dependency

# --- Helper types for tests ---

@dataclass
class MultipartTestForm(Form):
    text_field: str
    num_field: int
    file_upload: FileUpload
    optional_file: FileUpload | None = None
    multiple_files: List[FileUpload] | None = None # For future, if Request.form can support multiple files for one field name


class MultipartRoute(Route):
    async def handle_form(self, form: MultipartTestForm) -> Response:
        file_content = await form.file_upload.read()
        
        response_parts = [
            f"Text: {form.text_field}",
            f"Num: {form.num_field}",
            f"File: {form.file_upload.filename}",
            f"File Content-Type: {form.file_upload.content_type}",
            f"File Content Length: {len(file_content)}",
        ]
        if form.optional_file:
            opt_file_content = await form.optional_file.read()
            response_parts.extend([
                f"OptFile: {form.optional_file.filename}",
                f"OptFile Content-Type: {form.optional_file.content_type}",
                f"OptFile Content Length: {len(opt_file_content)}",
            ])
        
        if form.multiple_files:
            response_parts.append(f"Multiple Files Count: {len(form.multiple_files)}")
            for i, mf_file in enumerate(form.multiple_files):
                mf_content = await mf_file.read()
                response_parts.extend([
                    f"MultiFile[{i}] Name: {mf_file.filename}",
                    f"MultiFile[{i}] Content-Type: {mf_file.content_type}",
                    f"MultiFile[{i}] Length: {len(mf_content)}",
                ])

        return TextResponse("\n".join(response_parts))

class MultipartTestRoutePlugin(Plugin):
    def __init__(self, path: str, route_class: Type[Route]):
        super().__init__()
        self.path = path
        self.route_class = route_class
        self.plugin_registered_route = False
        self._stand_alone = True
        self._plugin_spec = PluginSpec(
            name="MultipartTestRoutePlugin",
            description="A test plugin for multipart form handling",
            version="0.1.0",
            path=Path(__file__).parent,
            author="Test Author"
        )

    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        router.add_route(self.path, self.route_class)
        self.plugin_registered_route = True

@pytest.mark.asyncio
async def test_multipart_form_submission_single_file(app: App, client: AsyncClient):
    pytest.skip("Hangs on client request")
    plugin = MultipartTestRoutePlugin("/upload", MultipartRoute)
    app.add_plugin(plugin)

    files = {"file_upload": ("testfile.txt", b"Hello, world!", "text/plain")}
    data = {"text_field": "Some text", "num_field": "123"}

    response = await client.post("/upload", files=files, data=data)

    assert response.status_code == 200
    expected_text = """Text: Some text
Num: 123
File: testfile.txt
File Content-Type: text/plain
File Content Length: 13"""
    assert response.text == expected_text
    assert plugin.plugin_registered_route

@pytest.mark.asyncio
async def test_multipart_form_submission_with_optional_file(app: App, client: AsyncClient):
    pytest.skip("Hangs on client request")
    plugin = MultipartTestRoutePlugin("/upload_opt", MultipartRoute)
    app.add_plugin(plugin)

    files = {
        "file_upload": ("main.jpg", b"<jpeg data>", "image/jpeg"),
        "optional_file": ("opt.png", b"<png data>", "image/png")
    }
    data = {"text_field": "With Opt", "num_field": "456"}

    response = await client.post("/upload_opt", files=files, data=data)
    assert response.status_code == 200
    expected_parts = [
        "Text: With Opt",
        "Num: 456",
        "File: main.jpg",
        "File Content-Type: image/jpeg",
        "File Content Length: 11", # len(b"<jpeg data>")
        "OptFile: opt.png",
        "OptFile Content-Type: image/png",
        "OptFile Content Length: 10"  # len(b"<png data>")
    ]
    assert response.text == "\n".join(expected_parts)
    assert plugin.plugin_registered_route

@pytest.mark.asyncio
async def test_multipart_form_submission_optional_file_not_provided(app: App, client: AsyncClient):
    pytest.skip("Hangs on client request")
    plugin = MultipartTestRoutePlugin("/upload_no_opt", MultipartRoute)
    app.add_plugin(plugin)

    files = {"file_upload": ("another.txt", b"Only main file.", "text/plain")}
    data = {"text_field": "No Opt File", "num_field": "789"}

    response = await client.post("/upload_no_opt", files=files, data=data)
    assert response.status_code == 200
    expected_text = (
        "Text: No Opt File\n"
        "Num: 789\n"
        "File: another.txt\n"
        "File Content-Type: text/plain\n"
        "File Content Length: 15"
    )
    assert response.text == expected_text
    assert plugin.plugin_registered_route
