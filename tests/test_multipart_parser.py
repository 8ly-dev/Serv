from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from serv.multipart_parser import (
    DEFAULT_MULTIPART_CONFIG,
    MultipartParser,
    MultipartParserError,
    ParsedFileUpload,
)

# --- Helper Functions ---


def create_form_data_part(name: str, value: str, boundary: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"\r\n'
        f"\r\n"
        f"{value}\r\n"
    ).encode()


def create_file_data_part(
    name: str,
    filename: str,
    content: bytes,
    content_type: str,
    boundary: str,
    extra_headers: dict[str, str] | None = None,
) -> bytes:
    headers_str = (
        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
    )
    headers_str += f"Content-Type: {content_type}\r\n"
    if extra_headers:
        for h_name, h_val in extra_headers.items():
            headers_str += f"{h_name}: {h_val}\r\n"
    headers_str += "\r\n"

    return (
        f"--{boundary}\r\n".encode() + headers_str.encode("utf-8") + content + b"\r\n"
    )


def create_multipart_body(parts: list[bytes], boundary: str) -> bytes:
    body = b"".join(parts)
    body += f"--{boundary}--\r\n".encode()
    return body


async def mock_receive_callable(
    body_chunks: list[bytes],
) -> Callable[[], Awaitable[dict[str, Any]]]:
    idx = 0

    async def receive() -> dict[str, Any]:
        nonlocal idx
        if idx < len(body_chunks):
            chunk = body_chunks[idx]
            idx += 1
            more_body = idx < len(body_chunks)
            return {"type": "http.request", "body": chunk, "more_body": more_body}
        return {"type": "http.request", "body": b"", "more_body": False}

    return receive


# --- Pytest Fixtures ---


@pytest.fixture
def default_parser() -> MultipartParser:
    return MultipartParser(boundary=b"testboundary")


@pytest.fixture
def custom_config_parser_factory():
    def _factory(config_overrides: dict[str, int]) -> MultipartParser:
        config = DEFAULT_MULTIPART_CONFIG.copy()
        config.update(config_overrides)
        return MultipartParser(boundary=b"testboundary", config=config)

    return _factory


# --- Test Cases ---


@pytest.mark.asyncio
async def test_parse_simple_field(default_parser: MultipartParser):
    boundary = "testboundary"
    parts = [
        create_form_data_part("field1", "value1", boundary),
    ]
    body = create_multipart_body(parts, boundary)
    receive = await mock_receive_callable([body])

    result = await default_parser.parse(receive)

    assert "field1" in result
    assert result["field1"] == ["value1"]
    assert not default_parser.files


@pytest.mark.asyncio
async def test_parse_simple_file(default_parser: MultipartParser):
    boundary = "testboundary"
    file_content = b"this is a test file"
    parts = [
        create_file_data_part(
            "file1", "test.txt", file_content, "text/plain", boundary
        ),
    ]
    body = create_multipart_body(parts, boundary)
    receive = await mock_receive_callable([body])

    result = await default_parser.parse(receive)

    assert "file1" in result
    assert len(result["file1"]) == 1
    file_upload: ParsedFileUpload = result["file1"][0]
    assert file_upload["filename"] == "test.txt"
    assert file_upload["content_type"] == "text/plain"
    assert file_upload["file"].read() == file_content
    assert not default_parser.fields


@pytest.mark.asyncio
async def test_parse_multiple_fields_and_files(default_parser: MultipartParser):
    boundary = "testboundary"
    file_content1 = b"file one content"
    file_content2 = b"file two content"
    parts = [
        create_form_data_part("fieldA", "valA", boundary),
        create_file_data_part(
            "upload1", "first.dat", file_content1, "application/octet-stream", boundary
        ),
        create_form_data_part("fieldB", "valB", boundary),
        create_file_data_part(
            "upload2", "second.dat", file_content2, "image/png", boundary
        ),
    ]
    body = create_multipart_body(parts, boundary)
    receive = await mock_receive_callable([body])

    result = await default_parser.parse(receive)

    assert result["fieldA"] == ["valA"]
    assert result["fieldB"] == ["valB"]
    assert len(result["upload1"]) == 1
    assert result["upload1"][0]["filename"] == "first.dat"
    assert result["upload1"][0]["file"].read() == file_content1
    assert len(result["upload2"]) == 1
    assert result["upload2"][0]["filename"] == "second.dat"
    assert result["upload2"][0]["file"].read() == file_content2


# --- Limit Tests ---


@pytest.mark.asyncio
async def test_max_file_size_exceeded(custom_config_parser_factory):
    parser = custom_config_parser_factory({"max_file_size": 100})
    boundary = "testboundary"
    file_content = b"a" * 101
    parts = [
        create_file_data_part(
            "bigfile", "large.txt", file_content, "text/plain", boundary
        )
    ]
    body = create_multipart_body(parts, boundary)
    receive = await mock_receive_callable([body])

    with pytest.raises(MultipartParserError, match="exceeds maximum size"):
        await parser.parse(receive)


