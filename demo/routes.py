from serving.injectors import QueryParam
from serving.router import Router
from serving.types import HTML, Jinja2, PlainText
from serving import redirect


app = Router()

@app.route("/")
async def index() -> Jinja2:
    return "home.html", {"message": "Hello World!"}


@app.route("/redirect")
async def redirect_page() -> PlainText:
    redirect("/")
    return "Hello World!"


@app.route("/{user_id}")
async def user_dashboard(user_id: int, page: QueryParam[int]) -> HTML:
    return f"<h1>User Dashboard</h1><p>Hello, {user_id}, {page}</p>"
