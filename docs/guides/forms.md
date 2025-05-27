# Forms and Validation

Serv provides a powerful form handling system built around the `routes.Form` base class. This system automatically detects form submissions, handles type conversion, and integrates seamlessly with dataclasses, Pydantic models, and attrs classes for structured data processing.

## Overview

Serv's form system is designed around automatic detection and type safety:

1. **Form Base Class**: Inherit from `routes.Form` to define form structure
2. **Automatic Detection**: Handler methods with `Form` parameters are automatically detected
3. **Type Conversion**: Form data is automatically converted to the types specified in your form class
4. **Validation Integration**: Works with dataclasses, Pydantic, and attrs for validation
5. **File Upload Support**: Built-in handling for single and multiple file uploads

The key concept is that when you create a dataclass (or Pydantic/attrs class) that inherits from `routes.Form`, Serv automatically detects form submissions and routes them to handler methods that accept that form type as a parameter.

## Basic Form Handling

### Creating a Contact Form

Let's start with a complete contact form example that demonstrates the core concepts:

```bash
# Create a extension for contact functionality
serv create extension --name "Contact"

# Create a route to handle the contact form
serv create route --name "contact" --path "/contact" --extension "contact"
```

**extensions/contact/route_contact.py:**
```python
from dataclasses import dataclass
from typing import Annotated, Optional
from serv.routes import Route, Form, GetRequest, HtmlResponse
from serv.exceptions import HTTPBadRequestException

@dataclass
class ContactForm(Form):
    """Contact form definition - inherits from routes.Form for auto-detection"""
    name: str
    email: str
    message: str
    phone: Optional[str] = None
    newsletter: bool = False

class ContactRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[str, HtmlResponse]:
        """Display the contact form"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Contact Us</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                .form-group { margin-bottom: 15px; }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                input, textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
                button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; }
            </style>
        </head>
        <body>
            <h1>Contact Us</h1>
            <form method="post" action="/contact">
                <div class="form-group">
                    <label for="name">Name:</label>
                    <input type="text" id="name" name="name" required>
                </div>
                <div class="form-group">
                    <label for="email">Email:</label>
                    <input type="email" id="email" name="email" required>
                </div>
                <div class="form-group">
                    <label for="phone">Phone (optional):</label>
                    <input type="tel" id="phone" name="phone">
                </div>
                <div class="form-group">
                    <label for="message">Message:</label>
                    <textarea id="message" name="message" rows="5" required></textarea>
                </div>
                <div class="form-group">
                    <label>
                        <input type="checkbox" name="newsletter" value="true">
                        Subscribe to newsletter
                    </label>
                </div>
                <button type="submit">Send Message</button>
            </form>
        </body>
        </html>
        """
    
    async def handle_contact_form(self, form: ContactForm) -> Annotated[str, HtmlResponse]:
        """Handle contact form submission - automatically detected by Serv"""
        
        # Validate form data (you can also use Pydantic validators)
        if not form.name.strip():
            raise HTTPBadRequestException("Name is required")
        
        if "@" not in form.email:
            raise HTTPBadRequestException("Valid email is required")
        
        if len(form.message.strip()) < 10:
            raise HTTPBadRequestException("Message must be at least 10 characters")
        
        # Process the form (send email, save to database, etc.)
        await self.process_contact(form)
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Thank You</title></head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center;">
            <h1 style="color: #28a745;">Thank You, {form.name}!</h1>
            <p>Your message has been sent successfully. We'll get back to you soon.</p>
            <a href="/contact">Send Another Message</a>
        </body>
        </html>
        """
    
    async def process_contact(self, form: ContactForm):
        """Process the contact form submission"""
        # In a real application, you might:
        # - Send an email notification
        # - Save to database
        # - Add to CRM system
        print(f"Contact from {form.name} ({form.email}): {form.message}")
        if form.newsletter:
            print(f"Added {form.email} to newsletter")
```

**extensions/contact/extension.yaml:**
```yaml
name: Contact
description: Contact form handling
version: 1.0.0

routers:
  - name: main_router
    routes:
      - path: /contact
        handler: route_contact:ContactRoute
```

### How Form Detection Works

The magic happens in the `handle_contact_form` method. Serv automatically detects that this method should handle form submissions because:

1. The method parameter `form: ContactForm` indicates it expects a `ContactForm` instance
2. `ContactForm` inherits from `routes.Form`
3. When a POST request is made to `/contact`, Serv automatically parses the form data and creates a `ContactForm` instance
4. Type conversion happens automatically (strings to booleans, numbers, etc.)

## File Upload Forms

File uploads are handled seamlessly within the form system. Here's a comprehensive example:

