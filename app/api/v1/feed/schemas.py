"""
Feed/Posts Request/Response Schemas
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class PostCreate(BaseModel):
    """Schema for creating a post"""
    content: str = Field(..., min_length=1, max_length=5000, description="Post content")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "Excited to share insights from today's cardiology conference! The latest research on heart disease prevention is truly groundbreaking."
            }
        }


class PostResponse(BaseModel):
    """Schema for post response"""
    post_id: str = Field(..., description="Post ID")
    author_id: str = Field(..., description="Author user ID")
    author_name: str = Field(..., description="Author name")
    author_role: str = Field(..., description="Author role: DOCTOR or MR")
    author_specialization: Optional[str] = Field(None, description="Doctor's specialization")
    author_territory: Optional[str] = Field(None, description="MR's territory")
    content: str = Field(..., description="Post content")
    likes_count: int = Field(..., description="Number of likes")
    comments_count: int = Field(..., description="Number of comments")
    created_at: datetime = Field(..., description="Post creation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "post_id": "post123",
                "author_id": "user123",
                "author_name": "Dr. Sarah Sharma",
                "author_role": "DOCTOR",
                "author_specialization": "Cardiology",
                "author_territory": None,
                "content": "Excited to share insights from today's conference!",
                "likes_count": 15,
                "comments_count": 3,
                "created_at": "2024-04-09T10:30:00"
            }
        }


class PostFeedResponse(BaseModel):
    """Schema for paginated feed response"""
    posts: List[PostResponse] = Field(..., description="List of posts")
    total: int = Field(..., description="Total number of posts")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Posts per page")
    total_pages: int = Field(..., description="Total number of pages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "posts": [
                    {
                        "post_id": "post123",
                        "author_id": "user123",
                        "author_name": "Dr. Sarah Sharma",
                        "author_role": "DOCTOR",
                        "author_specialization": "Cardiology",
                        "author_territory": None,
                        "content": "Excited to share insights!",
                        "likes_count": 15,
                        "comments_count": 3,
                        "created_at": "2024-04-09T10:30:00"
                    }
                ],
                "total": 150,
                "page": 1,
                "limit": 20,
                "total_pages": 8
            }
        }
