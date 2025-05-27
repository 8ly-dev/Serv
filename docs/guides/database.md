# Database Integration

Serv provides flexible database integration patterns that work with any database library. This guide covers how to connect to databases, manage connections, implement data models, and follow best practices for database operations in Serv applications.

## Overview

Serv's database integration approach:

1. **Extension-Based**: Database connections are managed within extensions
2. **Dependency Injection**: Database connections are injected into route handlers
3. **Flexible**: Works with any Python database library (asyncpg, SQLAlchemy, etc.)
4. **Connection Pooling**: Efficient connection management for production
5. **Transaction Support**: Middleware for automatic transaction handling

## Database Setup

### Creating a Database Extension

Use the CLI to create a database extension:

```bash
# Create a database extension
serv create extension --name "Database"
```

### Basic Database Extension Structure

**extensions/database/extension.yaml:**
```yaml
name: Database
description: Database connection and management
version: 1.0.0
author: Your Name

settings:
  database_url: "sqlite:///app.db"
  pool_size: 10
  max_overflow: 20
```

**extensions/database/database.py:**
```python
import asyncpg
from serv.extensions import Extension
from bevy import dependency

class Database(Extension):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        config = self.__extension_spec__.config
        self.database_url = config.get("database_url", "sqlite:///app.db")
        self.pool_size = config.get("pool_size", 10)
        self.max_overflow = config.get("max_overflow", 20)
        self.pool = None
    
    async def on_app_startup(self):
        """Initialize database connection pool"""
        if self.database_url.startswith("postgresql://"):
            # PostgreSQL with asyncpg
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=self.pool_size
            )
            print(f"PostgreSQL pool created: {self.database_url}")
        else:
            # For SQLite or other databases, implement accordingly
            print(f"Database initialized: {self.database_url}")
        
        # Make pool available to route handlers via dependency injection
        from serv.app import get_current_app
        app = get_current_app()
        app._container.instances[asyncpg.Pool] = self.pool
    
    async def on_app_shutdown(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            print("Database pool closed")
```

## PostgreSQL with asyncpg

### Setup and Configuration

Install asyncpg:

```bash
pip install asyncpg
```

**extensions/database/database.py:**
```python
import asyncpg
from serv.extensions import Extension
from bevy import dependency
from typing import Optional

class PostgreSQLExtension(Extension):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        config = self.__extension_spec__.config
        self.database_url = config.get("database_url")
        self.min_size = config.get("min_size", 1)
        self.max_size = config.get("max_size", 10)
        self.pool: Optional[asyncpg.Pool] = None
    
    async def on_app_startup(self):
        """Initialize PostgreSQL connection pool"""
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=self.min_size,
            max_size=self.max_size,
            command_timeout=60
        )
        print(f"PostgreSQL pool created with {self.max_size} max connections")
        
        # Register pool for dependency injection
        from serv.app import get_current_app
        app = get_current_app()
        app._container.instances[asyncpg.Pool] = self.pool
        
        # Run database migrations
        await self._run_migrations()
    
    async def on_app_shutdown(self):
        """Close PostgreSQL connection pool"""
        if self.pool:
            await self.pool.close()
            print("PostgreSQL pool closed")
    
    async def _run_migrations(self):
        """Run database migrations on startup"""
        async with self.pool.acquire() as connection:
            # Create tables if they don't exist
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    author_id INTEGER REFERENCES users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            print("Database migrations completed")
```

### Using PostgreSQL in Routes

