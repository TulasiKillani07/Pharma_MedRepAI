"""
Doctor routes - API endpoints for doctor management.
"""

from fastapi import APIRouter, Depends, status, UploadFile, File, HTTPException, Query
from typing import Dict, Any, Optional
from app.api.v1.doctors.schemas import (
    DoctorCreateRequest,
    DoctorUpdateRequest,
    DoctorResponse,
    DoctorListResponse,
    MessageResponse,
    DoctorCreateResponse,
    DoctorUpdateResponse,
    BulkUploadResponse,
    DoctorRequestCreate,
    DoctorRequestResponse,
    DoctorRequestListResponse,
    DoctorRequestCreateResponse,
    DoctorRequestRejectRequest,
    DoctorRequestApproveResponse
)
from app.api.v1.doctors.service import (
    create_doctor,
    get_all_doctors,
    get_doctor_by_id,
    update_doctor,
    delete_doctor,
    get_available_doctors,
    bulk_upload_doctors,
    download_doctors_template,
    create_doctor_request,
    get_doctor_requests,
    approve_doctor_request,
    reject_doctor_request
)
from app.core.auth import get_current_user, require_admin
from typing import Optional
from fastapi import Query


# Create router for doctor endpoints
router = APIRouter()


@router.post("", response_model=DoctorCreateResponse, status_code=status.HTTP_201_CREATED, summary="Add Doctor")
async def add_doctor(
    request: DoctorCreateRequest,
    current_user: Dict = Depends(require_admin)
):
    """
    Add a new doctor (Admin only).
    
    **Access:** Company Admin only
    
    **Flow:**
    1. Admin provides doctor details including classification (A/B/C)
    2. Backend validates email is unique
    3. Backend hashes password
    4. Backend creates doctor account with classification
    5. Doctor can now login
    
    **Doctor Classification (SFE):**
    - Class A: High-value doctors, requires 2 visits per month
    - Class B: Medium-value doctors, requires 1 visit per month
    - Class C: Low-value doctors, requires 1 visit per 2 months
    
    **Usage:**
    ```
    POST /api/v1/doctors
    Headers: Authorization: Bearer <admin_token>
    {
        "name": "Dr. Sarah Sharma",
        "email": "sharma@gmail.com",
        "password": "Doctor123",
        "phone": "+919876543210",
        "specialization": "Cardiologist",
        "classification": "A",
        "hospital": "City Hospital",
        "license_number": "MH12345",
        "address": "123 Medical Street"
    }
    ```
    
    **Response:**
    ```json
    {
        "message": "Doctor added successfully",
        "doctor_id": "507f1f77bcf86cd799439011"
    }
    ```
    
    **Creator Tracking:**
    When admin adds a doctor directly:
    - `added_by`: Contains admin's role, id, name, and department
    - `approved_by`: null (no approval needed for direct admin adds)
    
    The created doctor will have:
    ```json
    {
        "added_by": {
            "role": "ADMIN",
            "id": "admin_id",
            "name": "Admin Full Name",
            "department": "general"
        },
        "approved_by": null
    }
    ```
    """
    return await create_doctor(
        name=request.name,
        email=request.email,
        password=request.password,
        phone=request.phone,
        specialization=request.specialization,
        classification=request.classification,
        hospital=request.hospital,
        license_number=request.license_number,
        address=request.address,
        current_user=current_user
    )


@router.get("/download-template", dependencies=[Depends(require_admin)])
async def download_doctors_template_endpoint():
    """
    Download CSV template for bulk doctor upload.
    
    **Access:** Admin only
    
    **Purpose:**
    Provides a CSV template file that admins can fill with doctor data and upload via bulk upload.
    
    **Template Columns:**
    1. name (REQUIRED) - Doctor's full name
    2. email (REQUIRED) - Doctor's email address
    3. phone (REQUIRED) - Phone number with country code (e.g., +919876543210)
    4. specialization (REQUIRED) - Medical specialization
    5. classification (REQUIRED) - Doctor classification: A, B, or C
    6. hospital (optional) - Hospital name
    7. license_number (optional) - Medical license number
    8. address (optional) - Full address
    
    **Instructions:**
    - Fill all required fields (name, email, phone, specialization, classification)
    - Classification must be A, B, or C (A=2 visits/month, B=1 visit/month, C=1 visit/2 months)
    - Email must be unique (not already in system)
    - Phone must be unique and in E.164 format (+country code)
    - Maximum 100 rows per upload
    
    **Usage:**
    ```
    GET /api/v1/doctors/download-template
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Response:**
    Downloads file: doctors_template.csv
    """
    return await download_doctors_template()


