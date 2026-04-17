"""
Post, Like, and Comment models - MongoDB document structure for feed/social features.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PostInDB(BaseModel):
    """Database model for post document"""
    author_id: str
    content: str
    likes_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    created_at: datetime
    updated_at: datetime


class LikeInDB(BaseModel):
    """Database model for like document"""
    post_id: str
    user_id: str
    created_at: datetime


class CommentInDB(BaseModel):
    """Database model for comment document"""
    post_id: str
    author_id: str
    content: str
    created_at: datetime
