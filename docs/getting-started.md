# Getting Started

This guide walks you through installing Serv, creating a minimal app, and running it.

## Install

- With the CLI (recommended): `pip install getserving[server]`
- Core only: `pip install getserving` (you must install and run an ASGI server yourself)

Requires Python 3.13+.

## Minimal Project

1) Create a router module:

```python
# myapp/web.py
from serving.router import Router
from serving.types import PlainText

app = Router()

@app.route("/")
async def home() -> PlainText:
    return "Hello, Serv!"
```

2) Add a configuration file in your working directory. Serv looks for `serving.{env}.yaml` (defaults to `prod`).

```yaml
# serving.dev.yaml
environment: dev

auth:
  # Implement your own provider; see guides/custom-auth-provider.md
  credential_provider: myapp.auth:MyProvider
  # Required for CSRF protection
  config:
    csrf_secret: "change-me-long-random-string"
    # Optional: validity window for time-bound CSRF tokens
    csrf_ttl_seconds: 3600

routers:
  - entrypoint: myapp.web:app
    routes:
      - path: "/"
        method: GET
```

3) Run the server with the CLI:

```bash
# From the directory containing serving.dev.yaml
serv -e dev --reload
```

- `-e/--env` selects the environment (e.g., `dev`, `prod`) and picks `serving.{env}.yaml`.
- Add any extra `uvicorn` flags after the Serv options (e.g., `--host`, `--port`).

## Return Types

Serv inspects your endpoint’s return annotation to format responses:

- `PlainText` -> `text/plain`
- `HTML` -> `text/html`
- `JSON` -> JSON response
- `Jinja2` -> render `templates/<file>` with context dict

See [Response Helpers](response.md) for details and examples.

## Next Steps

- Add routes and path params: [Routing](routing.md)
- Configure auth and permissions: [Authentication](authentication.md)
- Use forms with CSRF: [Forms & CSRF](forms.md)
- Customize error pages: [Error Handling & Theming](error-handling.md)
