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


@router.get(
    "",
    response_model=ActivityLogListResponse,
    summary="Get Activity Logs",
    description="""
    **Purpose:** Get paginated activity logs with filters. Tracks all admin and MR actions in the system.
    
    **Access:** Admin only
    
    **What Gets Logged:**
    - User Management: user_created, user_updated, user_activated, user_deactivated, user_deleted
    - Visit Management: visit_scheduled, visit_completed, visit_cancelled
    - Drug Management: drug_created, drug_updated, drug_deleted, drug_bulk_upload
    - CME Management: cme_created, cme_updated, cme_deleted, cme_registered
    - Content Moderation: post_deleted, comment_deleted, user_reported, content_flagged
    - Bulk Operations: bulk_upload_doctors, bulk_upload_mrs
    - Authentication: user_login, user_logout, admin_login, admin_logout, password_changed, failed_login
    
    **Severity Levels:**
    - `info`: Normal operations (user created, visit scheduled)
    - `warning`: Notable actions (user deactivated, visit cancelled)
    - `critical`: High-impact actions (user deleted, bulk operations)
    
    **Example Request:**
    ```
    GET /api/v1/activity-logs?page=1&limit=20&severity=critical
    GET /api/v1/activity-logs?action_type=visit_completed&date_from=2026-05-01
    GET /api/v1/activity-logs?actor_id=6a0d9eb8...&target_type=visit
    ```
    
    **Example Response:**
    ```json
    {
      "logs": [
        {
          "log_id": "6a0d...",
          "action_type": "visit_completed",
          "message": "Rajesh Kumar completed a visit with Dr. Sneha",
          "actor_id": "6a0d9eb8...",
          "actor_name": "Rajesh Kumar",
          "actor_role": "MR",
          "target_type": "visit",
          "target_id": "6a0edec2...",
          "target_name": null,
          "action_details": {
            "doctor_id": "6a0d9fa2...",
            "doctor_name": "Dr. Sneha",
            "outcome": "Doctor interested in product",
            "products_promoted_count": 2,
            "samples_given": 3
          },
          "severity": "info",
          "ip_address": "183.82.41.52",
          "user_agent": "Mozilla/5.0...",
          "created_at": "2026-05-25T10:08:07"
        },
        {
          "log_id": "6a0d...",
          "action_type": "visit_scheduled",
          "message": "Vamsi scheduled a visit with Dr. Sneha Sharma",
          "actor_id": "6a141e8d...",
          "actor_name": "Vamsi",
          "actor_role": "MR",
          "target_type": "visit",
          "target_id": "6a141ef9...",
          "target_name": null,
          "action_details": {
            "doctor_id": "6a0edbdd...",
            "doctor_name": "Dr. Sneha Sharma",
            "scheduled_date": "2026-06-26",
            "scheduled_time": "15:36",
            "purpose": "Drug Promotion"
          },
          "severity": "info",
          "ip_address": "183.82.41.52",
          "user_agent": "Mozilla/5.0...",
          "created_at": "2026-05-25T10:05:45"
        },
        {
          "log_id": "6a0d...",
          "action_type": "user_created",
          "message": "Admin created Suresh Patel",
          "actor_id": "6a0d...",
          "actor_name": "Admin",
          "actor_role": "ADMIN",
          "target_type": "mr",
          "target_id": "6a0d...",
          "target_name": "Suresh Patel",
          "action_details": {
            "email": "suresh@example.com",
            "territory": "Hyderabad"
          },
          "severity": "info",
          "ip_address": "103.217.239.66",
          "user_agent": "Mozilla/5.0...",
          "created_at": "2026-05-25T09:30:00"
        }
      ],
      "total": 150,
      "page": 1,
      "limit": 20,
      "total_pages": 8
    }
    ```
    
    **Filter Options:**
    - `action_type`: user_created | user_updated | user_activated | user_deactivated | user_deleted | visit_scheduled | visit_completed | visit_cancelled | drug_created | drug_updated | drug_deleted | drug_bulk_upload | cme_created | cme_updated | cme_deleted | post_deleted | bulk_upload_doctors | bulk_upload_mrs | user_login | admin_login | failed_login | password_changed
    - `target_type`: doctor | mr | visit | drug | cme_event | post | comment | system
    - `severity`: info | warning | critical
    - `actor_id`: Filter by specific MR or Admin ID
    - `date_from` / `date_to`: ISO datetime format (e.g., 2026-05-01T00:00:00)
    """
)
async def get_activity_logs_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Logs per page (max 100)"),
    action_type: Optional[str] = Query(None, description="Filter by action type (e.g., visit_completed, user_created)"),
    actor_id: Optional[str] = Query(None, description="Filter by actor ID (MR or Admin)"),
    target_type: Optional[str] = Query(None, description="Filter by target type (doctor, mr, visit, drug, cme_event)"),
    severity: Optional[str] = Query(None, description="Filter by severity: info | warning | critical"),
    date_from: Optional[datetime] = Query(None, description="Filter from date (ISO format: 2026-05-01T00:00:00)"),
    date_to: Optional[datetime] = Query(None, description="Filter to date (ISO format: 2026-05-31T23:59:59)"),
    current_user: Dict = Depends(get_current_user)
):
    if current_user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Only admins can access activity logs")
    
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


