# Guide: Hello World

This quick guide gets you from zero to a running Serv app.

## 1) Create a Router

```python
# myapp/web.py
from serving.router import Router
from serving.types import PlainText

app = Router()

@app.route("/")
async def home() -> PlainText:
    return "Hello, Serv!"
```

## 2) Create Config

```yaml
# serving.dev.yaml
environment: dev

auth:
  credential_provider: myapp.auth:MyProvider
  config:
    csrf_secret: dev-secret
    csrf_ttl_seconds: 3600

routers:
  - entrypoint: myapp.web:app
    routes:
      - path: "/"
```

## 3) Run

```bash
serv -e dev --reload
```

Visit http://127.0.0.1:8000/ and you should see your greeting.

## Next

- Add more routes and return types: [Routing](../routing.md)
- Set up forms & CSRF: [Forms & CSRF](../forms.md)
- Customize error pages: [Error Handling & Theming](../error-handling.md)
