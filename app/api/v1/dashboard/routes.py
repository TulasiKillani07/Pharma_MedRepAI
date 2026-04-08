"""
Dashboard API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.core.auth import get_current_user
from app.api.v1.dashboard.schemas import AdminDashboardResponse
from app.api.v1.dashboard import service


router = APIRouter()


@router.get("", response_model=AdminDashboardResponse)
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
        "recent_activity": [
            {
                "id": "doctor_507f1f77bcf86cd799439011",
                "type": "doctor_added",
                "title": "New Doctor Added",
                "description": "Dr. Sarah Sharma joined as Cardiologist",
                "timestamp": "2024-04-07T10:30:00",
                "user": "Dr. Sarah Sharma"
            },
            {
                "id": "cme_507f1f77bcf86cd799439012",
                "type": "cme_created",
                "title": "CME Event Created",
                "description": "Hypertension Management Webinar scheduled",
                "timestamp": "2024-04-07T09:15:00",
                "user": "Admin"
            },
            {
                "id": "drug_507f1f77bcf86cd799439013",
                "type": "drug_added",
                "title": "New Drug Added",
                "description": "Paracetamol (Crocin) added to inventory",
                "timestamp": "2024-04-07T08:45:00",
                "user": "Admin"
            }
        ]
    }
    ```
    
    **Activity Types:**
    - `doctor_added`: New doctor registered
    - `mr_added`: New MR registered
    - `drug_added`: New drug added to inventory
    - `cme_created`: New CME event created
    - `visit_scheduled`: New visit scheduled
    
    **Statistics Explained:**
    - `total_drugs`: Count of active drugs in inventory
    - `total_mrs`: Total MRs in system
    - `total_doctors`: Total doctors in system
    - `total_cme_events`: Total CME events created
    - `active_mrs`: MRs with is_active=true
    - `active_doctors`: Doctors with is_active=true
    - `upcoming_cme_events`: CME events with status="upcoming"
    
    **Recent Activity:**
    - Shows last 10 activities across all entities
    - Sorted by timestamp (most recent first)
    - Includes: doctors, MRs, drugs, CME events, visits
    
    **Future Enhancement:**
    - Doctor dashboard: Shows doctor-specific data
    - MR dashboard: Shows MR-specific data
    - Currently only admin dashboard is implemented
    """
    role = current_user.get("role")
    
    if role == "ADMIN":
        return await service.get_admin_dashboard()
    elif role == "DOCTOR":
        # TODO: Implement doctor dashboard
        raise HTTPException(
            status_code=501,
            detail="Doctor dashboard not yet implemented"
        )
    elif role == "MR":
        # TODO: Implement MR dashboard
        raise HTTPException(
            status_code=501,
            detail="MR dashboard not yet implemented"
        )
    else:
        raise HTTPException(
            status_code=403,
            detail="Invalid role for dashboard access"
        )
