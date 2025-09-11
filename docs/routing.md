# Routing

Serv routing is centered around a lightweight `Router` that collects Starlette `Route` objects via a decorator. You declaratively wire routers in YAML.

## Define a Router

```python
from serving.router import Router
from serving.types import PlainText, JSON, HTML, Jinja2

app = Router()

@app.route("/")
async def home() -> PlainText:
    return "Hello from Serv"

@app.route("/health")
async def health() -> JSON:
    return {"status": "ok"}

@app.route("/page")
async def page() -> HTML:
    return "<h1>Static Page</h1>"

@app.route("/template")
async def templated() -> Jinja2:
    return "home.html", {"message": "Hi"}
```

## HTTP Methods

You can register methods via the decorator’s `methods` argument or add multiple decorators:

```python
@app.route("/items", methods={"GET"})
async def list_items() -> JSON:
    return []

@app.route("/items", methods={"POST"})
async def create_item() -> JSON:
    return {"id": 1}
```

## Path Params

Use Python parameters that match path placeholders. Serv will pass `request.path_params` into your function.

```python
@app.route("/users/{user_id}")
async def user(user_id: int) -> JSON:
    return {"id": user_id}
```

## Query/Header/Cookie Params

Serv provides lightweight type helpers that make it easy to pull values from the request without touching `Request` directly:

```python
from serving.injectors import QueryParam, Header, Cookie

@app.route("/search")
async def search(q: QueryParam[str]) -> JSON:  # ?q=...
    return {"q": q}

@app.route("/agent")
async def agent(user_agent: Header[str]) -> PlainText:  # reads header "user-agent"
    return user_agent

@app.route("/visit")
async def visit(session_id: Cookie[str] = None) -> JSON:
    return {"session": session_id}
```

- By default the parameter name is used as the key (e.g., `q`, `user_agent`, `session_id`).
- Advanced: you can override the key name using `typing.Annotated`, e.g. `Annotated[QueryParam[str], "query"]`.

## Wire the Router in YAML

```yaml
routers:
  - entrypoint: myapp.web:app
    routes:
      - path: "/users/{user_id}"
        permissions: [user]
      - path: "/"
```

Permissions (strings) are passed to your `CredentialProvider` for access checks.
