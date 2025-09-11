# Serv Blog Demo

A minimal blog built on Serv demonstrating routing, forms + CSRF, templating, and simple in-memory storage. Uses Markdown for content and slugify for URLs.

## Install demo deps

Using uv (recommended):



Using pip (editable install with extras):



## Run

From this directory:

1) Ensure you have Serv installed (CLI recommended): `pip install getserving[server]`
2) Run the app against the included config:

```bash
serv -d . -e dev --reload
```

Then open http://127.0.0.1:8000/blog

## Notes

- CSRF uses `serving.auth:TimedHMACCredentialProvider` with settings under `auth.config` in `serving.dev.yaml`.
  - `csrf_secret` is required (demo uses `dev-secret`; change for your env)
  - `csrf_ttl_seconds` controls token validity window (default 3600s)
- Posts are stored in-memory and will be cleared on process restart.
- Posts are stored in-memory and will be cleared on process restart.
