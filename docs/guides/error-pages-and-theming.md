# Guide: Error Pages & Theming

Customize the look and feel of your error pages.

## 1) Create Templates

```
# templates/errors/404.html
# templates/errors/500.html
# templates/errors/error.html  # default catch-all
```

Each template receives:

- `error_code`: the HTTP status code
- `error_message`: a short message
- `details`: optional technical details (present in dev for some errors)

## 2) Configure YAML

```yaml
# serving.dev.yaml
templates:
  directory: templates

theming:
  error_templates:
    "404": errors/404.html
    "500": errors/500.html
  default_error_template: errors/error.html
```

## 3) Dev-specific Details

In `dev`/`development` environments, Serv may include debugging context on error pages:

- 404 shows the missing path
- 500 includes a formatted traceback
