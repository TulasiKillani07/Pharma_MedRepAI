"""
Visit routes - API endpoints for visit management.
"""

from fastapi import APIRouter, Depends, Query, status, HTTPException, Request
from typing import Dict, Any, Optional
from datetime import date
from app.api.v1.visits.schemas import (
    VisitCreateRequest,
    VisitRescheduleRequest,
    VisitCompleteRequest,
    VisitCancelRequest,
    VisitResponse,
    VisitListResponse,
    MessageResponse,
    VisitCreateResponse
)
from app.api.v1.visits.service import (
    schedule_visit,
    get_visits,
    get_visit_by_id,
    reschedule_visit,
    complete_visit,
    cancel_visit
)
from app.core.auth import get_current_user, require_admin
from app.core.roles import UserRole


# Create router for visit endpoints
router = APIRouter()


@router.post("", response_model=VisitCreateResponse, status_code=status.HTTP_201_CREATED, summary="Schedule Visit")
async def schedule_visit_endpoint(
    visit_request: VisitCreateRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Schedule a new visit (MR only).
    
    **Access:** MR only
    
    **Validations:**
    - MR can only schedule with their assigned doctors
    - Doctor must not have another scheduled visit
    
    **Usage:**
    ```
    POST /api/v1/visits
    Headers: Authorization: Bearer <mr_token>
    {
        "doctor_id": "507f1f77bcf86cd799439011",
        "scheduled_date": "2024-04-15",
        "scheduled_time": "10:30",
        "purpose": "Product presentation",
        "location": "City Hospital, Room 301",
        "notes": "Bring samples"
    }
    ```
    """
    # Check if user is MR
    if current_user.get("role") != UserRole.MR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MRs can schedule visits"
        )
    
    return await schedule_visit(
        doctor_id=visit_request.doctor_id,
        scheduled_date=visit_request.scheduled_date,
        scheduled_time=visit_request.scheduled_time,
        purpose=visit_request.purpose,
        location=visit_request.location,
        notes=visit_request.notes,
        current_user=current_user,
        request=request
    )


@router.get("", response_model=VisitListResponse, summary="List Visits")
async def list_visits(
    current_user: Dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    doctor_id: Optional[str] = Query(None, description="Filter by doctor"),
    mr_id: Optional[str] = Query(None, description="Filter by MR (admin only)")
):
    """
    Get list of visits with filters.
    
    **Access:** Admin (all visits) and MR (own visits only)
    
    **Usage:**
    ```
    GET /api/v1/visits?status=scheduled&date_from=2024-04-01
    Headers: Authorization: Bearer <token>
    ```
    """
    # Check if user is admin or MR
    user_role = current_user.get("role")
    if user_role not in [UserRole.ADMIN.value, UserRole.MR.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin and MR can access visits"
        )
    
    visits = await get_visits(
        current_user=current_user,
        status_filter=status,
        date_from=date_from,
        date_to=date_to,
        doctor_id=doctor_id,
        mr_id=mr_id
    )
    
    return {
        "total": len(visits),
        "visits": visits
    }


@router.get("/{visit_id}", response_model=VisitResponse, summary="Get Visit Details")
async def get_visit(
    visit_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get details of a specific visit.
    
    **Access:** Admin (all visits) and MR (own visits only)
    """
    # Check if user is admin or MR
    user_role = current_user.get("role")
    if user_role not in [UserRole.ADMIN.value, UserRole.MR.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin and MR can access visits"
        )
    
    return await get_visit_by_id(visit_id, current_user)


@router.put("/{visit_id}/reschedule", response_model=MessageResponse, summary="Reschedule Visit")
async def reschedule_visit_endpoint(
    visit_id: str,
    request: VisitRescheduleRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Reschedule a visit (MR only).
    
    **Access:** MR only (own visits)
    
    **Can change:** Date, Time, Location, Notes
    **Cannot change:** Doctor, Purpose
    
    **Usage:**
    ```
    PUT /api/v1/visits/{visit_id}/reschedule
    Headers: Authorization: Bearer <mr_token>
    {
        "scheduled_date": "2024-04-16",
        "scheduled_time": "14:00",
        "location": "City Hospital, Room 302",
        "reason": "Doctor requested different time"
    }
    ```
    """
    # Check if user is MR
    if current_user.get("role") != UserRole.MR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MRs can reschedule visits"
        )
    
    return await reschedule_visit(
        visit_id=visit_id,
        scheduled_date=request.scheduled_date,
        scheduled_time=request.scheduled_time,
        location=request.location,
        notes=request.notes,
        reason=request.reason,
        current_user=current_user
    )


@router.put("/{visit_id}/complete", response_model=MessageResponse, summary="Complete Visit")
async def complete_visit_endpoint(
    visit_id: str,
    complete_request: VisitCompleteRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Complete a visit (MR only).
    
    **Access:** MR only (own visits)
    
    **Usage:**
    ```
    PUT /api/v1/visits/{visit_id}/complete
    Headers: Authorization: Bearer <mr_token>
    {
        "outcome": "Successfully presented new product line",
        "feedback": "Doctor requested follow-up next month"
    }
    ```
    """
    # Check if user is MR
    if current_user.get("role") != UserRole.MR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MRs can complete visits"
        )
    
    return await complete_visit(
        visit_id=visit_id,
        outcome=complete_request.outcome,
        feedback=complete_request.feedback,
        current_user=current_user,
        request=request
    )


@router.put("/{visit_id}/cancel", response_model=MessageResponse, summary="Cancel Visit")
async def cancel_visit_endpoint(
    visit_id: str,
    cancel_request: VisitCancelRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Cancel a visit (MR only).
    
    **Access:** MR only (own visits)
    
    **Usage:**
    ```
    PUT /api/v1/visits/{visit_id}/cancel
    Headers: Authorization: Bearer <mr_token>
    {
        "reason": "Doctor emergency, not available"
    }
    ```
    """
    # Check if user is MR
    if current_user.get("role") != UserRole.MR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MRs can cancel visits"
        )
    
    return await cancel_visit(
        visit_id=visit_id,
        reason=cancel_request.reason,
        current_user=current_user,
        request=request
    )
