"""
Grievance routes - API endpoints for grievance management.
MRs can create and view their grievances.
Admins can view and respond to grievances (filtered by department).
"""

from fastapi import APIRouter, Depends, Query, status
from typing import Dict, Any, Optional
from app.core.auth import require_mr, require_admin
from app.api.v1.grievances.schemas import (
    GrievanceCreateRequest,
    GrievanceResponseRequest,
    GrievanceCreateResponse,
    GrievanceListResponse,
    GrievanceDetailResponse,
    GrievanceStatsResponse,
    MessageResponse
)
from app.api.v1.grievances.service import (
    create_grievance,
    get_my_grievances,
    get_grievance_detail,
    get_all_grievances_admin,
    get_grievance_detail_admin,
    respond_to_grievance,
    get_grievance_stats
)


router = APIRouter()


# ============ MR ENDPOINTS ============

@router.post(
    "",
    response_model=GrievanceCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create grievance (MR)",
    description="MR creates a new grievance ticket"
)
async def create_new_grievance(
    request: GrievanceCreateRequest,
    current_user: Dict[str, Any] = Depends(require_mr)
):
    """
    Create a new grievance.
    
    Request Body:
    - department: Department code (hr, finance, it)
    - subject: Grievance subject (5-200 chars)
    - description: Detailed description (10-2000 chars)
    - priority: Priority level (low, medium, high, urgent)
    
    Returns:
    - Success message with generated ticket_id
    """
    result = await create_grievance(
        department=request.department,
        subject=request.subject,
        description=request.description,
        priority=request.priority,
        current_user=current_user
    )
    
    return result


@router.get(
    "",
    response_model=GrievanceListResponse,
    summary="Get my grievances (MR)",
    description="MR gets their own grievances with pagination and filters"
)
async def list_my_grievances(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    current_user: Dict[str, Any] = Depends(require_mr)
):
    """
    Get MR's own grievances.
    
    Query Parameters:
    - page: Page number (default: 1)
    - limit: Items per page (default: 20, max: 100)
    - status: Filter by status (open, in_progress, resolved, rejected)
    - priority: Filter by priority (low, medium, high, urgent)
    
    Returns:
    - Paginated list of grievances
    """
    result = await get_my_grievances(
        current_user=current_user,
        page=page,
        limit=limit,
        status_filter=status,
        priority_filter=priority
    )
    
    return result


@router.get(
    "/{ticket_id}",
    response_model=GrievanceDetailResponse,
    summary="Get grievance details (MR)",
    description="MR gets details of their own grievance"
)
async def get_my_grievance_detail(
    ticket_id: str,
    current_user: Dict[str, Any] = Depends(require_mr)
):
    """
    Get grievance details.
    
    Path Parameters:
    - ticket_id: Ticket ID (e.g., HR-2026-001)
    
    Returns:
    - Full grievance details including admin response
    """
    result = await get_grievance_detail(
        ticket_id=ticket_id,
        current_user=current_user
    )
    
    return result


# ============ ADMIN ENDPOINTS ============

@router.get(
    "/admin/list",
    response_model=GrievanceListResponse,
    summary="Get all grievances (Admin)",
    description="Admin gets grievances filtered by their department"
)
async def list_all_grievances_admin(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    department: Optional[str] = Query(None, description="Filter by department (general admin only)"),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Get all grievances for admin.
    
    Query Parameters:
    - page: Page number (default: 1)
    - limit: Items per page (default: 20, max: 100)
    - status: Filter by status (open, in_progress, resolved, rejected)
    - priority: Filter by priority (low, medium, high, urgent)
    - department: Filter by department (general admin only)
    
    Access Control:
    - General admin: Sees all grievances (can filter by department)
    - Department admin: Sees only their department's grievances
    
    Returns:
    - Paginated list of grievances sorted by status, priority, date
    """
    result = await get_all_grievances_admin(
        current_user=current_user,
        page=page,
        limit=limit,
        status_filter=status,
        priority_filter=priority,
        department_filter=department
    )
    
    return result


@router.get(
    "/admin/{ticket_id}",
    response_model=GrievanceDetailResponse,
    summary="Get grievance details (Admin)",
    description="Admin gets grievance details (with department access control)"
)
async def get_grievance_detail_for_admin(
    ticket_id: str,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Get grievance details for admin.
    
    Path Parameters:
    - ticket_id: Ticket ID (e.g., HR-2026-001)
    
    Access Control:
    - General admin: Can view any grievance
    - Department admin: Can only view their department's grievances
    
    Returns:
    - Full grievance details
    """
    result = await get_grievance_detail_admin(
        ticket_id=ticket_id,
        current_user=current_user
    )
    
    return result


@router.put(
    "/admin/{ticket_id}",
    response_model=MessageResponse,
    summary="Respond to grievance (Admin)",
    description="Admin responds to a grievance and updates status"
)
async def respond_to_grievance_admin(
    ticket_id: str,
    request: GrievanceResponseRequest,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Respond to a grievance and update status.
    
    Path Parameters:
    - ticket_id: Ticket ID (e.g., HR-2026-001)
    
    Request Body:
    - admin_response: Admin's response text (10-2000 chars)
    - status: Updated status (open, in_progress, resolved, rejected)
    
    Access Control:
    - General admin: Can respond to any grievance
    - Department admin: Can only respond to their department's grievances
    
    Returns:
    - Success message
    """
    result = await respond_to_grievance(
        ticket_id=ticket_id,
        admin_response=request.admin_response,
        new_status=request.status,
        current_user=current_user
    )
    
    return result


@router.get(
    "/admin/stats/dashboard",
    response_model=GrievanceStatsResponse,
    summary="Get grievance statistics (Admin)",
    description="Get dashboard statistics for grievances"
)
async def get_grievance_statistics(
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Get grievance statistics for dashboard.
    
    Access Control:
    - General admin: Stats for all departments
    - Department admin: Stats for their department only
    
    Returns:
    - Total counts by status, department, and priority
    """
    result = await get_grievance_stats(current_user=current_user)
    
    return result
