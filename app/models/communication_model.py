"""
Communication model - MongoDB schema for communications collection.
One-way broadcast system where Admin sends targeted messages to MRs.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class CommunicationType(str, Enum):
    """Communication type categories"""
    ANNOUNCEMENT = "announcement"
    ALERT = "alert"
    TARGET = "target"
    TRAINING = "training"


class CommunicationPriority(str, Enum):
    """Communication priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AttachmentInfo(BaseModel):
    """Schema for file attachments"""
    file_name: str
    file_url: str
    file_type: str  # pdf, jpg, png, etc.
    file_size: int  # in bytes


class CommunicationTargeting(BaseModel):
    """
    Targeting criteria for communications.
    No 'type' field - backend derives targeting from populated arrays.
    Uses OR logic: MR matches if they match ANY condition.
    """
    zones: List[str] = Field(default=[], description="Target zones (e.g., ['South'])")
    states: List[str] = Field(default=[], description="Target states (e.g., ['Telangana', 'Karnataka'])")
    territories: List[str] = Field(default=[], description="Target territories (e.g., ['Hyderabad', 'Bangalore'])")
    specific_mrs: List[str] = Field(default=[], description="Target specific MR IDs")


class CommunicationInDB(BaseModel):
    """Schema for communication stored in database"""
    title: str
    content: str
    type: CommunicationType
    priority: CommunicationPriority
    targeting: CommunicationTargeting
    attachments: List[AttachmentInfo] = []
    link: Optional[str] = Field(None, description="Optional external link (URL)")
    expires_at: Optional[datetime] = None
    created_by: str  # Admin ID
    created_by_name: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
