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
    BulkUploadResponse
)
from app.api.v1.doctors.service import (
    create_doctor,
    get_all_doctors,
    get_doctor_by_id,
    update_doctor,
    delete_doctor,
    get_available_doctors,
    bulk_upload_doctors,
    download_doctors_template
)
from app.core.auth import get_current_user, require_admin


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
    1. Admin provides doctor details
    2. Backend validates email is unique
    3. Backend hashes password
    4. Backend creates doctor account
    5. Doctor can now login
    
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
    5. hospital (optional) - Hospital name
    6. license_number (optional) - Medical license number
    7. address (optional) - Full address
    
    **Instructions:**
    - Fill all required fields (name, email, phone, specialization)
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
    
    **Optional Columns:**
    - hospital: Hospital name
    - license_number: Medical license number
    - address: Full address
    
    **CSV Example:**
    ```csv
    name,email,phone,specialization,hospital,license_number,address
    Dr. John Smith,john@example.com,9876543210,Cardiology,Apollo Hospital,MH12345,Mumbai Maharashtra
    Dr. Sarah Jones,sarah@example.com,9876543211,Neurology,Fortis Hospital,DL67890,Delhi
    Dr. Mike Brown,mike@example.com,9876543212,Orthopedics,Max Hospital,MH54321,Pune Maharashtra
    ```
    
    **Validation Rules:**
    - Email must be valid format and unique in database
    - Phone must be exactly 10 digits and unique in database
    - Name, email, phone, specialization are required
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
