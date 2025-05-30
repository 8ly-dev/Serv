# File Upload Service Demo (MVP)

A simple file upload service built with Serv showcasing multipart file handling, local storage, and basic file management.

## Features

- File upload with drag-and-drop interface
- Local file storage
- File listing and preview
- Basic file validation
- Upload progress display
- Simple file metadata

## MVP TODO List

### Core File Handling
- [ ] Create file upload route handler
- [ ] Implement multipart file parsing in Serv
- [ ] Set up local file storage directory
- [ ] Add basic file validation (size, type)
- [ ] Generate unique filenames to prevent conflicts

### Upload Interface
- [ ] Create HTML page with file upload form
- [ ] Add drag-and-drop file upload area
- [ ] Implement JavaScript for file selection
- [ ] Add upload progress bar
- [ ] Show upload status and results

### File Management
- [ ] Create file listing endpoint
- [ ] Add file download/serving endpoint
- [ ] Implement file deletion
- [ ] Store basic file metadata (name, size, upload date)
- [ ] Create file preview for images

### API Endpoints
- [ ] POST /api/upload - Upload single file
- [ ] GET /api/files - List uploaded files
- [ ] GET /api/files/{id} - Download/serve file
- [ ] DELETE /api/files/{id} - Delete file
- [ ] GET /api/files/{id}/info - Get file metadata

### Frontend Features
- [ ] File upload form with progress
- [ ] File list with thumbnails for images
- [ ] File download links
- [ ] File deletion buttons
- [ ] Basic file type icons

### Extensions Integration
- [ ] Create FileUploadExtension
- [ ] Add file serving middleware
- [ ] Create upload validation middleware

## Running the Demo

```bash
cd demos/file_upload_service
pip install -r requirements.txt  # Only Pillow for image thumbnails
serv launch
```

Visit http://localhost:8000 to start uploading files!

## File Structure

```
demos/file_upload_service/
├── README.md
├── requirements.txt              # Pillow for image processing
├── serv.config.yaml             # Basic config
├── uploads/                     # Local file storage (created at runtime)
├── extensions/
│   └── file_upload_extension.py # Upload routes and logic
├── templates/
│   └── upload.html             # File upload interface
└── static/
    ├── upload.js               # Upload handling JavaScript
    └── style.css               # Basic styling
```

## MVP Scope

- **Local file storage only** (uploads/ directory)
- **Basic file types** (images, documents, text files)
- **Simple validation** (file size limits, allowed extensions)
- **In-memory metadata** (no database for file info)
- **Single upload per request** (no batch uploads)

## Upload Flow

1. User selects or drags files to upload area
2. JavaScript validates file before upload
3. File is uploaded via POST request
4. Server saves file with unique name
5. File appears in the file list
6. User can download or delete files

## File Validation

- Maximum file size: 10MB
- Allowed types: images (jpg, png, gif), documents (pdf, txt, md)
- Filename sanitization to prevent path traversal

## Demo Features

- **Drag & Drop**: Modern file upload interface
- **Progress Bar**: Visual upload feedback
- **File Preview**: Thumbnail generation for images
- **File Management**: List, download, and delete files
- **Responsive Design**: Works on desktop and mobile

This MVP demonstrates Serv's file handling capabilities with a practical upload service! 