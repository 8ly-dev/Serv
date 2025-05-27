# Templates

Templates allow you to generate dynamic HTML content by combining static markup with dynamic data. While Serv doesn't include a built-in template engine, it provides excellent integration with popular Python template engines like Jinja2, Mako, and others. This guide covers everything you need to know about using templates in Serv applications.

## Overview

Template features in Serv:

1. **Template Engine Integration**: Support for popular template engines
2. **Context Management**: Pass data to templates efficiently
3. **Template Inheritance**: Build reusable template hierarchies
4. **Custom Filters**: Extend template functionality
5. **Async Support**: Asynchronous template rendering

## Template Engine Setup

### Jinja2 Integration

Jinja2 is the most popular template engine for Python web applications:

```bash
pip install jinja2
```

**extensions/templates/template_engine.py:**
```python
import os
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
from bevy import dependency

class TemplateEngine:
    """Jinja2 template engine wrapper"""
    
    def __init__(self, template_dir: str = "templates"):
        self.template_dir = Path(template_dir)
        self.template_dir.mkdir(exist_ok=True)
        
        # Configure Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            enable_async=True,  # Enable async support
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['currency'] = self.currency_filter
        self.env.filters['datetime'] = self.datetime_filter
        self.env.filters['truncate_words'] = self.truncate_words_filter
    
    async def render(self, template_name: str, context: Dict[str, Any] = None) -> str:
        """Render template with context"""
        template = self.env.get_template(template_name)
        return await template.render_async(context or {})
    
    def render_string(self, template_string: str, context: Dict[str, Any] = None) -> str:
        """Render template from string"""
        template = self.env.from_string(template_string)
        return template.render(context or {})
    
    # Custom filters
    def currency_filter(self, value: float, currency: str = "USD") -> str:
        """Format currency"""
        symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
        symbol = symbols.get(currency, currency)
        return f"{symbol}{value:,.2f}"
    
    def datetime_filter(self, value, format: str = "%Y-%m-%d %H:%M") -> str:
        """Format datetime"""
        if hasattr(value, 'strftime'):
            return value.strftime(format)
        return str(value)
    
    def truncate_words_filter(self, value: str, length: int = 50) -> str:
        """Truncate text to specified word count"""
        words = str(value).split()
        if len(words) <= length:
            return value
        return ' '.join(words[:length]) + '...'

# Register as dependency
def create_template_engine() -> TemplateEngine:
    return TemplateEngine()
```

**extensions/templates/extension.py:**
```python
from bevy import dependency
from serv.extensions import Extension
from .template_engine import TemplateEngine, create_template_engine

class TemplatesExtension(Extension):
    """Extension for template engine integration"""
    
    async def on_startup(self):
        """Register template engine as dependency"""
        # Register the template engine
        dependency.register(TemplateEngine, create_template_engine)
```

**extensions/templates/extension.yaml:**
```yaml
name: Templates Extension
version: 1.0.0
description: Template engine integration for Serv
dependencies: []
```

### Using Templates in Routes

```python
from serv.routes import Route, GetRequest
from typing import Annotated
from serv.responses import HtmlResponse
from bevy import dependency
from extensions.templates.template_engine import TemplateEngine

class HomeRoute(Route):
    async def handle_get(
        self, 
        request: GetRequest,
        template_engine: TemplateEngine = dependency()
    ) -> Annotated[str, HtmlResponse]:
        """Render home page template"""
        
        context = {
            "title": "Welcome to Serv",
            "user": {
                "name": "John Doe",
                "email": "john@example.com"
            },
            "products": [
                {"id": 1, "name": "Product 1", "price": 29.99},
                {"id": 2, "name": "Product 2", "price": 49.99},
                {"id": 3, "name": "Product 3", "price": 19.99}
            ],
            "current_year": 2024
        }
        
        return await template_engine.render("home.html", context)
```

## Template Structure

### Base Template

Create a base template for consistent layout:

