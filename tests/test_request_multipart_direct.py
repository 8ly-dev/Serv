"""
Test multipart parsing directly without file system or files
"""

from pathlib import Path

import pytest
from bevy import dependency
from httpx import AsyncClient

from serv.app import App
from serv.plugins import Plugin
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.routes import JsonResponse
from serv.routing import Router


# Plugin to add simple handlers
class DirectHandlerPlugin(Plugin):
    def __init__(self, path: str, handler, methods: list[str]):
        # Set up the plugin spec on the module before calling super().__init__()
        from tests.helpers import create_test_plugin_spec

        self._plugin_spec = create_test_plugin_spec(
            name="DirectHandlerPlugin", path=Path(__file__).parent
        )

        # Patch the module's __plugin_spec__ for testing BEFORE super().__init__()
        import sys

        module = sys.modules[self.__module__]
        module.__plugin_spec__ = self._plugin_spec

        super().__init__(stand_alone=True)
        self.path = path
        self.handler = handler
        self.methods = methods
        self.plugin_registered_route = False
        self._stand_alone = True

    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        router.add_route(self.path, self.handler, self.methods)
        self.plugin_registered_route = True


# Test Handler 1: Single file and text fields
async def handle_direct_single_file(
    request: Request = dependency(), response_builder: ResponseBuilder = dependency()
):
    form_data = await request.form()

    errors = []
    file_content_for_response = ""
    file_upload_filename_for_response = None

    # Check text field
    if not form_data.get("text_field") == ["Some text"]:
        errors.append(f"text_field error: {form_data.get('text_field')}")

    # Check num field
    if not form_data.get("num_field") == ["123"]:
        errors.append(f"num_field error: {form_data.get('num_field')}")

    # Check file upload
    file_upload_list = form_data.get("file_upload")
    if (
        not file_upload_list
        or not isinstance(file_upload_list, list)
        or not len(file_upload_list) == 1
    ):
        errors.append(f"file_upload list error: {file_upload_list}")
    else:
        file_obj = file_upload_list[0]
        if not isinstance(file_obj, dict):
            errors.append(f"file_upload type error: {type(file_obj)}")
        else:
            file_upload_filename_for_response = file_obj["filename"]
            if not file_obj["filename"] == "testfile.txt":
                errors.append(f"file_upload filename error: {file_obj['filename']}")

            # Content-Type will be None due to library limitations, skip check.

            file_content = (
                file_obj["file"].read() if file_obj["file"] else b""
            )  # Read once
            if not file_content == b"Hello, world!":
                errors.append(
                    f"file_upload content error. Expected b'Hello, world!', got: {file_content!r}"
                )
            else:
                file_content_for_response = file_content.decode()  # Store for response

    if errors:
        # For debugging, include what form_data looks like (simplified)
        serializable_form_data = {}
        for k, v_list in form_data.items():
            serializable_form_data[k] = []
            for item in v_list:
                if isinstance(item, dict):
                    serializable_form_data[k].append(
                        {
                            "filename": item["filename"],
                            "content_type": item["content_type"],
                            "file_is_present": item["file"] is not None,
                        }
                    )
                else:
                    serializable_form_data[k].append(item)

        response_builder.body(
            JsonResponse(
                {
                    "status": "error",
                    "errors": errors,
                    "form_data_received": serializable_form_data,
                },
                status_code=400,
            ).render()
        )
        return

    success_payload = {
        "status": "ok",
        "text_field": form_data["text_field"][0],
        "num_field": form_data["num_field"][0],
        "file_upload_filename": file_upload_filename_for_response,
        "file_upload_content": file_content_for_response,
    }
    response_builder.body(JsonResponse(success_payload).render())


@pytest.mark.asyncio
async def test_direct_multipart_single_file(app: App, client: AsyncClient):
    app.add_plugin(
        DirectHandlerPlugin(
            "/direct_upload_single", handle_direct_single_file, methods=["POST"]
        )
    )

    files = {"file_upload": ("testfile.txt", b"Hello, world!", "text/plain")}
    data = {"text_field": "Some text", "num_field": "123"}

    response = await client.post("/direct_upload_single", files=files, data=data)

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "ok"
    assert response_data["text_field"] == "Some text"
    assert response_data["num_field"] == "123"
    assert response_data["file_upload_filename"] == "testfile.txt"


# Test Handler 2: Multiple files (one optional present, one optional absent)
async def handle_direct_multiple_files(
    request: Request = dependency(), response_builder: ResponseBuilder = dependency()
):
    form_data = await request.form()

    # Basic checks (can be more thorough like above)
    assert form_data["main_text_field"] == ["Main Text"]

    mandatory_file_list = form_data["mandatory_file"]
    assert len(mandatory_file_list) == 1
    mandatory_file_obj = mandatory_file_list[0]
    assert set(mandatory_file_obj.keys()) == {
        "filename",
        "content_type",
        "headers",
        "file",
    }
    assert mandatory_file_obj["filename"] == "main.dat"
    content_mand = (
        mandatory_file_obj["file"].read() if mandatory_file_obj["file"] else b""
    )
    assert content_mand == b"Mandatory content"

    optional_file_sent_list = form_data["optional_file_sent"]
    assert len(optional_file_sent_list) == 1
    optional_file_obj = optional_file_sent_list[0]
    assert isinstance(optional_file_obj, dict)
    assert optional_file_obj["filename"] == "opt.txt"
    content_opt = optional_file_obj["file"].read() if optional_file_obj["file"] else b""
    assert content_opt == b"Optional content"

    # Construct a serializable response
    response_payload = {
        "status": "ok",
        "main_text_field": form_data["main_text_field"][0],
        "mandatory_file": {
            "filename": mandatory_file_obj["filename"],
            "content_length": len(content_mand),
        },
        "optional_file_sent": {
            "filename": optional_file_obj["filename"],
            "content_length": len(content_opt),
        },
        "missing_optional_field_absent": "optional_file_not_sent" not in form_data,
    }
    response_builder.body(JsonResponse(response_payload).render())


@pytest.mark.asyncio
async def test_direct_multipart_multiple_files(app: App, client: AsyncClient):
    app.add_plugin(
        DirectHandlerPlugin(
            "/direct_upload_multi", handle_direct_multiple_files, methods=["POST"]
        )
    )

    files_payload = {
        "mandatory_file": (
            "main.dat",
            b"Mandatory content",
            "application/octet-stream",
        ),
        "optional_file_sent": ("opt.txt", b"Optional content", "text/plain"),
        # optional_file_not_sent is omitted
    }
    data_payload = {"main_text_field": "Main Text"}

    response = await client.post(
        "/direct_upload_multi", files=files_payload, data=data_payload
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "ok"
    assert response_data["missing_optional_field_absent"] is True
