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
    department: str = Field(default="general", description="Department code (general, hr, finance, it)")


class AdminInDB(AdminBase):
    """Schema for admin stored in database"""
    password_hash: str
    role: str = Field(default="ADMIN", description="User role")
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
