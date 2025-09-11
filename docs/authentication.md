# Authentication & Permissions

Serv delegates authentication and authorization to a pluggable `CredentialProvider`. You must configure one in YAML for the app to start.

## Configure in YAML

```yaml
auth:
  credential_provider: myapp.auth:MyProvider  # module:ClassName
  config:
    csrf_secret: "change-me-long-random-string"
    csrf_ttl_seconds: 3600  # optional; validity window for time-bound CSRF tokens
```

- `credential_provider` must resolve to a class implementing the protocol below
- `config` is passed as keyword args to the provider; e.g., `csrf_secret` and `csrf_ttl_seconds` for the built-ins

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

`HMACCredentialProvider` demonstrates a simple token signer for CSRF using an HMAC secret. For time-bound tokens that embed creation time and enforce expiry, use `TimedHMACCredentialProvider` or implement your own scheme using values under `auth.config` (e.g., `csrf_secret`, `csrf_ttl_seconds`).

```python
from serving.auth import HMACCredentialProvider, TimedHMACCredentialProvider, AuthConfig
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
