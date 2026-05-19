"""
Notification model - MongoDB document structure for notifications collection.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class NotificationType(str, Enum):
    """Notification type constants"""
    # Network notifications
    CONNECTION_REQUEST = "connection_request"
    CONNECTION_ACCEPTED = "connection_accepted"
    POST_LIKED = "post_liked"
    POST_COMMENTED = "post_commented"
    POST_SHARED = "post_shared"
    NEW_MESSAGE = "new_message"
    GROUP_MESSAGE = "group_message"
    GROUP_ADDED = "group_added"
    
    # CME notifications
    CME_CREATED = "cme_created"
    CME_UPDATED = "cme_updated"
    CME_CANCELLED = "cme_cancelled"
    CME_REMINDER_1DAY = "cme_reminder_1day"
    CME_REMINDER_1HOUR = "cme_reminder_1hour"
    CME_RECORDING = "cme_recording"
    CME_REGISTRATION_CONFIRMED = "cme_registration_confirmed"
    CME_REGISTRATION_CANCELLED = "cme_registration_cancelled"
    
    # Drug notifications
    DRUG_ADDED = "drug_added"
    
    # Visit notifications
    VISIT_SCHEDULED = "visit_scheduled"
    VISIT_RESCHEDULED = "visit_rescheduled"
    VISIT_COMPLETED = "visit_completed"
    VISIT_CANCELLED = "visit_cancelled"
    
    # Doctor approval notifications
    DOCTOR_REQUEST_PENDING = "doctor_request_pending"
    DOCTOR_REQUEST_APPROVED = "doctor_request_approved"
    DOCTOR_REQUEST_REJECTED = "doctor_request_rejected"


class NotificationInDB(BaseModel):
    """
    Write model for notification document (INSERT operations)
    
    Collection: notifications
    Indexes:
    - Compound: (user_id, created_at) DESC
    - Compound: (user_id, is_read)
    - TTL: created_at (30 days)
    """
    user_id: str = Field(..., description="Recipient user ID (internal, no validation needed)")
    type: NotificationType = Field(..., description="Notification type")
    title: str = Field(..., min_length=1, max_length=200, description="Notification title")
    message: str = Field(..., min_length=1, max_length=500, description="Notification message")
    data: Dict[str, Any] = Field(default_factory=dict, description="Type-specific data")
    is_read: bool = Field(default=False, description="Read status")
    read_at: Optional[datetime] = Field(None, description="When marked as read")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    
    class Config:
        extra = "forbid"  # Strict - no extra fields allowed for writes


class NotificationDocument(NotificationInDB):
    """
    Read model for notification document (if validation needed)
    Inherits all fields from NotificationInDB
    """
    class Config:
        extra = "allow"  # Flexible - allow extra fields from DB
