# Middleware

Serv configures a small, focused middleware stack by default.

## Stack Overview

- `ExceptionMiddleware` — Converts 404s and exceptions into themed error pages
- `ServMiddleware` — Creates a request-scoped DI container branch and manages response headers/status/redirects
- `CSRFMiddleware` — Validates CSRF tokens for mutating HTTP methods

These are always enabled by Serv when constructing the Starlette app.

## ServMiddleware Behavior

- Opens a DI container branch per request and preloads `Request` and response accumulator
- Lets helpers like `set_header()`, `set_status_code()`, `set_cookie()`, and `redirect()` affect the live response

## CSRF

- Applies to `POST`, `PUT`, `PATCH`, and `DELETE`
- Reads `csrf_token` from form body and validates via your `CredentialProvider`
- Returns 400 if invalid

You must configure `auth.csrf_secret` in your YAML for CSRF to work. If using time-bound tokens, set `auth.csrf_ttl_seconds` to define the validity window.
