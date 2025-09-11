# Testing

Serv apps are standard ASGI applications (Starlette under the hood), so you can test them with `starlette.testclient.TestClient` or HTTPX.

## Test a Router End-to-End

```python
# tests/test_web.py
from pathlib import Path
from starlette.testclient import TestClient

from serving.serv import Serv

# Your router code in myapp/web.py


def test_home(tmp_path: Path, monkeypatch):
    # Write a minimal config for the test environment
    (tmp_path / "serving.test.yaml").write_text(
        """
        environment: test
        auth:
          credential_provider: myapp.auth:MyProvider
          config:
            csrf_secret: test-secret
        routers:
          - entrypoint: myapp.web:app
            routes:
              - path: "/"
        """
    )

    # Build a Serv instance against the temp dir
    serv = Serv(working_directory=tmp_path, environment="test")
    client = TestClient(serv.app)

    r = client.get("/")
    assert r.status_code == 200
```

## Dependency Injection in Tests

If you need to bypass auth for tests, provide a simple `CredentialProvider` in your test code and point `auth.credential_provider` to it in your test YAML.

For unit-testing helpers that use DI directly (e.g., forms), you can create a Bevy `Registry` and `Container`, add the pieces you need (like `Jinja2Templates` or `Request`), and then call your injected functions. See the project’s own tests in `src/tests/serving` for patterns.
