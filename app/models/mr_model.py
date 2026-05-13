"""
MR (Medical Representative) model - MongoDB schema for mrs collection.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class MRBase(BaseModel):
    """Base schema for MR with common fields"""
    email: EmailStr
    full_name: str
    phone: str
    zone: str  # Geographic zone (e.g., South, North, East, West)
    state: str  # State (e.g., Telangana, Karnataka, Maharashtra)
    territory: str  # Sales territory (e.g., Hyderabad, Bangalore North)
    assigned_doctors: List[str] = []


class MRInDB(MRBase):
    """Schema for MR stored in database"""
    password_hash: str
    is_active: bool = True
    is_password_changed: bool = False  # Track if user changed their password
    password_changed_at: Optional[datetime] = None  # When password was last changed
    first_login_completed: bool = False  # Track if user has logged in at least once
    first_login_at: Optional[datetime] = None  # When user first logged in
    created_at: datetime
    updated_at: datetime
