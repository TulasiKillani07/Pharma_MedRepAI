"""
Chat Request/Response Schemas
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


class MessageResponse(BaseModel):
    """Schema for message response"""
    message_id: str = Field(..., description="Message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    sender_id: str = Field(..., description="Sender user ID")
    sender_name: str = Field(..., description="Sender name")
    sender_role: str = Field(..., description="Sender role")
    content: str = Field(..., description="Message content")
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
                "content": "Hello!",
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
