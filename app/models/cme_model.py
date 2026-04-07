"""
CME (Continuing Medical Education) Event Model
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CMEEvent(BaseModel):
    """CME Event document"""
    title: str
    description: Optional[str] = None
    event_date: datetime  # Date of the event
    event_time: str  # Time as string (e.g., "10:00 AM - 12:00 PM")
    event_type: str  # Webinar, Conference, Workshop, etc.
    max_attendees: Optional[int] = None
    
    # Event Mode fields
    event_mode: str  # "online" or "offline"
    
    # Online mode fields (required if event_mode = "online")
    platform: Optional[str] = None  # "Zoom", "Teams", "Google Meet", "Other"
    platform_name: Optional[str] = None  # Required if platform = "Other"
    meeting_link: Optional[str] = None  # Meeting URL
    
    # Offline mode fields (required if event_mode = "offline")
    venue_name: Optional[str] = None  # Venue name
    address: Optional[str] = None  # Venue address
    
    speaker: str  # Speaker name
    status: str  # upcoming, completed, cancelled, rescheduled
    event_recording: Optional[str] = None  # URL to recording
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
