# Serving: The Extensible Python Web Framework 🚀

> [!WARNING]
> Serving is currently in alpha and is NOT recommended for production use. APIs are subject to change.

Serving is a small ASGI web framework built on Starlette with first‑class dependency injection (Bevy), YAML configuration, typed routing, forms with CSRF, and themed error pages.

## ✨ Highlights

- ASGI/Starlette core with a minimal surface area
- Dependency Injection via Bevy (request‑scoped container)
- YAML configuration with typed `ConfigModel`s (including collections)
- Lightweight routing decorator; return‑type‑based responses
- Forms + CSRF with Jinja2 templates
- Themed error pages with dev‑mode details
- Simple CLI wrapper around Uvicorn

## 🚀 Quick Start

### Install

```bash
pip install getserving[server]
```

### Minimal App

1) Router module

```python
# myapp/web.py
from serving.router import Router
from serving.types import PlainText, JSON, Jinja2
from serving.injectors import QueryParam
from serving import redirect

app = Router()

@app.route("/")
async def index() -> Jinja2:
    return "home.html", {"message": "Hello from Serving"}

@app.route("/hello")
async def hello(name: QueryParam[str] = "world") -> PlainText:
    return f"Hello, {name}!"

@app.route("/redirect")
async def go_home() -> PlainText:
    redirect("/")
    return "This will not be sent"
```

2) Template

```html
<!-- templates/home.html -->
<h1>{{ message }}</h1>
```

3) Configuration

```yaml
# serving.dev.yaml
environment: dev

auth:
  credential_provider: myapp.auth:MyProvider
  config:
    csrf_secret: change-me-long-random-string

templates:
  directory: templates

routers:
  - entrypoint: myapp.web:app
    routes:
      - path: "/"
      - path: "/hello"
      - path: "/redirect"
```

4) Run

```bash
serv -e dev --reload
```

Your app will be available at http://127.0.0.1:8000.

## 🧭 Return Types

- `PlainText` → PlainTextResponse
- `JSON` → JSONResponse
- `HTML` → HTMLResponse
- `Jinja2` → TemplateResponse (tuple of `template_name`, `context_dict`)
- Returning a Starlette `Response` is passed through as‑is

## 🔐 Authentication & Permissions

Configure an auth provider in YAML (`auth.credential_provider`). Serving calls `has_credentials(permissions)` before invoking a route; if denied, a themed 401 page is rendered. See [Authentication](docs/authentication.md) for the `CredentialProvider` protocol and examples.

## 🧾 Forms & CSRF

Use `serving.forms.Form` with Jinja2. When CSRF is enabled (default), templates must call `{{ csrf() }}`; invalid tokens are rejected by `CSRFMiddleware`. See [Forms & CSRF](docs/forms.md).

## 🎨 Error Pages & Theming

Customize error templates via the `theming` section in YAML. Dev mode can include extra details (stack traces, missing path). See [Error Handling & Theming](docs/error-handling.md).

## 🧰 CLI

```bash
serv [-d DIR] [-e ENV] [uvicorn options...]
```

- `-d, --working-directory DIR` — where your `serving.{env}.yaml` lives
- `-e, --env ENV` — choose environment (e.g., `dev`, `prod`)
- All other flags are passed to Uvicorn (e.g., `--reload`, `--host`, `--port`)

## 📚 Documentation

See the [docs/](docs/README.md) directory for detailed guides and references:

- [Getting Started](docs/getting-started.md) — install and minimal setup
- [Configuration](docs/configuration.md) — YAML layout, templates, theming, routers, auth
- [Routing](docs/routing.md) — router decorator, params, permissions
- [Dependency Injection](docs/dependency-injection.md) — Bevy DI and `ConfigModel`s
- [Forms & CSRF](docs/forms.md) — forms + CSRF
- [Error Handling](docs/error-handling.md) — exceptions and theming
- [Authentication](docs/authentication.md) — provider protocol and configuration
- [Middleware](docs/middleware.md) — default middleware stack
- [Response Helpers](docs/response.md) — `set_header`, `redirect`, etc.
- [CLI](docs/cli.md) — CLI flags and examples
- [Testing](docs/testing.md) — testing patterns

Also see the [demo/blog](demo/blog/README.md) demo for a runnable example.

## 🤝 Contributing

Contributions are welcome! Bug reports, feature suggestions, docs, and tests are appreciated. Please open an issue or pull request.

## 📄 License

MIT — see [LICENSE](LICENSE).