@router.get(
    "/stats",
    response_model=ActivityStatsResponse,
    summary="Get Activity Statistics",
    description="""
    **Purpose:** Get aggregated statistics about all system activities.
    
    **Access:** Admin only
    
    **What It Shows:**
    - Total log count
    - Breakdown by action type (which actions happen most)
    - Breakdown by severity (how many critical events)
    - Breakdown by target type (which resources are most affected)
    - Breakdown by actor (which MRs/Admins are most active)
    - Today's activity count
    - Recent critical events (last 24 hours)
    
    **Example Response:**
    ```json
    {
      "total_logs": 1500,
      "today_logs": 45,
      "by_action_type": {
        "visit_completed": 320,
        "visit_scheduled": 280,
        "user_created": 50,
        "drug_created": 30,
        "failed_login": 10
      },
      "by_severity": {
        "info": 1400,
        "warning": 80,
        "critical": 20
      },
      "by_target_type": {
        "visit": 600,
        "doctor": 100,
        "mr": 80,
        "drug": 60
      },
      "by_actor": [
        { "actor_id": "6a0d...", "actor_name": "Rajesh Kumar", "actor_role": "MR", "count": 120 },
        { "actor_id": "6a0d...", "actor_name": "Admin", "actor_role": "ADMIN", "count": 85 }
      ],
      "recent_critical": 5
    }
    ```
    
    **Use Cases:**
    - Admin dashboard overview
    - Identify most active MRs
    - Monitor security events (failed_login, critical actions)
    - Track system usage patterns
    """
)
async def get_activity_stats_endpoint(
    current_user: Dict = Depends(get_current_user)
):
    if current_user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Only admins can access activity stats")
    
    return await service.get_activity_stats()


@router.get(
    "/export",
    summary="Export Activity Logs as CSV",
    description="""
    **Purpose:** Download activity logs as a CSV file for external analysis or compliance reporting.
    
    **Access:** Admin only
    
    **Response:** CSV file download (max 10,000 records)
    
    **CSV Columns:**
    - Timestamp, Action Type, Actor Name, Actor Role, Target Type, Target Name, Severity, IP Address, User Agent, Details
    
    **Example Request:**
    ```
    GET /api/v1/activity-logs/export?severity=critical&date_from=2026-05-01
    GET /api/v1/activity-logs/export?action_type=failed_login
    GET /api/v1/activity-logs/export?actor_id=6a0d9eb8...
    ```
    
    **Use Cases:**
    - Compliance reporting
    - External audit
    - Data archiving
    - Security investigation
    """
)
async def export_activity_logs_endpoint(
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    actor_id: Optional[str] = Query(None, description="Filter by actor ID"),
    target_type: Optional[str] = Query(None, description="Filter by target type"),
    severity: Optional[str] = Query(None, description="Filter by severity: info | warning | critical"),
    date_from: Optional[datetime] = Query(None, description="Filter from date (ISO format)"),
    date_to: Optional[datetime] = Query(None, description="Filter to date (ISO format)"),
    current_user: Dict = Depends(get_current_user)
):
    if current_user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Only admins can export activity logs")
    
    csv_content = await service.export_activity_logs(
        action_type=action_type,
        actor_id=actor_id,
        target_type=target_type,
        severity=severity,
        date_from=date_from,
        date_to=date_to
    )
    
    return StreamingResponse(
        StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=activity-logs-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )
