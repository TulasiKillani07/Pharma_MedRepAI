"""
Chat/Message Request/Response Schemas
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class MessageCreate(BaseModel):
    """Schema for creating a message"""
    content: str = Field(..., min_length=1, max_length=2000, description="Message content")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "Hello! How are you doing today?"
            }
        }


class SharedPostData(BaseModel):
    """Schema for shared post data in message"""
    post_id: str = Field(..., description="Post ID")
    author_name: str = Field(..., description="Post author name")
    author_role: str = Field(..., description="Post author role")
    content: str = Field(..., description="Post content")
    likes_count: int = Field(..., description="Number of likes")
    comments_count: int = Field(..., description="Number of comments")
    created_at: datetime = Field(..., description="Post creation time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "post_id": "post123",
                "author_name": "Dr. John Doe",
                "author_role": "DOCTOR",
                "content": "New drug insights...",
                "likes_count": 10,
                "comments_count": 5,
                "created_at": "2024-04-10T10:00:00"
            }
        }


class MessageResponse(BaseModel):
    """Schema for message response"""
    message_id: str = Field(..., description="Message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    sender_id: str = Field(..., description="Sender user ID")
    sender_name: str = Field(..., description="Sender name")
    sender_role: str = Field(..., description="Sender role")
    content: str = Field(..., description="Message content")
    message_type: str = Field(default="text", description="Message type: text or shared_post")
    shared_post: Optional[SharedPostData] = Field(None, description="Shared post data (only if message_type=shared_post)")
    is_read: bool = Field(..., description="Read status")
    read_at: Optional[datetime] = Field(None, description="When message was read")
    created_at: datetime = Field(..., description="Message creation time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "msg123",
                "conversation_id": "conv123",
                "sender_id": "user123",
                "sender_name": "Dr. Sarah Sharma",
                "sender_role": "DOCTOR",
                "content": "Thought you'd find this interesting!",
                "message_type": "shared_post",
                "shared_post": {
                    "post_id": "post123",
                    "author_name": "Dr. John Doe",
                    "author_role": "DOCTOR",
                    "content": "New drug insights...",
                    "likes_count": 10,
                    "comments_count": 5,
                    "created_at": "2024-04-10T10:00:00"
                },
                "is_read": True,
                "read_at": "2024-04-10T15:35:00",
                "created_at": "2024-04-10T15:30:00"
            }
        }


class MessageListResponse(BaseModel):
    """Schema for paginated messages list"""
    messages: List[MessageResponse] = Field(..., description="List of messages")
    total: int = Field(..., description="Total number of messages")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Messages per page")
    total_pages: int = Field(..., description="Total number of pages")


class OtherUser(BaseModel):
    """Schema for other user in conversation"""
    user_id: str = Field(..., description="User ID")
    name: str = Field(..., description="User name")
    role: str = Field(..., description="User role")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user456",
                "name": "Raj Kumar",
                "role": "MR"
            }
        }


class ConversationResponse(BaseModel):
    """Schema for conversation response"""
    conversation_id: str = Field(..., description="Conversation ID")
    other_user: OtherUser = Field(..., description="Other user details")
    last_message: Optional[str] = Field(None, description="Last message preview")
    last_message_at: Optional[datetime] = Field(None, description="Last message time")
    unread_count: int = Field(..., description="Unread messages count")
    
    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv123",
                "other_user": {
                    "user_id": "user456",
                    "name": "Raj Kumar",
                    "role": "MR"
                },
                "last_message": "Thanks for the information!",
                "last_message_at": "2024-04-10T15:30:00",
                "unread_count": 2
            }
        }


class ConversationListResponse(BaseModel):
    """Schema for conversations list"""
    conversations: List[ConversationResponse] = Field(..., description="List of conversations")
    total: int = Field(..., description="Total number of conversations")
    
    class Config:
        json_schema_extra = {
            "example": {
                "conversations": [
                    {
                        "conversation_id": "conv123",
                        "other_user": {
                            "user_id": "user456",
                            "name": "Raj Kumar",
                            "role": "MR"
                        },
                        "last_message": "Thanks!",
                        "last_message_at": "2024-04-10T15:30:00",
                        "unread_count": 2
                    }
                ],
                "total": 10
            }
        }


class ConversationStartResponse(BaseModel):
    """Schema for starting conversation response"""
    conversation_id: str = Field(..., description="Conversation ID")
    message: str = Field(..., description="Success message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv123",
                "message": "Conversation started"
            }
        }
