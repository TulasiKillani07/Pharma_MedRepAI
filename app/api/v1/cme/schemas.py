"""
CME Event Request/Response Schemas
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date
from app.core.validators import DateValidator, URLValidator, TextValidator


# ============ CME EVENT SCHEMAS ============

class CMEEventCreate(BaseModel):
    """Schema for creating a CME event"""
    title: str
    description: Optional[str] = None
    event_date: date  # Accept date from frontend
    event_time: str  # e.g., "10:00 AM - 12:00 PM"
    event_type: str  # Webinar, Conference, Workshop, Seminar
    max_attendees: Optional[int] = None
    
    # Event Mode
    event_mode: str  # "online" or "offline"
    
    # Online mode fields
    platform: Optional[str] = None  # "Zoom", "Teams", "Google Meet", "Other"
    platform_name: Optional[str] = None  # Required if platform = "Other"
    meeting_link: Optional[str] = None  # Meeting URL
    
    # Offline mode fields
    venue_name: Optional[str] = None  # Venue name
    address: Optional[str] = None  # Venue address
    
    speaker: str
    status: str = "upcoming"  # Default to upcoming, admin must change manually
    
    # Validators
    @field_validator('event_date')
    @classmethod
    def validate_date(cls, v: date) -> date:
        return DateValidator.validate_future_date(v, max_years=2)
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        return TextValidator.validate(v, max_length=2000, strip_html=True)
    
    @field_validator('meeting_link')
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        return URLValidator.validate(v, max_length=500)


class CMEEventUpdate(BaseModel):
    """Schema for updating a CME event"""
    title: Optional[str] = None
    description: Optional[str] = None
    event_date: Optional[date] = None
    event_time: Optional[str] = None
    event_type: Optional[str] = None
    max_attendees: Optional[int] = None
    
    # Event Mode
    event_mode: Optional[str] = None
    
    # Online mode fields
    platform: Optional[str] = None
    platform_name: Optional[str] = None
    meeting_link: Optional[str] = None
    
    # Offline mode fields
    venue_name: Optional[str] = None
    address: Optional[str] = None
    
    speaker: Optional[str] = None
    status: Optional[str] = None  # Can manually set to cancelled/rescheduled
    event_recording: Optional[str] = None
    
    # Validators
    @field_validator('event_date')
    @classmethod
    def validate_date(cls, v: Optional[date]) -> Optional[date]:
        if v is None:
            return None
        return DateValidator.validate_future_date(v, max_years=2)
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        return TextValidator.validate(v, max_length=2000, strip_html=True)
    
    @field_validator('meeting_link', 'event_recording')
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        return URLValidator.validate(v, max_length=500)


class CMEEventResponse(BaseModel):
    """Schema for CME event response"""
    id: str = Field(alias="_id")
    title: str
    description: Optional[str]
    event_date: datetime
    event_time: str
    event_type: str
    max_attendees: Optional[int]
    
    # Event Mode (optional for backward compatibility with old data)
    event_mode: Optional[str] = None
    
    # Online mode fields
    platform: Optional[str] = None
    platform_name: Optional[str] = None
    meeting_link: Optional[str] = None
    
    # Offline mode fields
    venue_name: Optional[str] = None
    address: Optional[str] = None
    
    # Legacy field (for old data)
    location: Optional[str] = None
    
    speaker: str
    status: str
    event_recording: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class CMEEventListResponse(BaseModel):
    """Schema for listing CME events"""
    events: List[CMEEventResponse]
    total: int
