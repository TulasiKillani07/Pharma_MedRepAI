"""
Message and Conversation models - MongoDB document structure for chat features.
"""

from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime


class MessageInDB(BaseModel):
    """Database model for message document"""
    conversation_id: str
    sender_id: str
    sender_name: str
    sender_role: str
    content: str
    message_type: str = "text"  # text or shared_post
    shared_post: Optional[Dict] = None
    is_read: bool = False
    read_at: Optional[datetime] = None
    created_at: datetime


class ConversationInDB(BaseModel):
    """Database model for conversation document"""
    participants: List[str]  # Sorted list of user IDs
    participant_details: List[Dict]
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: Dict[str, int]  # {user_id: count}
    created_at: datetime
    updated_at: datetime
