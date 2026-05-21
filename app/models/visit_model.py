"""
Visit model - MongoDB schema for visits collection.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum
from bson import ObjectId


class VisitStatus(str, Enum):
    """Visit status constants"""
    SCHEDULED = "scheduled"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RescheduleHistoryEntry(BaseModel):
    """Schema for reschedule history entry"""
    old_date: date
    old_time: str
    new_date: date
    new_time: str
    rescheduled_at: datetime
    reason: Optional[str] = None


class VisitInDB(BaseModel):
    """
    Write model for visit document (INSERT operations)
    
    Collection: visits
    Indexes:
    - mr_id
    - doctor_id
    - scheduled_date
    - status
    """
    mr_id: str = Field(..., description="MR user ID")
    mr_name: str = Field(..., description="MR name")
    doctor_id: str = Field(..., description="Doctor user ID")
    doctor_name: str = Field(..., description="Doctor name")
    scheduled_date: date = Field(..., description="Visit date")
    scheduled_time: str = Field(..., description="Visit time")
    purpose: str = Field(..., min_length=1, max_length=500, description="Visit purpose")
    location: str = Field(..., min_length=1, max_length=200, description="Visit location")
    
    @field_validator('location')
    @classmethod
    def validate_location(cls, v: str) -> str:
        """Ensure location is not empty"""
        if not v or not v.strip():
            raise ValueError('Location cannot be empty')
        return v.strip()
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    status: VisitStatus = Field(default=VisitStatus.SCHEDULED, description="Visit status")
    
    # Check-in/Check-out data
    check_in: Optional[dict] = Field(None, description="Check-in data: {timestamp, latitude, longitude}")
    check_out: Optional[dict] = Field(None, description="Check-out data: {timestamp, latitude, longitude}")
    duration_minutes: Optional[int] = Field(None, description="Visit duration in minutes")
    
    # Check-in cancellation audit
    check_in_cancelled: Optional[dict] = Field(None, description="Check-in cancellation data: {timestamp, reason, original_check_in}")
    
    # Visit report (DCR)
    report: Optional[dict] = Field(None, description="Visit report data")
    
    # Legacy fields (for backward compatibility)
    outcome: Optional[str] = Field(None, max_length=1000, description="Visit outcome")
    feedback: Optional[str] = Field(None, max_length=1000, description="Visit feedback")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    cancelled_at: Optional[datetime] = Field(None, description="Cancellation timestamp")
    cancel_reason: Optional[str] = Field(None, max_length=500, description="Cancellation reason")
    reschedule_history: List[RescheduleHistoryEntry] = Field(default_factory=list, description="Reschedule history")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    @field_validator('mr_id', 'doctor_id')
    @classmethod
    def validate_object_id(cls, v: str) -> str:
        """Validate IDs are valid ObjectId format"""
        try:
            ObjectId(v)
            return v
        except Exception:
            raise ValueError(f'Invalid ObjectId format: {v}')
    
    class Config:
        extra = "forbid"


class VisitDocument(VisitInDB):
    """Read model for visit document"""
    class Config:
        extra = "allow"
