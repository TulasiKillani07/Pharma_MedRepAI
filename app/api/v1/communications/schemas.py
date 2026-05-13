"""
Communication schemas - Request/Response models for API endpoints.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime
from app.models.communication_model import CommunicationType, CommunicationPriority, AttachmentInfo


# ============ REQUEST SCHEMAS ============

class CommunicationTargetingRequest(BaseModel):
    """
    Targeting criteria for creating/updating communications.
    No 'type' field - backend derives targeting from populated arrays.
    At least one array must be populated (or all empty for "all MRs").
    
    Fixed values for dropdowns:
    - zones: Only "South" available
    - states: "Telangana", "Andhra Pradesh"
    - territories: "Hyderabad", "Visakhapatnam"
    """
    zones: Optional[List[Literal["South"]]] = Field(default=[], description="Target zones (only South available)")
    states: Optional[List[Literal["Telangana", "Andhra Pradesh"]]] = Field(default=[], description="Target states")
    territories: Optional[List[Literal["Hyderabad", "Visakhapatnam"]]] = Field(default=[], description="Target territories")
    specific_mrs: Optional[List[str]] = Field(default=[], description="Target specific MR IDs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "zones": [],
                "states": ["Telangana"],
                "territories": [],
                "specific_mrs": []
            }
        }


class CommunicationCreateRequest(BaseModel):
    """Schema for creating a new communication"""
    title: str = Field(..., min_length=1, max_length=200, description="Communication title")
    content: str = Field(..., min_length=1, description="Communication content")
    type: CommunicationType = Field(..., description="Communication type")
    priority: CommunicationPriority = Field(..., description="Priority level")
    targeting: CommunicationTargetingRequest = Field(..., description="Targeting criteria")
    attachments: Optional[List[AttachmentInfo]] = Field(default=[], description="File attachments")
    expires_at: Optional[datetime] = Field(None, description="Expiry date (optional)")
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        return v
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Content cannot be empty")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Hyderabad Meeting Tomorrow",
                "content": "Team meeting at 10 AM at Hyderabad office. Please be on time.",
                "type": "announcement",
                "priority": "high",
                "targeting": {
                    "zones": [],
                    "states": [],
                    "territories": ["Hyderabad"],
                    "specific_mrs": []
                },
                "attachments": [],
                "expires_at": "2024-12-31T23:59:59"
            }
        }


class CommunicationUpdateRequest(BaseModel):
    """Schema for updating a communication (all fields optional)"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    type: Optional[CommunicationType] = None
    priority: Optional[CommunicationPriority] = None
    targeting: Optional[CommunicationTargetingRequest] = None
    attachments: Optional[List[AttachmentInfo]] = None
    expires_at: Optional[datetime] = None
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Title cannot be empty")
        return v
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Content cannot be empty")
        return v


# ============ RESPONSE SCHEMAS ============

class CommunicationTargetingResponse(BaseModel):
    """Targeting info in response"""
    zones: List[str]
    states: List[str]
    territories: List[str]
    specific_mrs: List[str]


class CommunicationListItem(BaseModel):
    """Schema for communication in list view (preview)"""
    id: str
    title: str
    type: CommunicationType
    priority: CommunicationPriority
    preview: str = Field(..., description="First 100 characters of content")
    is_read: bool = Field(..., description="Whether current MR has read this")
    created_at: datetime
    created_by_name: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "title": "Hyderabad Meeting Tomorrow",
                "type": "announcement",
                "priority": "high",
                "preview": "Team meeting at 10 AM at Hyderabad office...",
                "is_read": False,
                "created_at": "2024-03-30T10:00:00",
                "created_by_name": "Admin"
            }
        }


class CommunicationDetailResponse(BaseModel):
    """Schema for full communication details"""
    id: str
    title: str
    content: str
    type: CommunicationType
    priority: CommunicationPriority
    targeting: CommunicationTargetingResponse
    attachments: List[AttachmentInfo]
    expires_at: Optional[datetime]
    created_at: datetime
    created_by_name: str
    is_read: bool = Field(..., description="Whether current MR has read this (MR view only)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "title": "Hyderabad Meeting Tomorrow",
                "content": "Team meeting at 10 AM at Hyderabad office. Please be on time. Agenda: Q4 targets review.",
                "type": "announcement",
                "priority": "high",
                "targeting": {
                    "zones": [],
                    "states": [],
                    "territories": ["Hyderabad"],
                    "specific_mrs": []
                },
                "attachments": [
                    {
                        "file_name": "agenda.pdf",
                        "file_url": "https://cloudinary.com/...",
                        "file_type": "pdf",
                        "file_size": 1024000
                    }
                ],
                "expires_at": "2024-12-31T23:59:59",
                "created_at": "2024-03-30T10:00:00",
                "created_by_name": "Admin",
                "is_read": False
            }
        }


class CommunicationAdminDetailResponse(BaseModel):
    """Schema for admin view of communication (includes targeting stats)"""
    id: str
    title: str
    content: str
    type: CommunicationType
    priority: CommunicationPriority
    targeting: CommunicationTargetingResponse
    attachments: List[AttachmentInfo]
    expires_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by_name: str


class CommunicationListResponse(BaseModel):
    """Schema for paginated list of communications"""
    total: int
    page: int
    limit: int
    total_pages: int
    communications: List[CommunicationListItem]


class CommunicationCreateResponse(BaseModel):
    """Response after creating communication"""
    message: str
    communication_id: str
    targeted_mrs: int = Field(..., description="Number of MRs targeted")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Communication sent successfully",
                "communication_id": "507f1f77bcf86cd799439011",
                "targeted_mrs": 15
            }
        }


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str


class UnreadCountResponse(BaseModel):
    """Response for unread count"""
    unread_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "unread_count": 5
            }
        }


# ============ ANALYTICS SCHEMAS ============

class MRReadInfo(BaseModel):
    """Info about MR who read/didn't read"""
    mr_id: str
    mr_name: str
    territory: str
    state: str
    read_at: Optional[datetime] = None


class CommunicationAnalyticsResponse(BaseModel):
    """Analytics for a specific communication"""
    communication_id: str
    title: str
    total_targeted: int = Field(..., description="Total MRs targeted")
    total_read: int = Field(..., description="Number of MRs who read")
    read_percentage: float = Field(..., description="Percentage of MRs who read")
    read_by: List[MRReadInfo] = Field(..., description="MRs who read")
    not_read_by: List[MRReadInfo] = Field(..., description="MRs who haven't read")
    
    class Config:
        json_schema_extra = {
            "example": {
                "communication_id": "507f1f77bcf86cd799439011",
                "title": "Hyderabad Meeting Tomorrow",
                "total_targeted": 15,
                "total_read": 12,
                "read_percentage": 80.0,
                "read_by": [
                    {
                        "mr_id": "mr_123",
                        "mr_name": "Rajesh Kumar",
                        "territory": "Hyderabad",
                        "state": "Telangana",
                        "read_at": "2024-03-30T11:00:00"
                    }
                ],
                "not_read_by": [
                    {
                        "mr_id": "mr_456",
                        "mr_name": "Priya Sharma",
                        "territory": "Hyderabad",
                        "state": "Telangana",
                        "read_at": None
                    }
                ]
            }
        }
