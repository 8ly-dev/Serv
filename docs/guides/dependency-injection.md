# Dependency Injection

Serv uses the powerful `bevy` library for dependency injection, making your code clean, testable, and maintainable. This guide covers everything you need to know about dependency injection in Serv.

## What is Dependency Injection?

Dependency injection (DI) is a design pattern where objects receive their dependencies from external sources rather than creating them internally. This makes code more modular, testable, and flexible.

### Without DI (tightly coupled)

```python
class UserService:
    def __init__(self):
        self.db = Database()  # Hard dependency
    
    def get_user(self, user_id: int):
        return self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
```

### With DI (loosely coupled)

```python
class UserService:
    def __init__(self, db: Database):
        self.db = db  # Injected dependency
    
    def get_user(self, user_id: int):
        return self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
```

## Basic Dependency Injection

### Using `dependency()`

The simplest way to inject dependencies in Serv is using the `dependency()` function:

```python
from serv.responses import ResponseBuilder
from serv.requests import Request
from bevy import dependency

async def my_handler(
    request: Request = dependency(),
    response: ResponseBuilder = dependency()
):
    response.content_type("text/plain")
    response.body(f"Hello from {request.path}")
```

### Built-in Dependencies

Serv automatically provides several built-in dependencies:

```python
from serv import App
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.extensions.routing import Router
from bevy import dependency, Container

async def handler_with_all_deps(
    request: Request = dependency(),           # Current request
    response: ResponseBuilder = dependency(),  # Response builder
    router: Router = dependency(),            # Current router
    container: Container = dependency(),      # DI container
    app: App = dependency()                   # Application instance
):
    # Use all the dependencies
    pass
```

## Custom Dependencies

### Registering Services

Register your own services in the DI container:

```python
from bevy import dependency

class DatabaseService:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    def query(self, sql: str):
        # Database query implementation
        pass

class MyExtension(Extension):
    async def on_app_startup(self, container: Container = dependency()):
        # Register the database service
        db_service = DatabaseService("postgresql://localhost/mydb")
        container.instances[DatabaseService] = db_service
    
    async def on_app_request_begin(self, router: Router = dependency()):
        router.add_route("/users", self.list_users)
    
    async def list_users(
        self,
        db: DatabaseService = dependency(),
        response: ResponseBuilder = dependency()
    ):
        users = db.query("SELECT * FROM users")
        response.content_type("application/json")
        response.body(json.dumps(users))
```

### Factory Functions

Use factory functions for complex object creation:

```python
from bevy import dependency

def create_email_service(config: dict) -> EmailService:
    return EmailService(
        smtp_host=config.get('smtp_host'),
        smtp_port=config.get('smtp_port'),
        username=config.get('smtp_user'),
        password=config.get('smtp_password')
    )

class EmailExtension(Extension):
    async def on_app_startup(self, container: Container = dependency()):
        config = self.get_config()
        email_service = create_email_service(config)
        container.instances[EmailService] = email_service
```

## Advanced Dependency Injection

### Interface-Based Dependencies

Use abstract base classes for better testability:

```python
from abc import ABC, abstractmethod

class UserRepository(ABC):
    @abstractmethod
    async def get_user(self, user_id: int) -> User:
        pass
    
    @abstractmethod
    async def create_user(self, user_data: dict) -> User:
        pass

class DatabaseUserRepository(UserRepository):
    def __init__(self, db: Database):
        self.db = db
    
    async def get_user(self, user_id: int) -> User:
        # Database implementation
        pass
    
    async def create_user(self, user_data: dict) -> User:
        # Database implementation
        pass

class InMemoryUserRepository(UserRepository):
    def __init__(self):
        self.users = {}
    
    async def get_user(self, user_id: int) -> User:
        # In-memory implementation
        pass
    
    async def create_user(self, user_data: dict) -> User:
        # In-memory implementation
        pass

# Register the implementation
class UserExtension(Extension):
    async def on_app_startup(self, container: Container = dependency()):
        # Use database implementation in production
        db = container.get(Database)
        user_repo = DatabaseUserRepository(db)
        container.instances[UserRepository] = user_repo
```

### Conditional Dependencies

Register different implementations based on configuration:

