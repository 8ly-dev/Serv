from dataclasses import dataclass
from typing import Optional

from slugify import slugify
import markdown
from starlette.exceptions import HTTPException

from serving.router import Router
from serving.types import HTML, Jinja2
from serving.forms import Form
from serving import redirect


app = Router()


# In-memory post store (demo only)
POSTS: list[dict] = []


@dataclass
class PostForm(Form, template="blog/new.html"):
    title: str
    slug: Optional[str] = None
    content: str = ""


@app.route("/blog")
async def blog_index() -> Jinja2:
    # Show newest first
    return "blog/index.html", {"posts": list(reversed(POSTS))}


@app.route("/blog/new", methods={"GET"})
async def blog_new_get() -> HTML:
    # Render empty form with CSRF token
    return PostForm(title="", slug="", content="").render()


@app.route("/blog/new", methods={"POST"})
async def blog_new_post(form: PostForm) -> HTML:
    # Generate slug
    raw_slug = form.slug.strip() if form.slug else form.title
    s = slugify(raw_slug or "post")
    # Render markdown to HTML
    html = markdown.markdown(form.content or "", extensions=["fenced_code"])  # noqa: S308

    POSTS.append({
        "title": form.title,
        "slug": s,
        "content_md": form.content,
        "content_html": html,
    })

    redirect(f"/blog/{s}")
    return "Created"


@app.route("/blog/{slug}")
async def blog_post(slug: str) -> Jinja2:
    for post in POSTS:
        if post["slug"] == slug:
            return "blog/post.html", {"post": post}
    raise HTTPException(status_code=404, detail="Post not found")

