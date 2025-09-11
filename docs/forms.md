# Forms & CSRF

Serv includes a simple form abstraction built on Jinja2 with built-in CSRF protection.

## Define a Form

Subclass `Form` and declare fields via type annotations. Attach a template and choose CSRF behavior.

```python
from dataclasses import dataclass
from serving.forms import Form, CSRFProtection

@dataclass
class Contact(Form, template="contact.html"):
    name: str
    email: str
    message: str

@dataclass
class Newsletter(Form, template="newsletter.html", csrf=CSRFProtection.Disabled):
    email: str
```

## Rendering a Form

```python
html = Contact(name="", email="", message="").render()
```

- When CSRF is enabled (default), your template must call `csrf()` somewhere to include the token input.
- If CSRF is enabled and the template did not call `csrf()`, rendering raises `MissingCSRFTokenError`.

Example Jinja2 template snippet:

```html
<form method="post">
  <input name="name">
  <input name="email" type="email">
  <textarea name="message"></textarea>
  {{ csrf() }}
  <button type="submit">Send</button>
</form>
```

## Parsing a Form From a Request

Use the async classmethod `from_request()` to validate CSRF and build an instance from request data:

```python
from starlette.requests import Request

contact = await Contact.from_request(request)
```

- CSRF tokens are validated via the configured `CredentialProvider`
- When disabled via `csrf=CSRFProtection.Disabled`, no token is required

## Middleware Enforcement

`CSRFMiddleware` automatically validates CSRF tokens for `POST`, `PUT`, `PATCH`, and `DELETE` requests. It returns `400 Invalid CSRF token` if validation fails.

Ensure you provide `auth.csrf_secret` in your YAML so the provider can sign tokens.

If you use time-bound CSRF tokens (e.g., `TimedHMACCredentialProvider`), also configure `auth.csrf_ttl_seconds` to control how long tokens remain valid.