```python
class StorageExtension(Extension):
    async def on_app_startup(self, container: Container = dependency()):
        config = self.get_config()
        storage_type = config.get('storage_type', 'local')
        
        if storage_type == 'local':
            storage = LocalFileStorage(config.get('local_path', './uploads'))
        elif storage_type == 's3':
            storage = S3Storage(
                bucket=config.get('s3_bucket'),
                access_key=config.get('s3_access_key'),
                secret_key=config.get('s3_secret_key')
            )
        else:
            raise ValueError(f"Unknown storage type: {storage_type}")
        
        container.instances[FileStorage] = storage
```

### Scoped Dependencies

Create request-scoped dependencies that are unique per request:

```python
class RequestScopedService:
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.data = {}
    
    def store(self, key: str, value: any):
        self.data[key] = value
    
    def get(self, key: str):
        return self.data.get(key)

class ScopedExtension(Extension):
    async def on_app_request_begin(
        self,
        container: Container = dependency(),
        request: Request = dependency()
    ):
        # Create a request-scoped service
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        scoped_service = RequestScopedService(request_id)
        container.instances[RequestScopedService] = scoped_service
```

## Dependency Injection in Different Contexts

### In Route Handlers

```python
async def user_handler(
    user_id: str,
    user_service: UserService = dependency(),
    response: ResponseBuilder = dependency()
):
    user = await user_service.get_user(int(user_id))
    if user:
        response.content_type("application/json")
        response.body(json.dumps(user.to_dict()))
    else:
        response.set_status(404)
        response.body("User not found")
```

### In Class-Based Routes

```python
from serv.routes import Route

class UserRoute(Route):
    async def get_user(
        self,
        request: GetRequest,
        user_service: UserService = dependency(),
        response: ResponseBuilder = dependency()
    ):
        user_id = request.path_params.get('user_id')
        user = await user_service.get_user(int(user_id))
        # Handle response...
    
    async def create_user(
        self,
        form: CreateUserForm,
        user_service: UserService = dependency(),
        response: ResponseBuilder = dependency()
    ):
        user = await user_service.create_user(form.to_dict())
        # Handle response...
```

### In Middleware

```python
from typing import AsyncIterator

async def auth_middleware(
    request: Request = dependency(),
    auth_service: AuthService = dependency(),
    response: ResponseBuilder = dependency()
) -> AsyncIterator[None]:
    # Check authentication before request
    token = request.headers.get('Authorization')
    if not token or not auth_service.validate_token(token):
        response.set_status(401)
        response.body("Unauthorized")
        return
    
    # Set current user in request context
    user = auth_service.get_user_from_token(token)
    request.context['current_user'] = user
    
    yield  # Process the request
    
    # Cleanup after request if needed
```

### In Extension Event Handlers

```python
class MyExtension(Extension):
    async def on_app_startup(
        self,
        container: Container = dependency(),
        app: App = dependency()
    ):
        # Initialize services
        config = self.get_config()
        service = MyService(config)
        container.instances[MyService] = service
    
    async def on_app_request_begin(
        self,
        router: Router = dependency(),
        my_service: MyService = dependency()
    ):
        # Use the service to configure routes
        if my_service.is_enabled():
            router.add_route("/my-route", self.my_handler)
```

## Testing with Dependency Injection

### Mocking Dependencies

DI makes testing much easier by allowing you to mock dependencies:

```python
import pytest
from unittest.mock import Mock, AsyncMock
from bevy import Container

@pytest.mark.asyncio
async def test_user_handler():
    # Create mocks
    mock_user_service = Mock(spec=UserService)
    mock_user_service.get_user = AsyncMock(return_value=User(id=1, name="John"))
    
    mock_response = Mock(spec=ResponseBuilder)
    
    # Create container with mocked dependencies
    container = Container()
    container.instances[UserService] = mock_user_service
    container.instances[ResponseBuilder] = mock_response
    
    # Test the handler
    await container.call(user_handler, user_id="1")
    
    # Verify interactions
    mock_user_service.get_user.assert_called_once_with(1)
    mock_response.content_type.assert_called_once_with("application/json")
```

### Test Fixtures

Create reusable test fixtures:

```python
@pytest.fixture
def mock_user_service():
    service = Mock(spec=UserService)
    service.get_user = AsyncMock()
    service.create_user = AsyncMock()
    return service

@pytest.fixture
def test_container(mock_user_service):
    container = Container()
    container.instances[UserService] = mock_user_service
    return container

@pytest.mark.asyncio
async def test_create_user(test_container, mock_user_service):
    mock_user_service.create_user.return_value = User(id=1, name="John")
    
    # Test using the container
    result = await test_container.call(create_user_handler, user_data={"name": "John"})
    
    assert result is not None
    mock_user_service.create_user.assert_called_once()
```

## Best Practices

### 1. Use Type Hints

Always use type hints for better IDE support and clarity:

```python
async def handler(
    user_service: UserService = dependency(),  # Clear type
    response: ResponseBuilder = dependency()
) -> None:  # Clear return type
    pass
```

### 2. Prefer Interfaces

Use abstract base classes for better testability:

```python
from abc import ABC, abstractmethod

class EmailService(ABC):
    @abstractmethod
    async def send_email(self, to: str, subject: str, body: str) -> bool:
        pass

class SMTPEmailService(EmailService):
    async def send_email(self, to: str, subject: str, body: str) -> bool:
        # SMTP implementation
        pass

class MockEmailService(EmailService):
    async def send_email(self, to: str, subject: str, body: str) -> bool:
        # Mock implementation for testing
        return True
```

### 3. Register Dependencies Early

Register dependencies during application startup:

```python
class MyExtension(Extension):
    async def on_app_startup(self, container: Container = dependency()):
        # Register all services early
        container.instances[UserService] = UserService()
        container.instances[EmailService] = SMTPEmailService()
        container.instances[CacheService] = RedisCache()
```

### 4. Avoid Circular Dependencies

Be careful about circular dependencies:

```python
# Bad: Circular dependency
class UserService:
    def __init__(self, order_service: OrderService):
        self.order_service = order_service

class OrderService:
    def __init__(self, user_service: UserService):
        self.user_service = user_service

# Good: Use events or interfaces to break the cycle
class UserService:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    def create_user(self, user_data):
        user = User(**user_data)
        self.event_bus.emit('user.created', user)
        return user

class OrderService:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.event_bus.subscribe('user.created', self.on_user_created)
    
    def on_user_created(self, user):
        # Handle user creation
        pass
```

### 5. Use Factory Functions for Complex Setup

For complex object creation, use factory functions:

```python
def create_database_service(config: dict) -> DatabaseService:
    connection_pool = create_connection_pool(
        host=config['db_host'],
        port=config['db_port'],
        database=config['db_name'],
        username=config['db_user'],
        password=config['db_password'],
        pool_size=config.get('db_pool_size', 10)
    )
    
    return DatabaseService(connection_pool)

class DatabaseExtension(Extension):
    async def on_app_startup(self, container: Container = dependency()):
        config = self.get_config()
        db_service = create_database_service(config)
        container.instances[DatabaseService] = db_service
```

## Common Patterns

### Service Locator Pattern

Sometimes you need to access the container directly:

```python
from bevy import dependency

class ServiceLocator:
    def __init__(self, container: Container):
        self.container = container
    
    def get_service(self, service_type: type):
        return self.container.get(service_type)

class MyExtension(Extension):
    async def on_app_startup(self, container: Container = dependency()):
        locator = ServiceLocator(container)
        container.instances[ServiceLocator] = locator
```

### Configuration Injection

Inject configuration objects:

```python
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    host: str
    port: int
    database: str
    username: str
    password: str

class DatabaseExtension(Extension):
    async def on_app_startup(self, container: Container = dependency()):
        config_dict = self.get_config()
        db_config = DatabaseConfig(**config_dict)
        container.instances[DatabaseConfig] = db_config
        
        # Use config to create service
        db_service = DatabaseService(db_config)
        container.instances[DatabaseService] = db_service

async def handler(
    db_config: DatabaseConfig = dependency(),
    response: ResponseBuilder = dependency()
):
    response.body(f"Connected to {db_config.host}:{db_config.port}")
```

## Next Steps

- **[Extensions](extensions.md)** - Learn how to create extensions that use DI
- **[Middleware](middleware.md)** - Use DI in middleware
- **[Testing](testing.md)** - Test code that uses dependency injection
- **[Routing](routing.md)** - Use DI in route handlers 