@pytest.mark.asyncio
async def test_max_num_files_exceeded(custom_config_parser_factory):
    parser = custom_config_parser_factory({"max_num_files": 1})
    boundary = "testboundary"
    parts = [
        create_file_data_part("file1", "f1.txt", b"c1", "text/plain", boundary),
        create_file_data_part("file2", "f2.txt", b"c2", "text/plain", boundary),
    ]
    body = create_multipart_body(parts, boundary)
    receive = await mock_receive_callable([body])

    with pytest.raises(
        MultipartParserError, match="Maximum number of files .* exceeded"
    ):
        await parser.parse(receive)


@pytest.mark.asyncio
async def test_max_total_body_size_exceeded(custom_config_parser_factory):
    max_size = 200
    parser = custom_config_parser_factory({"max_total_body_size": max_size})
    boundary = "testboundary"

    field_val_len = 60
    file_content_len = 60

    part1 = create_form_data_part("field1", "v" * field_val_len, boundary)
    part2 = create_file_data_part(
        "file1", "f.txt", b"c" * file_content_len, "text/plain", boundary
    )
    terminator = f"--{boundary}--\r\n".encode()

    body_content = part1 + part2 + terminator
    assert len(body_content) > max_size

    chunks = [body_content[i : i + 80] for i in range(0, len(body_content), 80)]
    if not chunks:
        chunks = [b""]

    receive = await mock_receive_callable(chunks)

    with pytest.raises(
        MultipartParserError, match="Total request body size exceeds maximum"
    ):
        await parser.parse(receive)


@pytest.mark.asyncio
async def test_max_header_name_size_exceeded(custom_config_parser_factory):
    parser = custom_config_parser_factory({"max_header_name_size": 10})
    boundary = "testboundary"
    long_header_name = "X-" + "A" * 9
    parts = [
        create_file_data_part(
            "file1",
            "f.txt",
            b"c",
            "text/plain",
            boundary,
            extra_headers={long_header_name: "val"},
        )
    ]
    body = create_multipart_body(parts, boundary)
    receive = await mock_receive_callable([body])

    with pytest.raises(MultipartParserError, match="Header name exceeds maximum size"):
        await parser.parse(receive)


@pytest.mark.asyncio
async def test_max_header_value_size_exceeded(custom_config_parser_factory):
    parser = custom_config_parser_factory({"max_header_value_size": 10})
    boundary = "testboundary"
    long_header_value = "V" * 11
    parts = [
        create_file_data_part(
            "file1",
            "f.txt",
            b"c",
            "text/plain",
            boundary,
            extra_headers={"X-Custom": long_header_value},
        )
    ]
    body = create_multipart_body(parts, boundary)
    receive = await mock_receive_callable([body])

    with pytest.raises(MultipartParserError, match="Header value exceeds maximum size"):
        await parser.parse(receive)


@pytest.mark.asyncio
async def test_max_headers_per_part_exceeded(custom_config_parser_factory):
    parser = custom_config_parser_factory({"max_headers_per_part": 2})
    boundary = "testboundary"
    parts = [
        create_file_data_part(
            "file1",
            "f.txt",
            b"c",
            "text/plain",
            boundary,
            extra_headers={"X-Another-Header": "val"},
        )
    ]
    body = create_multipart_body(parts, boundary)
    receive = await mock_receive_callable([body])

    with pytest.raises(
        MultipartParserError, match="Number of headers in part exceeds maximum"
    ):
        await parser.parse(receive)


# --- Filename Security Tests ---


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unsafe_filename, description",
    [
        ("../etc/passwd", "Path traversal up"),
        ("test/../../boot.ini", "Path traversal complex"),
        ("file.txt\0", "Null byte injection"),
        (" space lead.txt", "Leading space"),
        ("file with spaces.txt", "Spaces (becomes underscores)"),
        ("file<with>bad&chars.zip", "Special chars"),
        ("COM1", "Reserved filename on Windows"),
        (".hiddenfile", "Leading dot (often kept)"),
    ],
)
async def test_unsafe_filenames_rejected_or_sanitized(
    default_parser: MultipartParser, unsafe_filename: str, description: str
):
    boundary = "testboundary"
    parts = [
        create_file_data_part(
            "upload", unsafe_filename, b"content", "text/plain", boundary
        )
    ]
    body = create_multipart_body(parts, boundary)
    receive = await mock_receive_callable([body])

    from werkzeug.utils import secure_filename

    expected_filename = secure_filename(unsafe_filename)

    if not expected_filename and unsafe_filename:
        with pytest.raises(
            MultipartParserError, match=f"Unsafe filename provided: '{unsafe_filename}'"
        ):
            await default_parser.parse(receive)
    else:
        result = await default_parser.parse(receive)
        if not expected_filename:
            if "upload" in result and result["upload"]:
                assert not isinstance(result["upload"][0], ParsedFileUpload), (
                    "Should not be a file upload if filename became empty"
                )
                assert isinstance(result["upload"][0], str), (
                    "Should be a string field if filename was invalid"
                )
            assert not default_parser.files.get("upload"), (
                "File should not appear in parser.files if filename was invalid"
            )

        else:
            assert "upload" in result, f"Key 'upload' missing for {description}"
            assert len(result["upload"]) == 1, (
                f"Incorrect number of files for {description}"
            )
            file_upload: ParsedFileUpload = result["upload"][0]
            assert file_upload["filename"] == expected_filename, (
                f"Filename sanitization failed for: {description}"
            )


