"""
Group model - MongoDB document structure for groups collection.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId


class GroupInDB(BaseModel):
    """
    Write model for group document (INSERT operations)
    
    Collection: groups
    Indexes:
    - members (array)
    - created_by
    - is_active
    """
    group_name: str = Field(..., min_length=1, max_length=100, description="Group name")
    group_description: Optional[str] = Field(None, max_length=500, description="Group description")
    created_by: str = Field(..., description="Creator user ID")
    admins: List[str] = Field(default_factory=list, description="List of admin user IDs")
    members: List[str] = Field(default_factory=list, description="List of member user IDs")
    member_details: List[Dict[str, Any]] = Field(default_factory=list, description="Member info cache")
    last_message: Optional[str] = Field(None, description="Last message content")
    last_message_at: Optional[datetime] = Field(None, description="Last message timestamp")
    unread_count: Dict[str, int] = Field(default_factory=dict, description="Unread count per user")
    left_members: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Users who left")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Group settings")
    is_active: bool = Field(default=True, description="Soft delete flag")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    @field_validator('created_by')
    @classmethod
    def validate_created_by(cls, v: str) -> str:
        """Validate created_by is valid ObjectId format"""
        try:
            ObjectId(v)
            return v
        except Exception:
            raise ValueError(f'Invalid ObjectId format: {v}')
    
    class Config:
        extra = "forbid"


class GroupDocument(GroupInDB):
    """Read model for group document"""
    class Config:
        extra = "allow"
