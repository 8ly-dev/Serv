# Error Handling & Theming

Serv centralizes error rendering so you can theme error pages consistently. In production it shows clean messages; in development it can include details.

## Built-in Behavior

- `ExceptionMiddleware` intercepts 404s and exceptions and uses the `ErrorHandler`
- Starlette exception handlers are also configured for `HTTPException`, 404, and 500
- In `dev`/`development` environments, 404 pages can include the missing path and 500 pages can include traces

## Custom Templates

Configure error templates via the `theming` section in YAML:

```yaml
theming:
  error_templates:
    "404": errors/404.html
    "500": errors/500.html
  default_error_template: errors/error.html
```

- Template paths are resolved relative to your `templates.directory`
- If a specific code template is not found, `default_error_template` is used
- If theming is not configured, a polished built-in fallback template is used

## Fallback Template

Serv ships a default `error.html` used when no custom template is available. You can find it in the package at `serving/templates/error.html` for inspiration.

## Passing Details in Dev

When running with `SERV_ENVIRONMENT=dev` (or `-e dev`), Serv includes additional details for errors:

- HTTP 404: shows the missing path
- Exceptions: includes a formatted traceback
