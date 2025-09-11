# Authentication & Permissions

Serv delegates authentication and authorization to a pluggable `CredentialProvider`. You must configure one in YAML for the app to start.

## Configure in YAML

```yaml
auth:
  credential_provider: myapp.auth:MyProvider  # module:ClassName
  csrf_secret: "change-me-long-random-string"
```

- `credential_provider` must resolve to a class implementing the protocol below
- `csrf_secret` powers CSRF token signing/validation used by forms and middleware

## CredentialProvider Protocol

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class CredentialProvider(Protocol):
    def has_credentials(self, permissions: set[str]) -> bool: ...
    def generate_csrf_token(self) -> str: ...
    def validate_csrf_token(self, token: str) -> bool: ...
```

At runtime Serv wraps each route to call `has_credentials(permissions)` with the set declared for that path in your YAML. If it returns `False`, Serv renders a themed 401 page.

## Built-in Example Provider

`HMACCredentialProvider` demonstrates a simple token signer for CSRF using an HMAC secret. You can adopt its CSRF pieces or implement your own provider end-to-end.

```python
from serving.auth import HMACCredentialProvider, AuthConfig
```

Note: you still need to implement `has_credentials()` according to your app’s needs when writing your own provider.

## Declaring Permissions per Route

```yaml
routers:
  - entrypoint: myapp.web:app
    routes:
      - path: "/admin"
        permissions: [admin]
```

Permissions are strings; your provider decides what they mean. In `dev`, denial pages can include the required permission set as debug context.