**extensions/blog/route_posts.py:**
```python
import asyncpg
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime
from serv.responses import ResponseBuilder
from serv.exceptions import HTTPNotFoundException, HTTPBadRequestException
from bevy import dependency

@dataclass
class Post:
    id: int
    title: str
    content: str
    author_id: int
    created_at: datetime
    updated_at: datetime

async def PostList(
    db_pool: asyncpg.Pool = dependency(),
    response: ResponseBuilder = dependency()
):
    """Get all posts"""
    async with db_pool.acquire() as connection:
        rows = await connection.fetch("""
            SELECT p.id, p.title, p.content, p.author_id, 
                   p.created_at, p.updated_at, u.username
            FROM posts p
            JOIN users u ON p.author_id = u.id
            ORDER BY p.created_at DESC
        """)
        
        posts = []
        for row in rows:
            posts.append({
                "id": row["id"],
                "title": row["title"],
                "content": row["content"][:200] + "..." if len(row["content"]) > 200 else row["content"],
                "author": row["username"],
                "created_at": row["created_at"].isoformat()
            })
        
        response.content_type("application/json")
        response.body({"posts": posts})

async def PostDetail(
    post_id: str,
    db_pool: asyncpg.Pool = dependency(),
    response: ResponseBuilder = dependency()
):
    """Get a specific post"""
    try:
        post_id_int = int(post_id)
    except ValueError:
        raise HTTPBadRequestException("Invalid post ID")
    
    async with db_pool.acquire() as connection:
        row = await connection.fetchrow("""
            SELECT p.id, p.title, p.content, p.author_id,
                   p.created_at, p.updated_at, u.username
            FROM posts p
            JOIN users u ON p.author_id = u.id
            WHERE p.id = $1
        """, post_id_int)
        
        if not row:
            raise HTTPNotFoundException(f"Post {post_id} not found")
        
        post = {
            "id": row["id"],
            "title": row["title"],
            "content": row["content"],
            "author": row["username"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat()
        }
        
        response.content_type("application/json")
        response.body(post)

async def CreatePost(
    request: PostRequest,
    db_pool: asyncpg.Pool = dependency(),
    response: ResponseBuilder = dependency()
):
    """Create a new post"""
    form_data = await request.form()
    
    title = form_data.get("title", [""])[0]
    content = form_data.get("content", [""])[0]
    author_id = int(form_data.get("author_id", ["1"])[0])  # In real app, get from session
    
    if not title or not content:
        raise HTTPBadRequestException("Title and content are required")
    
    async with db_pool.acquire() as connection:
        row = await connection.fetchrow("""
            INSERT INTO posts (title, content, author_id)
            VALUES ($1, $2, $3)
            RETURNING id, created_at
        """, title, content, author_id)
        
        response.content_type("application/json")
        response.body({
            "id": row["id"],
            "title": title,
            "content": content,
            "author_id": author_id,
            "created_at": row["created_at"].isoformat()
        })
```

## SQLite Integration

### SQLite Extension

**extensions/database/sqlite_extension.py:**
```python
import sqlite3
import aiosqlite
from serv.extensions import Extension
from bevy import dependency
from pathlib import Path

class SQLiteExtension(Extension):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        config = self.__extension_spec__.config
        self.database_path = config.get("database_path", "app.db")
        self.connection = None
    
    async def on_app_startup(self):
        """Initialize SQLite database"""
        # Ensure database directory exists
        db_path = Path(self.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create connection
        self.connection = await aiosqlite.connect(self.database_path)
        
        # Enable foreign keys
        await self.connection.execute("PRAGMA foreign_keys = ON")
        
        # Register connection for dependency injection
        from serv.app import get_current_app
        app = get_current_app()
        app._container.instances[aiosqlite.Connection] = self.connection
        
        # Run migrations
        await self._run_migrations()
        
        print(f"SQLite database initialized: {self.database_path}")
    
    async def on_app_shutdown(self):
        """Close SQLite connection"""
        if self.connection:
            await self.connection.close()
            print("SQLite connection closed")
    
    async def _run_migrations(self):
        """Run database migrations"""
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author_id INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self.connection.commit()
        print("SQLite migrations completed")
```

### Using SQLite in Routes

