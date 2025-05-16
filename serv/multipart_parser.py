import io
from collections import defaultdict
from typing import Dict, List, Any, Optional, TypedDict, Union, Callable, Awaitable

# Using PBaseParser to avoid name clash with our MultipartParser
from multipart.multipart import MultipartParser as PBaseParser
from multipart.multipart import parse_options_header


class ParsedFileUpload(TypedDict):
    filename: Optional[str]
    content_type: Optional[str]
    file: io.BytesIO
    headers: Dict[str, str]



class MultipartParser:
    """
    An asynchronous streaming multipart/form-data parser using python_multipart.multipart.MultipartParser.

    This parser processes a multipart body stream obtained via an ASGI receive callable
    and returns a dictionary of fields and files. ParsedFileUpload instances capture
    individual file details, including their content_type and all headers associated with their part.
    """
    def __init__(self, boundary: bytes, charset: str = 'utf-8'):
        if not boundary:
            raise ValueError("Boundary is required for MultipartParser")
        self.boundary = boundary
        self.charset = charset

        self._callbacks = {
            'on_part_begin': self._on_part_begin,
            'on_part_data': self._on_part_data,
            'on_part_end': self._on_part_end,
            'on_header_begin': self._on_header_begin,
            'on_header_field': self._on_header_field,
            'on_header_value': self._on_header_value,
            'on_header_end': self._on_header_end,
            'on_headers_finished': self._on_headers_finished,
            'on_end': self._on_end,
        }
        # The low_level_parser is re-initialized in each parse call
        # to ensure it's fresh, as it's stateful.
        self._low_level_parser: Optional[PBaseParser] = None

        # --- Results storage ---
        self.fields: Dict[str, List[str]] = defaultdict(list)
        self.files: Dict[str, List[ParsedFileUpload]] = defaultdict(list) # Use ParsedFileUpload

        # --- Current part processing state ---
        self._current_part_headers: Dict[str, str] = {}
        self._current_part_name: Optional[str] = None
        self._current_part_filename: Optional[str] = None
        self._current_part_content_type: Optional[str] = None
        self._current_part_data_buffer: Optional[io.BytesIO] = None
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
        self._is_file_part = False

    def _reset_current_header_state(self):
        """Resets the state for processing a new header within a part."""
        self._current_header_name_buffer.clear()
        self._current_header_value_buffer.clear()

    # --- Callbacks for PBaseParser ---
    def _on_part_begin(self):
        self._reset_current_part_state()
        self._current_part_data_buffer = io.BytesIO()

    def _on_header_begin(self):
        self._reset_current_header_state()

    def _on_header_field(self, data: bytes, start: int, end: int):
        self._current_header_name_buffer.extend(data[start:end])

    def _on_header_value(self, data: bytes, start: int, end: int):
        self._current_header_value_buffer.extend(data[start:end])

    def _on_header_end(self):
        name = self._current_header_name_buffer.decode('ascii', errors='ignore').strip().lower()
        value = self._current_header_value_buffer.decode(self.charset, errors='replace').strip()
        if name: # Only store if header name is valid
            self._current_part_headers[name] = value
        self._reset_current_header_state()

    def _on_headers_finished(self):
        disposition_header_value = self._current_part_headers.get('content-disposition')
        if disposition_header_value:
            try:
                disposition_bytes = disposition_header_value.encode('latin-1') # Headers are latin-1
                _main_value_bytes, params_bytes_dict = parse_options_header(disposition_bytes)
                
                name_bytes = params_bytes_dict.get(b'name')
                if name_bytes:
                    self._current_part_name = name_bytes.decode(self.charset, errors='replace')

                filename_bytes = params_bytes_dict.get(b'filename')
                if filename_bytes:
                    self._current_part_filename = filename_bytes.decode(self.charset, errors='replace')
                    self._is_file_part = True
            except Exception:
                # Potentially log this: print(f"Warning: Could not parse Content-Disposition: {disposition_header_value}")
                pass

        self._current_part_content_type = self._current_part_headers.get('content-type')

    def _on_part_data(self, data: bytes, start: int, end: int):
        if self._current_part_data_buffer:
            self._current_part_data_buffer.write(data[start:end])

    def _on_part_end(self):
        if self._current_part_data_buffer and self._current_part_name:
            self._current_part_data_buffer.seek(0)
            if self._is_file_part:
                file_upload = ParsedFileUpload(
                    filename=self._current_part_filename,
                    content_type=self._current_part_content_type,
                    file=self._current_part_data_buffer,
                    headers=self._current_part_headers.copy()
                )
                self.files[self._current_part_name].append(file_upload)
            else: # Regular form field
                field_value = self._current_part_data_buffer.read().decode(self.charset, errors='replace')
                self.fields[self._current_part_name].append(field_value)
        # The buffer is now associated with a ParsedFileUpload or its content read.
        # A new buffer will be created for the next part in _on_part_begin.

    def _on_end(self):
        """Called when all parts of the multipart message have been processed."""
        pass

    async def parse(self, receive: Callable[[], Awaitable[Dict[str, Any]]]) -> Dict[str, List[Union[str, ParsedFileUpload]]]:
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
                self._low_level_parser.write(body_chunk)
            
            more_body = message.get("more_body", False)
        
        self._low_level_parser.finalize()

        result: Dict[str, List[Any]] = defaultdict(list)
        for name, values_list in self.fields.items():
            result[name].extend(values_list)
        for name, file_uploads_list in self.files.items():
            result[name].extend(file_uploads_list)
            
        return dict(result) 