@router.post("/bulk-upload", response_model=BulkUploadResponse, status_code=status.HTTP_200_OK, summary="Bulk Upload Doctors")
async def bulk_upload_doctors_endpoint(
    file: UploadFile = File(..., description="CSV or Excel file with doctor data"),
    current_user: Dict = Depends(require_admin)
):
    """
    Bulk upload doctors from CSV or Excel file (Admin only).
    
    **Access:** Company Admin only
    
    **Purpose:**
    Upload multiple doctors at once using a CSV or Excel file instead of adding them one by one.
    
    **Flow:**
    1. Admin prepares CSV/Excel file with doctor data
    2. Admin uploads file via this endpoint
    3. Backend validates each row
    4. Valid rows are inserted into database
    5. Invalid rows are skipped and reported in response
    6. Admin receives detailed report of success/failures
    
    **File Format:**
    - Supported: CSV (.csv), Excel (.xlsx, .xls)
    - Max file size: 5MB
    - Max rows: 100 doctors per upload
    
    **Required Columns:**
    - name: Doctor's full name
    - email: Doctor's email (must be unique)
    - phone: Phone number (must be 10 digits)
    - specialization: Medical specialization
    - classification: Doctor classification (A, B, or C) for SFE tracking
    
    **Optional Columns:**
    - hospital: Hospital name
    - license_number: Medical license number
    - address: Full address
    
    **CSV Example:**
    ```csv
    name,email,phone,specialization,classification,hospital,license_number,address
    Dr. John Smith,john@example.com,9876543210,Cardiology,A,Apollo Hospital,MH12345,Mumbai Maharashtra
    Dr. Sarah Jones,sarah@example.com,9876543211,Neurology,B,Fortis Hospital,DL67890,Delhi
    Dr. Mike Brown,mike@example.com,9876543212,Orthopedics,C,Max Hospital,MH54321,Pune Maharashtra
    ```
    
    **Validation Rules:**
    - Email must be valid format and unique in database
    - Phone must be exactly 10 digits and unique in database
    - Name, email, phone, specialization, classification are required
    - Classification must be A, B, or C
    - Invalid rows are skipped, valid rows are inserted
    - All uploaded doctors get default password: Welcome@123
    
    **Usage:**
    ```
    POST /api/v1/doctors/bulk-upload
    Headers: Authorization: Bearer <admin_token>
    Content-Type: multipart/form-data
    Body: file=@doctors.csv
    ```
    
    **Response (All Success):**
    ```json
    {
        "total_rows": 100,
        "successful": 100,
        "failed": 0,
        "errors": [],
        "message": "Bulk upload completed successfully. All 100 doctors added."
    }
    ```
    
    **Creator Tracking:**
    All doctors uploaded via bulk upload will have:
    - `added_by`: Contains admin's role, id, name, and department
    - `approved_by`: null (no approval needed for bulk uploads by admin)
    
    Example:
    ```json
    {
        "added_by": {
            "role": "ADMIN",
            "id": "admin_id",
            "name": "Admin Full Name",
            "department": "general"
        },
        "approved_by": null
    }
    ```
    
    **Response (Partial Success):**
    ```json
    {
        "total_rows": 100,
        "successful": 95,
        "failed": 5,
        "errors": [
            {
                "row": 3,
                "email": "invalid-email",
                "error": "Invalid email format"
            },
            {
                "row": 7,
                "email": "existing@example.com",
                "error": "Email already exists in database"
            },
            {
                "row": 15,
                "phone": "12345",
                "error": "Phone must be 10 digits"
            },
            {
                "row": 23,
                "name": "Dr. Test",
                "error": "Email is required"
            },
            {
                "row": 45,
                "phone": "9876543210",
                "error": "Phone number already exists in database"
            }
        ],
        "message": "Bulk upload completed. 95 doctors added successfully, 5 rows failed."
    }
    ```
    
    **Response (All Failed):**
    ```json
    {
        "total_rows": 10,
        "successful": 0,
        "failed": 10,
        "errors": [
            {"row": 2, "error": "Invalid email format"},
            {"row": 3, "error": "Phone must be 10 digits"},
            ...
        ],
        "message": "Bulk upload failed. All 10 rows had errors."
    }
    ```
    
    **Error Types:**
    - "Name is required"
    - "Email is required"
    - "Invalid email format"
    - "Email already exists in database"
    - "Phone is required"
    - "Phone must be 10 digits"
    - "Phone number already exists in database"
    - "Specialization is required"
    - "Classification is required"
    - "Classification must be A, B, or C"
    
    **Notes:**
    - Row numbers in errors are 1-indexed (row 2 = first data row after header)
    - All doctors get default password: Welcome@123
    - Doctors can change password after first login
    - Invalid rows are skipped, processing continues
    - Admin can fix errors and re-upload only failed rows
    """
    return await bulk_upload_doctors(file, current_user)