**extensions/blog/route_sqlite_posts.py:**
```python
import aiosqlite
from serv.responses import ResponseBuilder
from serv.exceptions import HTTPNotFoundException, HTTPBadRequestException
from bevy import dependency

async def SQLitePostList(
    db: aiosqlite.Connection = dependency(),
    response: ResponseBuilder = dependency()
):
    """Get all posts from SQLite"""
    cursor = await db.execute("""
        SELECT p.id, p.title, p.content, p.author_id,
               p.created_at, u.username
        FROM posts p
        JOIN users u ON p.author_id = u.id
        ORDER BY p.created_at DESC
    """)
    
    rows = await cursor.fetchall()
    
    posts = []
    for row in rows:
        posts.append({
            "id": row[0],
            "title": row[1],
            "content": row[2][:200] + "..." if len(row[2]) > 200 else row[2],
            "author": row[5],
            "created_at": row[4]
        })
    
    response.content_type("application/json")
    response.body({"posts": posts})

async def SQLiteCreatePost(
    request: PostRequest,
    db: aiosqlite.Connection = dependency(),
    response: ResponseBuilder = dependency()
):
    """Create a new post in SQLite"""
    form_data = await request.form()
    
    title = form_data.get("title", [""])[0]
    content = form_data.get("content", [""])[0]
    author_id = int(form_data.get("author_id", ["1"])[0])
    
    if not title or not content:
        raise HTTPBadRequestException("Title and content are required")
    
    cursor = await db.execute("""
        INSERT INTO posts (title, content, author_id)
        VALUES (?, ?, ?)
    """, (title, content, author_id))
    
    await db.commit()
    
    response.content_type("application/json")
    response.body({
        "id": cursor.lastrowid,
        "title": title,
        "content": content,
        "author_id": author_id
    })
```

## SQLAlchemy Integration

### SQLAlchemy Extension

Install SQLAlchemy:

```bash
pip install sqlalchemy[asyncio] aiopg  # For PostgreSQL
# or
pip install sqlalchemy[asyncio] aiosqlite  # For SQLite
```

**extensions/database/sqlalchemy_extension.py:**
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from datetime import datetime
from serv.extensions import Extension
from bevy import dependency

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="author")

class Post(Base):
    __tablename__ = "posts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    author: Mapped[User] = relationship("User", back_populates="posts")

class SQLAlchemyExtension(Extension):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        config = self.__extension_spec__.config
        self.database_url = config.get("database_url")
        self.engine = None
        self.session_factory = None
    
    async def on_app_startup(self):
        """Initialize SQLAlchemy engine and session factory"""
        self.engine = create_async_engine(
            self.database_url,
            echo=True,  # Set to False in production
            pool_size=10,
            max_overflow=20
        )
        
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Register session factory for dependency injection
        from serv.app import get_current_app
        app = get_current_app()
        app._container.instances[async_sessionmaker] = self.session_factory
        
        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("SQLAlchemy initialized")
    
    async def on_app_shutdown(self):
        """Close SQLAlchemy engine"""
        if self.engine:
            await self.engine.dispose()
            print("SQLAlchemy engine disposed")
```

### Using SQLAlchemy in Routes

**extensions/blog/route_sqlalchemy_posts.py:**
```python
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select
from serv.responses import ResponseBuilder
from serv.exceptions import HTTPNotFoundException, HTTPBadRequestException
from bevy import dependency
from .models import User, Post

async def SQLAlchemyPostList(
    session_factory: async_sessionmaker = dependency(),
    response: ResponseBuilder = dependency()
):
    """Get all posts using SQLAlchemy"""
    async with session_factory() as session:
        stmt = select(Post, User).join(User).order_by(Post.created_at.desc())
        result = await session.execute(stmt)
        
        posts = []
        for post, user in result:
            posts.append({
                "id": post.id,
                "title": post.title,
                "content": post.content[:200] + "..." if len(post.content) > 200 else post.content,
                "author": user.username,
                "created_at": post.created_at.isoformat()
            })
        
        response.content_type("application/json")
        response.body({"posts": posts})

async def SQLAlchemyPostDetail(
    post_id: str,
    session_factory: async_sessionmaker = dependency(),
    response: ResponseBuilder = dependency()
):
    """Get a specific post using SQLAlchemy"""
    try:
        post_id_int = int(post_id)
    except ValueError:
        raise HTTPBadRequestException("Invalid post ID")
    
    async with session_factory() as session:
        stmt = select(Post, User).join(User).where(Post.id == post_id_int)
        result = await session.execute(stmt)
        row = result.first()
        
        if not row:
            raise HTTPNotFoundException(f"Post {post_id} not found")
        
        post, user = row
        
        response.content_type("application/json")
        response.body({
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "author": user.username,
            "created_at": post.created_at.isoformat(),
            "updated_at": post.updated_at.isoformat()
        })

