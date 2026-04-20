"""
CME (Continuing Medical Education) Event Model
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from bson import ObjectId


class CMEEventMode(str, Enum):
    """CME event mode constants"""
    ONLINE = "online"
    OFFLINE = "offline"


class CMEEventStatus(str, Enum):
    """CME event status constants"""
    UPCOMING = "upcoming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"


class CMEPlatform(str, Enum):
    """CME online platform constants"""
    ZOOM = "Zoom"
    TEAMS = "Teams"
    GOOGLE_MEET = "Google Meet"
    OTHER = "Other"


class CMEEventInDB(BaseModel):
    """
    Write model for CME event document (INSERT operations)
    
    Collection: cme_events
    Indexes:
    - event_date
    - status
    - event_mode
    """
    title: str = Field(..., min_length=1, max_length=200, description="Event title")
    description: Optional[str] = Field(None, max_length=2000, description="Event description")
    event_date: datetime = Field(..., description="Date and time of the event")
    event_time: str = Field(..., description="Time as string (e.g., '10:00 AM - 12:00 PM')")
    event_type: str = Field(..., description="Webinar, Conference, Workshop, etc.")
    max_attendees: Optional[int] = Field(None, ge=1, description="Maximum number of attendees")
    
    # Event Mode fields
    event_mode: CMEEventMode = Field(..., description="Online or offline event")
    
    # Online mode fields
    platform: Optional[CMEPlatform] = Field(None, description="Online platform")
    platform_name: Optional[str] = Field(None, description="Custom platform name if Other")
    meeting_link: Optional[str] = Field(None, description="Meeting URL")
    
    # Offline mode fields
    venue_name: Optional[str] = Field(None, description="Venue name")
    address: Optional[str] = Field(None, description="Venue address")
    
    speaker: str = Field(..., description="Speaker name")
    status: CMEEventStatus = Field(default=CMEEventStatus.UPCOMING, description="Event status")
    event_recording: Optional[str] = Field(None, description="URL to recording")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    class Config:
        extra = "forbid"


class CMEEventDocument(CMEEventInDB):
    """Read model for CME event document"""
    class Config:
        extra = "allow"
