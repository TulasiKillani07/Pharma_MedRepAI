"""
Activity Logs API Routes
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, Dict
from datetime import datetime
from io import StringIO

from app.core.auth import get_current_user
from app.api.v1.activity_logs import service
from app.api.v1.activity_logs.schemas import (
    ActivityLogListResponse,
    ActivityStatsResponse
)

router = APIRouter()


@router.get("", response_model=ActivityLogListResponse)
async def get_activity_logs_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Logs per page (max 100)"),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    actor_id: Optional[str] = Query(None, description="Filter by actor ID"),
    target_type: Optional[str] = Query(None, description="Filter by target type"),
    severity: Optional[str] = Query(None, regex="^(info|warning|critical)$", description="Filter by severity"),
    date_from: Optional[datetime] = Query(None, description="Filter from date (ISO format)"),
    date_to: Optional[datetime] = Query(None, description="Filter to date (ISO format)"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get paginated activity logs with filters.
    
    **Access:** Admin only
    
    **Purpose:**
    View all admin activities with filtering and pagination.
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Logs per page (default: 20, max: 100)
    - `action_type`: Filter by action type (e.g., "user_created", "post_deleted")
    - `actor_id`: Filter by admin who performed the action
    - `target_type`: Filter by resource type (e.g., "doctor", "post")
    - `severity`: Filter by severity (info, warning, critical)
    - `date_from`: Filter from date (ISO format: 2024-05-15T00:00:00Z)
    - `date_to`: Filter to date (ISO format: 2024-05-15T23:59:59Z)
    
    **Response:**
    ```json
    {
        "logs": [
            {
                "log_id": "...",
                "action_type": "user_created",
                "actor_name": "Admin User",
                "target_name": "Dr. John Doe",
                "severity": "info",
                "created_at": "2024-05-15T10:30:00Z"
            }
        ],
        "total": 150,
        "page": 1,
        "limit": 20,
        "total_pages": 8
    }
    ```
    
    **Use Cases:**
    - Audit admin actions
    - Track user management
    - Monitor content moderation
    - Security investigation
    """
    # Check if user is admin
    if current_user.get("role") != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Only admins can access activity logs"
        )
    
    return await service.get_activity_logs(
        page=page,
        limit=limit,
        action_type=action_type,
        actor_id=actor_id,
        target_type=target_type,
        severity=severity,
        date_from=date_from,
        date_to=date_to
    )


@router.get("/stats", response_model=ActivityStatsResponse)
async def get_activity_stats_endpoint(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get activity statistics.
    
    **Access:** Admin only
    
    **Purpose:**
    View aggregated statistics about admin activities.
    
    **Response:**
    ```json
    {
        "total_logs": 1500,
        "by_action_type": {
            "user_created": 50,
            "post_deleted": 25
        },
        "by_severity": {
            "info": 1400,
            "warning": 80,
            "critical": 20
        },
        "by_target_type": {
            "doctor": 100,
            "mr": 80
        },
        "recent_critical": 5
    }
    ```
    
    **Use Cases:**
    - Dashboard overview
    - Activity trends
    - Security monitoring
    """
    # Check if user is admin
    if current_user.get("role") != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Only admins can access activity stats"
        )
    
    return await service.get_activity_stats()


@router.get("/export")
async def export_activity_logs_endpoint(
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    actor_id: Optional[str] = Query(None, description="Filter by actor ID"),
    target_type: Optional[str] = Query(None, description="Filter by target type"),
    severity: Optional[str] = Query(None, regex="^(info|warning|critical)$", description="Filter by severity"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Export activity logs as CSV.
    
    **Access:** Admin only
    
    **Purpose:**
    Download activity logs for external analysis or archiving.
    
    **Query Parameters:**
    Same as GET /activity-logs (filters)
    
    **Response:**
    CSV file download (max 10,000 records)
    
    **Use Cases:**
    - Compliance reporting
    - External audit
    - Data archiving
    """
    from io import StringIO
    
    # Check if user is admin
    if current_user.get("role") != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Only admins can export activity logs"
        )
    
    csv_content = await service.export_activity_logs(
        action_type=action_type,
        actor_id=actor_id,
        target_type=target_type,
        severity=severity,
        date_from=date_from,
        date_to=date_to
    )
    
    # Return as downloadable CSV
    return StreamingResponse(
        StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=activity-logs-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )
