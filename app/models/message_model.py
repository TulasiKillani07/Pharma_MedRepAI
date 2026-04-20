"""
Message and Conversation models - MongoDB document structure for chat features.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum
from bson import ObjectId


class MessageType(str, Enum):
    """Message type constants"""
    TEXT = "text"
    SHARED_POST = "shared_post"


class MessageInDB(BaseModel):
    """
    Write model for message document (INSERT operations)
    
    Collection: messages
    Indexes:
    - conversation_id
    - sender_id
    - created_at DESC
    """
    conversation_id: str = Field(..., description="Conversation ID")
    sender_id: str = Field(..., description="Sender user ID")
    sender_name: str = Field(..., description="Sender name")
    sender_role: str = Field(..., description="Sender role")
    content: str = Field(..., min_length=1, max_length=5000, description="Message content")
    message_type: MessageType = Field(default=MessageType.TEXT, description="Message type")
    shared_post: Optional[Dict[str, Any]] = Field(None, description="Shared post data if type is shared_post")
    is_read: bool = Field(default=False, description="Read status")
    read_at: Optional[datetime] = Field(None, description="When marked as read")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    
    @field_validator('conversation_id', 'sender_id')
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


class MessageDocument(MessageInDB):
    """Read model for message document"""
    class Config:
        extra = "allow"


class ConversationInDB(BaseModel):
    """
    Write model for conversation document (INSERT operations)
    
    Collection: conversations
    Indexes:
    - participants (array)
    - last_message_at DESC
    """
    participants: List[str] = Field(..., description="Sorted list of participant user IDs")
    participant_details: List[Dict[str, Any]] = Field(default_factory=list, description="Participant info cache")
    last_message: Optional[str] = Field(None, description="Last message content")
    last_message_at: Optional[datetime] = Field(None, description="Last message timestamp")
    unread_count: Dict[str, int] = Field(default_factory=dict, description="Unread count per user")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    class Config:
        extra = "forbid"


class ConversationDocument(ConversationInDB):
    """Read model for conversation document"""
    class Config:
        extra = "allow"
