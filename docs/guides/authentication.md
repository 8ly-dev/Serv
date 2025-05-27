# Authentication

Authentication is a critical aspect of web applications. Serv provides flexible authentication patterns through middleware, extensions, and dependency injection. This guide covers how to implement various authentication strategies in Serv applications.

## Overview

Serv's authentication approach:

1. **Middleware-Based**: Authentication logic implemented as middleware
2. **Extension-Organized**: Authentication components organized within extensions
3. **Flexible**: Support for multiple authentication strategies
4. **Session Management**: Built-in support for cookies and sessions
5. **Dependency Injection**: Easy access to user information in route handlers

## Authentication Strategies

### Basic Authentication

Basic authentication using username and password credentials.

### Session-Based Authentication

Traditional session-based authentication with cookies.

### Token-Based Authentication

JWT tokens and API key authentication.

### OAuth Integration

Integration with third-party OAuth providers.

## Setting Up Authentication

### Creating an Authentication Extension

Use the CLI to create an authentication extension:

```bash
# Create an authentication extension
serv create extension --name "Auth"

# Create authentication middleware
serv create middleware --name "auth_check" --extension "auth"

# Create authentication routes
serv create route --name "login" --path "/login" --extension "auth"
serv create route --name "logout" --path "/logout" --extension "auth"
serv create route --name "register" --path "/register" --extension "auth"
```

### Basic Extension Structure

**extensions/auth/extension.yaml:**
```yaml
name: Auth
description: Authentication and authorization
version: 1.0.0
author: Your Name

settings:
  secret_key: "your-secret-key-change-in-production"
  session_timeout: 3600
  password_min_length: 8
  enable_registration: true

routers:
  - name: main_router
    routes:
      - path: /login
        handler: route_login:LoginPage
        methods: ["GET", "POST"]
      - path: /logout
        handler: route_logout:LogoutPage
        methods: ["POST"]
      - path: /register
        handler: route_register:RegisterPage
        methods: ["GET", "POST"]

middleware:
  - entry: middleware_auth_check:auth_check_middleware
    config:
      exempt_paths: ["/", "/login", "/register", "/public"]
```

## Session-Based Authentication

### User Model and Storage

**extensions/auth/models.py:**
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import hashlib
import secrets

@dataclass
class User:
    id: Optional[int]
    username: str
    email: str
    password_hash: str
    created_at: Optional[datetime] = None
    is_active: bool = True
    last_login: Optional[datetime] = None

