"""
Group model - MongoDB document structure for groups collection.
"""

from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


class GroupInDB(BaseModel):
    """Database model for group document"""
    group_name: str
    group_description: Optional[str] = None
    created_by: str
    admins: List[str]
    members: List[str]
    member_details: List[Dict]
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: Dict[str, int]  # {user_id: count}
    left_members: Dict[str, Dict] = {}  # {user_id: {user_id, name, role, left_at}}
    settings: Dict = {}
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
