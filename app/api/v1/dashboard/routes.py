"""
Dashboard API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.core.auth import get_current_user
from app.api.v1.dashboard import service


router = APIRouter()


@router.get("", summary="Get Dashboard Endpoint")
async def get_dashboard_endpoint(current_user: Dict = Depends(get_current_user)):
    """
    **Purpose:** Get role-based dashboard data.

    **Access:** Admin and MR only. Doctor returns 403 (use DRX).

    **Request Body:** None

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
      "upcoming_visits": [...],
      "recent_visits": [...]
    }
    ```
    """
    role = current_user.get("role")
    user_id = current_user.get("_id")

    if role == "ADMIN":
        return await service.get_admin_dashboard()
    elif role == "MR":
        return await service.get_mr_dashboard(user_id)
    elif role == "DOCTOR":
        raise HTTPException(status_code=403, detail="Doctor dashboard is on DRX platform. Use DRX.")
    else:
        raise HTTPException(status_code=403, detail="Invalid role for dashboard access")
