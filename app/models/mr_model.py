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
    territory: str
    assigned_doctors: List[str] = []


class MRInDB(MRBase):
    """Schema for MR stored in database"""
    password_hash: str
    is_active: bool = True
    is_password_changed: bool = False  # Track if user changed their password
    password_changed_at: Optional[datetime] = None  # When password was last changed
    created_at: datetime
    updated_at: datetime
