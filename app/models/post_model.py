"""
Post, Like, and Comment models - MongoDB document structure for feed/social features.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from bson import ObjectId


class PostInDB(BaseModel):
    """
    Write model for post document (INSERT operations)
    
    Collection: posts
    Indexes:
    - author_id
    - created_at DESC
    - is_active
    """
    author_id: str = Field(..., description="Post author user ID")
    content: str = Field(..., min_length=1, max_length=5000, description="Post content")
    likes_count: int = Field(default=0, ge=0, description="Number of likes")
    comments_count: int = Field(default=0, ge=0, description="Number of comments")
    shares_count: int = Field(default=0, ge=0, description="Number of shares")
    is_active: bool = Field(default=True, description="Soft delete flag")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    @field_validator('author_id')
    @classmethod
    def validate_author_id(cls, v: str) -> str:
        """Validate author_id is valid ObjectId format"""
        try:
            ObjectId(v)
            return v
        except Exception:
            raise ValueError(f'Invalid ObjectId format: {v}')
    
    class Config:
        extra = "forbid"


class PostDocument(PostInDB):
    """Read model for post document"""
    class Config:
        extra = "allow"


class LikeInDB(BaseModel):
    """
    Write model for like document (INSERT operations)
    
    Collection: post_likes
    Indexes:
    - Compound unique: (post_id, user_id)
    - post_id
    - user_id
    """
    post_id: str = Field(..., description="Post ID being liked")
    user_id: str = Field(..., description="User ID who liked")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Like timestamp")
    
    @field_validator('post_id', 'user_id')
    @classmethod
    def validate_object_id(cls, v: str) -> str:
        """Validate IDs are valid ObjectId format"""
        try:
            ObjectId(v)
            return v
        except Exception:
            raise ValueError(f'Invalid ObjectId format: {v}')
    
    class Config:
        extra = "forbid"


class LikeDocument(LikeInDB):
    """Read model for like document"""
    class Config:
        extra = "allow"


class CommentInDB(BaseModel):
    """
    Write model for comment document (INSERT operations)
    
    Collection: post_comments
    Indexes:
    - post_id
    - author_id
    - Compound: (post_id, is_active)
    """
    post_id: str = Field(..., description="Post ID being commented on")
    author_id: str = Field(..., description="Comment author user ID")
    content: str = Field(..., min_length=1, max_length=2000, description="Comment content")
    is_active: bool = Field(default=True, description="Soft delete flag")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Comment timestamp")
    
    @field_validator('post_id', 'author_id')
    @classmethod
    def validate_object_id(cls, v: str) -> str:
        """Validate IDs are valid ObjectId format"""
        try:
            ObjectId(v)
            return v
        except Exception:
            raise ValueError(f'Invalid ObjectId format: {v}')
    
    class Config:
        extra = "forbid"


class CommentDocument(CommentInDB):
    """Read model for comment document"""
    class Config:
        extra = "allow"
