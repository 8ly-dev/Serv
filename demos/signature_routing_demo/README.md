# Signature-Based Routing Demo

This demo showcases Serv's powerful signature-based routing system, where multiple handler methods can exist for the same HTTP method and are automatically selected based on the request parameters.

This demo uses the modern `serv launch` command with autoloaded extensions, demonstrating the recommended approach for Serv applications.

## Features Demonstrated

1. **Multiple GET Handlers**: Different handlers based on query parameters
2. **Parameter Injection**: Direct injection of query params, headers, and cookies
3. **Form Handling**: Automatic form matching and processing
4. **Handler Scoring**: Most specific handler wins based on available request data
5. **Extension Architecture**: Using `serv launch` with autoloaded extensions

## Routes

### `/api/search` - Search API with Multiple Handlers

- `GET /api/search` - Default search results
- `GET /api/search?q=term` - Search with query
- `GET /api/search?q=term&page=2` - Paginated search
- `GET /api/search?q=term&page=2&category=tech` - Advanced search with category

### `/api/users` - User API with Authentication

- `GET /api/users` - List all users (no auth required)
- `GET /api/users` with `Authorization` header - List users with private data
- `POST /api/users` with `Authorization` header - Create new user
- `PUT /api/users?id=123` with session cookie - Update user

### `/contact` - Contact Form

- `GET /contact` - Show contact form
- `POST /contact` - Process contact form submission

## Running the Demo

There are two ways to run this demo:

### Option 1: Using the main.py script
```bash
cd demos/signature_routing_demo
python main.py
```

### Option 2: Using serv launch directly
```bash
cd demos/signature_routing_demo
serv launch
```

Both methods use the `serv.config.yaml` configuration file and automatically load extensions from the `./extensions/` directory.

Then visit:
- http://127.0.0.1:8000/api/search
- http://127.0.0.1:8000/api/search?q=python
- http://127.0.0.1:8000/api/users
- http://127.0.0.1:8000/contact

## Example Requests

### Search Examples

```bash
# Basic search
curl http://127.0.0.1:8000/api/search

# Search with query
curl "http://127.0.0.1:8000/api/search?q=python"

# Paginated search
curl "http://127.0.0.1:8000/api/search?q=python&page=2&limit=5"

# Advanced search
curl "http://127.0.0.1:8000/api/search?q=python&page=2&category=programming"
```

### User API Examples

```bash
# List users (public)
curl http://127.0.0.1:8000/api/users

# List users with auth (private data)
curl -H "Authorization: Bearer valid-token" http://127.0.0.1:8000/api/users

# Create user
curl -X POST -H "Authorization: Bearer valid-token" \
  -H "Content-Type: application/json" \
  -d '{"username": "john", "email": "john@example.com"}' \
  http://127.0.0.1:8000/api/users

# Update user with session
curl -X PUT \
  -H "Content-Type: application/json" \
  -H "Cookie: session_id=valid-session" \
  -d '{"username": "john_updated"}' \
  "http://127.0.0.1:8000/api/users?id=123"
```

### Contact Form

```bash
# Get form
curl http://127.0.0.1:8000/contact

# Submit form
curl -X POST \
  -d "name=John Doe&email=john@example.com&message=Hello World" \
  http://127.0.0.1:8000/contact
```