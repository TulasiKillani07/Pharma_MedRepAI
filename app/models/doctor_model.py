"""
Doctor model - MongoDB schema for doctors collection.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class LocationType(str, Enum):
    """Location type constants"""
    PRIMARY = "primary"
    SECONDARY = "secondary"


class LocationSuggestionStatus(str, Enum):
    """Location suggestion status constants"""
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class DoctorLocation(BaseModel):
    """Schema for a doctor's location"""
    id: str = Field(..., description="Unique location ID")
    type: LocationType = Field(..., description="Location type: primary or secondary")
    name: str = Field(..., min_length=1, max_length=200, description="Location name")
    address: Optional[str] = Field(None, max_length=500, description="Full address")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    is_active: bool = Field(default=True, description="Whether location is active")
    geofence_radius: int = Field(default=100, ge=10, le=1000, description="Geofence radius in meters")
    added_by: str = Field(..., description="Admin user ID who added this location")
    added_at: datetime = Field(default_factory=datetime.utcnow, description="When location was added")
    suggested_from_usage: bool = Field(default=False, description="Whether this came from usage analysis")


class LocationSuggestion(BaseModel):
    """Schema for a suggested location (pending admin review)"""
    id: str = Field(..., description="Unique suggestion ID")
    name: str = Field(..., min_length=1, max_length=200, description="Location name")
    address: Optional[str] = Field(None, max_length=500, description="Full address")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    usage_count: int = Field(..., ge=1, description="Number of times used")
    first_used: datetime = Field(..., description="First time this location was used")
    last_used: datetime = Field(..., description="Last time this location was used")
    used_by_mrs: List[str] = Field(default_factory=list, description="List of MR IDs who used this location")
    status: LocationSuggestionStatus = Field(default=LocationSuggestionStatus.PENDING_REVIEW)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    admin_action: Optional[dict] = Field(None, description="Admin action details: {action_by, action_at, notes}")


class DoctorBase(BaseModel):
    """Base schema for Doctor with common fields"""
    email: EmailStr
    name: str  # Changed from full_name to match DB structure
    phone: str
    specialization: str
    classification: str  # Doctor classification (A/B/C) for SFE tracking
    hospital: Optional[str] = None
    license_number: Optional[str] = None
    address: Optional[str] = None


class DoctorInDB(DoctorBase):
    """Schema for doctor stored in database"""
    password_hash: str
    is_active: bool = True
    is_password_changed: bool = False  # Track if user changed their password
    password_changed_at: Optional[datetime] = None  # When password was last changed
    first_login_completed: bool = False  # Track if user has logged in at least once
    first_login_at: Optional[datetime] = None  # When user first logged in
    
    # Added by/Approved by tracking
    added_by: Optional[dict] = None  # {"role": str, "id": str, "name": str, "department": str}
    approved_by: Optional[dict] = None  # {"role": str, "id": str, "name": str, "department": str}
    
    # Location management
    locations: List[DoctorLocation] = Field(default_factory=list, description="Doctor's permanent locations")
    location_suggestions: List[LocationSuggestion] = Field(default_factory=list, description="Pending location suggestions")
    
    created_at: datetime
    updated_at: datetime
