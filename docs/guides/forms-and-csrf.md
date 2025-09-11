# Guide: Forms & CSRF

Build a simple form backed by a dataclass model and Jinja2 template with CSRF protection.

## 1) Template

```html
<!-- templates/contact.html -->
<form method="post">
  <input name="name" placeholder="Name" required>
  <input name="email" type="email" placeholder="Email" required>
  <textarea name="message" placeholder="Message" required></textarea>
  {{ csrf() }}
  <button type="submit">Send</button>
</form>
```

## 2) Form Class

```python
from dataclasses import dataclass
from serving.forms import Form

@dataclass
class Contact(Form, template="contact.html"):
    name: str
    email: str
    message: str
```

## 3) Routes

```python
from serving.router import Router
from serving.types import HTML

app = Router()

@app.route("/contact", methods={"GET"})
async def contact_form() -> HTML:
    return Contact(name="", email="", message="").render()

@app.route("/contact", methods={"POST"})
async def contact_submit(form: Contact) -> HTML:
    # Form is parsed and CSRF validated automatically
    return f"<h1>Thanks {form.name}!</h1>"
```

## 4) YAML

```yaml
# serving.dev.yaml
environment: dev

auth:
  credential_provider: myapp.auth:MyProvider
  csrf_secret: dev-secret

templates:
  directory: templates

routers:
  - entrypoint: myapp.web:app
    routes:
      - path: "/contact"
        method: GET
      - path: "/contact"
        method: POST
```

Ensure `auth.csrf_secret` is set; CSRF middleware will reject invalid submissions.
