"""
Drug and Drug Field Template Management Endpoints
"""

from fastapi import APIRouter, Depends, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Dict, Any
from app.core.auth import require_admin
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
    Download CSV template with 10 fixed drug fields.
    
    **Access:** Admin only
    
    **Purpose:**
    Provides a CSV template file that users can fill with drug data and upload via bulk upload.
    
    **Template Columns:**
    1. drug_name (REQUIRED)
    2. brand_name (REQUIRED)
    3. drug_class (optional)
    4. manufacturer (optional)
    5. indications (optional)
    6. mechanism_of_action (optional)
    7. dosage_strength (optional)
    8. dosage_form (optional)
    9. route (optional)
    10. side_effects (optional)
    
    **Instructions for Users:**
    - Fill drug_name and brand_name (required fields)
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


@router.post("/bulk-upload", response_model=BulkUploadResponse, dependencies=[Depends(require_admin)])
async def bulk_upload_drugs_endpoint(
    file: UploadFile = File(..., description="CSV or Excel file with drug data")
):
    """
    Bulk upload drugs from CSV or Excel file with auto-creation of custom fields.
    
    **Access:** Admin only
    
    **Purpose:**
    Upload multiple drugs at once. Backend automatically creates dynamic fields for any custom columns.
    
    **Flow:**
    1. Download template via GET /api/v1/drugs/download-template
    2. Fill required fields (drug_name, brand_name)
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
    - brand_name: Brand name (will be converted to lowercase)
    
    **Optional Fixed Columns:**
    - drug_class, manufacturer, indications, mechanism_of_action
    - dosage_strength, dosage_form, route, side_effects
    
    **Custom Columns:**
    - Add any additional columns you need (e.g., price, expiry_date)
    - Will be auto-created as dynamic fields in template
    - Type defaults to "text"
    
    **CSV Example (Fixed fields only):**
    ```csv
    drug_name,brand_name,drug_class,manufacturer,dosage_form
    Paracetamol,Crocin,Analgesic,GSK,Tablet
    Ibuprofen,Brufen,NSAID,Abbott,Tablet
    ```
    
    **CSV Example (With custom fields):**
    ```csv
    drug_name,brand_name,manufacturer,price,expiry_date,batch_number
    Paracetamol,Crocin,GSK,50,2025-12-31,BATCH001
    Ibuprofen,Brufen,Abbott,80,2026-06-30,BATCH002
    ```
    
    **Validation Rules:**
    - drug_name and brand_name are required (cannot be empty)
    - Both are converted to lowercase for storage and duplicate checking
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
    - "brand_name is required"
    - "Duplicate drug found in CSV (same drug_name and brand_name)"
    - "Drug already exists in database (same drug_name and brand_name)"
    
    **Notes:**
    - drug_name and brand_name are stored in lowercase
    - Other fields keep original case
    - Custom fields can be managed later via field APIs
    - Template grows automatically based on CSV columns
    """
    return await service.bulk_upload_drugs(file)


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

@router.post("", response_model=DrugResponse, dependencies=[Depends(require_admin)])
async def create_drug_endpoint(drug_data: DrugCreate):
    """
    Create a new drug.
    Admin only.
    """
    return await service.create_drug(drug_data)


@router.get("", response_model=DrugListResponse, dependencies=[Depends(require_admin)])
async def get_drugs_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Get all active drugs with pagination.
    Admin only.
    """
    return await service.get_all_drugs(skip, limit)


@router.get("/{drug_id}", response_model=DrugResponse, dependencies=[Depends(require_admin)])
async def get_drug_endpoint(drug_id: str):
    """
    Get drug by ID.
    Admin only.
    """
    return await service.get_drug_by_id(drug_id)


@router.put("/{drug_id}", response_model=DrugResponse, dependencies=[Depends(require_admin)])
async def update_drug_endpoint(drug_id: str, drug_data: DrugUpdate):
    """
    Update a drug.
    Admin only.
    """
    return await service.update_drug(drug_id, drug_data)


@router.delete("/{drug_id}", dependencies=[Depends(require_admin)])
async def delete_drug_endpoint(drug_id: str):
    """
    Soft delete a drug.
    Admin only.
    """
    return await service.delete_drug(drug_id)
