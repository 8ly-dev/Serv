# Dependency Injection

Serv uses the Bevy DI container to wire request-scoped dependencies into your route functions and helpers. Each request runs in a container branch created by `ServMiddleware` so your functions can declare values they need.

## What You Can Inject

- `Config`: your loaded YAML configuration (see [Configuration](configuration.md))
- `ConfigModel` subclasses: typed config sections
- `Request`: Starlette `Request`
- Form instances: subclasses of `serving.forms.Form` (see [Forms & CSRF](forms.md))
- Request parameters: `QueryParam[T]`, `Header[T]`, `Cookie[T]`, `PathParam[T]`

## Injecting Config Models

Create a model by subclassing `ConfigModel`. The class name (or `model_key`) maps to a YAML key.

```python
from serving.config import ConfigModel

class Database(ConfigModel):
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
```

```yaml
# serving.dev.yaml
Database:
  host: localhost
  port: 5432
```

Use it in a function (DI resolves it per call):

```python
from bevy import auto_inject, injectable, Inject

@auto_inject
@injectable
async def handler(db: Inject[Database]):
    return {"host": db.host}
```

### Collections

If a model describes a list, set `is_collection=True` on the class and inject `list[YourModel]`:

```python
class Worker(ConfigModel, is_collection=True):
    def __init__(self, id: int, queue: str):
        self.id = id
        self.queue = queue
```

```yaml
Worker:
  - id: 1
    queue: default
  - id: 2
    queue: priority
```

```python
workers: list[Worker] = container.get(list[Worker])
```

### Defaults and Missing Keys

- If a collection key is missing in YAML and you inject a collection, you get an empty list
- If a single model key is missing and there is no default parameter value, injection returns `None` (and your code should handle it)
- If parameters are missing for a required model, you’ll get a `TypeError` from construction

## Request Parameter Helpers

Use `QueryParam[T]`, `Header[T]`, `Cookie[T]`, `PathParam[T]` in your function signature. The parameter name is used as the key by default.

```python
from serving.injectors import QueryParam, Header

async def search(q: QueryParam[str]):  # ?q=...
    ...

async def agent(user_agent: Header[str]):  # header name becomes "user-agent"
    ...
```

You can also override the key using `Annotated`, e.g. `Annotated[QueryParam[str], "query"]`.

## Request-Scoped Container

For each request, Serv creates a container branch and preloads:

- `Request`
- a response accumulator (see [Response Helpers](response.md))

This ensures helpers like `redirect()` and `set_header()` only run during a request lifecycle.