class UserStorage:
    """Simple in-memory user storage (use database in production)"""
    
    def __init__(self):
        self.users: dict[int, User] = {}
        self.users_by_username: dict[str, User] = {}
        self.next_id = 1
        
        # Create default admin user
        self.create_user("admin", "admin@example.com", "admin123")
    
    def create_user(self, username: str, email: str, password: str) -> User:
        """Create a new user"""
        if username in self.users_by_username:
            raise ValueError("Username already exists")
        
        password_hash = self._hash_password(password)
        user = User(
            id=self.next_id,
            username=username,
            email=email,
            password_hash=password_hash,
            created_at=datetime.now()
        )
        
        self.users[self.next_id] = user
        self.users_by_username[username] = user
        self.next_id += 1
        
        return user
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.users_by_username.get(username)
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.users.get(user_id)
    
    def verify_password(self, user: User, password: str) -> bool:
        """Verify user password"""
        return self._hash_password(password) == user.password_hash
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256 (use bcrypt in production)"""
        return hashlib.sha256(password.encode()).hexdigest()

# Global user storage instance
user_storage = UserStorage()
```

### Session Management

**extensions/auth/sessions.py:**
```python
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict
from dataclasses import dataclass

@dataclass
class Session:
    session_id: str
    user_id: int
    created_at: datetime
    expires_at: datetime
    data: Dict = None

class SessionManager:
    """Simple in-memory session manager (use Redis in production)"""
    
    def __init__(self, timeout_seconds: int = 3600):
        self.sessions: Dict[str, Session] = {}
        self.timeout_seconds = timeout_seconds
    
    def create_session(self, user_id: int) -> str:
        """Create a new session for user"""
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(seconds=self.timeout_seconds)
        
        session = Session(
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.now(),
            expires_at=expires_at,
            data={}
        )
        
        self.sessions[session_id] = session
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        session = self.sessions.get(session_id)
        
        if session and session.expires_at > datetime.now():
            return session
        elif session:
            # Session expired, remove it
            del self.sessions[session_id]
        
        return None
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        now = datetime.now()
        expired_sessions = [
            session_id for session_id, session in self.sessions.items()
            if session.expires_at <= now
        ]
        
        for session_id in expired_sessions:
            del self.sessions[session_id]

# Global session manager
session_manager = SessionManager()
```

### Login Route

**extensions/auth/route_login.py:**
```python
from dataclasses import dataclass
from serv.routes import GetRequest, PostRequest
from serv.responses import ResponseBuilder
from serv.exceptions import HTTPBadRequestException
from bevy import dependency
from .models import user_storage
from .sessions import session_manager

@dataclass
class LoginForm:
    username: str
    password: str

async def LoginPage(
    request: GetRequest | PostRequest,
    response: ResponseBuilder = dependency()
):
    """Handle login page and form submission"""
    
    if request.method == "GET":
        # Display login form
        response.content_type("text/html")
        response.body("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Login</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; padding: 20px; }
                .form-group { margin-bottom: 15px; }
                label { display: block; margin-bottom: 5px; }
                input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
                button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
                .error { color: red; margin-top: 10px; }
            </style>
        </head>
        <body>
            <h2>Login</h2>
            <form method="post" action="/login">
                <div class="form-group">
                    <label for="username">Username:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                <div class="form-group">
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit">Login</button>
            </form>
            <p><a href="/register">Don't have an account? Register here</a></p>
        </body>
        </html>
        """)
    
    elif request.method == "POST":
        # Process login form
        try:
            form_data = await request.form(LoginForm)
            
            # Validate credentials
            user = user_storage.get_user_by_username(form_data.username)
            if not user or not user_storage.verify_password(user, form_data.password):
                raise HTTPBadRequestException("Invalid username or password")
            
            if not user.is_active:
                raise HTTPBadRequestException("Account is disabled")
            
            # Create session
            session_id = session_manager.create_session(user.id)
            
            # Set session cookie
            response.set_cookie(
                "session_id",
                session_id,
                max_age=3600,
                httponly=True,
                samesite="lax",
                secure=False  # Set to True in production with HTTPS
            )
            
            # Update last login
            user.last_login = datetime.now()
            
            # Redirect to dashboard or home
            response.redirect("/dashboard", status_code=302)
            
        except (ValueError, TypeError) as e:
            raise HTTPBadRequestException(f"Invalid form data: {str(e)}")
```

### Logout Route

**extensions/auth/route_logout.py:**
```python
from serv.routes import PostRequest
from serv.responses import ResponseBuilder
from bevy import dependency
from .sessions import session_manager

async def LogoutPage(
    request: PostRequest,
    response: ResponseBuilder = dependency()
):
    """Handle user logout"""
    
    # Get session ID from cookie
    session_id = request.cookies.get("session_id")
    
    if session_id:
        # Delete session
        session_manager.delete_session(session_id)
    
    # Clear session cookie
    response.set_cookie(
        "session_id",
        "",
        max_age=0,
        httponly=True,
        samesite="lax"
    )
    
    # Redirect to home page
    response.redirect("/", status_code=302)
```

### Registration Route

**extensions/auth/route_register.py:**
```python
from dataclasses import dataclass
from serv.routes import GetRequest, PostRequest
from serv.responses import ResponseBuilder
from serv.exceptions import HTTPBadRequestException
from bevy import dependency
from .models import user_storage
from .sessions import session_manager

@dataclass
class RegisterForm:
    username: str
    email: str
    password: str
    confirm_password: str

