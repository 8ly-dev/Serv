# Guide: Custom Auth Provider

Implement a `CredentialProvider` to authorize requests and back CSRF.

## 1) Implement the Provider

```python
# myapp/auth.py
from serving.auth import CredentialProvider

class MyProvider(CredentialProvider):
    def __init__(self):
        # Load secrets, keys, or services here
        ...

    def has_credentials(self, permissions: set[str]) -> bool:
        # TODO: implement check (read cookies/headers via DI if desired)
        # Return True to allow, False to deny
        return True

    def generate_csrf_token(self) -> str:
        # For production, prefer HMAC signing like HMACCredentialProvider
        import secrets
        return secrets.token_urlsafe(32)

    def validate_csrf_token(self, token: str) -> bool:
        # Match your generation scheme
        return isinstance(token, str) and len(token) > 0
```

You can also compose/extend `HMACCredentialProvider` for robust CSRF token signing using values under `auth.config`.

## 2) Configure YAML

```yaml
# serving.dev.yaml
auth:
  credential_provider: myapp.auth:MyProvider
  config:
    csrf_secret: dev-secret
```

## 3) Use Route Permissions

```yaml
routers:
  - entrypoint: myapp.web:app
    routes:
      - path: "/admin"
        permissions: [admin]
```

Serving passes the `permissions` set to `has_credentials()` before invoking your route handler. If it returns `False`, Serving renders a themed 401 page.
