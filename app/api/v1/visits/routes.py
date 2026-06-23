"""
Visit routes - API endpoints for visit management.
"""

from fastapi import APIRouter, Depends, Query, status, HTTPException, Request, Form, File, UploadFile
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
    VisitCreateResponse,
    # Schemas for check-in/check-out/report flow
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
    schedule_visit,
    get_visits,
    get_visit_by_id,
    reschedule_visit,
    complete_visit,
    cancel_visit,
    # New service functions for check-in/check-out/report flow
    check_in_visit,
    check_out_visit,
    submit_visit_report,
    get_active_visit,
    cancel_check_in
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
    Schedule a new visit (MR only) with location selection.
    
    **Access:** MR only
    
    **Location Selection:**
    MRs can now select either:
    - **Permanent Location**: Doctor's registered locations (requires location_id)
    - **Temporary Location**: One-time location with GPS coordinates
    
    **Validations:**
    - MR can only schedule with their assigned doctors
    - Doctor must not have another scheduled visit at same time
    - Location must be valid (either permanent with location_id OR temporary with coordinates)
    
    **Usage - Permanent Location:**
    ```json
    {
        "doctor_id": "507f1f77bcf86cd799439011",
        "scheduled_date": "2024-04-15",
        "scheduled_time": "10:30",
        "purpose": "Product presentation",
        "location": {
            "type": "permanent",
            "location_id": "loc_123",
            "location_name": "Apollo Hospital"
        },
        "notes": "Bring samples"
    }
    ```
    
    **Usage - Temporary Location:**
    ```json
    {
        "doctor_id": "507f1f77bcf86cd799439011",
        "scheduled_date": "2024-04-20",
        "scheduled_time": "14:00",
        "purpose": "Follow-up visit",
        "location": {
            "type": "temporary",
            "temporary_location": {
                "reason": "Medical camp at community center",
                "name": "Community Health Center",
                "address": "Gachibowli, Hyderabad",
                "latitude": 17.4435,
                "longitude": 78.3772
            }
        }
    }
    ```
    
    **Temporary Location Intelligence:**
    - System tracks all temporary location visits
    - After 5 completed visits at same location (within 50m radius)
    - System auto-creates suggestion for admin review
    - Admin can approve → becomes permanent location
    """
    # Check if user is MR
    if current_user.get("role") != UserRole.MR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MRs can schedule visits"
        )
    
    # Convert location object to dict for service layer
    location_dict = visit_request.location.model_dump()
    
    return await schedule_visit(
        doctor_id=visit_request.doctor_id,
        scheduled_date=visit_request.scheduled_date,
        scheduled_time=visit_request.scheduled_time,
        purpose=visit_request.purpose,
        location=location_dict,
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
    
    Access: 
    - Admin: Can view ALL visits from ALL MRs
    - MR: Can view own visits with targets array
    - Doctor: Can view visits where they are the doctor
    
    Admin Visibility (Important):
    Admins can see complete visit details including:
    - All location types (permanent and temporary)
    - Check-in GPS coordinates
    - Captured photos via photo_url in check_in data
    - Geofence status and distance (in kilometers)
    - Visit reports and outcomes
    
    Photo Access:
    When MR checks in at temporary location or outside geofence, they capture
    a photo. This photo URL is included in the response in check_in data.
    Admin can click photo_url to view the captured image from Cloudinary.
    
    Distance Display:
    The distance_from_location field shows how far the MR was from the expected
    location during check-in, measured in kilometers (km).
    
    Query Parameters:
    - status: Filter by visit status
    - date_from: Start date (YYYY-MM-DD)
    - date_to: End date (YYYY-MM-DD)  
    - doctor_id: Filter by doctor
    - mr_id: Filter by MR (Admin only)
    
    Examples:
    - Admin view all visits: GET /api/v1/visits
    - Admin view MR visits: GET /api/v1/visits?mr_id=xxx
    - MR view own visits: GET /api/v1/visits
    - Filter by date: GET /api/v1/visits?date_from=2026-05-01&date_to=2026-05-31
    
    Response Fields:
    - total: Total number of visits matching filters
    - visits: Array of visit objects with all details
    - targets: Array of visit target objects (MR only, shows current month progress)
    
    Notes:
    - Targets array is only populated for MR users
    - Targets always show current month progress (not affected by date filters)
    - If doctor has no classification, defaults to C
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


@router.get("/{visit_id}", response_model=VisitResponse, summary="Get Visit Details")
async def get_visit(
    visit_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get details of a specific visit by ID.
    
    Access:
    - Admin: Can view any visit
    - MR: Can view only own visits
    
    Admin Visibility:
    Admins can see complete visit details including:
    - All location information (permanent or temporary)
    - Check-in and check-out GPS coordinates
    - Captured photos via photo_url in check_in data
    - Geofence status and distance from location (in kilometers)
    - Visit reports and outcomes
    - Complete visit timeline and audit trail
    
    Photo Access:
    If MR captured a photo during check-in (required for temporary locations
    or when outside geofence), the photo URL will be available in the response:
    
    check_in: {
      timestamp: "2026-06-17T10:05:32Z",
      latitude: 17.4401,
      longitude: 78.3489,
      photo_url: "https://res.cloudinary.com/.../photo.jpg",
      photo_captured_at: "2026-06-17T10:05:32Z",
      geofence_status: "outside",
      distance_from_location: 0.15  (in kilometers)
    }
    
    Usage:
    GET /api/v1/visits/{visit_id}
    
    Response includes full visit data with check-in, check-out, and report details.
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
        "competitor_info": "Cipla competitor mentioned",
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


@router.put("/{visit_id}/check-in", response_model=CheckInResponse, summary="Check In to Visit")
async def check_in_visit_endpoint(
    visit_id: str,
    latitude: float = Form(..., description="Current GPS latitude", ge=-90, le=90),
    longitude: float = Form(..., description="Current GPS longitude", ge=-180, le=180),
    photo: Optional[UploadFile] = File(None, description="Check-in photo (required if outside geofence or temporary location)"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Check in to a visit with GPS coordinates and geofence validation (MR only).
    
    **NEW: Now supports multipart/form-data with optional photo upload**
    
    **Access:** MR only
    
    **Validations:**
    - Visit must be in scheduled status
    - MR cannot have another visit with status=checked_in (only 1 active visit at a time)
    - MR cannot have more than 2 pending reports (status=checked_out)
    - Visit must belong to this MR
    - GPS coordinates required
    - **NEW: Geofence validation (100m radius)**
    - **NEW: Photo required if outside geofence OR temporary location**
    
    **Geofence Logic:**
    1. System resolves visit location (permanent from doctor.locations OR temporary)
    2. Calculates distance from MR GPS to location
    3. If distance > 100m → Status: "outside", Photo: REQUIRED
    4. If distance <= 100m → Status: "inside", Photo: OPTIONAL
    5. If temporary location → Photo: ALWAYS REQUIRED
    
    **Usage (with photo):**
    ```
    PUT /api/v1/visits/{visit_id}/check-in
    Content-Type: multipart/form-data
    Headers: Authorization: Bearer <mr_token>
    
    Form Data:
    - latitude: 17.4401
    - longitude: 78.3489
    - photo: <image file>
    ```
    
    **Response:**
    ```json
    {
        "message": "Checked in successfully",
        "visit_id": "...",
        "check_in_time": "2026-06-17T10:05:32Z",
        "geofence_status": "outside",
        "distance_km": 0.15,
        "photo_uploaded": true
    }
    ```
    
    **Error Responses:**
    - 400: "Check out of your current visit first" - You have another active check-in
    - 400: "Submit pending reports before checking in" - You have 2+ pending reports
    - 400: "Photo is required for check-in (outside geofence or temporary location)"
    - 403: "You can only check in to your own visits" - Not your visit
    - 404: "Visit not found" - Invalid visit ID
    """
    # Check if user is MR
    if current_user.get("role") != "MR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MRs can check in to visits"
        )
    
    # Use new geofence service
    from app.api.v1.visits.geofence_service import check_in_with_geofence
    
    return await check_in_with_geofence(
        visit_id=visit_id,
        latitude=latitude,
        longitude=longitude,
        photo=photo,
        current_user=current_user

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
    - **Distance calculated from actual visit location (permanent or temporary)**
    - Geofence status determined (inside/outside)
    - Duration calculated from check-in to check-out
    - Visit now requires report submission
    - You can check in to another visit now
    
    **Distance Calculation:**
    System calculates how far the MR is from the actual visit location during check-out.
    This helps track if MR stayed at the location or moved away.
    
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
        "duration_minutes": 28,
        "distance_km": 0.05,
        "geofence_status": "inside"
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
