# Serv Blog Demo

A minimal blog built on Serv demonstrating routing, forms + CSRF, templating, and simple in-memory storage. Uses Markdown for content and slugify for URLs.

## Install demo deps

Using uv (recommended):



Using pip (editable install with extras):



## Run

From this directory:



Then open http://127.0.0.1:8000/blog

## Notes

- Demo auth provider allows all requests and uses a fixed CSRF token. Do not use in production.
- Posts are stored in-memory and will be cleared on process restart.
