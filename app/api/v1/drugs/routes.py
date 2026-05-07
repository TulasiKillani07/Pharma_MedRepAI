"""
Drug and Drug Field Template Management Endpoints
"""

from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, RedirectResponse
from typing import Dict, Any
from app.core.auth import require_admin, get_current_user
from app.api.v1.drugs.schemas import (
    TemplateCreate, TemplateUpdate, TemplateResponse,
    FieldDefinitionCreate, FieldDefinitionUpdate, FieldDefinitionResponse,
    DrugCreate, DrugUpdate, DrugResponse, DrugListResponse,
    BulkUploadResponse
)
from app.api.v1.drugs import service


router = APIRouter()


# ============ TEMPLATE ENDPOINTS ============

@router.post("/templates", response_model=TemplateResponse, dependencies=[Depends(require_admin)])
async def create_template_endpoint(template_data: TemplateCreate):
    """
    Create a new drug field template with default fixed fields.
    Only one template is allowed.
    Admin only.
    """
    return await service.create_template(template_data)


@router.get("/templates", response_model=TemplateResponse, dependencies=[Depends(require_admin)])
async def get_template_endpoint():
    """
    Get the active drug field template.
    Admin only.
    """
    return await service.get_template()


@router.put("/templates/{template_id}", response_model=TemplateResponse, dependencies=[Depends(require_admin)])
async def update_template_endpoint(template_id: str, template_data: TemplateUpdate):
    """
    Update template name and/or is_active status.
    To deactivate: {"is_active": false}
    To activate: {"is_active": true}
    Admin only.
    """
    return await service.update_template(template_id, template_data)


# ============ BULK UPLOAD ENDPOINTS ============

@router.get("/download-template", dependencies=[Depends(require_admin)])
async def download_template_endpoint():
    """
    Download CSV template with 12 fixed drug fields.
    
    **Access:** Admin only
    
    **Purpose:**
    Provides a CSV template file that users can fill with drug data and upload via bulk upload.
    
    **Template Columns:**
    1. drug_name (REQUIRED)
    2. symptoms (REQUIRED)
    3. brand_name (optional)
    4. drug_class (optional)
    5. manufacturer (optional)
    6. indications (optional)
    7. mechanism_of_action (optional)
    8. dosage_strength (optional)
    9. dosage_form (optional)
    10. route (optional)
    11. side_effects (optional)
    12. reference_url (optional)
    
    **Instructions for Users:**
    - Fill drug_name and symptoms (required fields)
    - Other fields are optional, can be left empty
    - You can ADD your own columns for custom data (e.g., price, expiry_date)
    - Custom columns will be auto-created as dynamic fields
    
    **Usage:**
    ```
    GET /api/v1/drugs/download-template
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Response:**
    Downloads file: drug_template.csv
    """
    return await service.download_drug_template()


