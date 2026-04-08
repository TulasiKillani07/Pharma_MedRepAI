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


class MRStatistics(BaseModel):
    """Statistics for MR dashboard"""
    assigned_doctors: int = Field(..., description="Number of assigned doctors")
    total_visits: int = Field(..., description="Total visits count")
    completion_rate: str = Field(..., description="Visit completion rate percentage")


class DoctorStatistics(BaseModel):
    """Statistics for doctor dashboard"""
    total_cme_events: int = Field(..., description="Total CME events")
    upcoming_cme_events: int = Field(..., description="Upcoming CME events count")
    completed_cme_events: int = Field(..., description="Completed CME events count")
    total_drugs: int = Field(..., description="Total active drugs")


# ============ MR DASHBOARD SCHEMAS ============

class UpcomingVisit(BaseModel):
    """Upcoming visit information"""
    visit_id: str
    doctor_name: str
    doctor_specialization: Optional[str] = None
    scheduled_date: datetime
    scheduled_time: str
    purpose: str
    location: str
    status: str


class RecentVisit(BaseModel):
    """Recent visit information"""
    visit_id: str
    doctor_name: str
    scheduled_date: datetime
    status: str
    outcome: Optional[str] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None


class MRDashboardResponse(BaseModel):
    """Response schema for MR dashboard"""
    statistics: MRStatistics
    upcoming_visits: List[UpcomingVisit]
    recent_visits: List[RecentVisit]
    
    class Config:
        json_schema_extra = {
            "example": {
                "statistics": {
                    "assigned_doctors": 15,
                    "total_visits": 150,
                    "completion_rate": "90%"
                },
                "upcoming_visits": [
                    {
                        "visit_id": "visit123",
                        "doctor_name": "Dr. Sarah Sharma",
                        "doctor_specialization": "Cardiology",
                        "scheduled_date": "2024-04-10T10:00:00",
                        "scheduled_time": "10:00 AM",
                        "purpose": "Product demo",
                        "location": "Apollo Hospital",
                        "status": "scheduled"
                    }
                ],
                "recent_visits": [
                    {
                        "visit_id": "visit120",
                        "doctor_name": "Dr. Priya Sharma",
                        "scheduled_date": "2024-04-05T10:00:00",
                        "status": "completed",
                        "outcome": "Positive",
                        "completed_at": "2024-04-05T11:30:00"
                    }
                ]
            }
        }


# ============ DOCTOR DASHBOARD SCHEMAS ============

class UpcomingCMEEvent(BaseModel):
    """Upcoming CME event information"""
    event_id: str
    title: str
    description: Optional[str] = None
    event_date: datetime
    event_time: str
    event_type: str
    event_mode: str
    platform: Optional[str] = None
    platform_name: Optional[str] = None
    meeting_link: Optional[str] = None
    venue_name: Optional[str] = None
    address: Optional[str] = None
    speaker: str
    max_attendees: Optional[int] = None
    status: str


class RecentCMEEvent(BaseModel):
    """Recently completed CME event information"""
    event_id: str
    title: str
    description: Optional[str] = None
    event_date: datetime
    event_time: str
    event_type: str
    speaker: str
    event_recording: Optional[str] = None
    status: str


class RecentDrug(BaseModel):
    """Recently launched drug information"""
    drug_id: str
    drug_name: str
    brand_name: str
    drug_class: Optional[str] = None
    manufacturer: Optional[str] = None
    dosage_form: Optional[str] = None
    created_at: datetime


class DoctorDashboardResponse(BaseModel):
    """Response schema for doctor dashboard"""
    statistics: DoctorStatistics
    upcoming_cme_events: List[UpcomingCMEEvent]
    recent_cme_events: List[RecentCMEEvent]
    recent_drugs: List[RecentDrug]
    
    class Config:
        json_schema_extra = {
            "example": {
                "statistics": {
                    "total_cme_events": 25,
                    "upcoming_cme_events": 8,
                    "completed_cme_events": 15,
                    "total_drugs": 150
                },
                "upcoming_cme_events": [
                    {
                        "event_id": "cme123",
                        "title": "Advanced Cardiology Techniques",
                        "description": "Latest developments in cardiac care",
                        "event_date": "2024-04-15T10:00:00",
                        "event_time": "10:00 AM - 12:00 PM",
                        "event_type": "Webinar",
                        "event_mode": "online",
                        "platform": "Zoom",
                        "meeting_link": "https://zoom.us/j/123456789",
                        "speaker": "Dr. John Smith",
                        "max_attendees": 100,
                        "status": "upcoming"
                    }
                ],
                "recent_cme_events": [
                    {
                        "event_id": "cme120",
                        "title": "Diabetes Management Workshop",
                        "description": "Comprehensive diabetes care strategies",
                        "event_date": "2024-04-05T14:00:00",
                        "event_time": "2:00 PM - 4:00 PM",
                        "event_type": "Workshop",
                        "speaker": "Dr. Sarah Johnson",
                        "event_recording": "https://example.com/recording123",
                        "status": "completed"
                    }
                ],
                "recent_drugs": [
                    {
                        "drug_id": "drug123",
                        "drug_name": "paracetamol",
                        "brand_name": "crocin",
                        "drug_class": "Analgesic",
                        "manufacturer": "GSK",
                        "dosage_form": "Tablet",
                        "created_at": "2024-04-07T09:00:00"
                    }
                ]
            }
        }
