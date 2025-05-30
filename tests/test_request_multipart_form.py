"""
Test multipart form parsing with file uploads
"""

from dataclasses import dataclass
from pathlib import Path

import pytest
from bevy import dependency
from httpx import AsyncClient

from serv.app import App
from serv.extensions import Extension, on
from serv.requests import FileUpload
from serv.routes import Form, Response, Route, TextResponse
from serv.routing import Router

# --- Helper types for tests ---


@dataclass
class MultipartTestForm(Form):
    text_field: str
    num_field: int
    file_upload: FileUpload
    optional_file: FileUpload | None = None
    multiple_files: list[FileUpload] | None = (
        None  # For future, if Request.form can support multiple files for one field name
    )


class MultipartRoute(Route):
    async def handle_post(self, form: MultipartTestForm) -> Response:
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
            response_parts.extend(
                [
                    f"OptFile: {form.optional_file.filename}",
                    f"OptFile Content-Type: {form.optional_file.content_type}",
                    f"OptFile Content Length: {len(opt_file_content)}",
                ]
            )

        if form.multiple_files:
            response_parts.append(f"Multiple Files Count: {len(form.multiple_files)}")
            for i, mf_file in enumerate(form.multiple_files):
                mf_content = await mf_file.read()
                response_parts.extend(
                    [
                        f"MultiFile[{i}] Name: {mf_file.filename}",
                        f"MultiFile[{i}] Content-Type: {mf_file.content_type}",
                        f"MultiFile[{i}] Length: {len(mf_content)}",
                    ]
                )

        return TextResponse("\n".join(response_parts))


class MultipartTestRouteExtension(Extension):
    def __init__(self, path: str, route_class: type[Route]):
        # Set up the plugin spec on the module before calling super().__init__()
        from tests.helpers import create_test_extension_spec

        self._extension_spec = create_test_extension_spec(
            name="MultipartTestRouteExtension", path=Path(__file__).parent
        )

        # Patch the module's __extension_spec__ for testing BEFORE super().__init__()
        import sys

        module = sys.modules[self.__module__]
        module.__extension_spec__ = self._extension_spec

        super().__init__(stand_alone=True)
        self.path = path
        self.route_class = route_class
        self.plugin_registered_route = False
        self._stand_alone = True

    @on("app.request.begin")
    async def setup_routes(self, router: Router = dependency()) -> None:
        router.add_route(self.path, self.route_class)
        self.plugin_registered_route = True


@pytest.mark.asyncio
async def test_multipart_form_submission_single_file(app: App, client: AsyncClient):
    plugin = MultipartTestRouteExtension("/upload", MultipartRoute)
    app.add_extension(plugin)

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
async def test_multipart_form_submission_with_optional_file(
    app: App, client: AsyncClient
):
    plugin = MultipartTestRouteExtension("/upload_opt", MultipartRoute)
    app.add_extension(plugin)

    files = {
        "file_upload": ("main.jpg", b"<jpeg data>", "image/jpeg"),
        "optional_file": ("opt.png", b"<png data>", "image/png"),
    }
    data = {"text_field": "With Opt", "num_field": "456"}

    response = await client.post("/upload_opt", files=files, data=data)
    assert response.status_code == 200
    expected_parts = [
        "Text: With Opt",
        "Num: 456",
        "File: main.jpg",
        "File Content-Type: image/jpeg",
        "File Content Length: 11",  # len(b"<jpeg data>")
        "OptFile: opt.png",
        "OptFile Content-Type: image/png",
        "OptFile Content Length: 10",  # len(b"<png data>")
    ]
    assert response.text == "\n".join(expected_parts)
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_multipart_form_submission_optional_file_not_provided(
    app: App, client: AsyncClient
):
    plugin = MultipartTestRouteExtension("/upload_no_opt", MultipartRoute)
    app.add_extension(plugin)

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
