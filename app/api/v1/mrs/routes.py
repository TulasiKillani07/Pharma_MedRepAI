"""
MR routes - API endpoints for MR management.
"""

from fastapi import APIRouter, Depends, status, UploadFile, File, Query
from typing import Dict, Any, Optional
from app.api.v1.mrs.schemas import (
    MRCreateRequest,
    MRUpdateRequest,
    MRResponse,
    MRListResponse,
    MessageResponse,
    MRCreateResponse,
    MRUpdateResponse,
    BulkUploadResponse,
    MRFilterResponse
)
from app.api.v1.mrs.service import (
    create_mr,
    get_all_mrs,
    get_mr_by_id,
    update_mr,
    delete_mr,
    bulk_upload_mrs,
    download_mrs_template,
    filter_mrs
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
    1. Admin provides MR details (name, email, phone, location, assigned doctors & drugs)
    2. Backend validates email is unique
    3. Backend validates assigned doctors are not already assigned to another MR
    4. Backend hashes password (or uses default Welcome@123)
    5. Backend creates MR account
    6. Backend sends invitation email with credentials
    7. MR can now login
    
    **Usage:**
    ```
    POST /api/v1/mrs
    Headers: Authorization: Bearer <admin_token>
    Content-Type: application/json
    
    {
        "name": "Rajesh Kumar",
        "email": "rajesh@xyzpharma.com",
        "phone": "+919876543210",
        "zone": "South",
        "state": "Telangana",
        "territory": "Hyderabad",
        "assigned_doctors": ["507f1f77bcf86cd799439012"],
        "assigned_drugs": ["507f1f77bcf86cd799439021", "507f1f77bcf86cd799439022"]
    }
    ```
    
    **Response:**
    ```
    {
        "message": "MR added successfully",
        "mr_id": "507f1f77bcf86cd799439011"
    }
    ```
    
    **Notes:**
    - Password is optional. If not provided, default password (Welcome@123) will be used
    - assigned_doctors: Array of doctor IDs to assign (optional, defaults to empty array)
    - assigned_drugs: Array of drug/product IDs to assign (optional, defaults to empty array)
    - Invitation email is sent automatically with login credentials
    """
    return await create_mr(
        username=request.username,
        name=request.name,
        email=request.email,
        password=request.password,
        phone=request.phone,
        zone=request.zone,
        state=request.state,
        territory=request.territory,
        assigned_doctors=request.assigned_doctors,
        assigned_drugs=request.assigned_drugs,
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
    4. zone (REQUIRED) - Geographic zone (currently only "South" supported)
    5. state (REQUIRED) - State (e.g., Telangana, Karnataka, Maharashtra)
    6. territory (REQUIRED) - Sales territory
    
    **Instructions:**
    - Fill all required fields (name, email, phone, zone, state, territory)
    - Email must be unique (not already in system)
    - Phone must be unique and in E.164 format (+country code)
    - Zone must be "South" (currently only South zone is supported)
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


@router.get("/filter", response_model=MRFilterResponse, summary="Filter MRs by Location")
async def filter_mrs_endpoint(
    zone: Optional[str] = Query(None, description="Filter by zone (e.g., South)"),
    state: Optional[str] = Query(None, description="Filter by state (e.g., Telangana, Andhra Pradesh)"),
    territory: Optional[str] = Query(None, description="Filter by territory (e.g., Hyderabad, Visakhapatnam)"),
    current_user: Dict = Depends(require_admin)
):
    """
    Filter MRs by zone, state, and/or territory (Admin only).
    
    **Access:** Admin only
    
    **Purpose:**
    Used for communications targeting - helps admin see which MRs match specific criteria.
    Frontend can use this to show MR names when creating communications.
    
    **Query Parameters:**
    - zone: Filter by zone (optional) - e.g., "South"
    - state: Filter by state (optional) - e.g., "Telangana", "Andhra Pradesh"
    - territory: Filter by territory (optional) - e.g., "Hyderabad", "Visakhapatnam"
    
    **Filtering Logic:**
    - All filters are optional
    - Multiple filters use AND logic (must match all specified filters)
    - No filters = returns all active MRs
    - Results sorted alphabetically by name
    
    **Use Cases:**
    
    1. **Get all MRs in a territory:**
    ```
    GET /api/v1/mrs/filter?territory=Hyderabad
    ```
    Returns all MRs in Hyderabad territory
    
    2. **Get all MRs in a state:**
    ```
    GET /api/v1/mrs/filter?state=Telangana
    ```
    Returns all MRs in Telangana state
    
    3. **Get all MRs in a specific state and territory:**
    ```
    GET /api/v1/mrs/filter?state=Telangana&territory=Hyderabad
    ```
    Returns all MRs in Hyderabad, Telangana
    
    4. **Get all active MRs:**
    ```
    GET /api/v1/mrs/filter
    ```
    Returns all active MRs (no filters)
    
    **Response:**
    ```json
    {
      "total": 5,
      "mrs": [
        {
          "id": "507f1f77bcf86cd799439011",
          "name": "Rajesh Kumar",
          "email": "rajesh@xyzpharma.com",
          "phone": "+919876543210",
          "zone": "South",
          "state": "Telangana",
          "territory": "Hyderabad",
          "is_active": true
        },
        {
          "id": "507f1f77bcf86cd799439012",
          "name": "Priya Sharma",
          "email": "priya@xyzpharma.com",
          "phone": "+919876543211",
          "zone": "South",
          "state": "Telangana",
          "territory": "Hyderabad",
          "is_active": true
        }
      ]
    }
    ```
    
    **Frontend Integration:**
    
    1. **Cascading Dropdowns:**
    - User selects state → call `/api/v1/mrs/filter?state=Telangana`
    - User selects territory → call `/api/v1/mrs/filter?state=Telangana&territory=Hyderabad`
    - Show MR names with checkboxes for selection
    
    2. **MR Selection UI:**
    - Display MR names from response
    - Show checkboxes for multi-select
    - "Select All" / "Deselect All" buttons
    - Show count: "5 MRs selected"
    
    3. **Targeting Preview:**
    - Show who will receive: "Targeting: 5 MRs in Hyderabad"
    - List selected MR names
    
    **Note:** Only returns active MRs (is_active = true)
    """
    return await filter_mrs(
        zone=zone,
        state=state,
        territory=territory,
        current_user=current_user
    )


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
    - zone: Geographic zone (currently only "South" supported)
    - state: State (e.g., Telangana, Karnataka, Maharashtra)
    - territory: Sales territory/region
    
    **CSV Example:**
    ```csv
    name,email,phone,zone,state,territory
    Rajesh Kumar,rajesh@xyzpharma.com,9876543210,South,Telangana,Hyderabad
    Priya Sharma,priya@xyzpharma.com,9876543211,South,Karnataka,Bangalore North
    Amit Patel,amit@xyzpharma.com,9876543212,South,Maharashtra,Mumbai West
    ```
    
    **Validation Rules:**
    - Email must be valid format and unique in database
    - Phone must be exactly 10 digits and unique in database
    - Name, email, phone, zone, state, territory are required
    - Zone must be "South" (currently only South zone is supported)
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
    - "Zone is required"
    - "Currently only 'South' zone is supported"
    - "State is required"
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
    Get list of all Medical Representatives with their assigned doctors and drugs.
    
    **Access:** All authenticated users (Admin, Doctor, MR)
    
    **Purpose:** View all MRs in the system with complete details including assigned doctors and drugs
    
    **Flow:**
    1. User requests list of MRs
    2. Backend fetches all MR records
    3. Backend fetches doctor details (id + name) for each assigned doctor
    4. Backend fetches drug details (id + name) for each assigned drug
    5. Returns complete MR list with nested doctor and drug information
    
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
                "zone": "South",
                "state": "Telangana",
                "territory": "Hyderabad",
                "assigned_doctors": [
                    {
                        "id": "507f1f77bcf86cd799439012",
                        "name": "Dr. Sarah Sharma"
                    }
                ],
                "assigned_drugs": [
                    {
                        "id": "507f1f77bcf86cd799439021",
                        "name": "Amlovas 5mg"
                    },
                    {
                        "id": "507f1f77bcf86cd799439022",
                        "name": "Telma 40mg"
                    }
                ],
                "is_active": true,
                "created_at": "2024-03-30T10:00:00"
            }
        ]
    }
    ```
    
    **Note:** Response includes full details (id + name) for both assigned_doctors and assigned_drugs arrays
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
    Get detailed information of a specific Medical Representative.
    
    **Access:** All authenticated users (Admin, Doctor, MR)
    
    **Purpose:** View complete details of a single MR including assigned doctors and drugs
    
    **Flow:**
    1. User provides MR ID
    2. Backend validates MR ID format
    3. Backend fetches MR record
    4. Backend fetches doctor details for assigned_doctors
    5. Backend fetches drug details for assigned_drugs
    6. Returns complete MR information
    
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
        "zone": "South",
        "state": "Telangana",
        "territory": "Hyderabad",
        "assigned_doctors": [
            {
                "id": "507f1f77bcf86cd799439012",
                "name": "Dr. Sarah Sharma"
            }
        ],
        "assigned_drugs": [
            {
                "id": "507f1f77bcf86cd799439021",
                "name": "Amlovas 5mg"
            }
        ],
        "is_active": true,
        "created_at": "2024-03-30T10:00:00"
    }
    ```
    
    **Error Responses:**
    - 400: Invalid MR ID format
    - 404: MR not found
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
    
    **Purpose:** Modify MR details including phone, location, assigned doctors/drugs, or active status
    
    **Flow:**
    1. Admin provides MR ID and fields to update
    2. Backend validates MR exists
    3. Backend validates assigned doctors are not already assigned to another MR
    4. Backend updates only the provided fields
    5. Backend logs the activity
    6. Returns success message with list of updated fields
    
    **Request Body (all fields optional):**
    ```json
    {
        "name": "Rajesh Kumar Updated",
        "phone": "+919876543211",
        "zone": "South",
        "state": "Karnataka",
        "territory": "Bangalore North",
        "assigned_doctors": ["507f1f77bcf86cd799439012", "507f1f77bcf86cd799439013"],
        "assigned_drugs": ["507f1f77bcf86cd799439021", "507f1f77bcf86cd799439022", "507f1f77bcf86cd799439023"],
        "is_active": true
    }
    ```
    
    **Usage:**
    ```
    PUT /api/v1/mrs/507f1f77bcf86cd799439011
    Headers: Authorization: Bearer <admin_token>
    Content-Type: application/json
    ```
    
    **Response:**
    ```
    {
        "message": "MR updated successfully",
        "updated_fields": {
            "phone": "+919876543211",
            "zone": "South",
            "state": "Karnataka",
            "territory": "Bangalore North",
            "assigned_doctors": ["507f1f77bcf86cd799439012", "507f1f77bcf86cd799439013"],
            "assigned_drugs": ["507f1f77bcf86cd799439021", "507f1f77bcf86cd799439022", "507f1f77bcf86cd799439023"],
            "is_active": true
        }
    }
    ```
    
    **Notes:**
    - Only provided fields will be updated (partial update supported)
    - Email cannot be changed
    - assigned_doctors: Replaces entire list (not append)
    - assigned_drugs: Replaces entire list (not append)
    - Activity is logged for audit trail
    
    **Error Responses:**
    - 400: Invalid MR ID or doctor already assigned to another MR
    - 404: MR not found
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
    
    **Purpose:** Soft delete an MR account (mark as inactive without removing from database)
    
    **Flow:**
    1. Admin provides MR ID to deactivate
    2. Backend validates MR exists
    3. Backend sets is_active = false
    4. Backend logs deactivation activity
    5. MR can no longer login
    6. MR data remains in database for historical records
    
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
    
    **What Happens:**
    - MR account is marked as inactive (is_active = false)
    - MR cannot login anymore
    - MR data remains in database
    - Assigned doctors and drugs remain linked
    - Historical data (visits, activities) is preserved
    
    **To Reactivate:**
    ```
    PUT /api/v1/mrs/507f1f77bcf86cd799439011
    Content-Type: application/json
    
    {
        "is_active": true
    }
    ```
    
    **Note:** This is a soft delete, not a hard delete. Use this to temporarily disable an MR account.
    
    **Error Responses:**
    - 400: Invalid MR ID format
    - 404: MR not found
    """
    return await delete_mr(mr_id, current_user)
