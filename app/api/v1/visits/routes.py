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
    VisitListWithTargetsResponse,
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


@router.get("", response_model=VisitListWithTargetsResponse, summary="List Visits")
async def list_visits(
    current_user: Dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    doctor_id: Optional[str] = Query(None, description="Filter by doctor"),
    mr_id: Optional[str] = Query(None, description="Filter by MR (admin only)")
):
    """
    Get list of visits with filters and visit targets.
    
    **Access:** 
    - Admin: Can view all visits (no targets array)
    - MR: Can view own visits with targets array showing monthly progress
    
    **New Feature - Visit Targets (MR Only):**
    The response includes a `targets` array that shows visit progress for each assigned doctor in the current month.
    This helps MRs track their monthly visit requirements.
    
    **How Targets Work:**
    1. System gets MR's assigned doctors from `mrs.assigned_doctors`
    2. For each doctor, reads their `classification` (A/B/C) from `doctors` collection
    3. Gets required visits from `sfe_settings.classification_targets[classification]`
    4. Counts completed visits for that doctor in current month
    5. Returns progress: completed/required
    
    **Target Calculation:**
    - **Classification**: From doctor's profile (A/B/C)
    - **Required**: From SFE settings (e.g., A=4, B=3, C=2 visits/month)
    - **Completed**: Count of visits with status="completed" this month
    - **Default**: If doctor has no classification, defaults to "C"
    
    **Usage Examples:**
    
    **MR - Get all visits with targets:**
    ```
    GET /api/v1/visits
    Headers: Authorization: Bearer <mr_token>
    ```
    
    **MR - Filter by status:**
    ```
    GET /api/v1/visits?status=scheduled
    Headers: Authorization: Bearer <mr_token>
    ```
    
    **MR - Filter by date range:**
    ```
    GET /api/v1/visits?date_from=2026-05-01&date_to=2026-05-31
    Headers: Authorization: Bearer <mr_token>
    ```
    
    **Admin - View specific MR's visits (no targets):**
    ```
    GET /api/v1/visits?mr_id=507f1f77bcf86cd799439013
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **MR Response Example:**
    ```json
    {
      "total": 10,
      "visits": [
        {
          "id": "507f1f77bcf86cd799439011",
          "mr_id": "507f1f77bcf86cd799439012",
          "mr_name": "Rajesh Kumar",
          "doctor_id": "507f1f77bcf86cd799439013",
          "doctor_name": "Dr. Sneha Sharma",
          "scheduled_date": "2026-05-25",
          "scheduled_time": "10:00",
          "purpose": "Product presentation",
          "location": "Apollo Hospital",
          "status": "completed",
          "outcome": "Successfully presented new product line",
          "completed_at": "2026-05-25T10:30:00",
          "created_at": "2026-05-20T09:00:00",
          "updated_at": "2026-05-25T10:30:00"
        }
      ],
      "targets": [
        {
          "doctor_id": "507f1f77bcf86cd799439013",
          "doctor_name": "Dr. Sneha Sharma",
          "classification": "A",
          "required": 4,
          "completed": 1
        },
        {
          "doctor_id": "507f1f77bcf86cd799439014",
          "doctor_name": "Dr. Ashok Patel",
          "classification": "C",
          "required": 2,
          "completed": 0
        },
        {
          "doctor_id": "507f1f77bcf86cd799439015",
          "doctor_name": "Dr. Priya Reddy",
          "classification": "B",
          "required": 3,
          "completed": 2
        }
      ]
    }
    ```
    
    **Admin Response Example:**
    ```json
    {
      "total": 50,
      "visits": [...],
      "targets": []
    }
    ```
    
    **What Targets Tell You:**
    - **Dr. Sneha (A)**: Needs 4 visits/month, completed 1 → Progress: 1/4 (25%)
    - **Dr. Ashok (C)**: Needs 2 visits/month, completed 0 → Progress: 0/2 (0%)
    - **Dr. Priya (B)**: Needs 3 visits/month, completed 2 → Progress: 2/3 (67%)
    
    **Integration with SFE Settings:**
    - Admin can change visit requirements via `PUT /api/v1/sfe/settings`
    - Changes immediately reflect in targets array
    - Example: If admin changes A from 4 to 6, Dr. Sneha's required becomes 6
    
    **Query Parameters:**
    - `status`: Filter by visit status (scheduled, completed, cancelled)
    - `date_from`: Start date for filtering (YYYY-MM-DD)
    - `date_to`: End date for filtering (YYYY-MM-DD)
    - `doctor_id`: Filter visits for specific doctor
    - `mr_id`: (Admin only) Filter visits for specific MR
    
    **Response Fields:**
    - `total`: Total number of visits matching filters
    - `visits`: Array of visit objects
    - `targets`: Array of visit target objects (MR only, always current month)
    
    **Notes:**
    - Targets array is **only populated for MR users**
    - Targets always show **current month** progress (not affected by date filters)
    - If doctor has no classification, defaults to "C"
    - If SFE settings not configured, uses defaults (A=2, B=1, C=1)
    """
    # Check if user is admin or MR
    user_role = current_user.get("role")
    if user_role not in [UserRole.ADMIN.value, UserRole.MR.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin and MR can access visits"
        )
    
    result = await get_visits(
        current_user=current_user,
        status_filter=status,
        date_from=date_from,
        date_to=date_to,
        doctor_id=doctor_id,
        mr_id=mr_id
    )
    
    return result


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
    Complete a visit with SFE data (MR only).
    
    **Access:** MR only (own visits)
    
    **Required fields:**
    - outcome: Visit outcome summary (min 10 characters)
    
    **Optional SFE fields:**
    - products_promoted: List of product IDs discussed
    - samples_given: Number of samples distributed
    - doctor_mood: Doctor's receptiveness (positive/neutral/negative)
    - competitor_info: Competitor information observed
    - followup_date: Next follow-up date (auto-creates next visit)
    - rx_commitment: Prescription commitment (product_id, rx_per_week, confidence)
    - gps_lat, gps_lng: GPS coordinates for location proof
    
    **Usage:**
    ```
    PUT /api/v1/visits/{visit_id}/complete
    Headers: Authorization: Bearer <mr_token>
    {
        "outcome": "Successfully presented Amlovas 5mg. Doctor showed interest.",
        "feedback": "Doctor requested follow-up next month",
        "products_promoted": ["prod_id_1", "prod_id_2"],
        "samples_given": 10,
        "doctor_mood": "positive",
        "followup_date": "2026-06-15",
        "rx_commitment": {
            "product_id": "prod_id_1",
            "rx_per_week": 15,
            "confidence": "high"
        },
        "gps_lat": 17.3850,
        "gps_lng": 78.4867
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
        request=request,
        # SFE fields
        products_promoted=complete_request.products_promoted,
        samples_given=complete_request.samples_given,
        doctor_mood=complete_request.doctor_mood,
        competitor_info=complete_request.competitor_info,
        followup_date=complete_request.followup_date,
        rx_commitment=complete_request.rx_commitment.model_dump() if complete_request.rx_commitment else None,
        gps_lat=complete_request.gps_lat,
        gps_lng=complete_request.gps_lng
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



# ============================================================================
# NEW ENDPOINTS FOR CHECK-IN/CHECK-OUT/REPORT FLOW
# ============================================================================

from app.api.v1.visits.schemas import (
    VisitCheckInRequest,
    VisitCheckOutRequest,
    VisitReportRequest,
    VisitCancelCheckInRequest,
    CheckInResponse,
    CheckOutResponse,
    ReportResponse,
    ActiveVisitResponse
)
from app.api.v1.visits.service import (
    check_in_visit,
    check_out_visit,
    submit_visit_report,
    get_active_visit,
    cancel_check_in
)


@router.put("/{visit_id}/check-in", response_model=CheckInResponse, summary="Check In to Visit")
async def check_in_visit_endpoint(
    visit_id: str,
    check_in_request: VisitCheckInRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Check in to a visit with GPS coordinates (MR only).
    
    **Access:** MR only
    
    **Validations:**
    - Visit must be in scheduled status
    - MR cannot have another visit with status=checked_in (only 1 active visit at a time)
    - MR cannot have more than 2 pending reports (status=checked_out)
    - Visit must belong to this MR
    - GPS coordinates required
    
    **Rules:**
    1. **Only 1 active check-in at a time** - If you're already checked in to another visit, you must check out first
    2. **Max 2 pending reports** - If you have 2 visits waiting for reports, submit them before checking in to a new visit
    
    **What Happens:**
    - Visit status changes: scheduled → checked_in
    - GPS coordinates and timestamp saved
    - Timer starts (duration calculated on check-out)
    - You cannot check in to another visit until you check out
    
    **Usage:**
    ```
    PUT /api/v1/visits/{visit_id}/check-in
    Headers: Authorization: Bearer <mr_token>
    {
        "latitude": 17.4401,
        "longitude": 78.3489
    }
    ```
    
    **Response:**
    ```json
    {
        "message": "Checked in successfully",
        "visit_id": "507f1f77bcf86cd799439011",
        "check_in_time": "2026-05-25T10:05:32"
    }
    ```
    
    **Error Responses:**
    - 400: "Check out of your current visit first" - You have another active check-in
    - 400: "Submit pending reports before checking in" - You have 2+ pending reports
    - 400: "Visit must be in scheduled status" - Visit is not scheduled
    - 403: "You can only check in to your own visits" - Not your visit
    - 404: "Visit not found" - Invalid visit ID
    """
    # Check if user is MR
    if current_user.get("role") != UserRole.MR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MRs can check in to visits"
        )
    
    return await check_in_visit(
        visit_id=visit_id,
        latitude=check_in_request.latitude,
        longitude=check_in_request.longitude,
        current_user=current_user,
        request=request
    )


@router.put("/{visit_id}/check-out", response_model=CheckOutResponse, summary="Check Out from Visit")
async def check_out_visit_endpoint(
    visit_id: str,
    check_out_request: VisitCheckOutRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Check out from a visit with GPS coordinates (MR only).
    
    **Access:** MR only
    
    **Validations:**
    - Visit must be in checked_in status
    - Visit must belong to this MR
    - GPS coordinates required
    
    **What Happens:**
    - Visit status changes: checked_in → checked_out
    - GPS coordinates and timestamp saved
    - Duration calculated from check-in to check-out
    - Visit now requires report submission
    - You can check in to another visit now
    
    **Usage:**
    ```
    PUT /api/v1/visits/{visit_id}/check-out
    Headers: Authorization: Bearer <mr_token>
    {
        "latitude": 17.4401,
        "longitude": 78.3490
    }
    ```
    
    **Response:**
    ```json
    {
        "message": "Checked out successfully",
        "visit_id": "507f1f77bcf86cd799439011",
        "duration_minutes": 28
    }
    ```
    
    **Error Responses:**
    - 400: "Cannot check out from {status} visit" - Visit is not checked_in
    - 403: "You can only check out from your own visits" - Not your visit
    - 404: "Visit not found" - Invalid visit ID
    """
    # Check if user is MR
    if current_user.get("role") != UserRole.MR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MRs can check out from visits"
        )
    
    return await check_out_visit(
        visit_id=visit_id,
        latitude=check_out_request.latitude,
        longitude=check_out_request.longitude,
        current_user=current_user,
        request=request
    )


@router.put("/{visit_id}/report", response_model=ReportResponse, summary="Submit Visit Report")
async def submit_report_endpoint(
    visit_id: str,
    report_request: VisitReportRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Submit visit report (DCR - Daily Call Report) (MR only).
    
    **Access:** MR only
    
    **IMPORTANT:** This is when the visit counts toward your monthly targets!
    
    **Validations:**
    - Visit must be in checked_out status
    - Visit must belong to this MR
    - outcome is required (min 10 characters)
    - doctor_mood must be: positive, neutral, or negative
    - products_discussed must be from your assigned drugs
    
    **What Happens:**
    - Visit status changes: checked_out → completed
    - Report data saved
    - **Visit now counts toward monthly target!**
    - Notification sent
    
    **Required Fields:**
    - doctor_mood: positive | neutral | negative
    - products_discussed: Array of drug IDs
    - samples_given: Number (0-1000)
    - outcome: String (min 10 chars)
    
    **Optional Fields:**
    - rx_commitment: Boolean
    - expected_rx_per_month: Number
    - competitor_info: String
    - follow_up_date: Date (YYYY-MM-DD)
    - notes: String
    
    **Usage:**
    ```
    PUT /api/v1/visits/{visit_id}/report
    Headers: Authorization: Bearer <mr_token>
    {
        "doctor_mood": "positive",
        "products_discussed": ["507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012"],
        "samples_given": 3,
        "outcome": "Positive — Doctor interested in Amlodipine 5mg. Discussed clinical trial data.",
        "rx_commitment": true,
        "expected_rx_per_month": 10,
        "competitor_info": "Cipla — Amlokind 5mg",
        "follow_up_date": "2026-06-01",
        "notes": "Doctor wants clinical trial data"
    }
    ```
    
    **Response:**
    ```json
    {
        "message": "Report submitted successfully",
        "visit_id": "507f1f77bcf86cd799439011",
        "status": "completed"
    }
    ```
    
    **Error Responses:**
    - 400: "Cannot submit report for {status} visit" - Visit is not checked_out
    - 400: "Product {id} is not in your assigned drugs list" - Invalid product
    - 400: "Doctor mood must be: positive, neutral, or negative" - Invalid mood
    - 403: "You can only submit reports for your own visits" - Not your visit
    - 404: "Visit not found" - Invalid visit ID
    """
    # Check if user is MR
    if current_user.get("role") != UserRole.MR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MRs can submit visit reports"
        )
    
    # Convert request to dict
    report_data = report_request.model_dump()
    
    return await submit_visit_report(
        visit_id=visit_id,
        report_data=report_data,
        current_user=current_user,
        request=request
    )


@router.get("/active", response_model=ActiveVisitResponse, summary="Get Active Visit")
async def get_active_visit_endpoint(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get current active (checked_in) visit and pending reports count (MR only).
    
    **Access:** MR only
    
    **Purpose:** 
    - Check if you have an active checked-in visit
    - See how many pending reports you have
    - Frontend uses this to show active visit timer and disable other check-ins
    
    **What You Get:**
    - **active_visit**: Visit details if you're checked in, otherwise null
    - **pending_reports**: Count of visits waiting for reports (checked_out status)
    
    **Usage:**
    ```
    GET /api/v1/visits/active
    Headers: Authorization: Bearer <mr_token>
    ```
    
    **Response (with active visit):**
    ```json
    {
        "active_visit": {
            "id": "507f1f77bcf86cd799439011",
            "doctor_id": "507f1f77bcf86cd799439013",
            "doctor_name": "Dr. Sneha",
            "check_in_time": "2026-05-25T10:05:32",
            "location": "Apollo Hospital",
            "duration_so_far_minutes": 15
        },
        "pending_reports": 1
    }
    ```
    
    **Response (no active visit):**
    ```json
    {
        "active_visit": null,
        "pending_reports": 2
    }
    ```
    
    **Frontend Usage:**
    - If active_visit exists: Show timer, disable other check-in buttons, show "Check Out" button
    - If pending_reports > 0: Show banner "⚠️ {count} pending report(s) — submit now"
    - If pending_reports >= 2: Disable all check-in buttons until reports submitted
    """
    # Check if user is MR
    if current_user.get("role") != UserRole.MR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MRs can access active visit information"
        )
    
    return await get_active_visit(current_user=current_user)


@router.put("/{visit_id}/cancel-checkin", response_model=MessageResponse, summary="Cancel Check-In")
async def cancel_check_in_endpoint(
    visit_id: str,
    cancel_request: VisitCancelCheckInRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Cancel check-in and revert visit to scheduled status (MR only).
    
    **Access:** MR only
    
    **When to Use:**
    - Checked in by mistake
    - Doctor suddenly unavailable (emergency, called away, etc.)
    - Wrong location
    - Any reason the visit can't proceed after check-in
    
    **Validations:**
    - Visit must be in checked_in status
    - Visit must belong to this MR
    - reason is required (min 5 characters)
    
    **What Happens:**
    - Visit status changes: checked_in → scheduled (back to scheduled!)
    - Check-in data removed
    - Cancellation audit trail saved (timestamp, reason, original check-in)
    - You can check in again later
    - You can check in to other visits now
    
    **Usage:**
    ```
    PUT /api/v1/visits/{visit_id}/cancel-checkin
    Headers: Authorization: Bearer <mr_token>
    {
        "reason": "Doctor was called for emergency surgery"
    }
    ```
    
    **Response:**
    ```json
    {
        "message": "Check-in cancelled successfully",
        "visit_id": "507f1f77bcf86cd799439011",
        "status": "scheduled"
    }
    ```
    
    **Common Reasons:**
    - "Doctor unavailable - emergency surgery"
    - "Checked in by mistake"
    - "Wrong location - went to different hospital"
    - "Doctor called away for urgent patient"
    - "Hospital closed unexpectedly"
    
    **Error Responses:**
    - 400: "Cannot cancel check-in for {status} visit" - Visit is not checked_in
    - 403: "You can only cancel check-in for your own visits" - Not your visit
    - 404: "Visit not found" - Invalid visit ID
    
    **Note:** Admin can see the cancellation audit trail in visit history
    """
    # Check if user is MR
    if current_user.get("role") != UserRole.MR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MRs can cancel check-in"
        )
    
    return await cancel_check_in(
        visit_id=visit_id,
        reason=cancel_request.reason,
        current_user=current_user,
        request=request
    )
