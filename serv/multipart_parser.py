import io
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

# Using PBaseParser to avoid name clash with our MultipartParser
from python_multipart.multipart import MultipartParser as PBaseParser
from python_multipart.multipart import parse_options_header
from werkzeug.utils import secure_filename


class MultipartParserError(ValueError):
    """Custom exception for multipart parsing errors."""

    pass


DEFAULT_MULTIPART_CONFIG = {
    "max_header_name_size": 1024,  # 1KB
    "max_header_value_size": 8192,  # 8KB
    "max_headers_per_part": 64,
    "max_file_size": 10 * 1024 * 1024,  # 10MB
    "max_num_files": 10,
    "max_total_body_size": 50 * 1024 * 1024,  # 50MB
}


class ParsedFileUpload(TypedDict):
    filename: str | None
    content_type: str | None
    file: io.BytesIO
    headers: dict[str, str]


class MultipartParser:
    """
    An asynchronous streaming multipart/form-data parser using python_multipart.multipart.MultipartParser.

    This parser processes a multipart body stream obtained via an ASGI receive callable
    and returns a dictionary of fields and files. ParsedFileUpload instances capture
    individual file details, including their content_type and all headers associated with their part.
    """

    def __init__(
        self,
        boundary: bytes,
        charset: str = "utf-8",
        config: dict[str, int] | None = None,
    ):
        if not boundary:
            raise ValueError("Boundary is required for MultipartParser")
        self.boundary = boundary
        self.charset = charset

        current_config = DEFAULT_MULTIPART_CONFIG.copy()
        if config:
            current_config.update(config)

        self._max_header_name_size = current_config["max_header_name_size"]
        self._max_header_value_size = current_config["max_header_value_size"]
        self._max_headers_per_part = current_config["max_headers_per_part"]
        self._max_file_size = current_config["max_file_size"]
        self._max_num_files = current_config["max_num_files"]
        self._max_total_body_size = current_config["max_total_body_size"]

        self._callbacks = {
            "on_part_begin": self._on_part_begin,
            "on_part_data": self._on_part_data,
            "on_part_end": self._on_part_end,
            "on_header_begin": self._on_header_begin,
            "on_header_field": self._on_header_field,
            "on_header_value": self._on_header_value,
            "on_header_end": self._on_header_end,
            "on_headers_finished": self._on_headers_finished,
            "on_end": self._on_end,
        }
        # The low_level_parser is re-initialized in each parse call
        # to ensure it's fresh, as it's stateful.
        self._low_level_parser: PBaseParser | None = None

        # --- Results storage ---
        self.fields: dict[str, list[str]] = defaultdict(list)
        self.files: dict[str, list[ParsedFileUpload]] = defaultdict(
            list
        )  # Use ParsedFileUpload

        # --- Current part processing state ---
        self._current_part_headers: dict[str, str] = {}
        self._current_part_name: str | None = None
        self._current_part_filename: str | None = None
        self._current_part_content_type: str | None = None
        self._current_part_data_buffer: io.BytesIO | None = None
        self._current_headers_count_in_part: int = 0  # For max_headers_per_part
        self._is_file_part: bool = False

        # --- Current header processing state ---
        self._current_header_name_buffer: bytearray = bytearray()
        self._current_header_value_buffer: bytearray = bytearray()

    def _reset_current_part_state(self):
        """Resets the state for processing a new multipart part."""
        self._current_part_headers.clear()
        self._current_part_name = None
        self._current_part_filename = None
        self._current_part_content_type = None
        self._current_part_data_buffer = None
        self._current_headers_count_in_part = 0
        self._is_file_part = False

    def _reset_current_header_state(self):
        """Resets the state for processing a new header within a part."""
        self._current_header_name_buffer.clear()
        self._current_header_value_buffer.clear()

    # --- Callbacks for PBaseParser ---
    def _on_part_begin(self):
        self._reset_current_part_state()
        self._current_part_data_buffer = io.BytesIO()
        self._current_headers_count_in_part = 0  # Reset for new part

    def _on_header_begin(self):
        self._reset_current_header_state()

    def _on_header_field(self, data: bytes, start: int, end: int):
        if (
            len(self._current_header_name_buffer) + (end - start)
            > self._max_header_name_size
        ):
            raise MultipartParserError(
                f"Header name exceeds maximum size of {self._max_header_name_size} bytes."
            )
        self._current_header_name_buffer.extend(data[start:end])

    def _on_header_value(self, data: bytes, start: int, end: int):
        if (
            len(self._current_header_value_buffer) + (end - start)
            > self._max_header_value_size
        ):
            raise MultipartParserError(
                f"Header value exceeds maximum size of {self._max_header_value_size} bytes."
            )
        self._current_header_value_buffer.extend(data[start:end])

    def _on_header_end(self):
        self._current_headers_count_in_part += 1
        if self._current_headers_count_in_part > self._max_headers_per_part:
            raise MultipartParserError(
                f"Number of headers in part exceeds maximum of {self._max_headers_per_part}."
            )

        name = (
            self._current_header_name_buffer.decode("ascii", errors="ignore")
            .strip()
            .lower()
        )
        value = self._current_header_value_buffer.decode(
            self.charset, errors="replace"
        ).strip()
        if name:  # Only store if header name is valid
            self._current_part_headers[name] = value
        self._reset_current_header_state()

    def _on_headers_finished(self):
        disposition_header_value = self._current_part_headers.get("content-disposition")
        if disposition_header_value:
            # Let errors propagate, no try-except here
            disposition_bytes = disposition_header_value.encode(
                "latin-1"
            )  # Headers are latin-1
            _main_value_bytes, params_bytes_dict = parse_options_header(
                disposition_bytes
            )

            name_bytes = params_bytes_dict.get(b"name")
            if name_bytes:
                self._current_part_name = name_bytes.decode(
                    self.charset, errors="replace"
                )

            filename_bytes = params_bytes_dict.get(b"filename")
            if filename_bytes:
                original_filename = filename_bytes.decode(
                    self.charset, errors="replace"
                )
                secured_filename = secure_filename(original_filename)
                if (
                    not secured_filename and original_filename
                ):  # Filename became empty after securing
                    raise MultipartParserError(
                        f"Unsafe filename provided: '{original_filename}'"
                    )
                if (
                    secured_filename
                ):  # Only set if filename is valid and not empty after securing
                    self._current_part_filename = secured_filename
                    self._is_file_part = True
                # If original_filename was empty or only unsafe chars, secured_filename will be empty.
                # In this case, it's not treated as a file part unless _is_file_part was somehow true before.
                # This logic ensures empty or unsafe filenames don't lead to file processing.
                else:
                    self._is_file_part = False  # Explicitly mark as not a file if filename is invalid/empty

        self._current_part_content_type = self._current_part_headers.get("content-type")

    def _on_part_data(self, data: bytes, start: int, end: int):
        if self._current_part_data_buffer:
            chunk_size = end - start
            if self._is_file_part:
                if (
                    self._current_part_data_buffer.tell() + chunk_size
                    > self._max_file_size
                ):
                    raise MultipartParserError(
                        f"File '{self._current_part_filename or 'unknown'}' "
                        f"exceeds maximum size of {self._max_file_size} bytes."
                    )
            # Note: We don't have a separate max_field_size, but max_total_body_size
            # and other limits (header size, part count) will indirectly limit field data.
            # If a very large non-file part is a concern, a specific max_field_data_size
            # check could be added here or in _on_part_end.
            self._current_part_data_buffer.write(data[start:end])

    def _on_part_end(self):
        if self._current_part_data_buffer and self._current_part_name:
            self._current_part_data_buffer.seek(0)
            if self._is_file_part:
                if self._total_files_count >= self._max_num_files:
                    raise MultipartParserError(
                        f"Maximum number of files ({self._max_num_files}) exceeded."
                    )

                self._total_files_count += 1
                file_upload = ParsedFileUpload(
                    filename=self._current_part_filename,
                    content_type=self._current_part_content_type,
                    file=self._current_part_data_buffer,
                    headers=self._current_part_headers.copy(),
                )
                self.files[self._current_part_name].append(file_upload)
            else:  # Regular form field
                field_value = self._current_part_data_buffer.read().decode(
                    self.charset, errors="replace"
                )
                self.fields[self._current_part_name].append(field_value)
        # The buffer is now associated with a ParsedFileUpload or its content read.
        # A new buffer will be created for the next part in _on_part_begin.

    def _on_end(self):
        """Called when all parts of the multipart message have been processed."""
        pass

    async def parse(
        self, receive: Callable[[], Awaitable[dict[str, Any]]]
    ) -> dict[str, list[str | ParsedFileUpload]]:
        """
        Asynchronously parses multipart/form-data from an ASGI receive callable.

        Args:
            receive: An ASGI receive callable.

        Returns:
            A dictionary where keys are field names and values are lists of
            strings (for regular fields) or ParsedFileUpload instances (for files).
        """
        self.fields.clear()
        self.files.clear()

        # Initialize the low-level parser for this parse operation
        self._low_level_parser = PBaseParser(self.boundary, self._callbacks)
        self._total_body_bytes_received = 0
        self._total_files_count = 0  # Reset for this parse call

        more_body = True
        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                # This shouldn't happen if called correctly within an ASGI request cycle
                # for the body, but handle defensively.
                # Could raise an error or log. For now, break.
                break

            body_chunk = message.get("body", b"")
            if body_chunk:
                self._total_body_bytes_received += len(body_chunk)
                if self._total_body_bytes_received > self._max_total_body_size:
                    raise MultipartParserError(
                        f"Total request body size exceeds maximum of {self._max_total_body_size} bytes."
                    )
                self._low_level_parser.write(body_chunk)

            more_body = message.get("more_body", False)

        self._low_level_parser.finalize()

        result: dict[str, list[Any]] = defaultdict(list)
        for name, values_list in self.fields.items():
            result[name].extend(values_list)
        for name, file_uploads_list in self.files.items():
            result[name].extend(file_uploads_list)

        return dict(result)
