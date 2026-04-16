"""
Post, Like, and Comment models - MongoDB schema for feed/social features.
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
    shares_count: int = Field(default=0, description="Number of times shared")
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
                "shares_count": 5,
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


class LikeResponse(BaseModel):
    """Schema for like/unlike response"""
    liked: bool = Field(..., description="True if liked, False if unliked")
    likes_count: int = Field(..., description="Updated total likes count")
    message: str = Field(..., description="Success message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "liked": True,
                "likes_count": 16,
                "message": "Post liked successfully"
            }
        }


class LikeUser(BaseModel):
    """Schema for user who liked a post"""
    user_id: str = Field(..., description="User ID")
    user_name: str = Field(..., description="User name")
    user_role: str = Field(..., description="User role: DOCTOR or MR")
    created_at: datetime = Field(..., description="When user liked the post")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "user_name": "Dr. Sarah Sharma",
                "user_role": "DOCTOR",
                "created_at": "2024-04-09T10:30:00"
            }
        }


class LikeListResponse(BaseModel):
    """Schema for list of users who liked a post"""
    likes: List[LikeUser] = Field(..., description="List of users who liked")
    total: int = Field(..., description="Total number of likes")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Likes per page")
    total_pages: int = Field(..., description="Total number of pages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "likes": [
                    {
                        "user_id": "user123",
                        "user_name": "Dr. Sarah Sharma",
                        "user_role": "DOCTOR",
                        "created_at": "2024-04-09T10:30:00"
                    }
                ],
                "total": 16,
                "page": 1,
                "limit": 20,
                "total_pages": 1
            }
        }


class LikeStatusResponse(BaseModel):
    """Schema for checking if user liked a post"""
    liked: bool = Field(..., description="True if user has liked this post")
    likes_count: int = Field(..., description="Total likes on the post")
    
    class Config:
        json_schema_extra = {
            "example": {
                "liked": True,
                "likes_count": 16
            }
        }


class CommentCreate(BaseModel):
    """Schema for creating a comment"""
    content: str = Field(..., min_length=1, max_length=1000, description="Comment content")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "Great insights! Thanks for sharing this information."
            }
        }


class CommentResponse(BaseModel):
    """Schema for comment response"""
    comment_id: str = Field(..., description="Comment ID")
    post_id: str = Field(..., description="Post ID")
    author_id: str = Field(..., description="Author user ID")
    author_name: str = Field(..., description="Author name")
    author_role: str = Field(..., description="Author role: DOCTOR or MR")
    content: str = Field(..., description="Comment content")
    created_at: datetime = Field(..., description="Comment creation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "comment_id": "comment123",
                "post_id": "post123",
                "author_id": "user456",
                "author_name": "Dr. Sarah Sharma",
                "author_role": "DOCTOR",
                "content": "Great insights! Thanks for sharing.",
                "created_at": "2024-04-10T10:30:00"
            }
        }


class CommentListResponse(BaseModel):
    """Schema for paginated comments list"""
    comments: List[CommentResponse] = Field(..., description="List of comments")
    total: int = Field(..., description="Total number of comments")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Comments per page")
    total_pages: int = Field(..., description="Total number of pages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "comments": [
                    {
                        "comment_id": "comment123",
                        "post_id": "post123",
                        "author_id": "user456",
                        "author_name": "Dr. Sarah Sharma",
                        "author_role": "DOCTOR",
                        "content": "Great insights!",
                        "created_at": "2024-04-10T10:30:00"
                    }
                ],
                "total": 15,
                "page": 1,
                "limit": 20,
                "total_pages": 1
            }
        }


class SharePostRequest(BaseModel):
    """Schema for sharing a post via DM"""
    user_ids: List[str] = Field(..., min_length=1, max_length=10, description="User IDs to share with (max 10)")
    message: Optional[str] = Field(None, max_length=500, description="Optional personal message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_ids": ["user123", "user456"],
                "message": "Thought you'd find this interesting!"
            }
        }


class ShareFailure(BaseModel):
    """Schema for failed share attempt"""
    user_id: str = Field(..., description="User ID that failed")
    reason: str = Field(..., description="Reason for failure")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user789",
                "reason": "Not connected"
            }
        }


class SharePostResponse(BaseModel):
    """Schema for share post response"""
    message: str = Field(..., description="Success message")
    shared_to: int = Field(..., description="Number of users successfully shared to")
    failed: List[ShareFailure] = Field(default=[], description="List of failed share attempts")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Post shared successfully",
                "shared_to": 2,
                "failed": []
            }
        }
