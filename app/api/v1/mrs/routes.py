"""
MR routes - API endpoints for MR management.
"""

from fastapi import APIRouter, Depends, status, UploadFile, File
from typing import Dict, Any
from app.api.v1.mrs.schemas import (
    MRCreateRequest,
    MRUpdateRequest,
    MRResponse,
    MRListResponse,
    MessageResponse,
    MRCreateResponse,
    MRUpdateResponse,
    BulkUploadResponse
)
from app.api.v1.mrs.service import (
    create_mr,
    get_all_mrs,
    get_mr_by_id,
    update_mr,
    delete_mr,
    bulk_upload_mrs,
    download_mrs_template
)
from app.core.auth import get_current_user, require_admin


# Create router for MR endpoints
router = APIRouter()


@router.post("", response_model=MRCreateResponse, status_code=status.HTTP_201_CREATED, summary="Add MR")
async def add_mr(
    request: MRCreateRequest,
    current_user: Dict = Depends(require_admin)
):
    """
    Add a new Medical Representative (Admin only).
    
    **Access:** Company Admin only
    
    **Flow:**
    1. Admin provides MR details
    2. Backend validates email is unique
    3. Backend hashes password (or uses default)
    4. Backend creates MR account
    5. MR can now login
    
    **Usage:**
    ```
    POST /api/v1/mrs
    Headers: Authorization: Bearer <admin_token>
    {
        "name": "Rajesh Kumar",
        "email": "rajesh@xyzpharma.com",
        "phone": "+919876543210",
        "territory": "Mumbai North",
        "assigned_doctors": []
    }
    ```
    
    **Response:**
    ```
    {
        "message": "MR added successfully",
        "mr_id": "507f1f77bcf86cd799439011"
    }
    ```
    
    **Note:** Password is optional. If not provided, default password (Welcome@123) will be used.
    """
    return await create_mr(
        name=request.name,
        email=request.email,
        password=request.password,
        phone=request.phone,
        territory=request.territory,
        assigned_doctors=request.assigned_doctors,
        current_user=current_user
    )


@router.get("/download-template", dependencies=[Depends(require_admin)])
async def download_mrs_template_endpoint():
    """
    Download CSV template for bulk MR upload.
    
    **Access:** Admin only
    
    **Purpose:**
    Provides a CSV template file that admins can fill with MR data and upload via bulk upload.
    
    **Template Columns:**
    1. name (REQUIRED) - MR's full name
    2. email (REQUIRED) - MR's email address
    3. phone (REQUIRED) - Phone number with country code (e.g., +919876543210)
    4. territory (REQUIRED) - Sales territory
    
    **Instructions:**
    - Fill all required fields (name, email, phone, territory)
    - Email must be unique (not already in system)
    - Phone must be unique and in E.164 format (+country code)
    - Maximum 100 rows per upload
    - Doctors can be assigned later via update endpoint
    
    **Usage:**
    ```
    GET /api/v1/mrs/download-template
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Response:**
    Downloads file: mrs_template.csv
    """
    return await download_mrs_template()


@router.post("/bulk-upload", response_model=BulkUploadResponse, status_code=status.HTTP_200_OK, summary="Bulk Upload MRs")
async def bulk_upload_mrs_endpoint(
    file: UploadFile = File(..., description="CSV or Excel file with MR data"),
    current_user: Dict = Depends(require_admin)
):
    """
    Bulk upload Medical Representatives from CSV or Excel file (Admin only).
    
    **Access:** Company Admin only
    
    **Purpose:**
    Upload multiple MRs at once using a CSV or Excel file instead of adding them one by one.
    
    **Flow:**
    1. Admin prepares CSV/Excel file with MR data
    2. Admin uploads file via this endpoint
    3. Backend validates each row
    4. Valid rows are inserted into database
    5. Invalid rows are skipped and reported in response
    6. Admin receives detailed report of success/failures
    
    **File Format:**
    - Supported: CSV (.csv), Excel (.xlsx, .xls)
    - Max file size: 5MB
    - Max rows: 100 MRs per upload
    
    **Required Columns:**
    - name: MR's full name
    - email: MR's email (must be unique)
    - phone: Phone number (must be 10 digits)
    - territory: Sales territory/region
    
    **CSV Example:**
    ```csv
    name,email,phone,territory
    Rajesh Kumar,rajesh@xyzpharma.com,9876543210,Mumbai North
    Priya Sharma,priya@xyzpharma.com,9876543211,Delhi Central
    Amit Patel,amit@xyzpharma.com,9876543212,Ahmedabad West
    ```
    
    **Validation Rules:**
    - Email must be valid format and unique in database
    - Phone must be exactly 10 digits and unique in database
    - Name, email, phone, territory are required
    - Invalid rows are skipped, valid rows are inserted
    - All uploaded MRs get default password: Welcome@123
    - assigned_doctors will be empty (can be assigned later via update)
    
    **Usage:**
    ```
    POST /api/v1/mrs/bulk-upload
    Headers: Authorization: Bearer <admin_token>
    Content-Type: multipart/form-data
    Body: file=@mrs.csv
    ```
    
    **Response (All Success):**
    ```json
    {
        "total_rows": 50,
        "successful": 50,
        "failed": 0,
        "errors": [],
        "message": "Bulk upload completed successfully. All 50 MRs added."
    }
    ```
    
    **Response (Partial Success):**
    ```json
    {
        "total_rows": 50,
        "successful": 45,
        "failed": 5,
        "errors": [
            {
                "row": 3,
                "email": "invalid-email",
                "error": "Invalid email format"
            },
            {
                "row": 7,
                "email": "existing@xyzpharma.com",
                "error": "Email already exists in database"
            },
            {
                "row": 15,
                "phone": "12345",
                "error": "Phone must be 10 digits"
            },
            {
                "row": 23,
                "name": "Test MR",
                "error": "Territory is required"
            },
            {
                "row": 45,
                "phone": "9876543210",
                "error": "Phone number already exists in database"
            }
        ],
        "message": "Bulk upload completed. 45 MRs added successfully, 5 rows failed."
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
    - "Territory is required"
    
    **Notes:**
    - Row numbers in errors are 1-indexed (row 2 = first data row after header)
    - All MRs get default password: Welcome@123
    - MRs can change password after first login
    - Invalid rows are skipped, processing continues
    - Admin can fix errors and re-upload only failed rows
    - Doctors can be assigned later via PUT /api/v1/mrs/{mr_id}
    """
    return await bulk_upload_mrs(file, current_user)


