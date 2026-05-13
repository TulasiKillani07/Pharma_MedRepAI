"""
Grievance model - MongoDB schema for grievances collection.
Internal ticketing system where MRs raise issues and admins respond.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class GrievancePriority(str, Enum):
    """Grievance priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class GrievanceStatus(str, Enum):
    """Grievance status lifecycle"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class GrievanceInDB(BaseModel):
    """Schema for grievance stored in database"""
    ticket_id: str = Field(..., description="Auto-generated ticket ID (e.g., HR-2026-001)")
    department: str = Field(..., description="Department code (references departments.code)")
    subject: str = Field(..., max_length=200, description="Grievance subject")
    description: str = Field(..., max_length=2000, description="Detailed description")
    priority: GrievancePriority = Field(..., description="Priority level")
    status: GrievanceStatus = Field(default=GrievanceStatus.OPEN, description="Current status")
    
    # MR Information
    created_by: str = Field(..., description="MR ID who created the grievance")
    created_by_name: str = Field(..., description="MR name")
    created_by_email: str = Field(..., description="MR email")
    mr_territory: Optional[str] = Field(None, description="MR's territory")
    mr_state: Optional[str] = Field(None, description="MR's state")
    
    # Admin Response
    admin_response: Optional[str] = Field(None, max_length=2000, description="Admin's response")
    responded_by: Optional[str] = Field(None, description="Admin ID who responded")
    responded_by_name: Optional[str] = Field(None, description="Admin name")
    responded_at: Optional[datetime] = Field(None, description="Response timestamp")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    
    # Soft delete
    is_active: bool = Field(default=True, description="Soft delete flag")
    
    class Config:
        json_schema_extra = {
            "example": {
                "ticket_id": "HR-2026-001",
                "department": "hr",
                "subject": "Leave balance discrepancy",
                "description": "My leave balance shows 5 days but I have only taken 3 days this year.",
                "priority": "medium",
                "status": "open",
                "created_by": "507f1f77bcf86cd799439011",
                "created_by_name": "Rajesh Kumar",
                "created_by_email": "rajesh@xyzpharma.com",
                "mr_territory": "Hyderabad",
                "mr_state": "Telangana",
                "admin_response": None,
                "responded_by": None,
                "responded_by_name": None,
                "responded_at": None,
                "created_at": "2026-05-13T10:00:00",
                "updated_at": "2026-05-13T10:00:00",
                "resolved_at": None,
                "is_active": True
            }
        }
