# Guide: Config & Environments

Run the same app in different environments by switching `serving.{env}.yaml` files.

## 1) Create Environment Files

```yaml
# serving.dev.yaml
environment: dev

auth:
  credential_provider: myapp.auth:MyProvider
  csrf_secret: dev-secret
```

```yaml
# serving.prod.yaml
environment: prod

auth:
  credential_provider: myapp.auth:MyProvider
  csrf_secret: ${PROD_CSRF_SECRET}
```

## 2) Choose Environment

- CLI flag: `serv -e dev` or `serv -e prod`
- Environment variable: `SERV_ENVIRONMENT=staging uvicorn serving.app:app`

When using the CLI, you can also change the working directory with `-d` if your config is not in the current directory.