**templates/base.html:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}{{ title | default('Serv Application') }}{% endblock %}</title>
    
    <!-- CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    {% block extra_css %}{% endblock %}
    
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .navbar-brand {
            font-weight: bold;
        }
        .footer {
            background-color: #f8f9fa;
            padding: 2rem 0;
            margin-top: 3rem;
        }
        {% block extra_styles %}{% endblock %}
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">
                {% block brand %}Serv App{% endblock %}
            </a>
            
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    {% block nav_items %}
                    <li class="nav-item">
                        <a class="nav-link" href="/">Home</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/products">Products</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/about">About</a>
                    </li>
                    {% endblock %}
                </ul>
                
                <ul class="navbar-nav">
                    {% if user %}
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="userDropdown" role="button" data-bs-toggle="dropdown">
                            {{ user.name }}
                        </a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="/profile">Profile</a></li>
                            <li><a class="dropdown-item" href="/settings">Settings</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item" href="/logout">Logout</a></li>
                        </ul>
                    </li>
                    {% else %}
                    <li class="nav-item">
                        <a class="nav-link" href="/login">Login</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/register">Register</a>
                    </li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <!-- Flash Messages -->
    {% if messages %}
    <div class="container mt-3">
        {% for message in messages %}
        <div class="alert alert-{{ message.type }} alert-dismissible fade show" role="alert">
            {{ message.text }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    <!-- Main Content -->
    <main class="container mt-4">
        {% block content %}
        <h1>Welcome to Serv</h1>
        <p>This is the default content.</p>
        {% endblock %}
    </main>

    <!-- Footer -->
    <footer class="footer mt-auto">
        <div class="container">
            <div class="row">
                <div class="col-md-6">
                    {% block footer_left %}
                    <p>&copy; {{ current_year }} Serv Application. All rights reserved.</p>
                    {% endblock %}
                </div>
                <div class="col-md-6 text-end">
                    {% block footer_right %}
                    <p>Built with <a href="https://getserv.ing">Serv</a></p>
                    {% endblock %}
                </div>
            </div>
        </div>
    </footer>

    <!-- JavaScript -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### Page Templates

Create specific page templates that extend the base:

**templates/home.html:**
```html
{% extends "base.html" %}

{% block title %}{{ title }} - Home{% endblock %}

{% block content %}
<div class="row">
    <div class="col-lg-8">
        <div class="jumbotron bg-light p-5 rounded">
            <h1 class="display-4">{{ title }}</h1>
            <p class="lead">Welcome to our amazing Serv application!</p>
            {% if user %}
            <p>Hello, {{ user.name }}! Great to see you again.</p>
            {% else %}
            <p>Please <a href="/login">login</a> or <a href="/register">register</a> to get started.</p>
            {% endif %}
        </div>

        <!-- Featured Products -->
        {% if products %}
        <h2 class="mt-5">Featured Products</h2>
        <div class="row">
            {% for product in products %}
            <div class="col-md-4 mb-4">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">{{ product.name }}</h5>
                        <p class="card-text">
                            <strong>{{ product.price | currency }}</strong>
                        </p>
                        <a href="/products/{{ product.id }}" class="btn btn-primary">View Details</a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}
    </div>

    <div class="col-lg-4">
        <div class="card">
            <div class="card-header">
                <h5>Quick Stats</h5>
            </div>
            <div class="card-body">
                <ul class="list-unstyled">
                    <li><strong>Products:</strong> {{ products | length }}</li>
                    <li><strong>Current Year:</strong> {{ current_year }}</li>
                    {% if user %}
                    <li><strong>User:</strong> {{ user.email }}</li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

**templates/products/list.html:**
```html
{% extends "base.html" %}

{% block title %}Products{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1>Products</h1>
    <a href="/products/new" class="btn btn-success">Add Product</a>
</div>

<!-- Search and Filter -->
<div class="row mb-4">
    <div class="col-md-6">
        <form method="get" action="/products">
            <div class="input-group">
                <input type="text" class="form-control" name="search" 
                       placeholder="Search products..." value="{{ search_query }}">
                <button class="btn btn-outline-secondary" type="submit">Search</button>
            </div>
        </form>
    </div>
    <div class="col-md-6">
        <form method="get" action="/products">
            <select name="category" class="form-select" onchange="this.form.submit()">
                <option value="">All Categories</option>
                {% for category in categories %}
                <option value="{{ category.id }}" 
                        {% if category.id == selected_category %}selected{% endif %}>
                    {{ category.name }}
                </option>
                {% endfor %}
            </select>
        </form>
    </div>
</div>

<!-- Products Grid -->
{% if products %}
<div class="row">
    {% for product in products %}
    <div class="col-lg-4 col-md-6 mb-4">
        <div class="card h-100">
            {% if product.image %}
            <img src="{{ product.image }}" class="card-img-top" alt="{{ product.name }}" style="height: 200px; object-fit: cover;">
            {% endif %}
            
            <div class="card-body d-flex flex-column">
                <h5 class="card-title">{{ product.name }}</h5>
                <p class="card-text">{{ product.description | truncate_words(20) }}</p>
                
                <div class="mt-auto">
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="h5 text-primary">{{ product.price | currency }}</span>
                        {% if product.in_stock %}
                        <span class="badge bg-success">In Stock</span>
                        {% else %}
                        <span class="badge bg-danger">Out of Stock</span>
                        {% endif %}
                    </div>
                    
                    <div class="mt-2">
                        <a href="/products/{{ product.id }}" class="btn btn-primary btn-sm">View</a>
                        <a href="/products/{{ product.id }}/edit" class="btn btn-outline-secondary btn-sm">Edit</a>
                    </div>
                </div>
            </div>
        </div>
    </div>
    {% endfor %}
</div>

<!-- Pagination -->
{% if pagination %}
<nav aria-label="Product pagination">
    <ul class="pagination justify-content-center">
        {% if pagination.has_prev %}
        <li class="page-item">
            <a class="page-link" href="?page={{ pagination.prev_num }}">Previous</a>
        </li>
        {% endif %}
        
        {% for page_num in pagination.iter_pages() %}
        {% if page_num %}
        <li class="page-item {% if page_num == pagination.page %}active{% endif %}">
            <a class="page-link" href="?page={{ page_num }}">{{ page_num }}</a>
        </li>
        {% else %}
        <li class="page-item disabled">
            <span class="page-link">...</span>
        </li>
        {% endif %}
        {% endfor %}
        
        {% if pagination.has_next %}
        <li class="page-item">
            <a class="page-link" href="?page={{ pagination.next_num }}">Next</a>
        </li>
        {% endif %}
    </ul>
</nav>
{% endif %}

{% else %}
<div class="text-center py-5">
    <h3>No products found</h3>
    <p class="text-muted">Try adjusting your search or filter criteria.</p>
    <a href="/products/new" class="btn btn-primary">Add First Product</a>
</div>
{% endif %}
{% endblock %}
```

## Form Templates

### Form Rendering

Create reusable form templates:

**templates/forms/base_form.html:**
```html
{% macro render_field(field, label=None, help_text=None, required=False) %}
<div class="mb-3">
    {% if label %}
    <label for="{{ field.name }}" class="form-label">
        {{ label }}
        {% if required %}<span class="text-danger">*</span>{% endif %}
    </label>
    {% endif %}
    
    {% if field.type == 'textarea' %}
    <textarea class="form-control {% if field.errors %}is-invalid{% endif %}" 
              id="{{ field.name }}" name="{{ field.name }}" 
              {% if required %}required{% endif %}
              {% if field.placeholder %}placeholder="{{ field.placeholder }}"{% endif %}
              rows="{{ field.rows | default(4) }}">{{ field.value | default('') }}</textarea>
    {% elif field.type == 'select' %}
    <select class="form-select {% if field.errors %}is-invalid{% endif %}" 
            id="{{ field.name }}" name="{{ field.name }}" 
            {% if required %}required{% endif %}>
        {% if field.placeholder %}
        <option value="">{{ field.placeholder }}</option>
        {% endif %}
        {% for option in field.options %}
        <option value="{{ option.value }}" 
                {% if option.value == field.value %}selected{% endif %}>
            {{ option.label }}
        </option>
        {% endfor %}
    </select>
    {% elif field.type == 'checkbox' %}
    <div class="form-check">
        <input class="form-check-input {% if field.errors %}is-invalid{% endif %}" 
               type="checkbox" id="{{ field.name }}" name="{{ field.name }}" 
               value="true" {% if field.value %}checked{% endif %}>
        <label class="form-check-label" for="{{ field.name }}">
            {{ label or field.label }}
        </label>
    </div>
    {% else %}
    <input type="{{ field.type | default('text') }}" 
           class="form-control {% if field.errors %}is-invalid{% endif %}" 
           id="{{ field.name }}" name="{{ field.name }}" 
           value="{{ field.value | default('') }}"
           {% if required %}required{% endif %}
           {% if field.placeholder %}placeholder="{{ field.placeholder }}"{% endif %}>
    {% endif %}
    
    {% if help_text %}
    <div class="form-text">{{ help_text }}</div>
    {% endif %}
    
    {% if field.errors %}
    <div class="invalid-feedback">
        {% for error in field.errors %}
        {{ error }}{% if not loop.last %}<br>{% endif %}
        {% endfor %}
    </div>
    {% endif %}
</div>
{% endmacro %}

{% macro render_form_errors(errors) %}
{% if errors %}
<div class="alert alert-danger">
    <h6>Please correct the following errors:</h6>
    <ul class="mb-0">
        {% for error in errors %}
        <li>{{ error }}</li>
        {% endfor %}
    </ul>
</div>
{% endif %}
{% endmacro %}
```

**templates/products/form.html:**
```html
{% extends "base.html" %}
{% from "forms/base_form.html" import render_field, render_form_errors %}

{% block title %}
{% if product.id %}Edit Product{% else %}New Product{% endif %}
{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-lg-8">
        <div class="card">
            <div class="card-header">
                <h4 class="mb-0">
                    {% if product.id %}
                    Edit Product: {{ product.name }}
                    {% else %}
                    Add New Product
                    {% endif %}
                </h4>
            </div>
            
            <div class="card-body">
                {{ render_form_errors(form_errors) }}
                
                <form method="post" enctype="multipart/form-data">
                    {{ render_field(form.name, "Product Name", required=True) }}
                    
                    {{ render_field(form.description, "Description", 
                                  help_text="Provide a detailed description of the product") }}
                    
                    <div class="row">
                        <div class="col-md-6">
                            {{ render_field(form.price, "Price", required=True) }}
                        </div>
                        <div class="col-md-6">
                            {{ render_field(form.category, "Category", required=True) }}
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6">
                            {{ render_field(form.stock_quantity, "Stock Quantity", required=True) }}
                        </div>
                        <div class="col-md-6">
                            {{ render_field(form.sku, "SKU", 
                                          help_text="Stock Keeping Unit (optional)") }}
                        </div>
                    </div>
                    
                    {{ render_field(form.image, "Product Image", 
                                  help_text="Upload an image for the product") }}
                    
                    {{ render_field(form.featured, "Featured Product") }}
                    
                    {{ render_field(form.active, "Active") }}
                    
                    <div class="d-flex justify-content-between">
                        <a href="/products" class="btn btn-secondary">Cancel</a>
                        <button type="submit" class="btn btn-primary">
                            {% if product.id %}Update Product{% else %}Create Product{% endif %}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

## Advanced Template Features

### Custom Template Tags

Create custom template functions:

```python
# In template_engine.py
class TemplateEngine:
    def __init__(self, template_dir: str = "templates"):
        # ... existing code ...
        
        # Add custom global functions
        self.env.globals['url_for'] = self.url_for
        self.env.globals['csrf_token'] = self.csrf_token
        self.env.globals['static'] = self.static_url
        self.env.globals['current_user'] = self.get_current_user
    
    def url_for(self, endpoint: str, **kwargs) -> str:
        """Generate URL for endpoint"""
        # Implement URL generation logic
        base_urls = {
            'home': '/',
            'products': '/products',
            'product_detail': '/products/{id}',
            'login': '/login',
            'logout': '/logout'
        }
        
        url = base_urls.get(endpoint, '/')
        
        # Replace path parameters
        for key, value in kwargs.items():
            url = url.replace(f'{{{key}}}', str(value))
        
        return url
    
    def csrf_token(self) -> str:
        """Generate CSRF token"""
        # Implement CSRF token generation
        import secrets
        return secrets.token_urlsafe(32)
    
    def static_url(self, filename: str) -> str:
        """Generate static file URL"""
        return f"/static/{filename}"
    
    def get_current_user(self):
        """Get current user from context"""
        # This would typically come from request context
        return None
```

### Template Caching

Implement template caching for better performance:

```python
import asyncio
from functools import lru_cache
from typing import Dict, Any, Optional

class CachedTemplateEngine(TemplateEngine):
    """Template engine with caching support"""
    
    def __init__(self, template_dir: str = "templates", cache_size: int = 128):
        super().__init__(template_dir)
        self.cache_size = cache_size
        self._cache: Dict[str, str] = {}
        self._cache_enabled = True
    
    async def render(self, template_name: str, context: Dict[str, Any] = None) -> str:
        """Render template with caching"""
        context = context or {}
        
        # Create cache key
        cache_key = self._create_cache_key(template_name, context)
        
        # Check cache
        if self._cache_enabled and cache_key in self._cache:
            return self._cache[cache_key]
        
        # Render template
        result = await super().render(template_name, context)
        
        # Store in cache
        if self._cache_enabled:
            if len(self._cache) >= self.cache_size:
                # Remove oldest entry
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            
            self._cache[cache_key] = result
        
        return result
    
    def _create_cache_key(self, template_name: str, context: Dict[str, Any]) -> str:
        """Create cache key from template name and context"""
        import hashlib
        import json
        
        # Create a hash of the context (excluding non-serializable objects)
        serializable_context = {}
        for key, value in context.items():
            try:
                json.dumps(value)
                serializable_context[key] = value
            except (TypeError, ValueError):
                # Skip non-serializable values
                pass
        
        context_hash = hashlib.md5(
            json.dumps(serializable_context, sort_keys=True).encode()
        ).hexdigest()
        
        return f"{template_name}:{context_hash}"
    
    def clear_cache(self):
        """Clear template cache"""
        self._cache.clear()
    
    def disable_cache(self):
        """Disable template caching"""
        self._cache_enabled = False
    
    def enable_cache(self):
        """Enable template caching"""
        self._cache_enabled = True
```

### Template Context Processors

Add global context to all templates:

```python
class TemplateContextProcessor:
    """Add global context to templates"""
    
    def __init__(self):
        self.global_context = {}
    
    def add_global_context(self, **kwargs):
        """Add global context variables"""
        self.global_context.update(kwargs)
    
    def process_context(self, context: Dict[str, Any], request=None) -> Dict[str, Any]:
        """Process template context"""
        # Start with global context
        processed_context = self.global_context.copy()
        
        # Add request-specific context
        if request:
            processed_context.update({
                'request': request,
                'current_url': str(request.url),
                'current_path': request.url.path,
                'user_agent': request.headers.get('user-agent', ''),
            })
        
        # Add provided context (overrides global)
        processed_context.update(context)
        
        return processed_context

class EnhancedTemplateEngine(CachedTemplateEngine):
    """Template engine with context processing"""
    
    def __init__(self, template_dir: str = "templates", cache_size: int = 128):
        super().__init__(template_dir, cache_size)
        self.context_processor = TemplateContextProcessor()
        
        # Add default global context
        self.context_processor.add_global_context(
            app_name="Serv Application",
            version="1.0.0",
            current_year=2024
        )
    
    async def render(self, template_name: str, context: Dict[str, Any] = None, request=None) -> str:
        """Render template with context processing"""
        context = context or {}
        
        # Process context
        processed_context = self.context_processor.process_context(context, request)
        
        return await super().render(template_name, processed_context)
```

## Template Organization

### Directory Structure

Organize templates logically:

```
templates/
├── base.html                 # Base template
├── layouts/
│   ├── admin.html           # Admin layout
│   ├── auth.html            # Authentication layout
│   └── minimal.html         # Minimal layout
├── components/
│   ├── navbar.html          # Navigation component
│   ├── footer.html          # Footer component
│   ├── pagination.html      # Pagination component
│   └── flash_messages.html  # Flash messages
├── forms/
│   ├── base_form.html       # Form macros
│   ├── login.html           # Login form
│   └── register.html        # Registration form
├── products/
│   ├── list.html            # Product list
│   ├── detail.html          # Product detail
│   └── form.html            # Product form
├── users/
│   ├── profile.html         # User profile
│   └── settings.html        # User settings
└── errors/
    ├── 404.html             # Not found page
    ├── 500.html             # Server error page
    └── generic.html         # Generic error page
```

### Component Templates

Create reusable components:

**templates/components/pagination.html:**
```html
{% macro render_pagination(pagination, endpoint='products', **kwargs) %}
{% if pagination.pages > 1 %}
<nav aria-label="Page navigation">
    <ul class="pagination justify-content-center">
        <!-- Previous page -->
        {% if pagination.has_prev %}
        <li class="page-item">
            <a class="page-link" href="{{ url_for(endpoint, page=pagination.prev_num, **kwargs) }}">
                <span aria-hidden="true">&laquo;</span>
                <span class="sr-only">Previous</span>
            </a>
        </li>
        {% else %}
        <li class="page-item disabled">
            <span class="page-link">
                <span aria-hidden="true">&laquo;</span>
            </span>
        </li>
        {% endif %}
        
        <!-- Page numbers -->
        {% for page_num in pagination.iter_pages(left_edge=1, right_edge=1, left_current=1, right_current=2) %}
        {% if page_num %}
        {% if page_num != pagination.page %}
        <li class="page-item">
            <a class="page-link" href="{{ url_for(endpoint, page=page_num, **kwargs) }}">{{ page_num }}</a>
        </li>
        {% else %}
        <li class="page-item active">
            <span class="page-link">{{ page_num }}</span>
        </li>
        {% endif %}
        {% else %}
        <li class="page-item disabled">
            <span class="page-link">...</span>
        </li>
        {% endif %}
        {% endfor %}
        
        <!-- Next page -->
        {% if pagination.has_next %}
        <li class="page-item">
            <a class="page-link" href="{{ url_for(endpoint, page=pagination.next_num, **kwargs) }}">
                <span aria-hidden="true">&raquo;</span>
                <span class="sr-only">Next</span>
            </a>
        </li>
        {% else %}
        <li class="page-item disabled">
            <span class="page-link">
                <span aria-hidden="true">&raquo;</span>
            </span>
        </li>
        {% endif %}
    </ul>
</nav>
{% endif %}
{% endmacro %}
```

**templates/components/flash_messages.html:**
```html
{% macro render_flash_messages(messages) %}
{% if messages %}
<div class="flash-messages">
    {% for message in messages %}
    <div class="alert alert-{{ message.category }} alert-dismissible fade show" role="alert">
        {% if message.category == 'error' %}
        <i class="fas fa-exclamation-triangle me-2"></i>
        {% elif message.category == 'success' %}
        <i class="fas fa-check-circle me-2"></i>
        {% elif message.category == 'warning' %}
        <i class="fas fa-exclamation-circle me-2"></i>
        {% elif message.category == 'info' %}
        <i class="fas fa-info-circle me-2"></i>
        {% endif %}
        
        {{ message.message }}
        
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>
    {% endfor %}
</div>
{% endif %}
{% endmacro %}
```

## Template Route Integration

### Complete Route Example

```python
from serv.routes import Route, GetRequest, PostRequest
from typing import Annotated
from serv.responses import HtmlResponse, RedirectResponse
from serv.exceptions import HTTPNotFoundException
from bevy import dependency
from extensions.templates.template_engine import EnhancedTemplateEngine

class ProductRoute(Route):
    async def handle_get(
        self, 
        request: GetRequest,
        template_engine: EnhancedTemplateEngine = dependency()
    ) -> Annotated[str, HtmlResponse]:
        """Display product list or detail"""
        
        # Check if this is a detail view
        product_id = request.path_params.get('product_id')
        
        if product_id:
            return await self.show_product_detail(request, template_engine, product_id)
        else:
            return await self.show_product_list(request, template_engine)
    
    async def show_product_list(self, request, template_engine):
        """Show product list"""
        # Get query parameters
        search = request.query_params.get('search', '')
        category = request.query_params.get('category', '')
        page = int(request.query_params.get('page', '1'))
        
        # Fetch products (mock data)
        products = await self.get_products(search, category, page)
        categories = await self.get_categories()
        pagination = await self.get_pagination(page, total_products=100)
        
        context = {
            'title': 'Products',
            'products': products,
            'categories': categories,
            'pagination': pagination,
            'search_query': search,
            'selected_category': category
        }
        
        return await template_engine.render('products/list.html', context, request)
    
    async def show_product_detail(self, request, template_engine, product_id):
        """Show product detail"""
        product = await self.get_product(product_id)
        
        if not product:
            raise HTTPNotFoundException(f"Product {product_id} not found")
        
        related_products = await self.get_related_products(product['category'])
        
        context = {
            'title': f"{product['name']} - Product Detail",
            'product': product,
            'related_products': related_products
        }
        
        return await template_engine.render('products/detail.html', context, request)
    
    async def handle_post(
        self, 
        request: PostRequest,
        template_engine: EnhancedTemplateEngine = dependency()
    ) -> RedirectResponse:
        """Handle product creation/update"""
        
        form_data = await request.form()
        
        # Validate and process form
        if await self.validate_product_form(form_data):
            product = await self.save_product(form_data)
            return RedirectResponse(f"/products/{product['id']}")
        else:
            # Re-render form with errors
            context = {
                'title': 'Product Form',
                'form_data': form_data,
                'form_errors': await self.get_form_errors(form_data)
            }
            
            html_content = await template_engine.render('products/form.html', context, request)
            return HtmlResponse(html_content, status_code=400)
    
    # Mock data methods
    async def get_products(self, search, category, page):
        """Get products with filtering and pagination"""
        return [
            {
                'id': i,
                'name': f'Product {i}',
                'description': f'Description for product {i}',
                'price': 29.99 + i,
                'category': 'Electronics',
                'in_stock': True,
                'image': f'/static/images/product{i}.jpg'
            }
            for i in range(1, 13)
        ]
    
    async def get_categories(self):
        """Get product categories"""
        return [
            {'id': 1, 'name': 'Electronics'},
            {'id': 2, 'name': 'Clothing'},
            {'id': 3, 'name': 'Books'},
            {'id': 4, 'name': 'Home & Garden'}
        ]
    
    async def get_pagination(self, page, total_products):
        """Get pagination info"""
        per_page = 12
        total_pages = (total_products + per_page - 1) // per_page
        
        return {
            'page': page,
            'pages': total_pages,
            'per_page': per_page,
            'total': total_products,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_num': page - 1 if page > 1 else None,
            'next_num': page + 1 if page < total_pages else None,
            'iter_pages': lambda **kwargs: range(1, total_pages + 1)
        }
    
    async def get_product(self, product_id):
        """Get single product"""
        return {
            'id': product_id,
            'name': f'Product {product_id}',
            'description': 'Detailed product description...',
            'price': 99.99,
            'category': 'Electronics',
            'in_stock': True,
            'images': ['/static/images/product1.jpg', '/static/images/product2.jpg']
        }
    
    async def get_related_products(self, category):
        """Get related products"""
        return [
            {'id': i, 'name': f'Related Product {i}', 'price': 19.99 + i}
            for i in range(1, 4)
        ]
```

## Best Practices

### 1. Template Organization

```python
# Good: Organized template structure
templates/
├── base.html
├── layouts/
├── components/
├── pages/
└── forms/

# Avoid: Flat structure
templates/
├── template1.html
├── template2.html
├── template3.html
```

### 2. Context Management

```python
# Good: Clear context structure
context = {
    'title': 'Page Title',
    'user': current_user,
    'data': {
        'products': products,
        'categories': categories
    },
    'meta': {
        'page': page,
        'total': total
    }
}

# Avoid: Flat context
context = {
    'title': 'Page Title',
    'user': current_user,
    'products': products,
    'categories': categories,
    'page': page,
    'total': total
}
```

### 3. Template Inheritance

```html
<!-- Good: Use template inheritance -->
{% extends "base.html" %}
{% block content %}
<!-- Page-specific content -->
{% endblock %}

<!-- Avoid: Duplicating layout code -->
<!DOCTYPE html>
<html>
<!-- Repeated layout code -->
```

### 4. Security

```html
<!-- Good: Auto-escape user content -->
<p>{{ user.bio }}</p>

<!-- Dangerous: Raw content without escaping -->
<p>{{ user.bio | safe }}</p>  <!-- Only if you trust the content -->
```

### 5. Performance

```python
# Good: Cache templates in production
template_engine = CachedTemplateEngine(cache_size=256)

# Good: Minimize context data
context = {
    'products': products[:10],  # Limit data
    'user': {'name': user.name, 'id': user.id}  # Only needed fields
}

# Avoid: Large context objects
context = {
    'products': all_products,  # Too much data
    'user': user  # Entire user object
}
```

## Development Workflow

### 1. Set Up Template Engine

Configure your preferred template engine with Serv.

### 2. Create Base Templates

Design your base layout and common components.

### 3. Build Page Templates

Create specific templates for each page type.

### 4. Add Template Context

Ensure templates receive the data they need.

### 5. Test Template Rendering

Test templates with various data scenarios.

## Next Steps

- **[Static Files](static-files.md)** - Serve CSS, JavaScript, and images
- **[Forms and File Uploads](forms.md)** - Handle form submissions
- **[Authentication](authentication.md)** - Add user authentication
- **[Testing](testing.md)** - Test your template rendering 