@router.get("", response_model=DoctorListResponse, summary="List All Doctors")
async def list_doctors(current_user: Dict = Depends(get_current_user)):
    """
    Get list of all doctors.
    
    **Access:** All authenticated users (Admin, Doctor, MR)
    
    **Purpose:**
    Retrieve a complete list of all doctors in the system with their details including classification.
    
    **Flow:**
    1. User sends request with valid JWT token
    2. Backend retrieves all doctors from database
    3. Returns list with doctor details including classification (A/B/C)
    4. Password hash is excluded from response
    
    **Usage:**
    ```
    GET /api/v1/doctors
    Headers: Authorization: Bearer <token>
    ```
    
    **Response:**
    ```json
    {
        "total": 2,
        "doctors": [
            {
                "id": "507f1f77bcf86cd799439011",
                "name": "Dr. Sarah Sharma",
                "email": "sharma@gmail.com",
                "phone": "+919876543210",
                "specialization": "Cardiologist",
                "classification": "A",
                "hospital": "City Hospital",
                "license_number": "MH12345",
                "address": "123 Medical Street, Mumbai",
                "is_active": true,
                "added_by": {
                    "role": "ADMIN",
                    "id": "admin_id",
                    "name": "Admin Name",
                    "department": "general"
                },
                "approved_by": null,
                "created_at": "2024-03-30T10:00:00"
            },
            {
                "id": "507f1f77bcf86cd799439012",
                "name": "Dr. Amit Patel",
                "email": "amit@hospital.com",
                "phone": "+919876543211",
                "specialization": "Neurologist",
                "classification": "B",
                "hospital": "Apollo Hospital",
                "license_number": "MH12346",
                "address": "456 Medical Street, Mumbai",
                "is_active": true,
                "added_by": {
                    "role": "MR",
                    "id": "mr_id",
                    "name": "MR Name"
                },
                "approved_by": {
                    "role": "ADMIN",
                    "id": "admin_id",
                    "name": "Admin Name",
                    "department": "general"
                },
                "created_at": "2024-03-30T11:00:00"
            }
        ]
    }
    ```
    
    **Creator Tracking:**
    - `added_by`: Shows who originally added the doctor (ADMIN or MR)
      - **Note:** MR users will NOT see this field (they already know they added it)
    - `approved_by`: Shows which admin approved (only for MR requests, null for direct admin adds)
    - `department`: Admin's department (only present for admin roles)
    
    **Role-Based Filtering:**
    - **Admin**: Sees all doctors with full creator tracking
    - **MR**: Sees only their assigned doctors, without `added_by` field
    - **Doctor**: Sees all doctors with full creator tracking
    
    **Classification Guide:**
    - **A**: High-value doctors (2 visits/month required)
    - **B**: Medium-value doctors (1 visit/month required)
    - **C**: Low-value doctors (1 visit/2 months required)
    
    **Notes:**
    - All doctors include classification field
    - Doctors without classification default to "C"
    - Password hash is never included in response
    - List includes both active and inactive doctors
    """
    doctors = await get_all_doctors(current_user)
    return {
        "total": len(doctors),
        "doctors": doctors
    }


@router.get("/available", response_model=DoctorListResponse, summary="List Available Doctors")
async def list_available_doctors(current_user: Dict = Depends(require_admin)):
    """
    Get list of doctors who are NOT assigned to any MR.
    
    **Access:** Company Admin only
    
    **Usage:**
    ```
    GET /api/v1/doctors/available
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Response:**
    ```
    {
        "total": 5,
        "doctors": [
            {
                "id": "507f1f77bcf86cd799439011",
                "name": "Dr. Sarah Sharma",
                "email": "sharma@gmail.com",
                "phone": "+919876543210",
                "specialization": "Cardiologist",
                "classification": "C",
                "hospital": "City Hospital",
                "license_number": "MH12345",
                "address": "123 Medical Street, Mumbai",
                "is_active": true,
                "added_by": {
                    "role": "ADMIN",
                    "id": "admin_id",
                    "name": "Admin Full Name",
                    "department": "general"
                },
                "approved_by": null,
                "created_at": "2024-03-30T10:00:00"
            }
        ]
    }
    ```
    
    **Creator Tracking:**
    - `added_by`: Shows who originally added the doctor
    - `approved_by`: Shows which admin approved (null for direct admin adds)
    - `department`: Admin's department (only for admin roles)
    
    **Use Case:** When admin is adding/updating MR and needs to assign doctors.
    """
    doctors = await get_available_doctors(current_user)
    return {
        "total": len(doctors),
        "doctors": doctors
    }


