"""
Doctor model - MongoDB schema for doctors collection.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class DoctorBase(BaseModel):
    """Base schema for Doctor with common fields"""
    email: EmailStr
    full_name: str
    phone: str
    specialization: str
    hospital: Optional[str] = None
    license_number: Optional[str] = None
    address: Optional[str] = None


class DoctorInDB(DoctorBase):
    """Schema for doctor stored in database"""
    password_hash: str
    is_active: bool = True
    is_password_changed: bool = False  # Track if user changed their password
    password_changed_at: Optional[datetime] = None  # When password was last changed
    first_login_completed: bool = False  # Track if user has logged in at least once
    first_login_at: Optional[datetime] = None  # When user first logged in
    created_at: datetime
    updated_at: datetime
