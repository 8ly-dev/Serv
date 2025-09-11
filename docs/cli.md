# CLI

Serving ships a small CLI wrapper around Uvicorn that handles working directory, environment selection, and configuration validation before launching.

## Command

- Entry: `serv`
- App module: always `serving.app:app` (provided by the package)

```bash
serv [-d DIR] [-e ENV] [uvicorn options...]
```

## Options

- `-d, --working-directory DIR` — change to this directory before launch (where your `serving.{env}.yaml` lives)
- `-e, --env ENV` — choose the environment (e.g., `dev`, `prod`, `staging`); picks `serving.{ENV}.yaml`
- Everything else is passed through to Uvicorn (e.g., `--reload`, `--host`, `--port`)

## Examples

```bash
# Dev with auto-reload, environment file serving.dev.yaml
serv -e dev --reload

# Custom working directory
serv -d ./example -e dev --host 0.0.0.0 --port 3000
```

If configuration is missing or invalid, the CLI prints a helpful message and exits with a non-zero code.