# ============================================================================
# DOCTOR REQUEST ENDPOINTS (MR Request → Admin Approval Workflow)
# ============================================================================
# NOTE: These routes MUST be defined BEFORE the /{doctor_id} catch-all route
# to avoid route conflicts where "requests" is treated as a doctor_id
# ============================================================================

@router.post("/request", response_model=DoctorRequestCreateResponse, status_code=status.HTTP_201_CREATED, summary="Request to Add Doctor (MR)")
async def request_add_doctor(
    request: DoctorRequestCreate,
    current_user: Dict = Depends(get_current_user)
):
    """
    Request to add a new doctor (MR only).
    MR submits doctor details, admin must approve before doctor is created.
    
    **Access:** MR only
    
    **Flow:**
    1. MR provides doctor details including classification (A/B/C)
    2. Backend validates email is not already in system
    3. Backend creates a pending request
    4. Admin receives notification
    5. Admin reviews and approves/rejects
    6. MR receives notification of decision
    7. If approved, doctor account is created with specified classification
    
    **Doctor Classification (SFE):**
    - Class A: High-value doctors, requires 2 visits per month
    - Class B: Medium-value doctors, requires 1 visit per month
    - Class C: Low-value doctors, requires 1 visit per 2 months
    
    **Usage:**
    ```
    POST /api/v1/doctors/request
    Headers: Authorization: Bearer <mr_token>
    {
        "name": "Dr. Amit Patel",
        "email": "amit.patel@hospital.com",
        "phone": "9876543210",
        "specialization": "Cardiologist",
        "classification": "A",
        "hospital": "Apollo Hospital",
        "license_number": "MH12345",
        "address": "123 Medical Street, Mumbai"
    }
    ```
    
    **Response:**
    ```
    {
        "message": "Doctor request submitted successfully. Waiting for admin approval.",
        "request_id": "507f1f77bcf86cd799439099"
    }
    ```
    
    **What happens next:**
    - Admin receives notification: "Rajesh Kumar requested to add Dr. Amit Patel (Cardiologist)"
    - Admin can view request details in GET /api/v1/doctors/requests
    - Admin approves via POST /api/v1/doctors/requests/{request_id}/approve
    - MR receives notification when approved/rejected
    - If approved, doctor account is created with random password and specified classification
    - Doctor receives invitation email with credentials
    """
    # Only MR can create doctor requests
    if current_user.get("role") != "MR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Medical Representatives can request to add doctors"
        )
    
    return await create_doctor_request(
        name=request.name,
        email=request.email,
        phone=request.phone,
        specialization=request.specialization,
        classification=request.classification,
        hospital=request.hospital,
        license_number=request.license_number,
        address=request.address,
        current_user=current_user
    )


