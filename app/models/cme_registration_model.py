"""
CME Event Registration Model
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class RegistrationStatus(str, Enum):
    """Registration status constants"""
    REGISTERED = "registered"


class CMERegistrationInDB(BaseModel):
    """
    Write model for CME registration document (INSERT operations)
    
    Collection: cme_registrations
    Indexes:
    - Compound: (cme_id, doctor_id) UNIQUE
    - Single: cme_id
    - Single: doctor_id
    """
    cme_id: str = Field(..., description="Reference to CME event")
    doctor_id: str = Field(..., description="Reference to doctor")
    doctor_name: str = Field(..., description="Cached doctor name")
    doctor_email: str = Field(..., description="Cached doctor email")
    registration_status: RegistrationStatus = Field(default=RegistrationStatus.REGISTERED, description="Registration status")
    registration_passcode: Optional[str] = Field(None, description="Passcode for offline event registration")
    registered_at: datetime = Field(default_factory=datetime.utcnow, description="Registration timestamp")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    class Config:
        extra = "forbid"


class CMERegistrationDocument(CMERegistrationInDB):
    """Read model for CME registration document"""
    class Config:
        extra = "allow"
