"""Main microblog extension module."""

import logging
from datetime import datetime

from bevy import Inject
from ommi import Ommi
from bevy import Options

from serv.extensions import Listener, on
from .models import microblog_collection, Post

logger = logging.getLogger("microblog")


class MicroblogExtension(Listener):
    """Microblog extension that sets up the database schema."""

    @on("app.startup")
    async def setup_database(self, ommi: Inject[Ommi, Options(qualifier="blog")]):
        """Initialize the database schema on app startup."""
        logger.info("Initializing microblog database schema...")
        
        try:
            await ommi.use_models(microblog_collection)

        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise

        welcome_post = Post(
            title="🎉 Welcome to your Beautiful Microblog!",
            content="""✅ **Database Integration Working!**

Your microblog is now fully functional with modern styling and **markdown support**!

## 🗄️ Database Features:
- SQLite database with Ommi ORM
- Automatic schema creation
- Full CRUD operations
- Type-safe models
- Dependency injection

## 🎨 UI Features:
- **Modern gradient design**
- *Responsive layout*
- `Markdown rendering`
- Beautiful typography
- Smooth animations

## 🚀 Try it out:
1. Click **Create New Post** above
2. Write some content with markdown:
   - Use `**bold**` and `*italic*` text
   - Add headers with `## Heading`
   - Create lists like this one
   - Include `inline code`
3. See the live preview as you type!

> This demonstrates Serv's powerful database integration system with Ommi ORM and a beautiful modern interface!""",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        await ommi.add(welcome_post).or_raise()
        logger.info("Microblog extension started successfully")