async def RegisterPage(
    request: GetRequest | PostRequest,
    response: ResponseBuilder = dependency()
):
    """Handle registration page and form submission"""
    
    if request.method == "GET":
        # Display registration form
        response.content_type("text/html")
        response.body("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Register</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; padding: 20px; }
                .form-group { margin-bottom: 15px; }
                label { display: block; margin-bottom: 5px; }
                input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
                button { background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
                .error { color: red; margin-top: 10px; }
            </style>
        </head>
        <body>
            <h2>Register</h2>
            <form method="post" action="/register">
                <div class="form-group">
                    <label for="username">Username:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                <div class="form-group">
                    <label for="email">Email:</label>
                    <input type="email" id="email" name="email" required>
                </div>
                <div class="form-group">
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <div class="form-group">
                    <label for="confirm_password">Confirm Password:</label>
                    <input type="password" id="confirm_password" name="confirm_password" required>
                </div>
                <button type="submit">Register</button>
            </form>
            <p><a href="/login">Already have an account? Login here</a></p>
        </body>
        </html>
        """)
    
    elif request.method == "POST":
        # Process registration form
        try:
            form_data = await request.form(RegisterForm)
            
            # Validate form data
            if form_data.password != form_data.confirm_password:
                raise HTTPBadRequestException("Passwords do not match")
            
            if len(form_data.password) < 8:
                raise HTTPBadRequestException("Password must be at least 8 characters")
            
            if not form_data.username or len(form_data.username) < 3:
                raise HTTPBadRequestException("Username must be at least 3 characters")
            
            # Create user
            try:
                user = user_storage.create_user(
                    form_data.username,
                    form_data.email,
                    form_data.password
                )
            except ValueError as e:
                raise HTTPBadRequestException(str(e))
            
            # Create session and log in user
            session_id = session_manager.create_session(user.id)
            
            response.set_cookie(
                "session_id",
                session_id,
                max_age=3600,
                httponly=True,
                samesite="lax",
                secure=False
            )
            
            # Redirect to dashboard
            response.redirect("/dashboard", status_code=302)
            
        except (ValueError, TypeError) as e:
            raise HTTPBadRequestException(f"Invalid form data: {str(e)}")
```

### Authentication Middleware

**extensions/auth/middleware_auth_check.py:**
```python
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency
from .models import user_storage
from .sessions import session_manager

async def auth_check_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Authentication middleware"""
    
    # Get middleware configuration
    config = getattr(auth_check_middleware, '_config', {})
    exempt_paths = config.get('exempt_paths', ["/", "/login", "/register", "/public"])
    
    # Skip authentication for exempt paths
    if request.path in exempt_paths or request.path.startswith("/public/"):
        yield
        return
    
    # Get session from cookie
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        # No session, redirect to login
        if request.headers.get("accept", "").startswith("application/json"):
            response.set_status(401)
            response.content_type("application/json")
            response.body('{"error": "Authentication required"}')
        else:
            response.redirect("/login", status_code=302)
        return
    
    # Validate session
    session = session_manager.get_session(session_id)
    if not session:
        # Invalid session, redirect to login
        response.set_cookie("session_id", "", max_age=0)
        if request.headers.get("accept", "").startswith("application/json"):
            response.set_status(401)
            response.content_type("application/json")
            response.body('{"error": "Session expired"}')
        else:
            response.redirect("/login", status_code=302)
        return
    
    # Get user
    user = user_storage.get_user_by_id(session.user_id)
    if not user or not user.is_active:
        # User not found or inactive
        session_manager.delete_session(session_id)
        response.set_cookie("session_id", "", max_age=0)
        response.redirect("/login", status_code=302)
        return
    
    # Add user to request context
    request.context['user'] = user
    request.context['session'] = session
    
    yield  # Continue processing
```

## Token-Based Authentication

### JWT Token Authentication

**extensions/auth/jwt_auth.py:**
```python
import jwt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class TokenPayload:
    user_id: int
    username: str
    exp: datetime
    iat: datetime

class JWTManager:
    def __init__(self, secret_key: str, algorithm: str = "HS256", expiry_hours: int = 24):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expiry_hours = expiry_hours
    
    def create_token(self, user_id: int, username: str) -> str:
        """Create a JWT token for user"""
        now = datetime.utcnow()
        payload = {
            "user_id": user_id,
            "username": username,
            "iat": now,
            "exp": now + timedelta(hours=self.expiry_hours)
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return TokenPayload(
                user_id=payload["user_id"],
                username=payload["username"],
                exp=datetime.fromtimestamp(payload["exp"]),
                iat=datetime.fromtimestamp(payload["iat"])
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def refresh_token(self, token: str) -> Optional[str]:
        """Refresh an existing token"""
        payload = self.verify_token(token)
        if payload:
            return self.create_token(payload.user_id, payload.username)
        return None

# Initialize JWT manager
jwt_manager = JWTManager(secret_key="your-secret-key-change-in-production")
```

### API Token Authentication

**extensions/auth/api_auth.py:**
```python
import secrets
from datetime import datetime
from typing import Optional, Dict
from dataclasses import dataclass

@dataclass
class APIKey:
    key: str
    user_id: int
    name: str
    created_at: datetime
    last_used: Optional[datetime] = None
    is_active: bool = True

class APIKeyManager:
    """Manage API keys for authentication"""
    
    def __init__(self):
        self.api_keys: Dict[str, APIKey] = {}
        
        # Create a demo API key
        demo_key = self.create_api_key(1, "Demo Key")
        print(f"Demo API Key: {demo_key}")
    
    def create_api_key(self, user_id: int, name: str) -> str:
        """Create a new API key for user"""
        key = f"sk_{secrets.token_urlsafe(32)}"
        
        api_key = APIKey(
            key=key,
            user_id=user_id,
            name=name,
            created_at=datetime.now()
        )
        
        self.api_keys[key] = api_key
        return key
    
    def verify_api_key(self, key: str) -> Optional[APIKey]:
        """Verify API key and return associated data"""
        api_key = self.api_keys.get(key)
        
        if api_key and api_key.is_active:
            api_key.last_used = datetime.now()
            return api_key
        
        return None
    
    def revoke_api_key(self, key: str) -> bool:
        """Revoke an API key"""
        if key in self.api_keys:
            self.api_keys[key].is_active = False
            return True
        return False

# Global API key manager
api_key_manager = APIKeyManager()
```

### JWT Authentication Middleware

**extensions/auth/middleware_jwt_auth.py:**
```python
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency
from .jwt_auth import jwt_manager
from .models import user_storage

async def jwt_auth_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """JWT token authentication middleware"""
    
    # Skip auth for public routes
    if request.path.startswith("/public") or request.path in ["/", "/login", "/register"]:
        yield
        return
    
    # Get token from Authorization header
    auth_header = request.headers.get("authorization", "")
    
    if not auth_header.startswith("Bearer "):
        response.set_status(401)
        response.content_type("application/json")
        response.body('{"error": "Missing or invalid authorization header"}')
        return
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    
    # Verify token
    payload = jwt_manager.verify_token(token)
    if not payload:
        response.set_status(401)
        response.content_type("application/json")
        response.body('{"error": "Invalid or expired token"}')
        return
    
    # Get user
    user = user_storage.get_user_by_id(payload.user_id)
    if not user or not user.is_active:
        response.set_status(401)
        response.content_type("application/json")
        response.body('{"error": "User not found or inactive"}')
        return
    
    # Add user to request context
    request.context['user'] = user
    request.context['token_payload'] = payload
    
    yield
```

### API Key Authentication Middleware

**extensions/auth/middleware_api_key.py:**
```python
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency
from .api_auth import api_key_manager
from .models import user_storage

async def api_key_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """API key authentication middleware"""
    
    # Only apply to API routes
    if not request.path.startswith("/api/"):
        yield
        return
    
    # Get API key from header
    api_key = request.headers.get("x-api-key") or request.headers.get("authorization")
    
    if not api_key:
        response.set_status(401)
        response.content_type("application/json")
        response.body('{"error": "API key required"}')
        return
    
    # Remove "Bearer " prefix if present
    if api_key.startswith("Bearer "):
        api_key = api_key[7:]
    
    # Verify API key
    key_data = api_key_manager.verify_api_key(api_key)
    if not key_data:
        response.set_status(401)
        response.content_type("application/json")
        response.body('{"error": "Invalid API key"}')
        return
    
    # Get user
    user = user_storage.get_user_by_id(key_data.user_id)
    if not user or not user.is_active:
        response.set_status(401)
        response.content_type("application/json")
        response.body('{"error": "User not found or inactive"}')
        return
    
    # Add user and API key info to request context
    request.context['user'] = user
    request.context['api_key'] = key_data
    
    yield
```

## Using Authentication in Routes

### Accessing Current User

**extensions/dashboard/route_dashboard.py:**
```python
from serv.routes import GetRequest
from serv.responses import ResponseBuilder
from bevy import dependency

async def Dashboard(
    request: GetRequest,
    response: ResponseBuilder = dependency()
):
    """User dashboard - requires authentication"""
    
    # Get current user from request context (set by auth middleware)
    user = request.context.get('user')
    
    if not user:
        # This shouldn't happen if auth middleware is working
        response.redirect("/login", status_code=302)
        return
    
    response.content_type("text/html")
    response.body(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }}
            .user-info {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Dashboard</h1>
            <form method="post" action="/logout" style="margin: 0;">
                <button type="submit">Logout</button>
            </form>
        </div>
        
        <div class="user-info">
            <h3>Welcome, {user.username}!</h3>
            <p><strong>Email:</strong> {user.email}</p>
            <p><strong>Member since:</strong> {user.created_at.strftime('%B %d, %Y') if user.created_at else 'Unknown'}</p>
            <p><strong>Last login:</strong> {user.last_login.strftime('%B %d, %Y at %I:%M %p') if user.last_login else 'Never'}</p>
        </div>
        
        <h2>Your Account</h2>
        <p>This is your personal dashboard. You can manage your account settings and view your activity here.</p>
        
        <h3>Quick Actions</h3>
        <ul>
            <li><a href="/profile">Edit Profile</a></li>
            <li><a href="/settings">Account Settings</a></li>
            <li><a href="/api/user/profile">View API Profile</a></li>
        </ul>
    </body>
    </html>
    """)
```

### API Endpoints with Authentication

**extensions/api/route_user_profile.py:**
```python
from serv.routes import GetRequest
from serv.responses import ResponseBuilder
from bevy import dependency

async def UserProfile(
    request: GetRequest,
    response: ResponseBuilder = dependency()
):
    """Get current user profile via API"""
    
    user = request.context.get('user')
    
    if not user:
        response.set_status(401)
        response.content_type("application/json")
        response.body('{"error": "Authentication required"}')
        return
    
    # Return user profile data
    profile_data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "is_active": user.is_active
    }
    
    response.content_type("application/json")
    response.body(profile_data)
```

## Role-Based Authorization

### Role System

**extensions/auth/roles.py:**
```python
from enum import Enum
from typing import Set, Dict
from dataclasses import dataclass

class Role(Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
    GUEST = "guest"

class Permission(Enum):
    READ_USERS = "read_users"
    WRITE_USERS = "write_users"
    DELETE_USERS = "delete_users"
    READ_POSTS = "read_posts"
    WRITE_POSTS = "write_posts"
    DELETE_POSTS = "delete_posts"
    MODERATE_CONTENT = "moderate_content"
    ADMIN_ACCESS = "admin_access"

# Role permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        Permission.READ_USERS, Permission.WRITE_USERS, Permission.DELETE_USERS,
        Permission.READ_POSTS, Permission.WRITE_POSTS, Permission.DELETE_POSTS,
        Permission.MODERATE_CONTENT, Permission.ADMIN_ACCESS
    },
    Role.MODERATOR: {
        Permission.READ_USERS, Permission.READ_POSTS, Permission.WRITE_POSTS,
        Permission.MODERATE_CONTENT
    },
    Role.USER: {
        Permission.READ_POSTS, Permission.WRITE_POSTS
    },
    Role.GUEST: {
        Permission.READ_POSTS
    }
}

@dataclass
class UserRole:
    user_id: int
    role: Role

class RoleManager:
    def __init__(self):
        self.user_roles: Dict[int, Role] = {}
        
        # Assign admin role to user ID 1
        self.user_roles[1] = Role.ADMIN
    
    def assign_role(self, user_id: int, role: Role):
        """Assign role to user"""
        self.user_roles[user_id] = role
    
    def get_user_role(self, user_id: int) -> Role:
        """Get user's role"""
        return self.user_roles.get(user_id, Role.GUEST)
    
    def has_permission(self, user_id: int, permission: Permission) -> bool:
        """Check if user has specific permission"""
        role = self.get_user_role(user_id)
        return permission in ROLE_PERMISSIONS.get(role, set())
    
    def require_permission(self, user_id: int, permission: Permission) -> bool:
        """Require user to have specific permission (raises exception if not)"""
        if not self.has_permission(user_id, permission):
            raise PermissionError(f"Permission {permission.value} required")
        return True

# Global role manager
role_manager = RoleManager()
```

### Authorization Middleware

**extensions/auth/middleware_authorization.py:**
```python
from typing import AsyncIterator
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency
from .roles import role_manager, Permission

async def authorization_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    """Authorization middleware for role-based access control"""
    
    user = request.context.get('user')
    
    # Skip authorization for unauthenticated users (handled by auth middleware)
    if not user:
        yield
        return
    
    # Define route permissions
    route_permissions = {
        "/admin": Permission.ADMIN_ACCESS,
        "/api/users": Permission.READ_USERS,
        "/api/admin": Permission.ADMIN_ACCESS,
        "/moderate": Permission.MODERATE_CONTENT
    }
    
    # Check if route requires specific permission
    required_permission = None
    for route_path, permission in route_permissions.items():
        if request.path.startswith(route_path):
            required_permission = permission
            break
    
    if required_permission:
        if not role_manager.has_permission(user.id, required_permission):
            response.set_status(403)
            if request.headers.get("accept", "").startswith("application/json"):
                response.content_type("application/json")
                response.body('{"error": "Insufficient permissions"}')
            else:
                response.content_type("text/html")
                response.body("""
                <h1>Access Denied</h1>
                <p>You don't have permission to access this resource.</p>
                <a href="/dashboard">Return to Dashboard</a>
                """)
            return
    
    # Add role info to request context
    request.context['role'] = role_manager.get_user_role(user.id)
    
    yield
```

## OAuth Integration

### OAuth Provider Setup

**extensions/auth/oauth.py:**
```python
import secrets
import urllib.parse
from typing import Dict, Optional
from dataclasses import dataclass

@dataclass
class OAuthConfig:
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    user_info_url: str
    redirect_uri: str
    scope: str

class OAuthProvider:
    def __init__(self, config: OAuthConfig):
        self.config = config
        self.state_storage: Dict[str, str] = {}  # Use Redis in production
    
    def get_authorization_url(self) -> tuple[str, str]:
        """Generate OAuth authorization URL and state"""
        state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": self.config.scope,
            "response_type": "code",
            "state": state
        }
        
        url = f"{self.config.authorize_url}?{urllib.parse.urlencode(params)}"
        self.state_storage[state] = "pending"
        
        return url, state
    
    def verify_state(self, state: str) -> bool:
        """Verify OAuth state parameter"""
        return state in self.state_storage
    
    async def exchange_code_for_token(self, code: str, state: str) -> Optional[Dict]:
        """Exchange authorization code for access token"""
        if not self.verify_state(state):
            return None
        
        # In a real implementation, make HTTP request to token endpoint
        # This is a simplified example
        return {
            "access_token": "example_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
    
    async def get_user_info(self, access_token: str) -> Optional[Dict]:
        """Get user information from OAuth provider"""
        # In a real implementation, make HTTP request to user info endpoint
        # This is a simplified example
        return {
            "id": "oauth_user_123",
            "email": "user@example.com",
            "name": "OAuth User"
        }

# Example GitHub OAuth configuration
github_oauth = OAuthProvider(OAuthConfig(
    client_id="your_github_client_id",
    client_secret="your_github_client_secret",
    authorize_url="https://github.com/login/oauth/authorize",
    token_url="https://github.com/login/oauth/access_token",
    user_info_url="https://api.github.com/user",
    redirect_uri="http://localhost:8000/auth/github/callback",
    scope="user:email"
))
```

### OAuth Routes

**extensions/auth/route_oauth.py:**
```python
from serv.routes import GetRequest
from serv.responses import ResponseBuilder
from bevy import dependency
from .oauth import github_oauth
from .models import user_storage
from .sessions import session_manager

async def GitHubLogin(
    request: GetRequest,
    response: ResponseBuilder = dependency()
):
    """Initiate GitHub OAuth login"""
    
    auth_url, state = github_oauth.get_authorization_url()
    
    # Store state in session for verification
    response.set_cookie("oauth_state", state, max_age=600, httponly=True)
    
    # Redirect to GitHub
    response.redirect(auth_url, status_code=302)

async def GitHubCallback(
    request: GetRequest,
    response: ResponseBuilder = dependency()
):
    """Handle GitHub OAuth callback"""
    
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    stored_state = request.cookies.get("oauth_state")
    
    if not code or not state or state != stored_state:
        response.set_status(400)
        response.body("Invalid OAuth callback")
        return
    
    # Exchange code for token
    token_data = await github_oauth.exchange_code_for_token(code, state)
    if not token_data:
        response.set_status(400)
        response.body("Failed to exchange code for token")
        return
    
    # Get user info
    user_info = await github_oauth.get_user_info(token_data["access_token"])
    if not user_info:
        response.set_status(400)
        response.body("Failed to get user information")
        return
    
    # Find or create user
    username = f"github_{user_info['id']}"
    user = user_storage.get_user_by_username(username)
    
    if not user:
        # Create new user
        user = user_storage.create_user(
            username=username,
            email=user_info.get("email", ""),
            password=secrets.token_urlsafe(32)  # Random password for OAuth users
        )
    
    # Create session
    session_id = session_manager.create_session(user.id)
    
    # Clear OAuth state cookie and set session cookie
    response.set_cookie("oauth_state", "", max_age=0)
    response.set_cookie(
        "session_id",
        session_id,
        max_age=3600,
        httponly=True,
        samesite="lax"
    )
    
    # Redirect to dashboard
    response.redirect("/dashboard", status_code=302)
```

## Testing Authentication

### Unit Tests

**tests/test_auth.py:**
```python
import pytest
from unittest.mock import Mock
from extensions.auth.models import UserStorage
from extensions.auth.sessions import SessionManager
from extensions.auth.jwt_auth import JWTManager

def test_user_creation():
    """Test user creation and password hashing"""
    storage = UserStorage()
    
    user = storage.create_user("testuser", "test@example.com", "password123")
    
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.password_hash != "password123"  # Should be hashed
    assert storage.verify_password(user, "password123")
    assert not storage.verify_password(user, "wrongpassword")

def test_session_management():
    """Test session creation and validation"""
    manager = SessionManager(timeout_seconds=3600)
    
    session_id = manager.create_session(user_id=1)
    assert session_id is not None
    
    session = manager.get_session(session_id)
    assert session is not None
    assert session.user_id == 1
    
    # Test invalid session
    invalid_session = manager.get_session("invalid_id")
    assert invalid_session is None

def test_jwt_tokens():
    """Test JWT token creation and verification"""
    jwt_manager = JWTManager("test-secret")
    
    token = jwt_manager.create_token(user_id=1, username="testuser")
    assert token is not None
    
    payload = jwt_manager.verify_token(token)
    assert payload is not None
    assert payload.user_id == 1
    assert payload.username == "testuser"
    
    # Test invalid token
    invalid_payload = jwt_manager.verify_token("invalid.token.here")
    assert invalid_payload is None

@pytest.mark.asyncio
async def test_auth_middleware():
    """Test authentication middleware"""
    from extensions.auth.middleware_auth_check import auth_check_middleware
    
    # Mock request without session
    request = Mock()
    request.path = "/protected"
    request.cookies = {}
    request.headers = {}
    
    response = Mock()
    
    middleware_gen = auth_check_middleware(request=request, response=response)
    
    # Should not yield (stops processing)
    with pytest.raises(StopAsyncIteration):
        await middleware_gen.__anext__()
    
    # Should redirect to login
    response.redirect.assert_called_with("/login", status_code=302)
```

### Integration Tests

**tests/test_auth_integration.py:**
```python
import pytest
from httpx import AsyncClient
from serv.app import App

@pytest.mark.asyncio
async def test_login_flow():
    """Test complete login flow"""
    app = App(dev_mode=True)
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test login page
        response = await client.get("/login")
        assert response.status_code == 200
        assert "login" in response.text.lower()
        
        # Test login with valid credentials
        response = await client.post("/login", data={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 302  # Redirect after login
        
        # Check that session cookie was set
        assert "session_id" in response.cookies

@pytest.mark.asyncio
async def test_protected_route():
    """Test access to protected routes"""
    app = App(dev_mode=True)
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test access without authentication
        response = await client.get("/dashboard")
        assert response.status_code == 302  # Redirect to login
        
        # Login first
        login_response = await client.post("/login", data={
            "username": "admin",
            "password": "admin123"
        })
        
        # Test access with authentication
        response = await client.get("/dashboard")
        assert response.status_code == 200
        assert "dashboard" in response.text.lower()

@pytest.mark.asyncio
async def test_api_authentication():
    """Test API authentication with tokens"""
    app = App(dev_mode=True)
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test API without token
        response = await client.get("/api/user/profile")
        assert response.status_code == 401
        
        # Test API with invalid token
        response = await client.get(
            "/api/user/profile",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401
        
        # Test API with valid token (would need to generate real token)
        # This is a simplified test
```

## Best Practices

### 1. Use Secure Session Management

```python
# Good: Secure session configuration
response.set_cookie(
    "session_id",
    session_id,
    max_age=3600,
    httponly=True,      # Prevent XSS
    secure=True,        # HTTPS only in production
    samesite="lax"      # CSRF protection
)

# Avoid: Insecure session cookies
response.set_cookie("session_id", session_id)
```

### 2. Hash Passwords Properly

```python
# Good: Use bcrypt for password hashing
import bcrypt

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Avoid: Simple hashing
import hashlib
def bad_hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()
```

### 3. Implement Rate Limiting

```python
# Good: Rate limit login attempts
from collections import defaultdict
import time

login_attempts = defaultdict(list)

async def rate_limited_login(username: str) -> bool:
    now = time.time()
    attempts = login_attempts[username]
    
    # Remove old attempts (older than 15 minutes)
    attempts[:] = [t for t in attempts if now - t < 900]
    
    # Check if too many attempts
    if len(attempts) >= 5:
        return False
    
    attempts.append(now)
    return True
```

### 4. Validate Input Thoroughly

```python
# Good: Comprehensive input validation
def validate_registration_data(form_data):
    errors = []
    
    if not form_data.username or len(form_data.username) < 3:
        errors.append("Username must be at least 3 characters")
    
    if not re.match(r'^[a-zA-Z0-9_]+$', form_data.username):
        errors.append("Username can only contain letters, numbers, and underscores")
    
    if not form_data.email or '@' not in form_data.email:
        errors.append("Valid email address required")
    
    if len(form_data.password) < 8:
        errors.append("Password must be at least 8 characters")
    
    return errors
```

### 5. Use Environment Variables for Secrets

```python
# Good: Use environment variables
import os

JWT_SECRET = os.getenv("JWT_SECRET", "fallback-secret-for-dev")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app.db")

# Avoid: Hardcoded secrets
JWT_SECRET = "my-secret-key"  # Never do this in production
```

## Development Workflow

### 1. Plan Your Authentication Strategy

Choose the appropriate authentication method:
- Session-based for traditional web apps
- JWT tokens for APIs and SPAs
- OAuth for third-party integration
- API keys for service-to-service communication

### 2. Create Authentication Extension

```bash
serv create extension --name "Auth"
serv create middleware --name "auth_check" --extension "auth"
```

### 3. Implement User Management

Create user models, storage, and management functions.

### 4. Add Authentication Routes

Implement login, logout, and registration routes.

### 5. Secure Your Application

Add authentication middleware and configure security settings.

### 6. Test Thoroughly

Test all authentication flows, edge cases, and security scenarios.

## Next Steps

- **[Forms and Validation](forms.md)** - Secure form handling with authentication
- **[Database Integration](database.md)** - Store user data securely
- **[Testing](testing.md)** - Test authentication flows
- **[Deployment](deployment.md)** - Deploy secure applications 