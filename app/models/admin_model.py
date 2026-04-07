"""
Company Admin model - MongoDB schema for company_admins collection.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class AdminBase(BaseModel):
    """Base schema for Admin with common fields"""
    email: EmailStr
    full_name: str
    phone: str
    company_name: str


class AdminInDB(AdminBase):
    """Schema for admin stored in database"""
    password_hash: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
