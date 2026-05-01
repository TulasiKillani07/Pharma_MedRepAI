"""
Password Reset Token model - MongoDB schema for password_reset_tokens collection.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class PasswordResetToken(BaseModel):
    """Schema for password reset token stored in database"""
    email: EmailStr
    role: str  # ADMIN, DOCTOR, or MR
    otp: str  # 6-digit OTP code
    created_at: datetime
    expires_at: datetime  # 15 minutes from creation
    is_used: bool = False
    used_at: Optional[datetime] = None
