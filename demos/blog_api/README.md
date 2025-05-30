# Blog API Demo (MVP)

A simple RESTful blog API built with Serv showcasing CRUD operations, JSON responses, and API design patterns.

## Features

- Full CRUD operations for blog posts
- JSON API responses
- In-memory data storage
- Request validation
- Pagination support
- Simple search functionality

## MVP TODO List

### Core API Structure
- [ ] Create blog post model (Python dataclass or dict)
- [ ] Set up in-memory storage (simple list/dict)
- [ ] Create BlogExtension for route registration
- [ ] Add sample data generation for demo

### CRUD Endpoints
- [ ] GET /api/posts - List all posts (with pagination)
- [ ] GET /api/posts/{id} - Get single post
- [ ] POST /api/posts - Create new post
- [ ] PUT /api/posts/{id} - Update existing post
- [ ] DELETE /api/posts/{id} - Delete post

### Request/Response Handling
- [ ] Create Post data model with validation
- [ ] Add JSON request parsing for POST/PUT
- [ ] Implement proper HTTP status codes
- [ ] Add error responses for not found, validation errors
- [ ] Create consistent API response format

### Features
- [ ] Add pagination query parameters (page, limit)
- [ ] Implement simple search by title/content
- [ ] Add post metadata (created_at, updated_at)
- [ ] Support for post drafts vs published
- [ ] Basic input validation and sanitization

### API Documentation Page
- [ ] Create simple HTML page documenting the API
- [ ] Add example requests and responses
- [ ] Include interactive forms to test endpoints
- [ ] Show current posts in a web interface

### Extensions Integration
- [ ] Create BlogApiExtension
- [ ] Add JSON response middleware
- [ ] Create request validation middleware
- [ ] Add CORS headers for browser testing

## Running the Demo

```bash
cd demos/blog_api
pip install -r requirements.txt  # No extra dependencies needed
serv launch
```

Visit:
- http://localhost:8000/api/posts (API endpoint)
- http://localhost:8000 (API documentation and testing interface)

## File Structure

```
demos/blog_api/
├── README.md
├── requirements.txt              # No extra deps needed
├── serv.config.yaml             # Basic config
├── extensions/
│   └── blog_api_extension.py    # API routes and logic
├── models/
│   └── post.py                  # Post data model
├── templates/
│   └── api_docs.html           # API documentation page
└── static/
    ├── api_test.js             # JavaScript for testing API
    └── style.css               # Basic styling
```

## MVP Scope

- **In-memory storage only** (no database)
- **No authentication** (public API)
- **Simple validation** (required fields only)
- **Basic features** (CRUD + search + pagination)
- **No external dependencies** (just Serv + standard library)

## API Examples

### Create a Post
```bash
curl -X POST http://localhost:8000/api/posts \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Post",
    "content": "This is the content of my first post.",
    "author": "John Doe"
  }'
```

### Get All Posts
```bash
curl http://localhost:8000/api/posts?page=1&limit=10
```

### Search Posts
```bash
curl "http://localhost:8000/api/posts?search=first"
```

## Sample Data

The demo will include 10 sample blog posts to showcase the API functionality immediately upon startup.

This MVP demonstrates Serv's API capabilities with a clean, simple REST interface! 