@router.post("/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload_drugs_endpoint(
    file: UploadFile = File(..., description="CSV or Excel file with drug data"),
    current_user: Dict = Depends(require_admin)
):
    """
    Bulk upload drugs from CSV or Excel file with auto-creation of custom fields.
    
    **Access:** Admin only
    
    **Purpose:**
    Upload multiple drugs at once. Backend automatically creates dynamic fields for any custom columns.
    
    **Flow:**
    1. Download template via GET /api/v1/drugs/download-template
    2. Fill required fields (drug_name, symptoms)
    3. Optionally add custom columns (e.g., price, expiry_date, batch_number)
    4. Upload file via this endpoint
    5. Backend validates and creates drugs
    6. Custom columns are auto-added to template as dynamic fields
    
    **File Format:**
    - Supported: CSV (.csv), Excel (.xlsx, .xls)
    - Max file size: 5MB
    - Max rows: 100 drugs per upload
    
    **Required Columns:**
    - drug_name: Drug name (will be converted to lowercase)
    - symptoms: Comma-separated symptoms (e.g., "Fever, Headache")
    
    **Optional Fixed Columns:**
    - brand_name, drug_class, manufacturer, indications, mechanism_of_action
    - dosage_strength, dosage_form, route, side_effects, reference_url
    
    **Custom Columns:**
    - Add any additional columns you need (e.g., price, expiry_date)
    - Will be auto-created as dynamic fields in template
    - Type defaults to "text"
    
    **CSV Example (Fixed fields only):**
    ```csv
    drug_name,symptoms,brand_name,drug_class,manufacturer,dosage_form,reference_url
    paracetamol,"Fever, Headache",crocin,Analgesic,GSK,Tablet,https://www.drugs.com/paracetamol.html
    ibuprofen,"Pain, Fever",brufen,NSAID,Abbott,Tablet,https://www.drugs.com/ibuprofen.html
    ```
    
    **CSV Example (With custom fields):**
    ```csv
    drug_name,symptoms,brand_name,manufacturer,price,expiry_date,batch_number
    paracetamol,"Fever, Headache",crocin,GSK,50,2025-12-31,BATCH001
    ibuprofen,"Pain, Fever",brufen,Abbott,80,2026-06-30,BATCH002
    ```
    
    **Validation Rules:**
    - drug_name and symptoms are required (cannot be empty)
    - drug_name is converted to lowercase for storage and duplicate checking
    - Duplicate check: drug_name + brand_name combination must be unique
    - Checks duplicates within CSV and against database
    - Invalid rows are skipped, valid rows are inserted
    
    **Duplicate Detection:**
    - Compares: drug_name (lowercase) + brand_name (lowercase)
    - Checks within uploaded CSV
    - Checks against existing drugs in database
    - If duplicate found, row is skipped and reported in errors
    
    **Custom Field Auto-Creation:**
    - Any column not in fixed 10 fields is treated as custom
    - Backend auto-creates dynamic field in template
    - Field properties: type="text", is_fixed=false, required=false
    - If field already exists in template, uses existing field
    
    **Usage:**
    ```
    POST /api/v1/drugs/bulk-upload
    Headers: Authorization: Bearer <admin_token>
    Content-Type: multipart/form-data
    Body: file=@drugs.csv
    ```
    
    **Response (All Success):**
    ```json
    {
        "total_rows": 50,
        "successful": 50,
        "failed": 0,
        "custom_fields_added": ["price", "expiry_date", "batch_number"],
        "errors": [],
        "message": "Bulk upload completed successfully. All 50 drugs added. 3 custom fields added to template."
    }
    ```
    
    **Response (Partial Success):**
    ```json
    {
        "total_rows": 50,
        "successful": 45,
        "failed": 5,
        "custom_fields_added": ["price"],
        "errors": [
            {
                "row": 3,
                "drug_name": "",
                "error": "drug_name is required"
            },
            {
                "row": 7,
                "drug_name": "Paracetamol",
                "brand_name": "Crocin",
                "error": "Duplicate drug found in CSV (same drug_name and brand_name)"
            },
            {
                "row": 15,
                "drug_name": "Aspirin",
                "brand_name": "Disprin",
                "error": "Drug already exists in database (same drug_name and brand_name)"
            }
        ],
        "message": "Bulk upload completed. 45 drugs added successfully, 5 rows failed. 1 custom field added to template."
    }
    ```
    
    **Error Types:**
    - "drug_name is required"
    - "symptoms is required"
    - "Duplicate drug found in CSV (same drug_name and brand_name)"
    - "Drug already exists in database (same drug_name and brand_name)"
    
    **Notes:**
    - drug_name is stored in lowercase
    - brand_name is stored in lowercase (if provided)
    - Other fields keep original case
    - Custom fields can be managed later via field APIs
    - Template grows automatically based on CSV columns
    """
    return await service.bulk_upload_drugs(file, current_user)


# ============ FIELD ENDPOINTS ============

@router.post("/templates/{template_id}/fields", response_model=FieldDefinitionResponse, dependencies=[Depends(require_admin)])
async def add_field_endpoint(template_id: str, field_data: FieldDefinitionCreate):
    """
    Add a dynamic field to template.
    Admin only.
    """
    return await service.add_dynamic_field(template_id, field_data)