async def SQLAlchemyCreatePost(
    request: PostRequest,
    session_factory: async_sessionmaker = dependency(),
    response: ResponseBuilder = dependency()
):
    """Create a new post using SQLAlchemy"""
    form_data = await request.form()
    
    title = form_data.get("title", [""])[0]
    content = form_data.get("content", [""])[0]
    author_id = int(form_data.get("author_id", ["1"])[0])
    
    if not title or not content:
        raise HTTPBadRequestException("Title and content are required")
    
    async with session_factory() as session:
        # Verify author exists
        author = await session.get(User, author_id)
        if not author:
            raise HTTPBadRequestException("Invalid author ID")
        
        # Create new post
        post = Post(title=title, content=content, author_id=author_id)
        session.add(post)
        await session.commit()
        await session.refresh(post)
        
        response.content_type("application/json")
        response.body({
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "author_id": post.author_id,
            "created_at": post.created_at.isoformat()
        })
```

## Database Middleware

### Transaction Middleware

Create middleware to automatically handle database transactions:

```bash
serv create middleware --name "database_transaction" --extension "database"
```

**extensions/database/middleware_database_transaction.py:**
```python
from typing import AsyncIterator
import asyncpg
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency

async def database_transaction_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency(),
    db_pool: asyncpg.Pool = dependency()
) -> AsyncIterator[None]:
    """Wrap requests in database transactions"""
    
    # Only use transactions for write operations
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        async with db_pool.acquire() as connection:
            async with connection.transaction():
                # Make connection available to route handlers
                request.context['db_connection'] = connection
                
                try:
                    yield  # Process the request
                    # Transaction commits automatically if no exception
                except Exception:
                    # Transaction rolls back automatically on exception
                    raise
    else:
        # For read operations, just use a connection from the pool
        async with db_pool.acquire() as connection:
            request.context['db_connection'] = connection
            yield
```

### Session Middleware for SQLAlchemy

**extensions/database/middleware_sqlalchemy_session.py:**
```python
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency

async def sqlalchemy_session_middleware(
    request: Request = dependency(),
    response: ResponseBuilder = dependency(),
    session_factory: async_sessionmaker = dependency()
) -> AsyncIterator[None]:
    """Provide SQLAlchemy session for each request"""
    
    async with session_factory() as session:
        # Make session available to route handlers
        request.context['db_session'] = session
        
        try:
            yield  # Process the request
            
            # Commit for write operations
            if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
                await session.commit()
                
        except Exception:
            # Rollback on error
            await session.rollback()
            raise
```

## Data Models and Repositories

### Repository Pattern

Create repository classes for clean data access:

**extensions/blog/repositories.py:**
```python
from typing import List, Optional
import asyncpg
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Post:
    id: Optional[int]
    title: str
    content: str
    author_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class User:
    id: Optional[int]
    username: str
    email: str
    password_hash: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class PostRepository:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
    
    async def get_all(self) -> List[Post]:
        """Get all posts"""
        async with self.db_pool.acquire() as connection:
            rows = await connection.fetch("""
                SELECT id, title, content, author_id, created_at, updated_at
                FROM posts
                ORDER BY created_at DESC
            """)
            
            return [Post(**dict(row)) for row in rows]
    
    async def get_by_id(self, post_id: int) -> Optional[Post]:
        """Get post by ID"""
        async with self.db_pool.acquire() as connection:
            row = await connection.fetchrow("""
                SELECT id, title, content, author_id, created_at, updated_at
                FROM posts
                WHERE id = $1
            """, post_id)
            
            return Post(**dict(row)) if row else None
    
    async def create(self, post: Post) -> Post:
        """Create a new post"""
        async with self.db_pool.acquire() as connection:
            row = await connection.fetchrow("""
                INSERT INTO posts (title, content, author_id)
                VALUES ($1, $2, $3)
                RETURNING id, created_at, updated_at
            """, post.title, post.content, post.author_id)
            
            post.id = row["id"]
            post.created_at = row["created_at"]
            post.updated_at = row["updated_at"]
            
            return post
    
    async def update(self, post: Post) -> Post:
        """Update an existing post"""
        async with self.db_pool.acquire() as connection:
            row = await connection.fetchrow("""
                UPDATE posts
                SET title = $1, content = $2, updated_at = CURRENT_TIMESTAMP
                WHERE id = $3
                RETURNING updated_at
            """, post.title, post.content, post.id)
            
            post.updated_at = row["updated_at"]
            return post
    
    async def delete(self, post_id: int) -> bool:
        """Delete a post"""
        async with self.db_pool.acquire() as connection:
            result = await connection.execute("""
                DELETE FROM posts WHERE id = $1
            """, post_id)
            
            return result == "DELETE 1"

