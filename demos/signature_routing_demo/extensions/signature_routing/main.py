from dataclasses import dataclass
from typing import Annotated

from bevy import dependency

from serv.exceptions import (
    ServException,
)
from serv.extensions import Listener, on
from serv.injectors import Cookie, Header, Query
from serv.responses import ResponseBuilder
from serv.routes import (
    Form,
    HtmlResponse,
    JsonResponse,
    PostRequest,
    PutRequest,
    Route,
    TextResponse,
    handle,
)
from serv.routing import Router


# Custom exception for demo
class HTTPUnauthorizedException(ServException):
    """Raised for authentication failures (HTTP 401)"""

    status_code = 401


# Form definitions
@dataclass
class ContactForm(Form):
    name: str
    email: str
    message: str


@dataclass
class CreateUserForm(Form):
    username: str
    email: str


# Route classes demonstrating signature-based routing
class SearchRoute(Route):
    """Search API with multiple GET handlers based on parameters"""

    @handle.GET
    async def default_search(self) -> Annotated[dict, JsonResponse]:
        """Default search - no parameters"""
        return {
            "message": "Default search results",
            "results": ["result1", "result2", "result3"],
            "handler": "default",
        }

    @handle.GET
    async def search_with_query(
        self, query: Annotated[str, Query("q")]
    ) -> Annotated[dict, JsonResponse]:
        """Search with query parameter only"""
        return {
            "query": query,
            "results": [f"result for '{query}' {i}" for i in range(1, 4)],
            "handler": "with_query",
        }

    @handle.GET
    async def search_paginated(
        self,
        query: Annotated[str, Query("q")],
        page: Annotated[str, Query("page", default="1")],
        limit: Annotated[str, Query("limit", default="10")],
    ) -> Annotated[dict, JsonResponse]:
        """Search with pagination"""
        return {
            "query": query,
            "page": int(page),
            "limit": int(limit),
            "results": [
                f"paginated result for '{query}' {i}" for i in range(1, int(limit) + 1)
            ],
            "handler": "paginated",
        }

    @handle.GET
    async def search_advanced(
        self,
        query: Annotated[str, Query("q")],
        page: Annotated[str, Query("page", default="1")],
        limit: Annotated[str, Query("limit", default="10")],
        category: Annotated[str, Query("category")],
    ) -> Annotated[dict, JsonResponse]:
        """Advanced search with category filter"""
        return {
            "query": query,
            "page": int(page),
            "limit": int(limit),
            "category": category,
            "results": [
                f"{category} result for '{query}' {i}" for i in range(1, int(limit) + 1)
            ],
            "handler": "advanced",
        }


class UserRoute(Route):
    """User API with authentication-based handler selection"""

    @handle.GET
    async def get_public_users(self) -> Annotated[dict, JsonResponse]:
        """Public user list - no auth required"""
        return {
            "users": [
                {"id": 1, "username": "john_public"},
                {"id": 2, "username": "jane_public"},
            ],
            "message": "Public user data",
            "handler": "public",
        }

    @handle.GET
    async def get_authenticated_users(
        self, auth_token: Annotated[str, Header("Authorization")]
    ) -> Annotated[dict, JsonResponse]:
        """Private user list - auth required"""
        if not self.validate_auth(auth_token):
            raise HTTPUnauthorizedException("Invalid token")

        return {
            "users": [
                {
                    "id": 1,
                    "username": "john",
                    "email": "john@example.com",
                    "private": "secret_data",
                },
                {
                    "id": 2,
                    "username": "jane",
                    "email": "jane@example.com",
                    "private": "secret_data",
                },
            ],
            "message": "Private user data with authentication",
            "handler": "authenticated",
        }

    @handle.POST
    async def create_user_json(
        self, request: PostRequest, auth_token: Annotated[str, Header("Authorization")]
    ) -> Annotated[dict, JsonResponse]:
        """Create user - requires authentication"""
        if not self.validate_auth(auth_token):
            raise HTTPUnauthorizedException("Authentication required for user creation")

        data = await request.json()
        return {
            "message": "User created successfully",
            "user": {
                "id": 123,
                "username": data.get("username"),
                "email": data.get("email"),
            },
            "handler": "create_authenticated",
        }

    @handle.POST
    async def create_user_form(
        self, form: CreateUserForm, auth_token: Annotated[str, Header("Authorization")]
    ) -> Annotated[str, TextResponse]:
        """Create user via form"""
        if not self.validate_auth(auth_token):
            raise HTTPUnauthorizedException("Authentication required")

        return f"User {form.username} created via form with email {form.email}"

    @handle.PUT
    async def update_user(
        self,
        request: PutRequest,
        user_id: Annotated[str, Query("id")],
        session_id: Annotated[str, Cookie("session_id")],
    ) -> Annotated[dict, JsonResponse]:
        """Update user - requires session"""
        if not self.validate_session(session_id):
            raise HTTPUnauthorizedException("Valid session required")

        data = await request.json()
        return {
            "message": f"User {user_id} updated successfully",
            "updated_data": data,
            "handler": "update_with_session",
        }

    def validate_auth(self, token: str) -> bool:
        """Validate authentication token"""
        return token == "Bearer valid-token"

    def validate_session(self, session_id: str) -> bool:
        """Validate session ID"""
        return session_id == "valid-session"


