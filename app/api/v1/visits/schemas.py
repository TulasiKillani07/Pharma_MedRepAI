"""
Visit request/response schemas.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum
from app.core.validators import DateValidator, TimeValidator, TextValidator


class VisitStatus(str, Enum):
    """Visit status enum"""
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class VisitCreateRequest(BaseModel):
    """Schema for scheduling a new visit"""
    doctor_id: str = Field(..., description="Doctor ID to visit")
    scheduled_date: date = Field(..., description="Visit date (YYYY-MM-DD)")
    scheduled_time: str = Field(..., description="Visit time (HH:MM or HH:MM AM/PM)")
    purpose: str = Field(..., min_length=5, description="Purpose of visit")
    location: str = Field(..., description="Visit location")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    # Validators
    @field_validator('scheduled_date')
    @classmethod
    def validate_date(cls, v: date) -> date:
        return DateValidator.validate_future_date(v, max_years=1)
    
    @field_validator('scheduled_time')
    @classmethod
    def validate_time(cls, v: str) -> str:
        result = TimeValidator.validate(v)
        if result is None:
            raise ValueError('Time is required')
        return result
    
    @field_validator('purpose')
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        result = TextValidator.validate(v, min_length=5, max_length=500, strip_html=True)
        if result is None:
            raise ValueError('Purpose is required')
        return result
    
    @field_validator('notes')
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        return TextValidator.validate(v, max_length=1000, strip_html=True)
    
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
    scheduled_time: str = Field(..., description="New visit time (HH:MM or HH:MM AM/PM)")
    location: Optional[str] = Field(None, description="New location")
    notes: Optional[str] = Field(None, description="Updated notes")
    reason: Optional[str] = Field(None, description="Reason for rescheduling")
    
    # Validators
    @field_validator('scheduled_date')
    @classmethod
    def validate_date(cls, v: date) -> date:
        return DateValidator.validate_future_date(v, max_years=1)
    
    @field_validator('scheduled_time')
    @classmethod
    def validate_time(cls, v: str) -> str:
        result = TimeValidator.validate(v)
        if result is None:
            raise ValueError('Time is required')
        return result
    
    @field_validator('notes', 'reason')
    @classmethod
    def validate_text(cls, v: Optional[str]) -> Optional[str]:
        return TextValidator.validate(v, max_length=1000, strip_html=True)
    
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
    
    # Validators
    @field_validator('outcome')
    @classmethod
    def validate_outcome(cls, v: str) -> str:
        result = TextValidator.validate(v, min_length=10, max_length=1000, strip_html=True)
        if result is None:
            raise ValueError('Outcome is required')
        return result
    
    @field_validator('feedback')
    @classmethod
    def validate_feedback(cls, v: Optional[str]) -> Optional[str]:
        return TextValidator.validate(v, max_length=1000, strip_html=True)
    
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
    
    # Validators
    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v: str) -> str:
        result = TextValidator.validate(v, min_length=5, max_length=500, strip_html=True)
        if result is None:
            raise ValueError('Reason is required')
        return result
    
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