@pytest.mark.asyncio
async def test_empty_filename_string_not_treated_as_file(
    default_parser: MultipartParser,
):
    boundary = "testboundary"
    parts = [
        create_file_data_part("upload_empty_fn", "", b"content", "text/plain", boundary)
    ]
    body = create_multipart_body(parts, boundary)
    receive = await mock_receive_callable([body])

    result = await default_parser.parse(receive)
    assert "upload_empty_fn" in result
    assert len(result["upload_empty_fn"]) == 1
    assert isinstance(result["upload_empty_fn"][0], str)
    assert result["upload_empty_fn"][0] == "content"
    assert not default_parser.files.get("upload_empty_fn")


@pytest.mark.asyncio
async def test_no_filename_directive_in_content_disposition(
    default_parser: MultipartParser,
):
    boundary = "testboundary"
    part_data = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="field_no_file_directive"\r\n'
        f"Content-Type: text/plain\r\n"
        f"\r\n"
        f"this is some data\r\n"
    ).encode()
    parts = [part_data]
    body = create_multipart_body(parts, boundary)
    receive = await mock_receive_callable([body])

    result = await default_parser.parse(receive)
    assert "field_no_file_directive" in result
    assert result["field_no_file_directive"] == ["this is some data"]
    assert not default_parser.files.get("field_no_file_directive")


# --- Malformed Request Tests ---


@pytest.mark.asyncio
async def test_malformed_content_disposition_rejected(
    default_parser: MultipartParser, mocker
):
    """Test that if parse_options_header raises ValueError, it propagates."""
    boundary = "testboundary"
    # A perfectly valid part, the error will be simulated by mocking parse_options_header
    part_data = create_file_data_part(
        "upload", "test.txt", b"content", "text/plain", boundary
    )
    body = create_multipart_body([part_data], boundary)
    receive = await mock_receive_callable([body])

    # Mock multipart.multipart.parse_options_header to raise a ValueError
    # This is the function imported and used by your MultipartParser.
    # Ensure the path to the patched object is where it is *looked up*,
    # which is in the module where it's imported and used.
    mocked_parse_options = mocker.patch("serv.multipart_parser.parse_options_header")
    mocked_parse_options.side_effect = ValueError("Simulated parsing error")

    with pytest.raises(ValueError, match="Simulated parsing error"):
        await default_parser.parse(receive)


@pytest.mark.asyncio
async def test_non_latin1_chars_in_header_value_disposition_filename(
    default_parser: MultipartParser,
):
    non_latin1_filename_value = "файл.txt"

    header_value_with_unicode_filename = (
        f'form-data; name="upload"; filename="{non_latin1_filename_value}"'
    )

    default_parser._current_part_headers = {
        "content-disposition": header_value_with_unicode_filename
    }
    default_parser._current_part_name = None
    default_parser._current_part_filename = None
    default_parser._is_file_part = False
    default_parser.charset = "utf-8"

    with pytest.raises(
        UnicodeEncodeError, match="'latin-1' codec can't encode character"
    ):
        default_parser._on_headers_finished()


@pytest.mark.asyncio
async def test_chunked_body_processing(default_parser: MultipartParser):
    boundary = "testboundary"
    file_content = b"this is a test file that will be sent in multiple chunks for sure"
    parts = [
        create_form_data_part("field1_chunked", "value1_chunked_long_enough", boundary),
        create_file_data_part(
            "file1_chunked",
            "chunked_test_long.txt",
            file_content,
            "text/plain",
            boundary,
        ),
    ]
    body = create_multipart_body(parts, boundary)

    chunk_size = 15
    body_chunks = [body[i : i + chunk_size] for i in range(0, len(body), chunk_size)]
    if not body_chunks and body:
        body_chunks = [body]
    elif not body_chunks and not body:
        body_chunks = [b""]

    receive = await mock_receive_callable(body_chunks)

    result = await default_parser.parse(receive)

    assert "field1_chunked" in result
    assert result["field1_chunked"] == ["value1_chunked_long_enough"]
    assert "file1_chunked" in result
    assert len(result["file1_chunked"]) == 1
    file_upload: ParsedFileUpload = result["file1_chunked"][0]
    assert file_upload["filename"] == "chunked_test_long.txt"
    assert file_upload["file"].read() == file_content
    field_list = default_parser.fields.get("file1_chunked")
    assert field_list is None or not any(
        isinstance(item, str) and item.startswith("this is a test file")
        for item in field_list
    )