@router.get("", response_model=MRListResponse, summary="List All MRs")
async def list_mrs(current_user: Dict = Depends(get_current_user)):
    """
    Get list of all Medical Representatives.
    
    **Access:** All authenticated users (Admin, Doctor, MR)
    
    **Usage:**
    ```
    GET /api/v1/mrs
    Headers: Authorization: Bearer <token>
    ```
    
    **Response:**
    ```
    {
        "total": 2,
        "mrs": [
            {
                "id": "507f1f77bcf86cd799439011",
                "name": "Rajesh Kumar",
                "email": "rajesh@xyzpharma.com",
                "phone": "+919876543210",
                "territory": "Mumbai North",
                "assigned_doctors": [
                    {
                        "id": "507f1f77bcf86cd799439012",
                        "name": "Dr. Sarah Sharma"
                    }
                ],
                "is_active": true,
                "created_at": "2024-03-30T10:00:00"
            }
        ]
    }
    ```
    """
    mrs = await get_all_mrs(current_user)
    return {
        "total": len(mrs),
        "mrs": mrs
    }


@router.get("/{mr_id}", response_model=MRResponse, summary="Get MR Details")
async def get_mr(
    mr_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get details of a specific Medical Representative.
    
    **Access:** All authenticated users (Admin, Doctor, MR)
    
    **Usage:**
    ```
    GET /api/v1/mrs/507f1f77bcf86cd799439011
    Headers: Authorization: Bearer <token>
    ```
    
    **Response:**
    ```
    {
        "id": "507f1f77bcf86cd799439011",
        "name": "Rajesh Kumar",
        "email": "rajesh@xyzpharma.com",
        "phone": "+919876543210",
        "territory": "Mumbai North",
        "assigned_doctors": [
            {
                "id": "507f1f77bcf86cd799439012",
                "name": "Dr. Sarah Sharma"
            }
        ],
        "is_active": true,
        "created_at": "2024-03-30T10:00:00"
    }
    ```
    """
    return await get_mr_by_id(mr_id, current_user)


@router.put("/{mr_id}", response_model=MRUpdateResponse, summary="Update MR")
async def update_mr_endpoint(
    mr_id: str,
    request: MRUpdateRequest,
    current_user: Dict = Depends(require_admin)
):
    """
    Update MR information (Admin only).
    
    **Access:** Company Admin only
    
    **Note:** Only provided fields will be updated. Email cannot be changed.
    
    **Usage:**
    ```
    PUT /api/v1/mrs/507f1f77bcf86cd799439011
    Headers: Authorization: Bearer <admin_token>
    {
        "phone": "+919876543211",
        "territory": "Mumbai South",
        "assigned_doctors": ["507f1f77bcf86cd799439012", "507f1f77bcf86cd799439013"],
        "is_active": true
    }
    ```
    
    **Response:**
    ```
    {
        "message": "MR updated successfully",
        "updated_fields": {
            "phone": "+919876543211",
            "territory": "Mumbai South",
            "assigned_doctors": ["507f1f77bcf86cd799439012", "507f1f77bcf86cd799439013"],
            "is_active": true
        }
    }
    ```
    """
    update_data = request.model_dump(exclude_unset=True)
    return await update_mr(mr_id, update_data, current_user)


@router.delete("/{mr_id}", response_model=MessageResponse, summary="Deactivate MR")
async def delete_mr_endpoint(
    mr_id: str,
    current_user: Dict = Depends(require_admin)
):
    """
    Deactivate an MR (Admin only).
    
    **Access:** Company Admin only
    
    **Note:** This is a soft delete - MR is marked as inactive (is_active = false).
    The MR account remains in the database but cannot login.
    Admin can reactivate by updating is_active to true.
    
    **Usage:**
    ```
    DELETE /api/v1/mrs/507f1f77bcf86cd799439011
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Response:**
    ```
    {
        "message": "MR deactivated successfully"
    }
    ```
    
    **To reactivate:**
    ```
    PUT /api/v1/mrs/507f1f77bcf86cd799439011
    {
        "is_active": true
    }
    ```
    """
    return await delete_mr(mr_id, current_user)
