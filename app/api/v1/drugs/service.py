"""
Drug and Drug Field Template Business Logic
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from bson import ObjectId
import pandas as pd
from io import BytesIO, StringIO
from app.database import get_database
from app.api.v1.drugs.schemas import (
    TemplateCreate, TemplateUpdate, FieldDefinitionCreate, FieldDefinitionUpdate,
    DrugCreate, DrugUpdate
)
import uuid


# ============ HELPER FUNCTIONS ============

def get_default_fixed_fields() -> List[Dict[str, Any]]:
    """Returns the 10 default fixed fields for drug template"""
    return [
        {
            "field_id": str(uuid.uuid4()),
            "key": "drug_name",
            "type": "text",
            "is_fixed": True,
            "required": True,
            "visible": True,
            "order": 1,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "brand_name",
            "type": "text",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 2,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "drug_class",
            "type": "text",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 3,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "manufacturer",
            "type": "text",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 4,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "indications",
            "type": "textarea",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 5,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "mechanism_of_action",
            "type": "textarea",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 6,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "dosage_strength",
            "type": "text",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 7,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "dosage_form",
            "type": "select",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 8,
            "options": ["Tablet", "Capsule", "Syrup", "Injection", "Cream", "Ointment", "Drops", "Inhaler"],
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "route",
            "type": "select",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 9,
            "options": ["Oral", "Intravenous", "Intramuscular", "Subcutaneous", "Topical", "Inhalation"],
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "side_effects",
            "type": "textarea",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 10,
            "options": None,
            "is_active": True
        }
    ]


# ============ TEMPLATE SERVICES ============

async def create_template(template_data: TemplateCreate) -> Dict[str, Any]:
    """Create a new drug field template with default fixed fields"""
    db = get_database()
    
    # Check if template already exists
    existing = await db["drug_field_templates"].find_one({"is_active": True})
    if existing:
        raise HTTPException(status_code=400, detail="Template already exists. Only one template is allowed.")
    
    template_doc = {
        "template_name": template_data.template_name,
        "fields": get_default_fixed_fields(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "is_active": True
    }
    
    result = await db["drug_field_templates"].insert_one(template_doc)
    template_doc["_id"] = str(result.inserted_id)
    
    return template_doc


async def get_template() -> Optional[Dict[str, Any]]:
    """Get the active template"""
    db = get_database()
    template = await db["drug_field_templates"].find_one({"is_active": True})
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Add is_active to fields if missing (for backward compatibility)
    for field in template.get("fields", []):
        if "is_active" not in field:
            field["is_active"] = True
    
    template["_id"] = str(template["_id"])
    return template


async def update_template(template_id: str, template_data: TemplateUpdate) -> Dict[str, Any]:
    """Update template name and/or is_active status"""
    db = get_database()
    
    if not ObjectId.is_valid(template_id):
        raise HTTPException(status_code=400, detail="Invalid template ID")
    
    update_data = {"updated_at": datetime.utcnow()}
    if template_data.template_name is not None:
        update_data["template_name"] = template_data.template_name
    if template_data.is_active is not None:
        update_data["is_active"] = template_data.is_active
    
    result = await db["drug_field_templates"].update_one(
        {"_id": ObjectId(template_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return await get_template()


# ============ FIELD SERVICES ============

async def add_dynamic_field(template_id: str, field_data: FieldDefinitionCreate) -> Dict[str, Any]:
    """Add a dynamic field to template"""
    db = get_database()
    
    if not ObjectId.is_valid(template_id):
        raise HTTPException(status_code=400, detail="Invalid template ID")
    
    # Get template
    template = await db["drug_field_templates"].find_one(
        {"_id": ObjectId(template_id), "is_active": True}
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Check if key already exists (including inactive fields)
    existing_keys = [f["key"] for f in template["fields"]]
    if field_data.key in existing_keys:
        raise HTTPException(status_code=400, detail=f"Field with key '{field_data.key}' already exists")
    
    # Create new field
    new_field = {
        "field_id": str(uuid.uuid4()),
        "key": field_data.key,
        "type": field_data.type,
        "is_fixed": False,  # Always false for user-created fields
        "required": field_data.required,
        "visible": field_data.visible,
        "order": field_data.order,
        "options": field_data.options,
        "is_active": True  # New fields are active by default
    }
    
    # Add field to template
    await db["drug_field_templates"].update_one(
        {"_id": ObjectId(template_id)},
        {
            "$push": {"fields": new_field},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    return new_field


async def update_field(template_id: str, field_id: str, field_data: FieldDefinitionUpdate) -> Dict[str, Any]:
    """Update a field (respects is_fixed rules)"""
    db = get_database()
    
    if not ObjectId.is_valid(template_id):
        raise HTTPException(status_code=400, detail="Invalid template ID")
    
    # Get template
    template = await db["drug_field_templates"].find_one(
        {"_id": ObjectId(template_id), "is_active": True}
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Find field
    field_index = None
    field = None
    for idx, f in enumerate(template["fields"]):
        if f["field_id"] == field_id:
            field_index = idx
            field = f
            break
    
    if field is None:
        raise HTTPException(status_code=404, detail="Field not found")
    
    # Add is_active if missing (for backward compatibility)
    if "is_active" not in field:
        field["is_active"] = True
    
    # Check if trying to deactivate a fixed field
    if field.get("is_fixed", False) and field_data.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate fixed field")
    
    # Note: key cannot be updated for any field (fixed or dynamic)
    # All other properties can be updated
    
    # Apply updates
    update_dict = field_data.dict(exclude_unset=True)
    for key, value in update_dict.items():
        field[key] = value
    
    # Update in database
    template["fields"][field_index] = field
    await db["drug_field_templates"].update_one(
        {"_id": ObjectId(template_id)},
        {
            "$set": {
                "fields": template["fields"],
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return field


# ============ DRUG SERVICES ============

async def create_drug(drug_data: DrugCreate) -> Dict[str, Any]:
    """Create a new drug"""
    db = get_database()
    
    # Validate template exists
    if not ObjectId.is_valid(drug_data.template_id):
        raise HTTPException(status_code=400, detail="Invalid template ID")
    
    template = await db["drug_field_templates"].find_one(
        {"_id": ObjectId(drug_data.template_id), "is_active": True}
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Validate field_ids and keys match template
    template_fields = {f["field_id"]: f for f in template["fields"]}
    
    for fv in drug_data.field_values:
        if fv.field_id not in template_fields:
            raise HTTPException(status_code=400, detail=f"Invalid field_id: {fv.field_id}")
        
        if fv.key != template_fields[fv.field_id]["key"]:
            raise HTTPException(status_code=400, detail=f"Key mismatch for field_id: {fv.field_id}")
    
    # Check required fields
    required_field_ids = [f["field_id"] for f in template["fields"] if f["required"]]
    provided_field_ids = [fv.field_id for fv in drug_data.field_values]
    
    missing_required = set(required_field_ids) - set(provided_field_ids)
    if missing_required:
        missing_keys = [template_fields[fid]["key"] for fid in missing_required]
        raise HTTPException(status_code=400, detail=f"Missing required fields: {', '.join(missing_keys)}")
    
    drug_doc = {
        "template_id": drug_data.template_id,
        "field_values": [fv.dict() for fv in drug_data.field_values],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "is_active": True
    }
    
    result = await db["drugs"].insert_one(drug_doc)
    drug_doc["_id"] = str(result.inserted_id)
    
    return drug_doc


async def get_all_drugs(skip: int = 0, limit: int = 100) -> Dict[str, Any]:
    """Get all active drugs"""
    db = get_database()
    
    cursor = db["drugs"].find({"is_active": True}).skip(skip).limit(limit)
    drugs = await cursor.to_list(length=limit)
    
    for drug in drugs:
        drug["_id"] = str(drug["_id"])
    
    total = await db["drugs"].count_documents({"is_active": True})
    
    return {"drugs": drugs, "total": total}


async def get_drug_by_id(drug_id: str) -> Dict[str, Any]:
    """Get drug by ID"""
    db = get_database()
    
    if not ObjectId.is_valid(drug_id):
        raise HTTPException(status_code=400, detail="Invalid drug ID")
    
    drug = await db["drugs"].find_one({"_id": ObjectId(drug_id), "is_active": True})
    
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
    
    drug["_id"] = str(drug["_id"])
    return drug


async def update_drug(drug_id: str, drug_data: DrugUpdate) -> Dict[str, Any]:
    """Update a drug"""
    db = get_database()
    
    if not ObjectId.is_valid(drug_id):
        raise HTTPException(status_code=400, detail="Invalid drug ID")
    
    # Get existing drug
    drug = await db["drugs"].find_one({"_id": ObjectId(drug_id), "is_active": True})
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
    
    # Validate against template
    template = await db["drug_field_templates"].find_one(
        {"_id": ObjectId(drug["template_id"]), "is_active": True}
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template_fields = {f["field_id"]: f for f in template["fields"]}
    
    for fv in drug_data.field_values:
        if fv.field_id not in template_fields:
            raise HTTPException(status_code=400, detail=f"Invalid field_id: {fv.field_id}")
        
        if fv.key != template_fields[fv.field_id]["key"]:
            raise HTTPException(status_code=400, detail=f"Key mismatch for field_id: {fv.field_id}")
    
    # Update drug
    result = await db["drugs"].update_one(
        {"_id": ObjectId(drug_id)},
        {
            "$set": {
                "field_values": [fv.dict() for fv in drug_data.field_values],
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Drug not found")
    
    return await get_drug_by_id(drug_id)


async def delete_drug(drug_id: str) -> Dict[str, str]:
    """Soft delete a drug"""
    db = get_database()
    
    if not ObjectId.is_valid(drug_id):
        raise HTTPException(status_code=400, detail="Invalid drug ID")
    
    result = await db["drugs"].update_one(
        {"_id": ObjectId(drug_id)},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Drug not found")
    
    return {"message": "Drug deleted successfully"}



# ============ BULK UPLOAD SERVICES ============

async def download_drug_template() -> StreamingResponse:
    """Generate and download CSV template with 10 fixed fields"""
    
    # Define the 10 fixed field columns
    columns = [
        "drug_name",
        "brand_name",
        "drug_class",
        "manufacturer",
        "indications",
        "mechanism_of_action",
        "dosage_strength",
        "dosage_form",
        "route",
        "side_effects"
    ]
    
    # Create empty DataFrame with these columns
    df = pd.DataFrame(columns=columns)
    
    # Convert to CSV
    output = StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    # Return as downloadable file
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=drug_template.csv"}
    )


async def bulk_upload_drugs(file: UploadFile) -> Dict[str, Any]:
    """
    Bulk upload drugs from CSV or Excel file.
    Auto-creates dynamic fields for custom columns.
    """
    db = get_database()
    
    # Validate file type
    filename = file.filename.lower()
    if not (filename.endswith('.csv') or filename.endswith('.xlsx') or filename.endswith('.xls')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only CSV and Excel (.xlsx, .xls) files are supported."
        )
    
    # Read file content
    try:
        content = await file.read()
        
        # Check file size (max 5MB)
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File size exceeds 5MB limit")
        
        # Parse file based on type
        if filename.endswith('.csv'):
            df = pd.read_csv(BytesIO(content))
        else:
            df = pd.read_excel(BytesIO(content))
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")
    
    # Define fixed field keys
    fixed_fields = [
        "drug_name", "brand_name", "drug_class", "manufacturer", "indications",
        "mechanism_of_action", "dosage_strength", "dosage_form", "route", "side_effects"
    ]
    
    # Validate required columns
    required_columns = ["drug_name", "brand_name"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(missing_columns)}"
        )
    
    # Check max rows limit (100)
    if len(df) > 100:
        raise HTTPException(
            status_code=400,
            detail=f"File contains {len(df)} rows. Maximum allowed is 100 rows per upload."
        )
    
    # Get or create template
    template = await db["drug_field_templates"].find_one({"is_active": True})
    
    if not template:
        # Create template with fixed fields
        template_doc = {
            "template_name": "Default Drug Template",
            "fields": get_default_fixed_fields(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True
        }
        result = await db["drug_field_templates"].insert_one(template_doc)
        template = await db["drug_field_templates"].find_one({"_id": result.inserted_id})
    
    template_id = str(template["_id"])
    
    # Identify custom columns (columns not in fixed fields)
    csv_columns = df.columns.tolist()
    custom_columns = [col for col in csv_columns if col not in fixed_fields]
    
    # Auto-create dynamic fields for custom columns
    custom_fields_added = []
    template_field_map = {f["key"]: f for f in template["fields"]}
    
    for custom_col in custom_columns:
        # Skip if field already exists
        if custom_col in template_field_map:
            continue
        
        # Create new dynamic field
        new_field = {
            "field_id": str(uuid.uuid4()),
            "key": custom_col,
            "type": "text",  # Default to text
            "is_fixed": False,
            "required": False,
            "visible": True,
            "order": len(template["fields"]) + 1,
            "options": None,
            "is_active": True
        }
        
        # Add to template
        await db["drug_field_templates"].update_one(
            {"_id": template["_id"]},
            {
                "$push": {"fields": new_field},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        template["fields"].append(new_field)
        template_field_map[custom_col] = new_field
        custom_fields_added.append(custom_col)
    
    # Initialize counters
    total_rows = len(df)
    successful = 0
    failed = 0
    errors = []
    
    # Track duplicates within CSV
    seen_drugs = set()
    
    # Process each row
    for index, row in df.iterrows():
        row_number = index + 2  # +2 for header and 0-index
        row_errors = []
        
        # Extract and clean required fields
        drug_name = str(row.get('drug_name', '')).strip() if pd.notna(row.get('drug_name')) else ''
        brand_name = str(row.get('brand_name', '')).strip() if pd.notna(row.get('brand_name')) else ''
        
        # Validate required fields
        if not drug_name:
            row_errors.append("drug_name is required")
        
        if not brand_name:
            row_errors.append("brand_name is required")
        
        if row_errors:
            failed += 1
            errors.append({
                "row": row_number,
                "drug_name": drug_name if drug_name else None,
                "brand_name": brand_name if brand_name else None,
                "error": "; ".join(row_errors)
            })
            continue
        
        # Convert to lowercase for duplicate checking
        drug_name_lower = drug_name.lower()
        brand_name_lower = brand_name.lower()
        
        # Check duplicate within CSV
        drug_key = (drug_name_lower, brand_name_lower)
        if drug_key in seen_drugs:
            failed += 1
            errors.append({
                "row": row_number,
                "drug_name": drug_name,
                "brand_name": brand_name,
                "error": "Duplicate drug found in CSV (same drug_name and brand_name)"
            })
            continue
        
        # Check duplicate in database
        existing_drug = await db["drugs"].find_one({
            "is_active": True,
            "field_values": {
                "$all": [
                    {"$elemMatch": {"key": "drug_name", "value": drug_name_lower}},
                    {"$elemMatch": {"key": "brand_name", "value": brand_name_lower}}
                ]
            }
        })
        
        if existing_drug:
            failed += 1
            errors.append({
                "row": row_number,
                "drug_name": drug_name,
                "brand_name": brand_name,
                "error": "Drug already exists in database (same drug_name and brand_name)"
            })
            continue
        
        # Mark as seen
        seen_drugs.add(drug_key)
        
        # Build field_values for all columns
        field_values = []
        
        for col in csv_columns:
            if col not in template_field_map:
                continue
            
            field_def = template_field_map[col]
            value = row.get(col)
            
            # Handle empty values
            if pd.isna(value) or value == '':
                value = None
            else:
                value = str(value).strip()
            
            # Convert drug_name and brand_name to lowercase
            if col == "drug_name":
                value = drug_name_lower
            elif col == "brand_name":
                value = brand_name_lower
            
            field_values.append({
                "field_id": field_def["field_id"],
                "key": col,
                "value": value
            })
        
        # Create drug document
        try:
            drug_doc = {
                "template_id": template_id,
                "field_values": field_values,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "is_active": True
            }
            
            await db["drugs"].insert_one(drug_doc)
            successful += 1
        
        except Exception as e:
            failed += 1
            errors.append({
                "row": row_number,
                "drug_name": drug_name,
                "brand_name": brand_name,
                "error": f"Database error: {str(e)}"
            })
    
    # Prepare response message
    if failed == 0:
        message = f"Bulk upload completed successfully. All {successful} drugs added."
    elif successful == 0:
        message = f"Bulk upload failed. All {failed} rows had errors."
    else:
        message = f"Bulk upload completed. {successful} drugs added successfully, {failed} rows failed."
    
    if custom_fields_added:
        message += f" {len(custom_fields_added)} custom fields added to template."
    
    return {
        "total_rows": total_rows,
        "successful": successful,
        "failed": failed,
        "custom_fields_added": custom_fields_added,
        "errors": errors,
        "message": message
    }
