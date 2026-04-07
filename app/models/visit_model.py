"""
Visit model - MongoDB schema for visits collection.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date


class RescheduleHistoryEntry(BaseModel):
    """Schema for reschedule history entry"""
    old_date: date
    old_time: str
    new_date: date
    new_time: str
    rescheduled_at: datetime
    reason: Optional[str] = None


class VisitBase(BaseModel):
    """Base schema for Visit with common fields"""
    mr_id: str
    mr_name: str
    doctor_id: str
    doctor_name: str
    scheduled_date: date
    scheduled_time: str
    purpose: str
    location: str
    notes: Optional[str] = None
    status: str  # scheduled, completed, cancelled


class VisitInDB(VisitBase):
    """Schema for Visit stored in database"""
    outcome: Optional[str] = None
    feedback: Optional[str] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    reschedule_history: List[RescheduleHistoryEntry] = []
    created_at: datetime
    updated_at: datetime
