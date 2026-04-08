"""
Dashboard API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.core.auth import get_current_user
from app.api.v1.dashboard.schemas import AdminDashboardResponse, MRDashboardResponse, DoctorDashboardResponse
from app.api.v1.dashboard import service


router = APIRouter()


@router.get("")
async def get_dashboard_endpoint(current_user: Dict = Depends(get_current_user)):
    """
    Get role-based dashboard data.
    
    **Access:** All authenticated users (Admin, Doctor, MR)
    
    **Purpose:**
    Provides dashboard statistics and recent activity based on user role.
    
    **Flow:**
    1. User requests dashboard
    2. Backend checks user role
    3. Returns role-specific dashboard data
    
    **Admin Dashboard:**
    - Statistics: Total drugs, MRs, doctors, CME events
    - Recent Activity: Last 10 activities across all entities
    
    **MR Dashboard:**
    - My Info: Name, email, phone, territory
    - Statistics: Assigned doctors, total visits, completion rate
    - Upcoming Visits: Next 5 scheduled/rescheduled visits
    - Recent Visits: Last 5 completed/cancelled visits
    
    **Doctor Dashboard:**
    - Statistics: Total CME events, upcoming CME events, completed CME events, total drugs
    - Upcoming CME Events: Next 5 upcoming CME events with full details
    - Recent CME Events: Last 5 completed CME events with recordings
    - Recent Drugs: Last 5 recently launched drugs
    
    **Usage:**
    ```
    GET /api/v1/dashboard
    Headers: Authorization: Bearer <token>
    ```
    
    **Response (Admin):**
    ```json
    {
        "statistics": {
            "total_drugs": 150,
            "total_mrs": 25,
            "total_doctors": 80,
            "total_cme_events": 12,
            "active_mrs": 23,
            "active_doctors": 75,
            "upcoming_cme_events": 5
        },
        "recent_activity": [...]
    }
    ```
    
    **Response (MR):**
    ```json
    {
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
                "scheduled_date": "2024-04-10",
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
                "scheduled_date": "2024-04-05",
                "status": "completed",
                "outcome": "Positive - Doctor interested",
                "completed_at": "2024-04-05T11:30:00"
            }
        ]
    }
    ```
    
    **Response (Doctor):**
    ```json
    {
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
    ```
    
    **Activity Types (Admin):**
    - `doctor_added`: New doctor registered
    - `mr_added`: New MR registered
    - `drug_added`: New drug added to inventory
    - `cme_created`: New CME event created
    - `visit_scheduled`: New visit scheduled
    
    **Visit Status (MR):**
    - Upcoming: `scheduled`, `rescheduled`
    - Recent: `completed`, `cancelled`
    
    **Statistics Explained (Admin):**
    - `total_drugs`: Count of active drugs in inventory
    - `total_mrs`: Total MRs in system
    - `total_doctors`: Total doctors in system
    - `total_cme_events`: Total CME events created
    - `active_mrs`: MRs with is_active=true
    - `active_doctors`: Doctors with is_active=true
    - `upcoming_cme_events`: CME events with status="upcoming"
    
    **Statistics Explained (MR):**
    - `assigned_doctors`: Number of doctors assigned to this MR
    - `total_visits`: Total visits created by this MR
    - `completion_rate`: Percentage of completed visits (completed / total)
    
    **Statistics Explained (Doctor):**
    - `total_cme_events`: Total CME events in the system
    - `upcoming_cme_events`: CME events with status="upcoming"
    - `completed_cme_events`: CME events with status="completed"
    - `total_drugs`: Count of active drugs in inventory
    
    **CME Event Details (Doctor):**
    - Upcoming events show full details including online/offline mode
    - Online events include platform and meeting link
    - Offline events include venue name and address
    - Completed events include recording links for on-demand learning
    
    **Drug Details (Doctor):**
    - Shows recently added drugs for reference
    - Includes drug name, brand name, class, manufacturer, dosage form
    - Sorted by creation date (most recent first)
    
    **Future Enhancement:**
    - Doctor dashboard: Track CME attendance and certificates (not yet implemented)
    """
    role = current_user.get("role")
    user_id = current_user.get("_id")
    
    if role == "ADMIN":
        return await service.get_admin_dashboard()
    elif role == "MR":
        return await service.get_mr_dashboard(user_id)
    elif role == "DOCTOR":
        return await service.get_doctor_dashboard(user_id)
    else:
        raise HTTPException(
            status_code=403,
            detail="Invalid role for dashboard access"
        )