class ContactRoute(Route):
    """Contact form demonstrating form handling"""

    @handle.GET
    async def show_contact_form(self) -> Annotated[str, HtmlResponse]:
        """Show contact form"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Contact Us</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                .form-group { margin-bottom: 15px; }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                input, textarea { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
                button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
                button:hover { background: #0056b3; }
            </style>
        </head>
        <body>
            <h1>Contact Us</h1>
            <form method="post">
                <div class="form-group">
                    <label for="name">Name:</label>
                    <input type="text" id="name" name="name" required>
                </div>
                <div class="form-group">
                    <label for="email">Email:</label>
                    <input type="email" id="email" name="email" required>
                </div>
                <div class="form-group">
                    <label for="message">Message:</label>
                    <textarea id="message" name="message" rows="5" required></textarea>
                </div>
                <button type="submit">Send Message</button>
            </form>

            <h2>Demo Instructions</h2>
            <p>This form demonstrates signature-based routing. Try:</p>
            <ul>
                <li>Fill out and submit the form</li>
                <li>Submit with missing fields (will show validation)</li>
            </ul>

            <h2>API Examples</h2>
            <h3>Search API:</h3>
            <ul>
                <li><a href="/api/search">Basic search</a></li>
                <li><a href="/api/search?q=python">Search with query</a></li>
                <li><a href="/api/search?q=python&page=2">Paginated search</a></li>
                <li><a href="/api/search?q=python&category=programming">Advanced search</a></li>
            </ul>

            <h3>User API:</h3>
            <ul>
                <li><a href="/api/users">Public users</a></li>
                <li>Private users: <code>curl -H "Authorization: Bearer valid-token" http://127.0.0.1:8000/api/users</code></li>
            </ul>
        </body>
        </html>
        """

    @handle.POST
    async def process_contact_form(
        self, form: ContactForm
    ) -> Annotated[str, HtmlResponse]:
        """Process contact form submission"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Message Sent</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                .success {{ background: #d4edda; color: #155724; padding: 15px; border-radius: 4px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="success">
                <h1>Thank you, {form.name}!</h1>
                <p>Your message has been received. We'll get back to you at {form.email}.</p>
                <p><strong>Your message:</strong> {form.message}</p>
            </div>
            <a href="/contact">← Send another message</a>
        </body>
        </html>
        """


class SignatureRoutingExtension(Listener):
    """Extension that registers our route classes"""

    def __init__(self):
        super().__init__()
        print("SignatureRoutingExtension.__init__ called!")

    @on("app.request.begin")
    async def setup_routing(self, router: Router = dependency()):
        """Set up the routes when the app starts up"""
        print("SignatureRoutingExtension.on_app_startup called!")
        print(f"Got router: {router}")

        # Register route classes
        router.add_route("/api/search", SearchRoute)
        router.add_route("/api/users", UserRoute)
        router.add_route("/contact", ContactRoute)

        # Add a simple homepage
        router.add_route("/", self.homepage)

        print("Routes registered successfully!")

    async def homepage(self, response: ResponseBuilder = dependency()):
        """Homepage with demo instructions"""
        response.content_type("text/html")
        response.body("""<!DOCTYPE html>
        <html>
        <head>
            <title>Signature-Based Routing Demo</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
                .feature { background: #f8f9fa; padding: 15px; margin: 15px 0; border-radius: 4px; }
                code { background: #e9ecef; padding: 2px 4px; border-radius: 3px; }
                .endpoint { margin: 10px 0; }
            </style>
        </head>
        <body>
            <h1>Serv Signature-Based Routing Demo</h1>

            <p>This demo showcases Serv's powerful signature-based routing system where multiple handlers can exist for the same HTTP method and are automatically selected based on request parameters.</p>

            <div class="feature">
                <h2>🔍 Search API - Multiple GET Handlers</h2>
                <p>The same endpoint behaves differently based on available parameters:</p>
                <div class="endpoint"><a href="/api/search">GET /api/search</a> - Default results</div>
                <div class="endpoint"><a href="/api/search?q=python">GET /api/search?q=python</a> - Search with query</div>
                <div class="endpoint"><a href="/api/search?q=python&page=2">GET /api/search?q=python&page=2</a> - Paginated</div>
                <div class="endpoint"><a href="/api/search?q=python&category=programming">GET /api/search?q=python&category=programming</a> - Advanced</div>
            </div>

            <div class="feature">
                <h2>👤 User API - Authentication-Based Selection</h2>
                <p>Different handlers based on authentication headers:</p>
                <div class="endpoint"><a href="/api/users">GET /api/users</a> - Public data</div>
                <div class="endpoint"><code>GET /api/users + Authorization header</code> - Private data</div>
                <div class="endpoint"><code>POST /api/users + Authorization header</code> - Create user</div>
            </div>

            <div class="feature">
                <h2>📝 Contact Form - Form Handling</h2>
                <p>Automatic form matching and processing:</p>
                <div class="endpoint"><a href="/contact">GET /contact</a> - Show form</div>
                <div class="endpoint"><code>POST /contact</code> - Process form</div>
            </div>

            <h2>Try It Out</h2>
            <p>Use curl, Postman, or your browser to test different endpoints and see how Serv automatically selects the most appropriate handler!</p>

            <h3>Example Commands:</h3>
            <pre><code># Search examples
curl http://127.0.0.1:8000/api/search
curl "http://127.0.0.1:8000/api/search?q=python&page=2"

# User API with authentication
curl -H "Authorization: Bearer valid-token" http://127.0.0.1:8000/api/users

# Create user
curl -X POST -H "Authorization: Bearer valid-token" \\
  -H "Content-Type: application/json" \\
  -d '{"username": "john", "email": "john@example.com"}' \\
  http://127.0.0.1:8000/api/users</code></pre>
        </body>
        </html>
        """)