@router.put("/templates/{template_id}/fields/{field_id}", response_model=FieldDefinitionResponse, dependencies=[Depends(require_admin)])
async def update_field_endpoint(template_id: str, field_id: str, field_data: FieldDefinitionUpdate):
    """
    Update a field.
    - Both fixed and dynamic fields: Can update type, required, visible, order, options
    - Dynamic fields: Can also update is_active (to deactivate: {"is_active": false})
    - Fixed fields: Cannot set is_active to false
    - Key (field name) cannot be updated for any field
    Admin only.
    """
    return await service.update_field(template_id, field_id, field_data)


# ============ DRUG ENDPOINTS ============

@router.post("", response_model=DrugResponse)
async def create_drug_endpoint(drug_data: DrugCreate, current_user: Dict = Depends(require_admin)):
    """
    Create a new drug.
    Admin only.
    """
    return await service.create_drug(drug_data, current_user)


@router.get("", response_model=DrugListResponse)
async def get_drugs_endpoint(
    current_user: Dict = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str = Query(None, description="Full-text search across all fields"),
    drug_name: str = Query(None, description="Filter by drug name (partial match)"),
    manufacturer: str = Query(None, description="Filter by manufacturer (partial match)"),
    dosage_form: str = Query(None, description="Filter by dosage form (exact)"),
    symptom: str = Query(None, description="Filter by symptom (partial match)"),
    indication: str = Query(None, description="Filter by indication (partial match)")
):
    """
    Get all drugs with search and filters.
    
    **Access:** All authenticated users (Admin, Doctor, MR)
    
    **Behavior by Role:**
    - **Doctors/MRs:** See only active drugs (is_active: true)
    - **Admins:** See all drugs with is_active field (can filter in frontend)
    
    **Search Parameters:**
    - `search`: Full-text search across all fields (drug_name, brand_name, symptoms, indications, etc.)
    - `drug_name`: Filter by drug name (partial match)
    - `manufacturer`: Filter by manufacturer (partial match)
    - `dosage_form`: Filter by dosage form (exact: Tablet, Capsule, etc.)
    - `symptom`: Filter drugs that treat this symptom
    - `indication`: Filter drugs by indication
    
    **Examples:**
    - `GET /api/v1/drugs?search=fever` — drugs related to fever
    - `GET /api/v1/drugs?drug_name=para` — drugs with "para" in name
    - `GET /api/v1/drugs?symptom=headache` — drugs for headache
    - `GET /api/v1/drugs?dosage_form=Tablet&manufacturer=GSK` — tablets by GSK
    
    **Response:**
    - Doctors/MRs: Only active drugs
    - Admins: All drugs with is_active field for frontend filtering
    """
    # Get user role
    user_role = current_user.get("role", "")
    
    # Get all drugs
    result = await service.get_all_drugs(
        skip=skip,
        limit=limit,
        search=search,
        drug_name=drug_name,
        manufacturer=manufacturer,
        dosage_form=dosage_form,
        symptom=symptom,
        indication=indication
    )
    
    # Filter by role: Doctors and MRs see only active drugs
    if user_role not in ["ADMIN", "SUPER_ADMIN"]:
        result["drugs"] = [drug for drug in result["drugs"] if drug.get("is_active", True)]
        result["total"] = len(result["drugs"])
    
    return result


