"""
Doctor routes - API endpoints for doctor management.
"""

from fastapi import APIRouter, Depends, status, UploadFile, File
from typing import Dict, Any
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
    ```
    {
        "message": "Doctor added successfully",
        "doctor_id": "507f1f77bcf86cd799439011"
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
    
    **Usage:**
    ```
    GET /api/v1/doctors
    Headers: Authorization: Bearer <token>
    ```
    
    **Response:**
    ```
    {
        "total": 2,
        "doctors": [
            {
                "id": "507f1f77bcf86cd799439011",
                "name": "Dr. Sarah Sharma",
                "email": "sharma@gmail.com",
                "phone": "+919876543210",
                "specialization": "Cardiologist",
                "hospital": "City Hospital",
                "is_active": true,
                "created_at": "2024-03-30T10:00:00"
            }
        ]
    }
    ```
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
                "hospital": "City Hospital",
                "is_active": true,
                "created_at": "2024-03-30T10:00:00"
            }
        ]
    }
    ```
    
    **Use Case:** When admin is adding/updating MR and needs to assign doctors.
    """
    doctors = await get_available_doctors(current_user)
    return {
        "total": len(doctors),
        "doctors": doctors
    }


@router.get("/{doctor_id}", response_model=DoctorResponse, summary="Get Doctor Details")
async def get_doctor(
    doctor_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get details of a specific doctor.
    
    **Access:** All authenticated users (Admin, Doctor, MR)
    
    **Usage:**
    ```
    GET /api/v1/doctors/507f1f77bcf86cd799439011
    Headers: Authorization: Bearer <token>
    ```
    
    **Response:**
    ```
    {
        "id": "507f1f77bcf86cd799439011",
        "name": "Dr. Sarah Sharma",
        "email": "sharma@gmail.com",
        "phone": "+919876543210",
        "specialization": "Cardiologist",
        "hospital": "City Hospital",
        "license_number": "MH12345",
        "address": "123 Medical Street",
        "is_active": true,
        "created_at": "2024-03-30T10:00:00"
    }
    ```
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
    - Admin: Can update any doctor's information including is_active status
    - Doctor: Can update only their own information (except email and is_active)
    
    **Note:** Email cannot be changed by anyone.
    
    **Usage (Admin):**
    ```
    PUT /api/v1/doctors/507f1f77bcf86cd799439011
    Headers: Authorization: Bearer <admin_token>
    {
        "phone": "+919876543211",
        "hospital": "New City Hospital",
        "is_active": false
    }
    ```
    
    **Usage (Doctor - updating own profile):**
    ```
    PUT /api/v1/doctors/507f1f77bcf86cd799439011
    Headers: Authorization: Bearer <doctor_token>
    {
        "phone": "+919876543211",
        "hospital": "New City Hospital",
        "specialization": "Senior Cardiologist"
    }
    ```
    
    **Response:**
    ```
    {
        "message": "Doctor updated successfully",
        "updated_fields": {
            "phone": "+919876543211",
            "hospital": "New City Hospital"
        }
    }
    ```
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



# ============================================================================
# DOCTOR REQUEST ENDPOINTS (MR Request → Admin Approval Workflow)
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


@router.get("/requests", response_model=DoctorRequestListResponse, summary="List Doctor Requests")
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
    - status: Filter by status (optional) - "pending", "approved", "rejected"
    
    **Usage (Admin - see all pending requests):**
    ```
    GET /api/v1/doctors/requests?status=pending
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
    GET /api/v1/doctors/requests?status=pending
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
    
    **What happens after approval:**
    - Doctor account is created in doctors collection
    - Doctor gets default random password (sent via email)
    - Request status changes to "approved"
    - Request is linked to created doctor_id
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
    - Request already processed: 400 "Request already approved/rejected"
    - Rejection reason too short: 400 "Rejection reason must be at least 10 characters"
    """
    return await reject_doctor_request(request_id, request.rejection_reason, current_user)
