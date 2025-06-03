"""Web routes for the microblog."""

import logging
from datetime import datetime, timedelta
from typing import Annotated

from bevy import Inject, Options, injectable
from ommi import Ommi
from ommi.query_ast import when

from serv.routes import GetRequest, PostRequest, Jinja2Response, RedirectResponse, Route, handle

logger = logging.getLogger("microblog.routes")


class HomeRoute(Route):
    """Home page showing all blog posts."""
    
    @handle.GET
    @injectable
    async def show_home(self, request: GetRequest, db: Inject[Ommi, Options(qualifier="blog")]) -> Annotated[tuple[str, dict], Jinja2Response]:
        """Display all blog posts on the home page."""
        try:
            # Import the Post model
            from .models import Post
            
            # Get all posts from the database using Ommi (global collection is used automatically)
            posts = []
            query_result = await db.find(Post).all.or_raise()
            async for post in query_result:
                posts.append(post)
            
            # Convert to dict format for template rendering
            posts_data = [post.to_dict() for post in posts]
            
            # Sort posts by newest first (by ID as a proxy for creation time)
            return "home.html", {"posts": posts_data}
            
        except Exception as e:
            logger.error(f"Error rendering home: {e}")
            return "error.html", {"error_message": f"Error loading posts: {e}"}


class CreatePostRoute(Route):
    """Route for creating new blog posts."""
    
    @handle.GET
    async def show_form(self, request: GetRequest) -> Annotated[tuple[str, dict], Jinja2Response]:
        """Show the create post form."""
        return "create_post.html", {}
    
    @handle.POST
    @injectable
    async def create_post(self, request: PostRequest, db: Inject[Ommi, Options(qualifier="blog")]) -> Annotated[tuple[str, dict[str, str]], Jinja2Response]:
        """Create a new blog post."""
        try:
            # Get form data
            form_data = await request.form()
            
            # Handle form data which may be lists or strings
            title_raw = form_data.get("title", "")
            content_raw = form_data.get("content", "")
            
            # Extract string values from lists if necessary
            title = title_raw[0] if isinstance(title_raw, list) and title_raw else str(title_raw)
            content = content_raw[0] if isinstance(content_raw, list) and content_raw else str(content_raw)
            
            # Strip whitespace
            title = title.strip()
            content = content.strip()
            
            # Validate input
            if not title:
                return "create_post.html", {"error": "Title is required"}
            
            if not content:
                return "create_post.html", {"error": "Content is required"}
            
            # Import the Post model
            from .models import Post
            
            # Create and save the post using Ommi ORM (global collection is used automatically)
            new_post = Post(title=title, content=content, created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            await db.add(new_post).or_raise()
            
            logger.info(f"Created post {new_post.id}: {title}")
            
            # Show success message
            return "success.html", {"title": title}
            
        except Exception as e:
            logger.error(f"Error creating post: {e}")
            return "create_post.html", {"error": f"Error creating post: {e}"}


class ViewPostRoute(Route):
    """Route for viewing individual blog posts."""
    
    @handle.GET
    @injectable
    async def view_post(self, request: GetRequest, post_id: str, db: Inject[Ommi, Options(qualifier="blog")]) -> Annotated[tuple[str, dict], Jinja2Response]:
        """View a single blog post."""
        try:
            if not post_id:
                return "error.html", {"error_message": "Post ID not provided"}
            
            try:
                post_id_int = int(post_id)
            except ValueError:
                return "error.html", {"error_message": "Invalid post ID"}
            
            # Import the Post model
            from .models import Post
            
            # Get the specific post from database using Ommi (global collection is used automatically)
            from ommi.database.query_results import DBStatusNoResultException
            post = await db.find(Post.id == post_id_int).one.or_use(None)
            if not post:
                return "error.html", {"error_message": "Post not found"}
            
            return "view_post.html", {"post": post.to_dict()}
            
        except Exception as e:
            logger.error(f"Error fetching post {post_id}: {e}")
            return "error.html", {"error_message": f"Error loading post: {e}"}