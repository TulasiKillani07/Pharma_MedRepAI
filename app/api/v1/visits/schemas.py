"""
Visit request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class VisitStatus(str, Enum):
    """Visit status enum"""
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class VisitCreateRequest(BaseModel):
    """Schema for scheduling a new visit"""
    doctor_id: str = Field(..., description="Doctor ID to visit")
    scheduled_date: date = Field(..., description="Visit date (YYYY-MM-DD)")
    scheduled_time: str = Field(..., description="Visit time (HH:MM)")
    purpose: str = Field(..., min_length=5, description="Purpose of visit")
    location: str = Field(..., description="Visit location")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "doctor_id": "507f1f77bcf86cd799439011",
                "scheduled_date": "2024-04-15",
                "scheduled_time": "10:30",
                "purpose": "Product presentation and discussion",
                "location": "City Hospital, Room 301",
                "notes": "Bring product samples"
            }
        }


class VisitRescheduleRequest(BaseModel):
    """Schema for rescheduling a visit"""
    scheduled_date: date = Field(..., description="New visit date")
    scheduled_time: str = Field(..., description="New visit time")
    location: Optional[str] = Field(None, description="New location")
    notes: Optional[str] = Field(None, description="Updated notes")
    reason: Optional[str] = Field(None, description="Reason for rescheduling")
    
    class Config:
        json_schema_extra = {
            "example": {
                "scheduled_date": "2024-04-16",
                "scheduled_time": "14:00",
                "location": "City Hospital, Room 302",
                "reason": "Doctor requested different time"
            }
        }


class VisitCompleteRequest(BaseModel):
    """Schema for completing a visit"""
    outcome: str = Field(..., min_length=10, description="Visit outcome summary")
    feedback: Optional[str] = Field(None, description="Additional feedback")
    
    class Config:
        json_schema_extra = {
            "example": {
                "outcome": "Successfully presented new product line. Doctor showed interest.",
                "feedback": "Doctor requested follow-up meeting next month"
            }
        }


class VisitCancelRequest(BaseModel):
    """Schema for cancelling a visit"""
    reason: str = Field(..., min_length=5, description="Reason for cancellation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Doctor emergency, not available"
            }
        }


class RescheduleHistoryResponse(BaseModel):
    """Schema for reschedule history entry"""
    old_date: date
    old_time: str
    new_date: date
    new_time: str
    rescheduled_at: datetime
    reason: Optional[str] = None


class VisitResponse(BaseModel):
    """Schema for visit response"""
    id: str
    mr_id: str
    mr_name: str
    doctor_id: str
    doctor_name: str
    scheduled_date: date
    scheduled_time: str
    purpose: str
    location: str
    notes: Optional[str] = None
    status: VisitStatus
    
    # Conditional fields
    outcome: Optional[str] = None
    feedback: Optional[str] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    reschedule_history: List[RescheduleHistoryResponse] = []
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "mr_id": "507f1f77bcf86cd799439012",
                "mr_name": "Rajesh Kumar",
                "doctor_id": "507f1f77bcf86cd799439013",
                "doctor_name": "Dr. Sarah Sharma",
                "scheduled_date": "2024-04-15",
                "scheduled_time": "10:30",
                "purpose": "Product presentation",
                "location": "City Hospital",
                "notes": "Bring samples",
                "status": "scheduled",
                "created_at": "2024-03-30T10:00:00",
                "updated_at": "2024-03-30T10:00:00"
            }
        }


class VisitListResponse(BaseModel):
    """Schema for list of visits"""
    total: int
    visits: List[VisitResponse]


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str


class VisitCreateResponse(BaseModel):
    """Response for visit creation"""
    message: str
    visit_id: str
