# Router Mount Demo

This demo shows how to use the new router mounting feature in Serv.

## What is Router Mounting?

Router mounting allows you to attach a router to another router at a specific path prefix. This is useful for:

1. **Organizing your routes** - Group related routes in separate routers
2. **Creating modular applications** - Develop independent sections of your app separately
3. **Versioning APIs** - Mount different API versions at different paths
4. **Building composable applications** - Reuse route collections across different parts of your app

## How It Works

The `mount()` method attaches a router at a specific path prefix:

```python
# Create routers
main_router = Router()
api_router = Router()

# Add routes to the API router
api_router.add_route("/users", users_handler)
api_router.add_route("/posts", posts_handler)

# Mount the API router at /api
main_router.mount("/api", api_router)
```

With this setup:
- `/api/users` will be handled by `users_handler`
- `/api/posts` will be handled by `posts_handler`

## Key Features

1. **Path Normalization**: Paths are automatically normalized, so both `/api` and `api` (without leading slash) work the same way.

2. **Nested Mounting**: You can mount routers onto other mounted routers, creating deep hierarchies:
   ```python
   api_v1_router = Router()
   api_router.mount("/v1", api_v1_router)
   main_router.mount("/api", api_router)
   ```
   This allows routing to `/api/v1/resource`.

3. **Path Parameter Support**: Path parameters in mounted routers work as expected.

## Difference Between `mount()` and `add_router()`

- **`mount(path, router)`**: Attaches a router at a specific path prefix. The router only sees the part of the path after the mount point.
- **`add_router(router)`**: Adds a router as a global sub-router that sees the entire request path.

## Running This Demo

```bash
python -m demos.router_mount_demo.main
```

This will start a server with the following routes:
- `/` - Home page
- `/about` - About page
- `/admin` - Admin dashboard
- `/admin/users` - Admin users page
- `/api/v1/users` - List of users API endpoint
- `/api/v1/users/{id}` - Specific user API endpoint
- `/api/v1/articles` - List of articles API endpoint
- `/api/v1/articles/{id}` - Specific article API endpoint 