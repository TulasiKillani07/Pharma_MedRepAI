"""
Doctor Location Management Schemas
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class AddLocationRequest(BaseModel):
    """Schema for adding a new location to doctor"""
    name: str = Field(..., min_length=1, max_length=200, description="Location name")
    address: str = Field(..., max_length=500, description="Full address")
    country: str = Field(..., max_length=100, description="Country")
    state: str = Field(..., max_length=100, description="State / Province")
    district: str = Field(..., max_length=100, description="District / City")
    city: str = Field(..., max_length=100, description="City")
    area: str = Field(..., max_length=200, description="Area / Locality / Neighbourhood")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    type: str = Field(default="hospital", description="Location type: hospital, solo_clinic, or polyclinic")
    geofence_radius: int = Field(default=100, ge=10, le=1000, description="Geofence radius in meters")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"hospital", "solo_clinic", "polyclinic"}
        if v not in allowed:
            raise ValueError(f"type must be one of: {', '.join(sorted(allowed))}")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Apollo Hospital - Jubilee Hills",
                "address": "Road 45, Jubilee Hills, Hyderabad - 500033",
                "country": "India",
                "state": "Telangana",
                "district": "Ranga Reddy",
                "city": "Hyderabad",
                "area": "Jubilee Hills",
                "latitude": 17.4401,
                "longitude": 78.3489,
                "type": "hospital",
                "geofence_radius": 100
            }
        }
    }


class UpdateLocationRequest(BaseModel):
    """Schema for updating a location"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    address: Optional[str] = Field(None, max_length=500)
    country: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    area: Optional[str] = Field(None, max_length=200)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    type: Optional[str] = Field(None, description="hospital, solo_clinic, or polyclinic")
    geofence_radius: Optional[int] = Field(None, ge=10, le=1000)
    is_active: Optional[bool] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"hospital", "solo_clinic", "polyclinic"}
        if v not in allowed:
            raise ValueError(f"type must be one of: {', '.join(sorted(allowed))}")
        return v


class LocationResponse(BaseModel):
    """Schema for location response"""
    id: str
    type: str  # str not enum — allows old values (primary/secondary) to pass through
    name: str
    address: Optional[str] = None    # Optional for backward compat with old docs
    country: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    area: Optional[str] = None       # Optional for backward compat with old docs
    latitude: float
    longitude: float
    is_active: bool
    geofence_radius: int
    added_by: str
    added_at: datetime
    suggested_from_usage: bool


class LocationListResponse(BaseModel):
    """Schema for list of locations"""
    total: int
    locations: List[LocationResponse]


class GeoSearchRequest(BaseModel):
    """Schema for geosearch request"""
    query: str = Field(..., min_length=1, max_length=200, description="Search query")
    limit: int = Field(default=5, ge=1, le=10, description="Maximum results")
    user_latitude: Optional[float] = Field(None, ge=-90, le=90, description="User's latitude for location bias")
    user_longitude: Optional[float] = Field(None, ge=-180, le=180, description="User's longitude for location bias")


class GeoSearchResult(BaseModel):
    """Schema for a single geosearch result"""
    display_name: str
    latitude: float
    longitude: float
    address: dict
    type: str
    importance: float


class GeoSearchResponse(BaseModel):
    """Schema for geosearch response"""
    total: int
    results: List[GeoSearchResult]


class LocationSuggestionResponse(BaseModel):
    """Schema for location suggestion"""
    id: str
    name: str
    address: Optional[str]
    latitude: float
    longitude: float
    usage_count: int
    first_used: datetime
    last_used: datetime
    used_by_mrs: List[str]
    status: str
    created_at: datetime
    admin_action: Optional[dict]


class LocationSuggestionsResponse(BaseModel):
    """Schema for list of suggestions"""
    total: int
    suggestions: List[LocationSuggestionResponse]


class ApproveSuggestionRequest(BaseModel):
    """Schema for approving a suggestion"""
    notes: Optional[str] = Field(None, max_length=500, description="Admin notes")
    geofence_radius: int = Field(default=100, ge=10, le=1000, description="Geofence radius in meters")


class RejectSuggestionRequest(BaseModel):
    """Schema for rejecting a suggestion"""
    notes: str = Field(..., min_length=1, max_length=500, description="Reason for rejection")


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    location: Optional[dict] = None  # For add location response
    location_id: Optional[str] = None  # For approve suggestion response
