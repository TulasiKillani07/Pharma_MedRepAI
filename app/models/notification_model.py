"""
Notification model - MongoDB document structure for notifications collection.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class NotificationType:
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
    CME_REMINDER_1DAY = "cme_reminder_1day"
    CME_REMINDER_1HOUR = "cme_reminder_1hour"
    CME_RECORDING = "cme_recording"
    
    # Drug notifications
    DRUG_ADDED = "drug_added"
    
    # Visit notifications
    VISIT_SCHEDULED = "visit_scheduled"
    VISIT_RESCHEDULED = "visit_rescheduled"
    VISIT_COMPLETED = "visit_completed"
    VISIT_CANCELLED = "visit_cancelled"


class NotificationInDB(BaseModel):
    """Database model for notification document"""
    user_id: str
    type: str
    title: str
    message: str
    data: Dict[str, Any]
    is_read: bool = False
    read_at: Optional[datetime] = None
    created_at: datetime