class UserRepository:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        async with self.db_pool.acquire() as connection:
            row = await connection.fetchrow("""
                SELECT id, username, email, password_hash, created_at, updated_at
                FROM users
                WHERE username = $1
            """, username)
            
            return User(**dict(row)) if row else None
    
    async def create(self, user: User) -> User:
        """Create a new user"""
        async with self.db_pool.acquire() as connection:
            row = await connection.fetchrow("""
                INSERT INTO users (username, email, password_hash)
                VALUES ($1, $2, $3)
                RETURNING id, created_at, updated_at
            """, user.username, user.email, user.password_hash)
            
            user.id = row["id"]
            user.created_at = row["created_at"]
            user.updated_at = row["updated_at"]
            
            return user
```

### Using Repositories in Routes

**extensions/blog/route_repository_posts.py:**
```python
import asyncpg
from serv.responses import ResponseBuilder
from serv.exceptions import HTTPNotFoundException, HTTPBadRequestException
from bevy import dependency
from .repositories import PostRepository, Post

async def RepositoryPostList(
    db_pool: asyncpg.Pool = dependency(),
    response: ResponseBuilder = dependency()
):
    """Get all posts using repository pattern"""
    repo = PostRepository(db_pool)
    posts = await repo.get_all()
    
    posts_data = [
        {
            "id": post.id,
            "title": post.title,
            "content": post.content[:200] + "..." if len(post.content) > 200 else post.content,
            "author_id": post.author_id,
            "created_at": post.created_at.isoformat() if post.created_at else None
        }
        for post in posts
    ]
    
    response.content_type("application/json")
    response.body({"posts": posts_data})

async def RepositoryCreatePost(
    request: PostRequest,
    db_pool: asyncpg.Pool = dependency(),
    response: ResponseBuilder = dependency()
):
    """Create a new post using repository pattern"""
    form_data = await request.form()
    
    title = form_data.get("title", [""])[0]
    content = form_data.get("content", [""])[0]
    author_id = int(form_data.get("author_id", ["1"])[0])
    
    if not title or not content:
        raise HTTPBadRequestException("Title and content are required")
    
    repo = PostRepository(db_pool)
    post = Post(
        id=None,
        title=title,
        content=content,
        author_id=author_id
    )
    
    created_post = await repo.create(post)
    
    response.content_type("application/json")
    response.body({
        "id": created_post.id,
        "title": created_post.title,
        "content": created_post.content,
        "author_id": created_post.author_id,
        "created_at": created_post.created_at.isoformat()
    })
```

## Database Migrations

### Simple Migration System

**extensions/database/migrations.py:**
```python
import asyncpg
from typing import List, Callable
from dataclasses import dataclass

@dataclass
class Migration:
    version: str
    description: str
    up: Callable
    down: Callable

class MigrationRunner:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.migrations: List[Migration] = []
    
    def add_migration(self, version: str, description: str, up: Callable, down: Callable):
        """Add a migration"""
        migration = Migration(version, description, up, down)
        self.migrations.append(migration)
    
    async def run_migrations(self):
        """Run all pending migrations"""
        async with self.db_pool.acquire() as connection:
            # Create migrations table if it doesn't exist
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    version VARCHAR(50) PRIMARY KEY,
                    description TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Get applied migrations
            applied = await connection.fetch("SELECT version FROM migrations")
            applied_versions = {row["version"] for row in applied}
            
            # Run pending migrations
            for migration in sorted(self.migrations, key=lambda m: m.version):
                if migration.version not in applied_versions:
                    print(f"Running migration {migration.version}: {migration.description}")
                    
                    async with connection.transaction():
                        await migration.up(connection)
                        await connection.execute("""
                            INSERT INTO migrations (version, description)
                            VALUES ($1, $2)
                        """, migration.version, migration.description)
                    
                    print(f"Migration {migration.version} completed")