@router.get("/requests", summary="List Doctor Requests")
async def list_doctor_requests(
    status_filter: Optional[str] = Query(None, description="Filter by status: pending, approved, rejected"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get list of doctor requests.
    
    **Access:**
    - Admin: Can see all requests
    - MR: Can see only their own requests
    
    **Query Parameters:**
    - status_filter: Filter by status (optional) - "pending", "approved", "rejected"
    
    **Usage (Admin - see all pending requests):**
    ```
    GET /api/v1/doctors/requests?status_filter=pending
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Usage (MR - see own requests):**
    ```
    GET /api/v1/doctors/requests
    Headers: Authorization: Bearer <mr_token>
    ```
    
    **Response:**
    ```
    {
        "total": 5,
        "requests": [
            {
                "request_id": "507f1f77bcf86cd799439099",
                "requested_by": "507f1f77bcf86cd799439011",
                "requested_by_name": "Rajesh Kumar",
                "requested_by_email": "rajesh@xyzpharma.com",
                "status": "pending",
                "name": "Dr. Amit Patel",
                "email": "amit.patel@hospital.com",
                "phone": "+919876543210",
                "specialization": "Cardiologist",
                "hospital": "Apollo Hospital",
                "license_number": "MH12345",
                "address": "123 Medical Street, Mumbai",
                "reviewed_by": null,
                "reviewed_by_name": null,
                "reviewed_at": null,
                "rejection_reason": null,
                "doctor_id": null,
                "created_at": "2024-03-30T10:00:00",
                "updated_at": "2024-03-30T10:00:00"
            }
        ]
    }
    ```
    
    **Use Cases:**
    
    1. **Admin Dashboard - Pending Approvals:**
    ```
    GET /api/v1/doctors/requests?status_filter=pending
    ```
    Shows all pending doctor requests that need admin review
    
    2. **MR Dashboard - My Requests:**
    ```
    GET /api/v1/doctors/requests
    ```
    Shows all requests submitted by the logged-in MR
    
    3. **Admin History - All Requests:**
    ```
    GET /api/v1/doctors/requests
    ```
    Shows complete history of all doctor requests
    """
    requests = await get_doctor_requests(current_user, status_filter)
    return {
        "total": len(requests),
        "requests": requests
    }


@router.post("/requests/{request_id}/approve", response_model=DoctorRequestApproveResponse, summary="Approve Doctor Request (Admin)")
async def approve_doctor_request_endpoint(
    request_id: str,
    current_user: Dict = Depends(require_admin)
):
    """
    Approve a doctor request and create the doctor account (Admin only).
    
    **Access:** Admin only
    
    **Flow:**
    1. Admin approves the request
    2. Backend creates doctor account with random password
    3. Backend updates request status to "approved"
    4. MR receives notification: "Your request to add Dr. X has been approved"
    5. Doctor receives invitation email with credentials
    
    **Usage:**
    ```
    POST /api/v1/doctors/requests/507f1f77bcf86cd799439099/approve
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Response:**
    ```
    {
        "message": "Doctor request approved and doctor account created successfully",
        "doctor_id": "507f1f77bcf86cd799439011"
    }
    ```
    
    **Creator Tracking:**
    When admin approves an MR request, the created doctor will have:
    - `added_by`: Contains MR's role, id, and name (who originally requested)
    - `approved_by`: Contains admin's role, id, name, and department (who approved)
    
    Example:
    ```json
    {
        "added_by": {
            "role": "MR",
            "id": "mr_id",
            "name": "MR Full Name"
        },
        "approved_by": {
            "role": "ADMIN",
            "id": "admin_id",
            "name": "Admin Full Name",
            "department": "general"
        }
    }
    ```
    
    **Note:** After approval, the request is DELETED from the `doctor_requests` collection.
    Only pending and rejected requests remain in that collection.
    
    **What happens after approval:**
    - Doctor account is created in doctors collection
    - Doctor gets default random password (sent via email)
    - **Doctor is automatically added to the requesting MR's assigned_doctors list**
    - Request status changes to "approved"
    - Request is DELETED from doctor_requests collection (no longer needed)
    - MR receives notification
    - Doctor receives invitation email
    - Doctor can now login and change password
    
    **Error Cases:**
    - Request not found: 404
    - Request already processed: 400 "Request already approved/rejected"
    - Email already exists: 400 "Doctor with this email already exists"
    """
    return await approve_doctor_request(request_id, current_user)


@router.post("/requests/{request_id}/reject", response_model=MessageResponse, summary="Reject Doctor Request (Admin)")
async def reject_doctor_request_endpoint(
    request_id: str,
    request: DoctorRequestRejectRequest,
    current_user: Dict = Depends(require_admin)
):
    """
    Reject a doctor request (Admin only).
    
    **Access:** Admin only
    
    **Flow:**
    1. Admin rejects the request with a reason
    2. Backend updates request status to "rejected"
    3. MR receives notification with rejection reason
    
    **Usage:**
    ```
    POST /api/v1/doctors/requests/507f1f77bcf86cd799439099/reject
    Headers: Authorization: Bearer <admin_token>
    {
        "rejection_reason": "Doctor already exists in the system with a different email address."
    }
    ```
    
    **Response:**
    ```
    {
        "message": "Doctor request rejected successfully"
    }
    ```
    
    **What happens after rejection:**
    - Request status changes to "rejected"
    - Rejection reason is stored
    - MR receives notification with reason
    - No doctor account is created
    - MR can submit a new request if needed
    
    **Common Rejection Reasons:**
    - "Doctor already exists in the system with a different email address."
    - "Incomplete or invalid doctor information provided."
    - "Doctor's license number could not be verified."
    - "Hospital information is incorrect or incomplete."
    - "Duplicate request - this doctor was already added by another MR."
    
    **Error Cases:**
    - Request not found: 404
    - Request already processed: 400 "Request already processed/rejected"
    - Rejection reason too short: 400 "Rejection reason must be at least 10 characters"
    """
    return await reject_doctor_request(request_id, request.rejection_reason, current_user)


# ============================================================================
# DOCTOR LOCATION MANAGEMENT ENDPOINTS
# NOTE: These routes MUST be defined BEFORE the /{doctor_id:path} catch-all route
# to avoid route conflicts where "{doctor_id}/locations" is treated as just doctor_id
# ============================================================================

from app.api.v1.doctors.location_schemas import (
    AddLocationRequest,
    UpdateLocationRequest,
    LocationResponse,
    LocationListResponse,
    GeoSearchRequest,
    GeoSearchResponse,
    LocationSuggestionsResponse,
    ApproveSuggestionRequest,
    RejectSuggestionRequest,
    MessageResponse as LocationMessageResponse
)
from app.api.v1.doctors.location_service import (
    add_doctor_location,
    get_doctor_locations,
    update_doctor_location,
    search_locations,
    get_location_suggestions,
    approve_location_suggestion,
    reject_location_suggestion
)


@router.post(
    "/geosearch",
    response_model=GeoSearchResponse,
    summary="Search Locations (Geocoding)"
)
async def geosearch_endpoint(
    request: GeoSearchRequest,
    current_user: Dict = Depends(require_admin)
):
    """
    Search for locations using Nominatim geocoding (Admin only).
    
    **Access:** Admin only
    
    **Usage:**
    - Admin types location name
    - Optionally provides current location for nearby results
    - System searches using Nominatim API
    - Returns list of results with coordinates
    
    **Example 1: Without location bias (global search):**
    ```json
    {
        "query": "Apollo Hospital Hyderabad",
        "limit": 5
    }
    ```
    
    **Example 2: With location bias (prioritizes nearby results):**
    ```json
    {
        "query": "apollo hospital",
        "limit": 5,
        "user_latitude": 17.4400,
        "user_longitude": 78.3489
    }
    ```
    
    **How location bias works:**
    - If you provide user_latitude and user_longitude
    - System tells Nominatim to prioritize results near that location
    - Results within ~50km radius get higher priority
    - But still searches globally (not restricted)
    
    **Response:**
    ```json
    {
        "total": 3,
        "results": [
            {
                "display_name": "Apollo Hospital, Road 45, Jubilee Hills, Hyderabad",
                "latitude": 17.4401,
                "longitude": 78.3489,
                "address": {...},
                "type": "hospital",
                "importance": 0.8
            }
        ]
    }
    ```
    """
    return await search_locations(
        request.query, 
        request.limit,
        request.user_latitude,
        request.user_longitude
    )


@router.post(
    "/{doctor_id}/locations",
    response_model=LocationMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Doctor Location"
)
async def add_location_endpoint(
    doctor_id: str,
    request: AddLocationRequest,
    current_user: Dict = Depends(require_admin)
):
    """
    Add a new location to a doctor's profile (Admin only).
    
    **Access:** Admin only
    
    **Usage:**
    - Admin searches location using GeoSearch
    - Gets coordinates and address
    - Adds location to doctor's profile
    
    **Validations:**
    - Location must not exist within 50m radius
    - Coordinates must be valid
    
    **Example:**
    ```json
    {
        "name": "Apollo Hospital",
        "address": "Road 45, Jubilee Hills, Hyderabad",
        "latitude": 17.4401,
        "longitude": 78.3489,
        "type": "primary",
        "geofence_radius": 100
    }
    ```
    """
    result = await add_doctor_location(
        doctor_id=doctor_id,
        name=request.name,
        address=request.address,
        latitude=request.latitude,
        longitude=request.longitude,
        location_type=request.type,
        geofence_radius=request.geofence_radius,
        admin_user=current_user
    )
    
    return result


@router.get(
    "/{doctor_id}/locations",
    response_model=LocationListResponse,
    summary="Get Doctor Locations"
)
async def get_locations_endpoint(
    doctor_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get all locations for a doctor.
    
    **Access:** Admin and MR
    
    **Returns:** List of doctor's permanent locations only (no suggestions)
    
    **Note:** MRs use this to select location when scheduling visits.
    """
    return await get_doctor_locations(doctor_id)


@router.put(
    "/{doctor_id}/locations/{location_id}",
    response_model=LocationMessageResponse,
    summary="Update Doctor Location"
)
async def update_location_endpoint(
    doctor_id: str,
    location_id: str,
    request: UpdateLocationRequest,
    current_user: Dict = Depends(require_admin)
):
    """
    Update a doctor's location (Admin only).
    
    **Access:** Admin only
    
    **Updatable fields:**
    - name: Location name
    - address: Full address
    - latitude: GPS latitude
    - longitude: GPS longitude
    - type: Location type (primary/secondary)
    - geofence_radius: Geofence radius in meters
    - is_active: Activate (true) or deactivate (false)
    
    **Common Use Cases:**
    
    1. **Deactivate location** (soft delete):
       ```json
       PUT /api/v1/doctors/{doctor_id}/locations/{location_id}
       {"is_active": false}
       ```
    
    2. **Reactivate location**:
       ```json
       {"is_active": true}
       ```
    
    3. **Update geofence radius**:
       ```json
       {"geofence_radius": 150}
       ```
    
    4. **Update address and coordinates**:
       ```json
       {
         "address": "New Address, Hyderabad",
         "latitude": 17.4500,
         "longitude": 78.3800
       }
       ```
    
    **Note:** 
    - Locations are never hard-deleted to preserve history
    - Deactivated locations (is_active=false) won't appear in MR's location selection
    - Can be reactivated anytime by setting is_active=true
    """
    updates = request.model_dump(exclude_unset=True)
    return await update_doctor_location(doctor_id, location_id, updates)


@router.get(
    "/{doctor_id}/location-suggestions",
    response_model=LocationSuggestionsResponse,
    summary="Get Location Suggestions"
)
async def get_suggestions_endpoint(
    doctor_id: str,
    current_user: Dict = Depends(require_admin)
):
    """
    Get location suggestions for a doctor (Admin only).
    
    **Access:** Admin only
    
    **Returns:** List of pending/approved/rejected location suggestions
    
    **How suggestions are created:**
    - System analyzes temporary location visits
    - Groups locations by proximity (50m)
    - Creates suggestion when location used 5+ times
    - Admin reviews and approves/rejects
    """
    return await get_location_suggestions(doctor_id)


@router.put(
    "/{doctor_id}/location-suggestions/{suggestion_id}/approve",
    response_model=LocationMessageResponse,
    summary="Approve Location Suggestion"
)
async def approve_suggestion_endpoint(
    doctor_id: str,
    suggestion_id: str,
    request: ApproveSuggestionRequest,
    current_user: Dict = Depends(require_admin)
):
    """
    Approve a location suggestion (Admin only).
    
    **Access:** Admin only
    
    **What happens:**
    - Suggestion moved to doctor's permanent locations
    - Marked as 'approved'
    - Future MRs can select this location when scheduling
    """
    return await approve_location_suggestion(
        doctor_id=doctor_id,
        suggestion_id=suggestion_id,
        admin_user=current_user,
        notes=request.notes,
        geofence_radius=request.geofence_radius
    )


@router.put(
    "/{doctor_id}/location-suggestions/{suggestion_id}/reject",
    response_model=LocationMessageResponse,
    summary="Reject Location Suggestion"
)
async def reject_suggestion_endpoint(
    doctor_id: str,
    suggestion_id: str,
    request: RejectSuggestionRequest,
    current_user: Dict = Depends(require_admin)
):
    """
    Reject a location suggestion (Admin only).
    
    **Access:** Admin only
    
    **What happens:**
    - Suggestion marked as 'rejected'
    - System won't suggest this location again for 180 days
    - Reason saved for audit
    """
    return await reject_location_suggestion(
        doctor_id=doctor_id,
        suggestion_id=suggestion_id,
        admin_user=current_user,
        notes=request.notes
    )


@router.get("/{doctor_id:path}", response_model=DoctorResponse, summary="Get Doctor Details")
async def get_doctor(
    doctor_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get details of a specific doctor.
    
    **Access:** All authenticated users (Admin, Doctor, MR)
    
    **Note:** This route uses a path parameter. Specific routes like /requests, /available 
    must be defined before this catch-all route to avoid conflicts.
    
    **Purpose:**
    Retrieve detailed information about a specific doctor including their classification.
    
    **Flow:**
    1. User provides doctor ID in URL
    2. Backend validates doctor ID format
    3. Backend retrieves doctor from database
    4. Returns doctor details with classification
    
    **Usage:**
    ```
    GET /api/v1/doctors/507f1f77bcf86cd799439011
    Headers: Authorization: Bearer <token>
    ```
    
    **Response:**
    ```json
    {
        "id": "507f1f77bcf86cd799439011",
        "name": "Dr. Sarah Sharma",
        "email": "sharma@gmail.com",
        "phone": "+919876543210",
        "specialization": "Cardiologist",
        "classification": "A",
        "hospital": "City Hospital",
        "license_number": "MH12345",
        "address": "123 Medical Street, Mumbai",
        "is_active": true,
        "added_by": {
            "role": "ADMIN",
            "id": "admin_id",
            "name": "Admin Full Name",
            "department": "general"
        },
        "approved_by": null,
        "created_at": "2024-03-30T10:00:00"
    }
    ```
    
    **Creator Tracking:**
    - `added_by`: Shows who originally added the doctor (ADMIN or MR with their details)
      - **Note:** MR users will NOT see this field (they already know they added it)
    - `approved_by`: Shows which admin approved (only for MR requests, null for direct admin adds)
    - `department`: Admin's department (only present for admin roles)
    
    **Classification:**
    - **A**: High-value (2 visits/month)
    - **B**: Medium-value (1 visit/month)
    - **C**: Low-value (1 visit/2 months)
    
    **Error Responses:**
    - 400: Invalid doctor ID format
    - 404: Doctor not found
    """
    return await get_doctor_by_id(doctor_id, current_user)


@router.put("/{doctor_id}", response_model=DoctorUpdateResponse, summary="Update Doctor")
async def update_doctor_endpoint(
    doctor_id: str,
    request: DoctorUpdateRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Update doctor information.
    
    **Access:** 
    - Admin: Can update any doctor's information including is_active status and classification
    - Doctor: Can update only their own information (except email, is_active, and classification)
    
    **Note:** Email cannot be changed by anyone.
    
    **Purpose:**
    Update doctor details including classification, contact info, or active status.
    
    **Flow:**
    1. User provides doctor ID and fields to update
    2. Backend validates authorization
    3. Backend updates specified fields
    4. Returns success message with updated fields
    
    **Usage (Admin - update classification):**
    ```json
    PUT /api/v1/doctors/507f1f77bcf86cd799439011
    Headers: Authorization: Bearer <admin_token>
    {
        "classification": "A",
        "phone": "+919876543211",
        "hospital": "New City Hospital"
    }
    ```
    
    **Usage (Admin - deactivate doctor):**
    ```json
    PUT /api/v1/doctors/507f1f77bcf86cd799439011
    Headers: Authorization: Bearer <admin_token>
    {
        "is_active": false
    }
    ```
    
    **Usage (Doctor - updating own profile):**
    ```json
    PUT /api/v1/doctors/507f1f77bcf86cd799439011
    Headers: Authorization: Bearer <doctor_token>
    {
        "phone": "+919876543211",
        "hospital": "New City Hospital",
        "specialization": "Senior Cardiologist"
    }
    ```
    
    **Response:**
    ```json
    {
        "message": "Doctor updated successfully",
        "updated_fields": {
            "classification": "A",
            "phone": "+919876543211",
            "hospital": "New City Hospital"
        }
    }
    ```
    
    **Updatable Fields (Admin):**
    - name, phone, specialization, classification
    - hospital, license_number, address
    - is_active (activate/deactivate)
    
    **Updatable Fields (Doctor - own profile):**
    - name, phone, specialization
    - hospital, license_number, address
    - Cannot update: email, is_active, classification
    
    **Classification Values:**
    - **A**: High-value (2 visits/month)
    - **B**: Medium-value (1 visit/month)
    - **C**: Low-value (1 visit/2 months)
    """
    update_data = request.model_dump(exclude_unset=True)
    return await update_doctor(doctor_id, update_data, current_user)


@router.delete("/{doctor_id}", response_model=MessageResponse, summary="Deactivate Doctor")
async def delete_doctor_endpoint(
    doctor_id: str,
    current_user: Dict = Depends(require_admin)
):
    """
    Deactivate a doctor (Admin only).
    
    **Access:** Company Admin only
    
    **Note:** This is a soft delete - doctor is marked as inactive (is_active = false).
    The doctor account remains in the database but cannot login.
    Admin can reactivate by updating is_active to true.
    
    **Usage:**
    ```
    DELETE /api/v1/doctors/507f1f77bcf86cd799439011
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Response:**
    ```
    {
        "message": "Doctor deactivated successfully"
    }
    ```
    
    **To reactivate:**
    ```
    PUT /api/v1/doctors/507f1f77bcf86cd799439011
    {
        "is_active": true
    }
    ```
    """
    return await delete_doctor(doctor_id, current_user)