```python
from dataclasses import dataclass
from typing import List, Optional
from serv.routes import Route, Form, GetRequest, HtmlResponse
from serv.requests import UploadFile

@dataclass
class DocumentUploadForm(Form):
    """Form for uploading documents with metadata"""
    title: str
    description: str
    category: str
    file: UploadFile  # Single file upload
    attachments: List[UploadFile]  # Multiple file uploads
    public: bool = False

class DocumentRoute(Route):
    async def handle_get(self, request: GetRequest) -> Annotated[str, HtmlResponse]:
        """Display document upload form"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Upload Document</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                .form-group { margin-bottom: 15px; }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                input, textarea, select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
                input[type="file"] { padding: 3px; }
                button { background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 4px; }
            </style>
        </head>
        <body>
            <h1>Upload Document</h1>
            <form method="post" action="/documents/upload" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="title">Document Title:</label>
                    <input type="text" id="title" name="title" required>
                </div>
                <div class="form-group">
                    <label for="description">Description:</label>
                    <textarea id="description" name="description" rows="3" required></textarea>
                </div>
                <div class="form-group">
                    <label for="category">Category:</label>
                    <select id="category" name="category" required>
                        <option value="">Select category...</option>
                        <option value="report">Report</option>
                        <option value="presentation">Presentation</option>
                        <option value="spreadsheet">Spreadsheet</option>
                        <option value="other">Other</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="file">Main Document:</label>
                    <input type="file" id="file" name="file" required>
                </div>
                <div class="form-group">
                    <label for="attachments">Additional Files (optional):</label>
                    <input type="file" id="attachments" name="attachments" multiple>
                </div>
                <div class="form-group">
                    <label>
                        <input type="checkbox" name="public" value="true">
                        Make this document public
                    </label>
                </div>
                <button type="submit">Upload Document</button>
            </form>
        </body>
        </html>
        """
    
    async def handle_document_upload_form(self, form: DocumentUploadForm) -> Annotated[str, HtmlResponse]:
        """Handle document upload form submission"""
        
        # Validate file types
        allowed_types = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt'}
        
        if not any(form.file.filename.lower().endswith(ext) for ext in allowed_types):
            raise HTTPBadRequestException("Invalid file type for main document")
        
        # Validate file size (10MB limit)
        if len(form.file.content) > 10 * 1024 * 1024:
            raise HTTPBadRequestException("File size must be less than 10MB")
        
        # Save main document
        main_file_path = await self.save_file(form.file, form.category)
        
        # Save attachments
        attachment_paths = []
        for attachment in form.attachments:
            if attachment.filename:  # Only process if file was uploaded
                attachment_path = await self.save_file(attachment, form.category)
                attachment_paths.append(attachment_path)
        
        # Save document metadata to database
        document_id = await self.save_document_metadata(
            title=form.title,
            description=form.description,
            category=form.category,
            main_file=main_file_path,
            attachments=attachment_paths,
            public=form.public
        )
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Upload Successful</title></head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
            <h1 style="color: #28a745;">Upload Successful!</h1>
            <p><strong>Document:</strong> {form.title}</p>
            <p><strong>Category:</strong> {form.category}</p>
            <p><strong>Main File:</strong> {form.file.filename}</p>
            <p><strong>Attachments:</strong> {len(form.attachments)} files</p>
            <p><strong>Public:</strong> {'Yes' if form.public else 'No'}</p>
            <p>Document ID: {document_id}</p>
            <a href="/documents/upload">Upload Another Document</a>
        </body>
        </html>
        """
    
    async def save_file(self, file: UploadFile, category: str) -> str:
        """Save uploaded file to disk"""
        import os
        import uuid
        
        # Create category directory if it doesn't exist
        upload_dir = f"uploads/{category}"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(file.content)
        
        return file_path
    
    async def save_document_metadata(self, **kwargs) -> str:
        """Save document metadata (mock implementation)"""
        import uuid
        document_id = str(uuid.uuid4())
        
        # In a real application, save to database
        print(f"Saved document {document_id} with metadata: {kwargs}")
        
        return document_id
```

### File Upload Key Points

- **Single Files**: Use `UploadFile` type for single file uploads
- **Multiple Files**: Use `List[UploadFile]` for multiple file uploads
- **Form Encoding**: Always use `enctype="multipart/form-data"` in your HTML form
- **File Validation**: Check file types, sizes, and content before processing
- **Storage**: Save files to disk, cloud storage, or database as needed

## Advanced Validation with Pydantic

For more sophisticated validation, you can use Pydantic models instead of dataclasses:

```python
from pydantic import BaseModel, EmailStr, validator
from typing import List, Optional
from serv.routes import Route, Form

class UserRegistrationForm(BaseModel, Form):
    """User registration form with Pydantic validation"""
    username: str
    email: EmailStr
    password: str
    confirm_password: str
    age: int
    interests: List[str] = []
    terms_accepted: bool
    
    @validator('username')
    def username_must_be_alphanumeric(cls, v):
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        return v
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain a number')
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('age')
    def age_must_be_adult(cls, v):
        if v < 18:
            raise ValueError('Must be 18 or older to register')
        return v
    
    @validator('terms_accepted')
    def terms_must_be_accepted(cls, v):
        if not v:
            raise ValueError('You must accept the terms and conditions')
        return v

class RegistrationRoute(Route):
    async def handle_user_registration_form(self, form: UserRegistrationForm) -> Annotated[dict, JsonResponse]:
        """Handle user registration with automatic Pydantic validation"""
        
        # If we reach here, all Pydantic validators have passed
        
        # Check if username is already taken
        if await self.username_exists(form.username):
            raise HTTPBadRequestException("Username already taken")
        
        # Create user account
        user_id = await self.create_user(form)
        
        return {
            "success": True,
            "message": f"Welcome, {form.username}! Your account has been created.",
            "user_id": user_id
        }
    
    async def username_exists(self, username: str) -> bool:
        """Check if username already exists"""
        # Mock implementation
        return username.lower() in ['admin', 'test', 'user']
    
    async def create_user(self, form: UserRegistrationForm) -> str:
        """Create new user account"""
        import uuid
        user_id = str(uuid.uuid4())
        
        # In real application, hash password and save to database
        print(f"Created user {user_id}: {form.username} ({form.email})")
        
        return user_id
```

