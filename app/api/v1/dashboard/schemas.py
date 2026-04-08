"""
Dashboard Request/Response Schemas
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ============ STATISTICS SCHEMAS ============

class AdminStatistics(BaseModel):
    """Statistics for admin dashboard"""
    total_drugs: int = Field(..., description="Total active drugs")
    total_mrs: int = Field(..., description="Total active MRs")
    total_doctors: int = Field(..., description="Total active doctors")
    total_cme_events: int = Field(..., description="Total CME events")
    active_mrs: int = Field(..., description="Active MRs count")
    active_doctors: int = Field(..., description="Active doctors count")
    upcoming_cme_events: int = Field(..., description="Upcoming CME events count")


# ============ ACTIVITY SCHEMAS ============

class RecentActivity(BaseModel):
    """Schema for recent activity item"""
    id: str = Field(..., description="Activity ID")
    type: str = Field(..., description="Activity type: doctor_added, mr_added, drug_added, cme_created, visit_scheduled")
    title: str = Field(..., description="Activity title")
    description: str = Field(..., description="Activity description")
    timestamp: datetime = Field(..., description="Activity timestamp")
    user: Optional[str] = Field(None, description="User who performed the action")


# ============ DASHBOARD RESPONSE SCHEMAS ============

class AdminDashboardResponse(BaseModel):
    """Response schema for admin dashboard"""
    statistics: AdminStatistics
    recent_activity: List[RecentActivity]
    
    class Config:
        json_schema_extra = {
            "example": {
                "statistics": {
                    "total_drugs": 150,
                    "total_mrs": 25,
                    "total_doctors": 80,
                    "total_cme_events": 12,
                    "active_mrs": 23,
                    "active_doctors": 75,
                    "upcoming_cme_events": 5
                },
                "recent_activity": [
                    {
                        "id": "activity_1",
                        "type": "doctor_added",
                        "title": "New Doctor Added",
                        "description": "Dr. Sarah Sharma joined as Cardiologist",
                        "timestamp": "2024-04-07T10:30:00",
                        "user": "Dr. Sarah Sharma"
                    }
                ]
            }
        }
