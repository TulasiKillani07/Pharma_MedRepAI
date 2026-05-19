"""
Doctor Request model - MongoDB schema for doctor_requests collection.
Stores MR requests to add new doctors, pending admin approval.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


class RequestStatus(str, Enum):
    """Doctor request status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DoctorRequestInDB(BaseModel):
    """
    Write model for doctor request document (INSERT operations)
    
    Collection: doctor_requests
    Indexes:
    - status
    - requested_by
    - created_at DESC
    """
    # Request metadata
    requested_by: str = Field(..., description="MR user ID who requested")
    requested_by_name: str = Field(..., description="MR name")
    requested_by_email: str = Field(..., description="MR email")
    status: RequestStatus = Field(default=RequestStatus.PENDING, description="Request status")
    
    # Doctor details
    name: str = Field(..., min_length=2, max_length=100, description="Doctor's full name")
    email: EmailStr = Field(..., description="Doctor's email address")
    phone: str = Field(..., description="Doctor's phone number")
    specialization: str = Field(..., min_length=2, max_length=100, description="Medical specialization")
    hospital: Optional[str] = Field(None, max_length=200, description="Hospital name")
    license_number: Optional[str] = Field(None, max_length=50, description="Medical license number")
    address: Optional[str] = Field(None, max_length=500, description="Full address")
    
    # Approval metadata
    reviewed_by: Optional[str] = Field(None, description="Admin user ID who reviewed")
    reviewed_by_name: Optional[str] = Field(None, description="Admin name")
    reviewed_at: Optional[datetime] = Field(None, description="When reviewed")
    rejection_reason: Optional[str] = Field(None, max_length=500, description="Reason for rejection")
    
    # Created doctor ID (if approved)
    doctor_id: Optional[str] = Field(None, description="Created doctor ID after approval")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Request creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    class Config:
        extra = "forbid"  # Strict - no extra fields allowed for writes


class DoctorRequestDocument(DoctorRequestInDB):
    """
    Read model for doctor request document
    Inherits all fields from DoctorRequestInDB
    """
    class Config:
        extra = "allow"  # Flexible - allow extra fields from DB