# Example migrations
async def create_users_table(connection):
    await connection.execute("""
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

async def create_posts_table(connection):
    await connection.execute("""
        CREATE TABLE posts (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            content TEXT NOT NULL,
            author_id INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

async def add_posts_index(connection):
    await connection.execute("""
        CREATE INDEX idx_posts_author_id ON posts(author_id);
        CREATE INDEX idx_posts_created_at ON posts(created_at);
    """)

# Register migrations
def setup_migrations(runner: MigrationRunner):
    runner.add_migration(
        "001", 
        "Create users table", 
        create_users_table, 
        lambda conn: conn.execute("DROP TABLE users")
    )
    
    runner.add_migration(
        "002", 
        "Create posts table", 
        create_posts_table, 
        lambda conn: conn.execute("DROP TABLE posts")
    )
    
    runner.add_migration(
        "003", 
        "Add posts indexes", 
        add_posts_index, 
        lambda conn: conn.execute("DROP INDEX idx_posts_author_id, idx_posts_created_at")
    )
```

## Configuration Management

### Environment-Based Configuration

**serv.config.yaml:**
```yaml
site_info:
  name: "My Blog App"
  description: "A blog built with Serv"

extensions:
  - extension: database
    settings:
      database_url: "${DATABASE_URL:postgresql://localhost/myapp}"
      pool_size: "${DB_POOL_SIZE:10}"
      max_overflow: "${DB_MAX_OVERFLOW:20}"
```

**Production configuration (serv.prod.config.yaml):**
```yaml
site_info:
  name: "My Blog App"
  description: "A blog built with Serv"

extensions:
  - extension: database
    settings:
      database_url: "${DATABASE_URL}"
      pool_size: 20
      max_overflow: 40
      ssl_mode: "require"
```

### Database Configuration Extension

**extensions/database/config.py:**
```python
import os
from serv.extensions import Extension

class DatabaseConfig:
    def __init__(self, config: dict):
        self.database_url = self._resolve_env_var(config.get("database_url"))
        self.pool_size = int(self._resolve_env_var(config.get("pool_size", "10")))
        self.max_overflow = int(self._resolve_env_var(config.get("max_overflow", "20")))
        self.ssl_mode = config.get("ssl_mode", "prefer")
    
    def _resolve_env_var(self, value: str) -> str:
        """Resolve environment variables in configuration values"""
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            # Extract variable name and default value
            var_spec = value[2:-1]  # Remove ${ and }
            if ":" in var_spec:
                var_name, default_value = var_spec.split(":", 1)
                return os.getenv(var_name, default_value)
            else:
                return os.getenv(var_spec, "")
        return value
```

## Testing with Databases

### Test Database Setup

**tests/conftest.py:**
```python
import pytest
import asyncpg
from serv.app import App

@pytest.fixture
async def test_db_pool():
    """Create a test database pool"""
    pool = await asyncpg.create_pool(
        "postgresql://localhost/test_db",
        min_size=1,
        max_size=5
    )
    
    # Clean up tables before each test
    async with pool.acquire() as connection:
        await connection.execute("TRUNCATE TABLE posts, users RESTART IDENTITY CASCADE")
    
    yield pool
    
    await pool.close()

@pytest.fixture
async def test_app_with_db(test_db_pool):
    """Create test app with database"""
    app = App(dev_mode=True)
    
    # Override database pool
    app._container.instances[asyncpg.Pool] = test_db_pool
    
    return app
```

### Database Integration Tests

**tests/test_database_integration.py:**
```python
import pytest
import asyncpg
from httpx import AsyncClient
from serv.app import App

@pytest.mark.asyncio
async def test_create_and_get_post(test_app_with_db, test_db_pool):
    """Test creating and retrieving a post"""
    
    # Create a test user first
    async with test_db_pool.acquire() as connection:
        user_id = await connection.fetchval("""
            INSERT INTO users (username, email, password_hash)
            VALUES ('testuser', 'test@example.com', 'hash')
            RETURNING id
        """)
    
    async with AsyncClient(app=test_app_with_db, base_url="http://test") as client:
        # Create a post
        response = await client.post("/posts", data={
            "title": "Test Post",
            "content": "This is a test post",
            "author_id": str(user_id)
        })
        
        assert response.status_code == 200
        post_data = response.json()
        assert post_data["title"] == "Test Post"
        
        # Get the post
        response = await client.get(f"/posts/{post_data['id']}")
        assert response.status_code == 200
        retrieved_post = response.json()
        assert retrieved_post["title"] == "Test Post"
        assert retrieved_post["content"] == "This is a test post"

@pytest.mark.asyncio
async def test_repository_pattern(test_db_pool):
    """Test repository pattern"""
    from extensions.blog.repositories import PostRepository, Post
    
    repo = PostRepository(test_db_pool)
    
    # Create a test user
    async with test_db_pool.acquire() as connection:
        user_id = await connection.fetchval("""
            INSERT INTO users (username, email, password_hash)
            VALUES ('testuser', 'test@example.com', 'hash')
            RETURNING id
        """)
    
    # Create a post using repository
    post = Post(
        id=None,
        title="Repository Test",
        content="Testing repository pattern",
        author_id=user_id
    )
    
    created_post = await repo.create(post)
    assert created_post.id is not None
    assert created_post.title == "Repository Test"
    
    # Get the post
    retrieved_post = await repo.get_by_id(created_post.id)
    assert retrieved_post is not None
    assert retrieved_post.title == "Repository Test"
```

## Best Practices

### 1. Use Connection Pooling

```python
# Good: Use connection pools for production
self.pool = await asyncpg.create_pool(
    self.database_url,
    min_size=1,
    max_size=10
)

# Avoid: Single connections for production apps
self.connection = await asyncpg.connect(self.database_url)
```

### 2. Handle Database Errors Gracefully

```python
# Good: Proper error handling
async def CreatePost(request, db_pool = dependency()):
    try:
        async with db_pool.acquire() as connection:
            # Database operations
            pass
    except asyncpg.UniqueViolationError:
        raise HTTPBadRequestException("Post title already exists")
    except asyncpg.ForeignKeyViolationError:
        raise HTTPBadRequestException("Invalid author ID")
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPInternalServerError("Database operation failed")
```

### 3. Use Transactions for Data Consistency

```python
# Good: Use transactions for related operations
async with connection.transaction():
    user_id = await connection.fetchval(
        "INSERT INTO users (...) VALUES (...) RETURNING id"
    )
    await connection.execute(
        "INSERT INTO user_profiles (user_id, ...) VALUES ($1, ...)",
        user_id
    )
```

### 4. Validate Input Before Database Operations

```python
# Good: Validate before database operations
if not title or len(title) > 200:
    raise HTTPBadRequestException("Title must be 1-200 characters")

if not content or len(content) > 10000:
    raise HTTPBadRequestException("Content must be 1-10000 characters")

# Then proceed with database operations
```

### 5. Use Repository Pattern for Complex Applications

```python
# Good: Repository pattern for clean separation
class PostService:
    def __init__(self, post_repo: PostRepository, user_repo: UserRepository):
        self.post_repo = post_repo
        self.user_repo = user_repo
    
    async def create_post(self, title: str, content: str, author_id: int) -> Post:
        # Validate author exists
        author = await self.user_repo.get_by_id(author_id)
        if not author:
            raise ValueError("Author not found")
        
        # Create post
        return await self.post_repo.create(Post(
            id=None, title=title, content=content, author_id=author_id
        ))
```

## Development Workflow

### 1. Plan Your Database Schema

Design your database schema before implementing:
- Identify entities and relationships
- Plan indexes for performance
- Consider data constraints and validation

### 2. Create Database Extension

```bash
serv create extension --name "Database"
```

### 3. Implement Models and Repositories

Create data models and repository classes for clean data access.

### 4. Add Database Middleware

Implement middleware for transaction management and connection handling.

### 5. Write Tests

Create comprehensive tests for database operations and edge cases.

### 6. Set Up Migrations

Implement a migration system for schema changes.

## Next Steps

- **[Authentication](authentication.md)** - Secure your database with user authentication
- **[Testing](testing.md)** - Advanced testing techniques for database operations
- **[Deployment](deployment.md)** - Deploy applications with database connections
- **[Performance](performance.md)** - Optimize database performance 