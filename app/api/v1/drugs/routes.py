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
    
    **Access:** Admin only
    
    **Response includes three sections:**
    
    **1. `fields[]`** — All field definitions (fixed + dynamic) with `field_id`, `key`, `type`, `required`, `options`
    
    **2. `packaging_metadata`** — Valid `sales_unit` + `measurement_unit` options per `dosage_form`:
    ```json
    [
      { "dosage_form": "Tablet", "sales_units": ["Strip", "Bottle", "Blister Pack"], "measurement_units": ["Tablet"] },
      { "dosage_form": "Syrup", "sales_units": ["Bottle"], "measurement_units": ["ml"] },
      { "dosage_form": "Injection", "sales_units": ["Vial", "Ampoule", "Prefilled Syringe"], "measurement_units": ["ml", "mg", "g"] }
    ]
    ```
    
    **3. `packaging_schema`** — Fixed schema of the packaging object (fields, types, required, descriptions):
    ```json
    {
      "is_fixed": true,
      "fields": {
        "sales_unit": { "type": "text", "required": true, "description": "..." },
        "pack_quantity": { "type": "number", "required": true, "description": "..." },
        "selling_price": { "type": "number", "required": true, "description": "..." },
        "max_discount_percent": { "type": "number", "required": true, "description": "..." },
        "box_pricing_mode": { "type": "select", "required": false, "options": ["auto", "discount", "manual"], "description": "..." }
      }
    }
    ```
    
    **Frontend flow:**
    1. Call this endpoint once when the Add Drug page opens
    2. Render `fields[]` as the main drug form
    3. Render the packaging section using `packaging_schema`
    4. When admin selects `dosage_form`, look up `packaging_metadata[dosage_form]` to filter valid `sales_unit` + `measurement_unit` options
    
    **Auto-migration:** New fixed fields are auto-added to existing templates on first call.
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
    - Add any additional columns you need (e.g., expiry_date, batch_number)
    - Will be auto-created as dynamic fields in template
    - Type defaults to "text"
    
    **CSV Example (Fixed fields only):**
    ```csv
    drug_name,symptoms,brand_name,drug_class,manufacturer,dosage_form
    amlodipine,"Hypertension,Chest Pain",Amlovas,Calcium Channel Blocker,Macleods Pharma,Tablet
    metformin,"Diabetes,Fatigue",Glycomet,Biguanide,USV Limited,Tablet
    ```
    
    **CSV Example (With custom fields):**
    ```csv
    drug_name,symptoms,brand_name,manufacturer,dosage_form,batch_number,expiry_date
    amlodipine,"Hypertension,Chest Pain",Amlovas,Macleods Pharma,Tablet,BATCH001,2025-12-31
    metformin,"Diabetes,Fatigue",Glycomet,USV Limited,Tablet,BATCH002,2026-06-30
    ```
    
    **Note:** Packaging and pricing are configured separately when creating drugs via `POST /drugs`. CSV bulk upload handles basic drug info fields only.
    
    **Important:** Multi-value fields (symptoms, indications, side_effects) must be wrapped in double quotes if they contain commas.
    
    **Important:** Multi-value fields (symptoms, indications, side_effects) must be wrapped in double quotes if they contain commas.
    
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
    Add a field to the template.
    
    **Access:** Admin only
    
    **Request:**
    ```json
    {
        "key": "batch_number",
        "type": "text",
        "required": false,
        "visible": true,
        "order": 20,
        "is_fixed": false
    }
    ```
    
    **Field Types:** text, textarea, number, select, boolean, date, array
    
    **Notes:**
    - `is_fixed: true` → field cannot be deactivated later
    - `is_fixed: false` (default) → field can be deactivated
    - `key` must be unique within the template
    - For `select` type, provide `options: ["Option1", "Option2"]`
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
    
    **Access:** Admin only
    
    **Request Body:**
    ```json
    {
        "field_values": [
            {"field_id": "uuid", "key": "drug_name", "value": "Paracetamol 650"},
            {"field_id": "uuid", "key": "symptoms", "value": ["Fever", "Headache"]},
            {"field_id": "uuid", "key": "dosage_form", "value": "Tablet"},
            {"field_id": "uuid", "key": "manufacturer", "value": "GSK"}
        ],
        "packaging": {
            "sales_unit": "Strip",
            "pack_quantity": 10,
            "measurement_unit": "Tablet",
            "selling_price": 80,
            "mrp": 100,
            "max_discount_percent": 10,
            "sales_units_per_box": 20,
            "box_pricing_mode": "discount",
            "box_discount_percent": 10,
            "box_price": 1440
        }
    }
    ```
    
    **Required field_values:** `drug_name`, `symptoms`, `dosage_form`
    
    **`packaging` is required** — flat object with fixed schema (see `GET /drugs/templates` → `packaging_schema`).
    
    **Valid `sales_unit` + `measurement_unit` per `dosage_form`** — see `GET /drugs/templates` → `packaging_metadata`.
    
    **`box_pricing_mode`:**
    - `auto` — box_price = selling_price × sales_units_per_box
    - `discount` — apply box_discount_percent to auto price
    - `manual` — set box_price directly
    
    **Get `field_id` values from `GET /drugs/templates`**
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
    - **Doctors/MRs:** See only active drugs
    - **Admins:** See all drugs including inactive
    
    **Search Parameters:**
    - `search`: Full-text search across all fields
    - `drug_name`: Partial match on drug name
    - `manufacturer`: Partial match on manufacturer
    - `dosage_form`: Exact match (Tablet, Capsule, Syrup, etc.)
    - `symptom`: Partial match in symptoms array
    - `indication`: Partial match in indications array
    
    **Response includes `packaging` object:**
    ```json
    {
      "drugs": [
        {
          "_id": "...",
          "field_values": [
            {"field_id": "...", "key": "drug_name", "value": "amlodipine", "type": "text"},
            {"field_id": "...", "key": "symptoms", "value": ["Hypertension"], "type": "array"}
          ],
          "packaging": {
            "sales_unit": "Strip",
            "pack_quantity": 10,
            "measurement_unit": "Tablet",
            "sales_units_per_box": 20,
            "pricing": {
              "selling_price": 80,
              "mrp": 100,
              "box_pricing": {"mode": "auto", "box_price": 1600}
            }
          },
          "is_active": true,
          "has_brochure": false
        }
      ],
      "total": 1
    }
    ```
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
    
    **Response:**
    ```json
    {
        "_id": "drug123",
        "template_id": "template456",
        "field_values": [
            {"field_id": "f1", "key": "drug_name", "value": "amlodipine", "type": "text"},
            {"field_id": "f2", "key": "brand_name", "value": "amlovas", "type": "text"},
            {"field_id": "f3", "key": "symptoms", "value": ["Hypertension", "Chest Pain"], "type": "array"},
            {"field_id": "f4", "key": "manufacturer", "value": "Macleods Pharma", "type": "text"},
            {"field_id": "f5", "key": "dosage_form", "value": "Tablet", "type": "select"}
        ],
        "packaging": {
            "sales_unit": "Strip",
            "pack_quantity": 10,
            "measurement_unit": "Tablet",
            "sales_units_per_box": 20,
            "pricing": {
                "selling_price": 80,
                "mrp": 100,
                "box_pricing": {"mode": "auto", "box_price": 1600}
            }
        },
        "is_active": true,
        "has_brochure": false,
        "created_at": "2026-06-29T06:30:00",
        "updated_at": "2026-06-29T06:30:00"
    }
    ```
    
    **Note:** Each field_value includes `type` from the template (text, number, array, textarea, select, boolean, date).
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
    Update a drug — merges field values and can update packaging/pricing and is_active status.
    
    **Access:** Admin only
    
    **Request Body:**
    ```json
    {
        "field_values": [
            {"field_id": "f1", "key": "dosage_strength", "value": "10mg"}
        ],
        "packaging": {
            "sales_unit": "Strip",
            "pack_quantity": 10,
            "measurement_unit": "Tablet",
            "sales_units_per_box": 20,
            "pricing": {
                "selling_price": 90,
                "mrp": 110,
                "box_pricing": {"mode": "discount", "discount_percent": 10, "box_price": 1620}
            }
        },
        "is_active": true
    }
    ```
    
    **Behavior:**
    - `field_values` are **merged** — only sent fields are updated, others kept
    - `packaging` is fully replaced if provided, otherwise kept as-is
    - `is_active: false` → soft delete; `is_active: true` → reactivate
    
    **Response:** Updated drug with all field_values + packaging.
    """
    return await service.update_drug(drug_id, drug_data)


@router.delete("/{drug_id}")
async def delete_drug_endpoint(drug_id: str, current_user: Dict = Depends(require_admin)):
    """
    Soft delete a drug (deactivate).
    
    **Access:** Admin only
    
    **What happens:**
    - Drug is marked as `is_active: false`
    - Drug won't appear in listings for Doctors/MRs
    - Data preserved in database
    - Can be reactivated via PUT with `is_active: true`
    
    **Response:**
    ```json
    { "message": "Drug deleted successfully" }
    ```
    """
    return await service.delete_drug(drug_id, current_user)


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
