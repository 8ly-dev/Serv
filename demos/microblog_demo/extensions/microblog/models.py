"""Database models for the microblog."""

from typing import Annotated
from dataclasses import dataclass

from ommi import ommi_model, Key
from ommi.models.collections import ModelCollection


microblog_collection = ModelCollection()


@ommi_model(collection=microblog_collection)
@dataclass
class Post:
    """Blog post model using Ommi v0.2.1 dataclass syntax."""
    
    title: str
    content: str
    created_at: str = ""  # Store as string to avoid type validation issues
    id: Annotated[int, Key] = None  # Auto-generated primary key
    
    def __repr__(self):
        return f"<Post {self.id}: {self.title}>"
    
    def to_dict(self):
        """Convert post to dictionary for easy template rendering."""
        from datetime import datetime
        
        # Parse the datetime string and format it nicely
        formatted_date = self.created_at
        if self.created_at:
            try:
                dt = datetime.strptime(self.created_at, "%Y-%m-%d %H:%M:%S")
                formatted_date = dt.strftime("%B %d, %Y at %I:%M %p")
            except ValueError:
                formatted_date = self.created_at
        
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at,
            "formatted_date": formatted_date,
        }