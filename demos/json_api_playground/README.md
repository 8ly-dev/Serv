# JSON API Playground Demo (MVP)

An interactive JSON API playground built with Serv showcasing API exploration, request building, and response formatting.

## Features

- Interactive API testing interface
- Multiple sample APIs to explore
- Request builder with parameters
- Response formatting and syntax highlighting
- API documentation generator
- Request history and favorites

## MVP TODO List

### Sample APIs
- [ ] Users API (CRUD operations)
- [ ] Products API (with search and filtering)
- [ ] Orders API (with relationships)
- [ ] Analytics API (with aggregations)
- [ ] Mock external API integration

### API Playground Interface
- [ ] API endpoint selector/browser
- [ ] Request method selector (GET, POST, PUT, DELETE)
- [ ] Parameter input forms (query, body, headers)
- [ ] Request builder interface
- [ ] Response display with formatting

### Response Features
- [ ] JSON syntax highlighting
- [ ] Response status code display
- [ ] Response headers viewer
- [ ] Response time measurement
- [ ] Copy response to clipboard
- [ ] Download response as file

### Interactive Features
- [ ] Save requests as favorites
- [ ] Request history tracking
- [ ] Share request links
- [ ] Export requests as curl commands
- [ ] Import/export request collections

### Documentation
- [ ] Auto-generated API documentation
- [ ] Interactive examples for each endpoint
- [ ] Schema documentation for request/response
- [ ] Code examples in multiple formats
- [ ] API usage analytics

### Extensions Integration
- [ ] Create APIPlaygroundExtension
- [ ] Add response formatting middleware
- [ ] Create request logging extension
- [ ] Add CORS middleware for browser testing

## Running the Demo

```bash
cd demos/json_api_playground
pip install -r requirements.txt  # Pygments for syntax highlighting
serv launch
```

Visit http://localhost:8000 to explore the API playground!

## File Structure

```
demos/json_api_playground/
├── README.md
├── requirements.txt              # Pygments for syntax highlighting
├── serv.config.yaml             # Basic config
├── extensions/
│   ├── api_playground_extension.py  # Playground interface
│   ├── users_api_extension.py       # Sample Users API
│   ├── products_api_extension.py    # Sample Products API
│   └── orders_api_extension.py      # Sample Orders API
├── templates/
│   ├── playground.html             # Main playground interface
│   └── api_docs.html              # Generated documentation
└── static/
    ├── playground.js              # Interactive API client
    ├── syntax-highlight.js        # JSON highlighting
    └── style.css                  # Playground styling
```

## MVP Scope

- **Multiple sample APIs** (users, products, orders)
- **In-memory data** (no database required)
- **Interactive interface** (no external API tools)
- **Built-in highlighting** (simple JSON formatting)
- **Local storage** (for favorites and history)

## Sample APIs

### Users API
- `GET /api/users` - List users with pagination
- `GET /api/users/{id}` - Get user by ID
- `POST /api/users` - Create new user
- `PUT /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Delete user

### Products API
- `GET /api/products` - List products (with search, filters)
- `GET /api/products/{id}` - Get product details
- `GET /api/products/categories` - List categories
- `POST /api/products` - Create product
- `PUT /api/products/{id}` - Update product

### Orders API
- `GET /api/orders` - List orders
- `GET /api/orders/{id}` - Get order with items
- `POST /api/orders` - Create new order
- `PUT /api/orders/{id}/status` - Update order status

## Playground Features

### Request Builder
- Dropdown for API selection
- Method selector (GET, POST, PUT, DELETE)
- URL parameter inputs
- JSON body editor
- Headers editor
- Query parameter builder

### Response Viewer
- Formatted JSON with syntax highlighting
- Response status and timing
- Headers display
- Error message formatting
- Response size information

### Interactive Tools
- "Try it" buttons for each API endpoint
- Request/response examples
- Parameter descriptions and validation
- Auto-completion for known values
- Request templates and snippets

## Demo Data

Each API includes realistic sample data:
- **Users**: 50 sample users with profiles
- **Products**: 100 products across various categories
- **Orders**: Order history with relationships to users and products

This MVP demonstrates Serv's API capabilities with an interactive exploration tool! 