@router.get("/{drug_id}", response_model=DrugResponse)
async def get_drug_endpoint(
    drug_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get drug by ID.
    
    **Access:** All authenticated users (Admin, Doctor, MR)
    
    **Behavior by Role:**
    - **Doctors/MRs:** Can only view active drugs (404 if inactive)
    - **Admins:** Can view any drug (active or inactive)
    
    **Purpose:**
    View detailed information about a specific drug.
    
    **Usage:**
    ```
    GET /api/v1/drugs/drug123
    Headers: Authorization: Bearer <token>
    ```
    
    **Response:**
    ```json
    {
        "_id": "drug123",
        "template_id": "template456",
        "field_values": [
            {"field_id": "f1", "key": "drug_name", "value": "paracetamol"},
            {"field_id": "f2", "key": "brand_name", "value": "crocin"},
            {"field_id": "f3", "key": "drug_class", "value": "Analgesic"},
            {"field_id": "f4", "key": "manufacturer", "value": "GSK"},
            {"field_id": "f5", "key": "dosage_form", "value": "Tablet"}
        ],
        "created_at": "2024-04-07T10:00:00",
        "updated_at": "2024-04-07T10:00:00",
        "is_active": true,
        "has_brochure": true
    }
    ```
    
    **Use Cases:**
    - Doctor: Check drug information before prescribing
    - MR: Reference drug details during doctor visits
    - Admin: View and manage drug information (including inactive drugs)
    """
    # Get user role
    user_role = current_user.get("role", "")
    
    # Get drug
    drug = await service.get_drug_by_id(drug_id)
    
    # Check access: Doctors and MRs can only see active drugs
    if user_role not in ["ADMIN", "SUPER_ADMIN"]:
        if not drug.get("is_active", True):
            raise HTTPException(status_code=404, detail="Drug not found")
    
    return drug


@router.put("/{drug_id}", response_model=DrugResponse, dependencies=[Depends(require_admin)])
async def update_drug_endpoint(drug_id: str, drug_data: DrugUpdate):
    """
    Update a drug - can update field values and is_active status.
    
    **Access:** Admin only
    
    **Purpose:**
    Update drug information including field values and active status.
    
    **Request Body:**
    ```json
    {
        "field_values": [
            {"field_id": "f1", "key": "drug_name", "value": "paracetamol"},
            {"field_id": "f2", "key": "brand_name", "value": "crocin"}
        ],
        "is_active": true
    }
    ```
    
    **Fields:**
    - `field_values`: Array of field values to update (merges with existing)
    - `is_active`: Optional boolean to activate/deactivate drug
    
    **Examples:**
    
    1. **Update drug information:**
    ```json
    {
        "field_values": [
            {"field_id": "f1", "key": "drug_name", "value": "paracetamol"},
            {"field_id": "f2", "key": "brand_name", "value": "crocin updated"}
        ]
    }
    ```
    
    2. **Deactivate drug:**
    ```json
    {
        "field_values": [],
        "is_active": false
    }
    ```
    
    3. **Reactivate drug:**
    ```json
    {
        "field_values": [],
        "is_active": true
    }
    ```
    
    4. **Update info and deactivate:**
    ```json
    {
        "field_values": [
            {"field_id": "f1", "key": "drug_name", "value": "updated name"}
        ],
        "is_active": false
    }
    ```
    
    **Note:** 
    - Field values are merged (not replaced) - only provided fields are updated
    - Can update inactive drugs (to reactivate them)
    - Setting `is_active: false` soft-deletes the drug
    - Setting `is_active: true` restores a deleted drug
    """
    return await service.update_drug(drug_id, drug_data)


@router.delete("/{drug_id}", dependencies=[Depends(require_admin)])
async def delete_drug_endpoint(drug_id: str):
    """
    Soft delete a drug (deactivate).
    
    **Access:** Admin only
    
    **Purpose:**
    Deactivate a drug instead of permanently deleting it. Drug remains in database but is hidden from listings.
    
    **Flow:**
    1. Admin requests to delete drug
    2. Backend sets is_active=false
    3. Drug no longer appears in GET /drugs list
    4. Drug data is preserved in database
    
    **Usage:**
    ```
    DELETE /api/v1/drugs/drug123
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Response:**
    ```json
    {
        "message": "Drug deleted successfully"
    }
    ```
    
    **Note:** This is a soft delete:
    - Drug is marked as inactive (is_active=false)
    - Drug data remains in database
    - Drug won't appear in drug listings
    - Can be reactivated by admin via PUT endpoint with is_active=true
    
    **To reactivate:**
    ```
    PUT /api/v1/drugs/drug123
    {
        "field_values": [...],  // Keep existing values
        // Backend can add is_active field to update schema if needed
    }
    ```
    
    **Use Cases:**
    - Drug discontinued by manufacturer
    - Drug temporarily out of stock
    - Drug no longer promoted by company
    """
    return await service.delete_drug(drug_id)


# ============ DRUG BROCHURE ENDPOINTS ============

@router.post("/{drug_id}/brochure")
async def upload_drug_brochure_endpoint(
    drug_id: str,
    file: UploadFile = File(..., description="PDF brochure file (max 10MB)"),
    current_user: Dict = Depends(require_admin)
):
    """
    Upload PDF brochure for a drug.
    
    **Access:** Admin only
    
    **Purpose:**
    Upload drug information brochure (PDF) to Cloudinary and link it to the drug.
    
    **Flow:**
    1. Admin uploads PDF file
    2. Backend validates file (PDF only, max 10MB)
    3. Uploads to Cloudinary (organized by drug_id)
    4. Saves brochure URL in drug document
    5. Returns brochure URL
    
    **File Requirements:**
    - Format: PDF only
    - Max size: 10MB
    - Overwrites existing brochure if present
    
    **Usage:**
    ```
    POST /api/v1/drugs/drug123/brochure
    Headers: 
      Authorization: Bearer <admin_token>
      Content-Type: multipart/form-data
    Body: 
      file: paracetamol_brochure.pdf
    ```
    
    **Response:**
    ```json
    {
        "drug_id": "drug123",
        "drug_name": "Paracetamol",
        "brochure_url": "https://res.cloudinary.com/dlfevdb7o/raw/upload/v1234/drugs/drug123/brochure.pdf",
        "brochure_size_kb": 245.6,
        "message": "Brochure uploaded successfully"
    }
    ```
    
    **Use Cases:**
    - Upload product information leaflet
    - Add prescribing information
    - Provide detailed drug specifications
    - Share marketing materials with MRs
    
    **Notes:**
    - Uploading a new brochure replaces the old one
    - Brochure URL is accessible to all authenticated users
    - MRs can share brochure link with doctors
    """
    return await service.upload_drug_brochure(drug_id, file, current_user)


@router.get("/{drug_id}/brochure/download")
async def download_drug_brochure_endpoint(
    drug_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Download drug brochure PDF file with proper headers.
    
    **Access:** All authenticated users (Admin, Doctor, MR)
    
    **Purpose:**
    Stream the drug brochure PDF with proper Content-Disposition headers to force download.
    
    **Flow:**
    1. User requests brochure download
    2. Backend fetches brochure from Cloudinary
    3. Streams PDF with proper download headers
    4. Browser downloads the PDF file with correct filename
    
    **Usage:**
    ```
    GET /api/v1/drugs/drug123/brochure/download
    Headers: Authorization: Bearer <token>
    ```
    
    **Response:**
    Streams PDF file with Content-Disposition: attachment header
    
    **Use Cases:**
    - Doctor downloads brochure to review drug information
    - MR downloads brochure to share with doctors
    - Admin downloads brochure to verify uploaded content
    """
    return await service.download_drug_brochure(drug_id)


@router.delete("/{drug_id}/brochure", dependencies=[Depends(require_admin)])
async def delete_drug_brochure_endpoint(drug_id: str):
    """
    Delete drug brochure.
    
    **Access:** Admin only
    
    **Purpose:**
    Remove brochure PDF from Cloudinary and drug document.
    
    **Flow:**
    1. Admin requests brochure deletion
    2. Backend deletes file from Cloudinary
    3. Removes brochure URL from drug document
    4. Returns success message
    
    **Usage:**
    ```
    DELETE /api/v1/drugs/drug123/brochure
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Response:**
    ```json
    {
        "message": "Brochure deleted successfully"
    }
    ```
    
    **Use Cases:**
    - Remove outdated brochure
    - Delete incorrect file
    - Clear brochure before uploading new version
    """
    return await service.delete_drug_brochure(drug_id)