## Error Handling and Validation

### Handling Validation Errors

When using Pydantic or custom validation, Serv automatically catches validation errors and can return appropriate responses:

```python
from serv.exceptions import HTTPBadRequestException
from pydantic import ValidationError

class FormRoute(Route):
    async def handle_user_registration_form(self, form: UserRegistrationForm) -> JsonResponse:
        """Handle registration with comprehensive error handling"""
        try:
            # Form validation happens automatically before this method is called
            # If we reach here, basic validation passed
            
            # Additional business logic validation
            if await self.email_exists(form.email):
                raise HTTPBadRequestException("Email address already registered")
            
            # Process successful registration
            user_id = await self.create_user(form)
            
            return JsonResponse({
                "success": True,
                "user_id": user_id,
                "message": "Registration successful"
            })
            
        except ValidationError as e:
            # Pydantic validation errors are automatically handled by Serv
            # This catch block is for demonstration - normally not needed
            return JsonResponse({
                "success": False,
                "errors": e.errors(),
                "message": "Validation failed"
            }, status_code=422)
        
        except HTTPBadRequestException as e:
            # Business logic validation errors
            return JsonResponse({
                "success": False,
                "message": str(e)
            }, status_code=400)
```

## Best Practices

### 1. Use Type Hints Consistently

Always use proper type hints in your form classes. This enables automatic type conversion and better IDE support:

```python
# Good: Clear type hints
@dataclass
class ProductForm(Form):
    name: str
    price: float
    quantity: int
    available: bool
    tags: List[str] = field(default_factory=list)

# Avoid: No type hints
@dataclass
class ProductForm(Form):
    name = ""
    price = 0.0
    quantity = 0
```

### 2. Validate Early and Often

Implement validation at multiple levels:

```python
# Good: Multiple validation layers
@dataclass
class OrderForm(Form):
    product_id: str
    quantity: int
    
    def __post_init__(self):
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")

async def handle_order_form(self, form: OrderForm):
    # Business logic validation
    if not await self.product_exists(form.product_id):
        raise HTTPNotFoundException("Product not found")
    
    if not await self.has_sufficient_stock(form.product_id, form.quantity):
        raise HTTPBadRequestException("Insufficient stock")
```

### 3. Handle File Uploads Securely

Always validate file uploads thoroughly:

```python
# Good: Comprehensive file validation
async def handle_upload_form(self, form: FileUploadForm):
    # Validate file type
    allowed_extensions = {'.jpg', '.png', '.pdf', '.doc'}
    file_ext = os.path.splitext(form.file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPBadRequestException(f"File type {file_ext} not allowed")
    
    # Validate file size
    max_size = 5 * 1024 * 1024  # 5MB
    if len(form.file.content) > max_size:
        raise HTTPBadRequestException("File too large")
    
    # Validate file content (basic check)
    if not form.file.content:
        raise HTTPBadRequestException("Empty file")
```

### 4. Use Appropriate Response Types

Return appropriate responses based on the request type:

```python
# Good: Context-aware responses
async def handle_contact_form(self, form: ContactForm, request: Request):
    # Process form...
    
    # Return JSON for API requests
    if request.path.startswith('/api/') or 'application/json' in request.headers.get('accept', ''):
        return JsonResponse({"success": True, "message": "Contact sent"})
    
    # Return HTML for web requests
    return HtmlResponse("<h1>Thank you! Your message has been sent.</h1>")
```

## Development Workflow

### 1. Design Your Forms

Start by identifying what data you need to collect and design your form classes:

```bash
# Create extension for your forms
serv create extension --name "Forms"

# Create routes for each form
serv create route --name "contact" --path "/contact" --extension "forms"
```

### 2. Implement Form Classes

Create form classes that inherit from `routes.Form` and use appropriate type hints.

### 3. Create Handler Methods

Implement handler methods that accept your form classes as parameters. Serv will automatically detect and route to these methods.

### 4. Add Validation

Implement validation using dataclass `__post_init__`, Pydantic validators, or custom validation logic.

### 5. Test Your Forms

Test form submission, validation, and error handling thoroughly.

## Next Steps

- **[Request Handling](requests.md)** - Learn more about processing different types of requests
- **[Response Building](responses.md)** - Master different response types and patterns
- **[Error Handling](error-handling.md)** - Implement comprehensive error handling
- **[Testing](testing.md)** - Test your form handling logic 