# Response Helpers

Serv provides a few helpers to modify the response from anywhere in your request-handling code. They operate on a request-scoped accumulator managed by `ServMiddleware`.

## Helpers

- `set_header(name: str, value: str)` — add/override a response header
- `set_status_code(code: int | Status)` — set the response status code
- `set_cookie(name: str, value: str)` — set a cookie header
- `delete_cookie(name: str)` — delete a cookie by name
- `redirect(url: str, status_code: int | Status = Status.TEMPORARY_REDIRECT)` — short-circuits the current request with a redirect

```python
from serving import set_header, set_status_code, set_cookie, delete_cookie, redirect
from serving.response import Status

@router.route("/download")
async def download() -> str:
    set_header("Cache-Control", "no-store")
    set_status_code(Status.OK)
    return "starting download"

@router.route("/go")
async def go() -> str:
    redirect("/")
    return "This will not be sent"
```

## Return Type Mapping

Serv formats your raw return value based on your function’s return annotation:

- `PlainText` -> `PlainTextResponse`
- `JSON` -> `JSONResponse`
- `HTML` -> `HTMLResponse`
- `Jinja2` -> `TemplateResponse` (tuple of `(template_name, context_dict)`)
- Any existing `starlette.responses.Response` is passed through as-is

If the annotation does not match any of the above and the return type is not a `Response`, Serv raises a `ValueError`.
