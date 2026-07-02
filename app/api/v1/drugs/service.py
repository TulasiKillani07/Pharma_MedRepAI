"""
Drug and Drug Field Template Business Logic
"""
import asyncio

from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from bson import ObjectId
import pandas as pd
from io import BytesIO, StringIO
import httpx
from app.database import get_database
from app.api.v1.drugs.schemas import (
    TemplateCreate, TemplateUpdate, FieldDefinitionCreate, FieldDefinitionUpdate,
    DrugCreate, DrugUpdate
)
import uuid
from app.api.v1.notifications.helpers import notify_drug_added
from app.models.drug_model import DrugInDB, DrugFieldTemplateInDB, DrugFieldType
from app.api.v1.activity_logs.helpers import log_activity
from app.models.activity_log_model import ActivityLogAction, ActorRole, TargetType, LogSeverity
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)


# ============ HELPER FUNCTIONS ============

def build_flat_fields(field_values: List[Dict]) -> Dict[str, Any]:
    """
    Build top-level flat fields and search_text from field_values.
    Used for fast querying and full-text search.
    
    Returns dict of flat fields + search_text to be merged into drug document.
    """
    flat = {}
    search_parts = []

    for fv in field_values:
        key = fv.get("key") if isinstance(fv, dict) else fv.key
        value = fv.get("value") if isinstance(fv, dict) else fv.value

        if value is None:
            continue

        flat[key] = value

        # Build search_text from value
        if isinstance(value, list):
            search_parts.extend([str(v).lower() for v in value if v])
        elif isinstance(value, str) and value.strip():
            search_parts.append(value.lower())
        elif value is not None:
            search_parts.append(str(value).lower())

    flat["search_text"] = " ".join(search_parts)
    return flat


def coerce_array_field(value: Any) -> List[str]:
    """
    Coerce a value to a list of strings for array-type fields.
    - If already a list, clean each item
    - If a string, split by comma and clean each item
    - If None/empty, return empty list
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def normalize_field_values(field_values: List[Any], template_fields: Dict[str, Any]) -> List[Dict]:
    """
    Normalize field values - coerce array fields to lists.
    Works with both Pydantic objects (DrugFieldValueInput) and plain dicts.
    """
    normalized = []
    for fv in field_values:
        # Support both Pydantic model and dict
        if hasattr(fv, "dict"):
            fv_dict = fv.dict()
        else:
            fv_dict = dict(fv)
        
        field_def = template_fields.get(fv_dict["field_id"])
        if field_def and field_def.get("type") == "array":
            fv_dict["value"] = coerce_array_field(fv_dict.get("value"))
        
        normalized.append(fv_dict)
    return normalized


def get_default_fixed_fields() -> List[Dict[str, Any]]:
    """Returns the 17 default fixed fields for drug template (14 drug fields + 3 brochure fields)"""
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
            "key": "symptoms",
            "type": "array",
            "is_fixed": True,
            "required": True,
            "visible": True,
            "order": 5,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "indications",
            "type": "array",
            "is_fixed": True,
            "required": False,  # Optional - some drugs only treat symptoms, not diseases
            "visible": True,
            "order": 6,
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
            "order": 7,
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
            "order": 8,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "dosage_form",
            "type": "select",
            "is_fixed": True,
            "required": True,
            "visible": True,
            "order": 9,
            "options": ["Tablet", "Capsule", "Syrup", "Injection", "Drops", "Cream", "Ointment", "Gel", "Powder", "Lotion", "Inhaler"],
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "route",
            "type": "select",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 10,
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
            "order": 11,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "reference_url",
            "type": "text",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 12,
            "options": None,
            "is_active": True
        },
        # Packaging fields
        {
            "field_id": str(uuid.uuid4()),
            "key": "pack_type",
            "type": "select",
            "is_fixed": True,
            "required": True,
            "visible": True,
            "order": 13,
            "options": ["Strip", "Bottle", "Vial", "Ampoule", "Tube", "Sachet", "Box", "Blister Pack"],
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "units_per_pack",
            "type": "number",
            "is_fixed": True,
            "required": True,
            "visible": True,
            "order": 14,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "packs_per_box",
            "type": "number",
            "is_fixed": True,
            "required": True,
            "visible": True,
            "order": 15,
            "options": None,
            "is_active": True
        },
        # Pricing fields
        {
            "field_id": str(uuid.uuid4()),
            "key": "price_per_drug",
            "type": "number",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 16,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "pack_price",
            "type": "number",
            "is_fixed": True,
            "required": True,
            "visible": True,
            "order": 17,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "box_price",
            "type": "number",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 18,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "mrp",
            "type": "number",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 19,
            "options": None,
            "is_active": True
        },
        # Brochure fields (optional, auto-filled by upload endpoint)
        {
            "field_id": str(uuid.uuid4()),
            "key": "brochure_url",
            "type": "text",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 19,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "brochure_public_id",
            "type": "text",
            "is_fixed": True,
            "required": False,
            "visible": False,  # Hidden - internal use only
            "order": 16,
            "options": None,
            "is_active": True
        },
        {
            "field_id": str(uuid.uuid4()),
            "key": "brochure_uploaded_at",
            "type": "text",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 17,
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
    
    # RULE 1: INSERT with model
    template = DrugFieldTemplateInDB(
        template_name=template_data.template_name,
        fields=get_default_fixed_fields()
    )
    
    result = await db["drug_field_templates"].insert_one(template.model_dump())
    
    return {
        "_id": str(result.inserted_id),
        **template.model_dump()
    }


async def get_template() -> Optional[Dict[str, Any]]:
    """Get the active template. Auto-creates one if none exists, and auto-migrates fields if needed."""
    import uuid as uuid_module
    db = get_database()
    template = await db["drug_field_templates"].find_one({"is_active": True})
    
    # Auto-create default template if none exists
    if not template:
        default_template = DrugFieldTemplateInDB(
            template_name="Default Drug Template",
            fields=get_default_fixed_fields()
        )
        result = await db["drug_field_templates"].insert_one(default_template.model_dump())
        template = await db["drug_field_templates"].find_one({"_id": result.inserted_id})
    
    fields = template.get("fields", [])
    changes = False

    # Build key -> index map
    key_to_index = {f["key"]: i for i, f in enumerate(fields)}

    # Add is_active to fields if missing (backward compatibility)
    for field in fields:
        if "is_active" not in field:
            field["is_active"] = True
            changes = True

    # Ensure indications exists as array (optional - some drugs only treat symptoms)
    if "indications" in key_to_index:
        idx = key_to_index["indications"]
        if fields[idx].get("type") != "array" or not fields[idx].get("is_fixed"):
            fields[idx]["type"] = "array"
            fields[idx]["required"] = False  # Optional field
            fields[idx]["is_fixed"] = True
            changes = True
    else:
        fields.append({
            "field_id": str(uuid_module.uuid4()),
            "key": "indications",
            "type": "array",
            "is_fixed": True,
            "required": False,  # Optional - some drugs only treat symptoms
            "visible": True,
            "order": 6,
            "options": None,
            "is_active": True
        })
        changes = True

    # Ensure symptoms exists as array, required=True, is_fixed=True
    if "symptoms" in key_to_index:
        idx = key_to_index["symptoms"]
        if fields[idx].get("type") != "array" or not fields[idx].get("required") or not fields[idx].get("is_fixed"):
            fields[idx]["type"] = "array"
            fields[idx]["required"] = True
            fields[idx]["is_fixed"] = True
            changes = True
    else:
        fields.append({
            "field_id": str(uuid_module.uuid4()),
            "key": "symptoms",
            "type": "array",
            "is_fixed": True,
            "required": True,
            "visible": True,
            "order": 5,
            "options": None,
            "is_active": True
        })
        changes = True

    # Ensure reference_url exists (optional field for official drug info page)
    if "reference_url" not in key_to_index:
        fields.append({
            "field_id": str(uuid_module.uuid4()),
            "key": "reference_url",
            "type": "text",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 12,
            "options": None,
            "is_active": True
        })
        changes = True

    # Remove old 'price' field (replaced by price_per_drug)
    if "price" in key_to_index:
        fields = [f for f in fields if f["key"] != "price"]
        key_to_index = {f["key"]: i for i, f in enumerate(fields)}
        changes = True

    # Ensure pack_type exists
    if "pack_type" not in key_to_index:
        fields.append({
            "field_id": str(uuid_module.uuid4()),
            "key": "pack_type",
            "type": "select",
            "is_fixed": True,
            "required": True,
            "visible": True,
            "order": 13,
            "options": ["Strip", "Bottle", "Vial", "Ampoule", "Tube", "Sachet", "Box", "Blister Pack"],
            "is_active": True
        })
        changes = True

    # Ensure units_per_pack exists
    if "units_per_pack" not in key_to_index:
        fields.append({
            "field_id": str(uuid_module.uuid4()),
            "key": "units_per_pack",
            "type": "number",
            "is_fixed": True,
            "required": True,
            "visible": True,
            "order": 14,
            "options": None,
            "is_active": True
        })
        changes = True

    # Ensure packs_per_box exists
    if "packs_per_box" not in key_to_index:
        fields.append({
            "field_id": str(uuid_module.uuid4()),
            "key": "packs_per_box",
            "type": "number",
            "is_fixed": True,
            "required": True,
            "visible": True,
            "order": 15,
            "options": None,
            "is_active": True
        })
        changes = True

    # Ensure pack_price exists
    if "pack_price" not in key_to_index:
        fields.append({
            "field_id": str(uuid_module.uuid4()),
            "key": "pack_price",
            "type": "number",
            "is_fixed": True,
            "required": True,
            "visible": True,
            "order": 17,
            "options": None,
            "is_active": True
        })
        changes = True

    # Ensure price_per_drug exists
    if "price_per_drug" not in key_to_index:
        fields.append({
            "field_id": str(uuid_module.uuid4()),
            "key": "price_per_drug",
            "type": "number",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 16,
            "options": None,
            "is_active": True
        })
        changes = True

    # Ensure box_price exists
    if "box_price" not in key_to_index:
        fields.append({
            "field_id": str(uuid_module.uuid4()),
            "key": "box_price",
            "type": "number",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 17,
            "options": None,
            "is_active": True
        })
        changes = True

    # Ensure mrp exists
    if "mrp" not in key_to_index:
        fields.append({
            "field_id": str(uuid_module.uuid4()),
            "key": "mrp",
            "type": "number",
            "is_fixed": True,
            "required": False,
            "visible": True,
            "order": 18,
            "options": None,
            "is_active": True
        })
        changes = True

    # Ensure dosage_form has updated options and is required
    if "dosage_form" in key_to_index:
        idx = key_to_index["dosage_form"]
        new_options = ["Tablet", "Capsule", "Syrup", "Injection", "Drops", "Cream", "Ointment", "Gel", "Powder", "Lotion", "Inhaler"]
        if fields[idx].get("options") != new_options or not fields[idx].get("required"):
            fields[idx]["options"] = new_options
            fields[idx]["required"] = True
            changes = True

    # Persist changes if anything was updated
    if changes:
        await db["drug_field_templates"].update_one(
            {"_id": template["_id"]},
            {"$set": {"fields": fields, "updated_at": datetime.utcnow()}}
        )
        template["fields"] = fields
        template["updated_at"] = datetime.utcnow()

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

async def create_drug(drug_data: DrugCreate, current_user: Dict) -> Dict[str, Any]:
    """Create a new drug"""
    db = get_database()
    
    # Auto-fetch template if not provided
    if not drug_data.template_id:
        template = await get_template()  # Gets or creates default template
        template_id = template["_id"]
    else:
        # Validate provided template_id
        if not ObjectId.is_valid(drug_data.template_id):
            raise HTTPException(status_code=400, detail="Invalid template ID")
        template_id = drug_data.template_id
        template = await db["drug_field_templates"].find_one(
            {"_id": ObjectId(template_id), "is_active": True}
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
    
    # Normalize field values (coerce array fields to lists)
    normalized_field_values = normalize_field_values(drug_data.field_values, template_fields)
    
    # Create drug using DrugInDB model
    drug = DrugInDB(
        template_id=template_id,
        field_values=normalized_field_values,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        is_active=True
    )
    
    # Convert to dict and add flat fields for DB optimization
    drug_doc = drug.model_dump()
    
    # Build flat top-level fields + search_text for fast querying (DB optimization)
    flat_fields = build_flat_fields(normalized_field_values)
    drug_doc.update(flat_fields)  # Add flat fields for fast querying
    
    result = await db["drugs"].insert_one(drug_doc)
    drug_doc["_id"] = str(result.inserted_id)
    
    # Send notification to all doctors and MRs
    doctors_cursor = db["doctors"].find({"is_active": True}, {"_id": 1})
    mrs_cursor = db["mrs"].find({"is_active": True}, {"_id": 1})
    
    doctors_list = await doctors_cursor.to_list(None)
    mrs_list = await mrs_cursor.to_list(None)
    
    user_ids = [str(doc["_id"]) for doc in doctors_list] + [str(mr["_id"]) for mr in mrs_list]
    
    # Extract drug_name and manufacturer from field_values
    drug_name = "New Drug"
    manufacturer = "Unknown"
    
    for fv in drug_data.field_values:
        if fv.key == "drug_name":
            drug_name = fv.value or drug_name
        elif fv.key == "manufacturer":
            manufacturer = fv.value or manufacturer
    
    if user_ids:
        await notify_drug_added(
            drug_id=str(result.inserted_id),
            drug_name=drug_name,
            manufacturer=manufacturer,
            user_ids=user_ids
        )
    
    # Log activity
    await log_activity(
        action_type=ActivityLogAction.DRUG_CREATED,
        actor=current_user,
        target_type=TargetType.DRUG,
        target_id=str(result.inserted_id),
        target_name=drug_name,
        details={
            "drug_name": drug_name,
            "manufacturer": manufacturer
        },
        severity=LogSeverity.INFO
    )
    
    return drug_doc


async def get_all_drugs(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    drug_name: Optional[str] = None,
    manufacturer: Optional[str] = None,
    dosage_form: Optional[str] = None,
    symptom: Optional[str] = None,
    indication: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get all drugs with optional search filters using flat fields.
    Returns all drugs with is_active field - frontend handles filtering.
    
    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        search: Full-text search across all fields
        drug_name: Filter by drug name (partial match)
        manufacturer: Filter by manufacturer (partial match)
        dosage_form: Filter by dosage form (exact match)
        symptom: Filter by symptom (partial match)
        indication: Filter by indication (partial match)
    
    Returns:
        Dict with drugs list (including is_active field) and total count
    """
    db = get_database()
    
    # Backfill is_active field for drugs that don't have it (backward compatibility)
    await db["drugs"].update_many(
        {"is_active": {"$exists": False}},
        {"$set": {"is_active": True, "updated_at": datetime.utcnow()}}
    )
    
    # Backfill any existing drugs that don't have flat fields yet (optimized batch operation)
    drugs_to_backfill = await db["drugs"].find(
        {"drug_name": {"$exists": False}}
    ).to_list(length=None)
    
    if drugs_to_backfill:
        update_tasks = []
        for drug in drugs_to_backfill:
            flat_fields = build_flat_fields(drug.get("field_values", []))
            update_tasks.append(
                db["drugs"].update_one(
                    {"_id": drug["_id"]},
                    {"$set": {**flat_fields, "updated_at": datetime.utcnow()}}
                )
            )
        await asyncio.gather(*update_tasks)
    
    query: Dict[str, Any] = {}
    
    # No is_active filter - return all drugs, frontend will filter
    
    # Full-text search across all fields
    if search:
        query["search_text"] = {"$regex": search.lower(), "$options": "i"}
    
    # Exact / partial field filters
    if drug_name:
        query["drug_name"] = {"$regex": drug_name.lower(), "$options": "i"}
    if manufacturer:
        query["manufacturer"] = {"$regex": manufacturer.lower(), "$options": "i"}
    if dosage_form:
        query["dosage_form"] = dosage_form
    # Array field filters — check if value is in array
    if symptom:
        query["symptoms"] = {"$regex": symptom.lower(), "$options": "i"}
    if indication:
        query["indications"] = {"$regex": indication.lower(), "$options": "i"}
    
    cursor = db["drugs"].find(query).skip(skip).limit(limit)
    drugs = await cursor.to_list(length=limit)
    
    for drug in drugs:
        drug["_id"] = str(drug["_id"])
        
        # Ensure is_active field is present
        if "is_active" not in drug:
            drug["is_active"] = True
        
        # Check if drug has brochure
        has_brochure = False
        if "brochure_url" in drug and drug["brochure_url"]:
            has_brochure = True
        elif "field_values" in drug:
            for fv in drug["field_values"]:
                if fv.get("key") == "brochure_url" and fv.get("value"):
                    has_brochure = True
                    break
        
        # Add has_brochure flag
        drug["has_brochure"] = has_brochure
        
        # Remove brochure fields from response (security/privacy)
        drug.pop("brochure_url", None)
        drug.pop("brochure_public_id", None)
        drug.pop("brochure_uploaded_at", None)
        
        # Remove brochure fields from field_values
        if "field_values" in drug:
            drug["field_values"] = [
                fv for fv in drug["field_values"]
                if fv.get("key") not in ["brochure_url", "brochure_public_id", "brochure_uploaded_at"]
            ]
    
    # Enrich field_values with type from template
    template = await db["drug_field_templates"].find_one({"is_active": True})
    if template:
        field_type_map = {f["field_id"]: f["type"] for f in template.get("fields", [])}
        for drug in drugs:
            if "field_values" in drug:
                for fv in drug["field_values"]:
                    fv["type"] = field_type_map.get(fv.get("field_id"))
    
    total = await db["drugs"].count_documents(query)
    
    return {"drugs": drugs, "total": total}


async def get_drug_by_id(drug_id: str) -> Dict[str, Any]:
    """Get drug by ID - returns drug with is_active field, excludes brochure URLs for security"""
    db = get_database()
    
    if not ObjectId.is_valid(drug_id):
        raise HTTPException(status_code=400, detail="Invalid drug ID")
    
    # Don't filter by is_active - return drug regardless of status
    drug = await db["drugs"].find_one({"_id": ObjectId(drug_id)})
    
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
    
    drug["_id"] = str(drug["_id"])
    
    # Ensure is_active field is present
    if "is_active" not in drug:
        drug["is_active"] = True
    
    # Check if drug has brochure
    has_brochure = False
    if "brochure_url" in drug and drug["brochure_url"]:
        has_brochure = True
    elif "field_values" in drug:
        for fv in drug["field_values"]:
            if fv.get("key") == "brochure_url" and fv.get("value"):
                has_brochure = True
                break
    
    # Add has_brochure flag
    drug["has_brochure"] = has_brochure
    
    # Remove brochure fields from response (security/privacy)
    drug.pop("brochure_url", None)
    drug.pop("brochure_public_id", None)
    drug.pop("brochure_uploaded_at", None)
    
    # Remove brochure fields from field_values
    if "field_values" in drug:
        drug["field_values"] = [
            fv for fv in drug["field_values"]
            if fv.get("key") not in ["brochure_url", "brochure_public_id", "brochure_uploaded_at"]
        ]
    
    # Enrich field_values with type from template
    template = await db["drug_field_templates"].find_one({"is_active": True})
    if template:
        field_type_map = {f["field_id"]: f["type"] for f in template.get("fields", [])}
        if "field_values" in drug:
            for fv in drug["field_values"]:
                fv["type"] = field_type_map.get(fv.get("field_id"))
    
    return drug


async def update_drug(drug_id: str, drug_data: DrugUpdate) -> Dict[str, Any]:
    """Update a drug - merges field_values instead of replacing them. Can update is_active status."""
    db = get_database()
    
    if not ObjectId.is_valid(drug_id):
        raise HTTPException(status_code=400, detail="Invalid drug ID")
    
    # Get existing drug (don't filter by is_active - allow updating inactive drugs)
    drug = await db["drugs"].find_one({"_id": ObjectId(drug_id)})
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
    
    # Get template (use drug's template_id or get default template)
    if drug.get("template_id"):
        template = await db["drug_field_templates"].find_one(
            {"_id": ObjectId(drug["template_id"]), "is_active": True}
        )
    else:
        # For old drugs without template_id, get default template
        template = await get_template()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template_fields = {f["field_id"]: f for f in template["fields"]}
    
    # Validate incoming field_values
    for fv in drug_data.field_values:
        if fv.field_id not in template_fields:
            raise HTTPException(status_code=400, detail=f"Invalid field_id: {fv.field_id}")
        
        if fv.key != template_fields[fv.field_id]["key"]:
            raise HTTPException(status_code=400, detail=f"Key mismatch for field_id: {fv.field_id}")
    
    # Get existing field_values from the drug
    existing_field_values = drug.get("field_values", [])
    
    # Create a map of existing field_values by field_id for easy lookup
    existing_field_map = {fv["field_id"]: fv for fv in existing_field_values}
    
    # Merge: Update existing fields with new values, keep unchanged fields
    incoming_field_ids = {fv.field_id for fv in drug_data.field_values}
    
    # Start with existing field_values
    merged_field_values = []
    
    # Add all existing fields, updating those that are in the incoming data
    for existing_fv in existing_field_values:
        field_id = existing_fv["field_id"]
        if field_id in incoming_field_ids:
            # This field is being updated - will be added from incoming data
            continue
        else:
            # This field is not being updated - keep existing value
            merged_field_values.append(existing_fv)
    
    # Add all incoming field_values (these are the updates)
    for incoming_fv in drug_data.field_values:
        merged_field_values.append({
            "field_id": incoming_fv.field_id,
            "key": incoming_fv.key,
            "value": incoming_fv.value
        })
    
    # Normalize field values (coerce array fields to lists)
    normalized_field_values = normalize_field_values(merged_field_values, template_fields)
    
    # Rebuild flat top-level fields + search_text from ALL field_values
    flat_fields = build_flat_fields(normalized_field_values)
    
    # Prepare update data
    update_data = {
        "field_values": normalized_field_values,
        **flat_fields,
        "updated_at": datetime.utcnow()
    }
    
    # Update is_active if provided
    if drug_data.is_active is not None:
        update_data["is_active"] = drug_data.is_active
    
    # Update drug
    result = await db["drugs"].update_one(
        {"_id": ObjectId(drug_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Drug not found")
    
    return await get_drug_by_id(drug_id)


async def delete_drug(drug_id: str, current_user: Dict) -> Dict[str, str]:
    """Soft delete a drug and log the activity"""
    db = get_database()
    
    if not ObjectId.is_valid(drug_id):
        raise HTTPException(status_code=400, detail="Invalid drug ID")
    
    # Get drug details before deactivating (for logging)
    drug = await db["drugs"].find_one({"_id": ObjectId(drug_id)})
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
    
    drug_name = drug.get("drug_name", "Unknown Drug")
    
    result = await db["drugs"].update_one(
        {"_id": ObjectId(drug_id)},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
    )
    
    # Log activity
    await log_activity(
        action_type=ActivityLogAction.DRUG_DELETED,
        actor=current_user,
        target_type=TargetType.DRUG,
        target_id=drug_id,
        target_name=drug_name,
        details={"drug_name": drug_name},
        severity=LogSeverity.CRITICAL
    )
    
    return {"message": "Drug deleted successfully"}


# ============ DRUG BROCHURE SERVICES ============

async def upload_drug_brochure(drug_id: str, file: UploadFile, current_user: Dict) -> Dict[str, Any]:
    """Upload brochure PDF for a drug - updates brochure fields in field_values"""
    from app.services.cloudinary_service import upload_drug_brochure as cloudinary_upload, delete_drug_brochure
    
    db = get_database()
    
    # Validate drug exists
    if not ObjectId.is_valid(drug_id):
        raise HTTPException(status_code=400, detail="Invalid drug ID")
    
    drug = await db["drugs"].find_one({"_id": ObjectId(drug_id), "is_active": True})
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
    
    # Get template to find brochure field IDs
    template = None
    if drug.get("template_id"):
        template = await db["drug_field_templates"].find_one(
            {"_id": ObjectId(drug["template_id"]), "is_active": True}
        )
    else:
        template = await get_template()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Find brochure field IDs from template
    brochure_url_field = None
    brochure_public_id_field = None
    brochure_uploaded_at_field = None
    
    for field in template["fields"]:
        if field["key"] == "brochure_url":
            brochure_url_field = field
        elif field["key"] == "brochure_public_id":
            brochure_public_id_field = field
        elif field["key"] == "brochure_uploaded_at":
            brochure_uploaded_at_field = field
    
    # Delete old brochure from Cloudinary if exists
    old_public_id = None
    if "field_values" in drug:
        for fv in drug["field_values"]:
            if fv.get("key") == "brochure_public_id" and fv.get("value"):
                old_public_id = fv["value"]
                break
    
    # Also check flat field for backward compatibility
    if not old_public_id and drug.get("brochure_public_id"):
        old_public_id = drug["brochure_public_id"]
    
    if old_public_id:
        try:
            await delete_drug_brochure(old_public_id)
        except Exception as e:
            # Log but don't fail if old brochure deletion fails
            logger.warning(f"Failed to delete old brochure: {e}")
    
    # Upload new brochure to Cloudinary
    upload_result = await cloudinary_upload(file, drug_id)
    
    # Get existing field_values
    existing_field_values = drug.get("field_values", [])
    
    # Create map of existing field_values by key
    field_values_map = {fv["key"]: fv for fv in existing_field_values}
    
    # Update or add brochure fields
    brochure_timestamp = datetime.utcnow().isoformat()
    
    if brochure_url_field:
        field_values_map["brochure_url"] = {
            "field_id": brochure_url_field["field_id"],
            "key": "brochure_url",
            "value": upload_result["secure_url"]
        }
    
    if brochure_public_id_field:
        field_values_map["brochure_public_id"] = {
            "field_id": brochure_public_id_field["field_id"],
            "key": "brochure_public_id",
            "value": upload_result["public_id"]
        }
    
    if brochure_uploaded_at_field:
        field_values_map["brochure_uploaded_at"] = {
            "field_id": brochure_uploaded_at_field["field_id"],
            "key": "brochure_uploaded_at",
            "value": brochure_timestamp
        }
    
    # Convert map back to list
    updated_field_values = list(field_values_map.values())
    
    # Rebuild flat fields from updated field_values
    template_fields = {f["field_id"]: f for f in template["fields"]}
    normalized_field_values = normalize_field_values(updated_field_values, template_fields)
    flat_fields = build_flat_fields(normalized_field_values)
    
    # Update drug document
    await db["drugs"].update_one(
        {"_id": ObjectId(drug_id)},
        {
            "$set": {
                "field_values": normalized_field_values,
                **flat_fields,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Get drug name for response
    drug_name = drug.get("drug_name", "")
    if not drug_name and "field_values" in drug:
        for field in drug.get("field_values", []):
            if field.get("key") == "drug_name":
                drug_name = field.get("value", "")
                break
    
    # Log activity
    await log_activity(
        action_type=ActivityLogAction.DRUG_UPDATED,
        actor=current_user,
        target_type=TargetType.DRUG,
        target_id=drug_id,
        target_name=drug_name,
        details={"action": "brochure_uploaded"},
        severity=LogSeverity.INFO
    )
    
    return {
        "drug_id": drug_id,
        "drug_name": drug_name,
        "brochure_url": upload_result["secure_url"],
        "brochure_size_kb": round(upload_result["bytes"] / 1024, 2),
        "message": "Brochure uploaded successfully"
    }


async def delete_drug_brochure(drug_id: str) -> Dict[str, str]:
    """Delete brochure for a drug - removes brochure fields from field_values"""
    from app.services.cloudinary_service import delete_drug_brochure as cloudinary_delete
    
    db = get_database()
    
    # Validate drug exists
    if not ObjectId.is_valid(drug_id):
        raise HTTPException(status_code=400, detail="Invalid drug ID")
    
    drug = await db["drugs"].find_one({"_id": ObjectId(drug_id), "is_active": True})
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
    
    # Find brochure_public_id from field_values or flat field
    public_id = None
    if "field_values" in drug:
        for fv in drug["field_values"]:
            if fv.get("key") == "brochure_public_id" and fv.get("value"):
                public_id = fv["value"]
                break
    
    # Check flat field for backward compatibility
    if not public_id and drug.get("brochure_public_id"):
        public_id = drug["brochure_public_id"]
    
    if not public_id:
        raise HTTPException(status_code=404, detail="No brochure found for this drug")
    
    # Delete from Cloudinary
    await cloudinary_delete(public_id)
    
    # Get template
    template = None
    if drug.get("template_id"):
        template = await db["drug_field_templates"].find_one(
            {"_id": ObjectId(drug["template_id"]), "is_active": True}
        )
    else:
        template = await get_template()
    
    if template:
        # Remove brochure fields from field_values
        existing_field_values = drug.get("field_values", [])
        updated_field_values = [
            fv for fv in existing_field_values 
            if fv.get("key") not in ["brochure_url", "brochure_public_id", "brochure_uploaded_at"]
        ]
        
        # Rebuild flat fields
        template_fields = {f["field_id"]: f for f in template["fields"]}
        normalized_field_values = normalize_field_values(updated_field_values, template_fields)
        flat_fields = build_flat_fields(normalized_field_values)
        
        # Update drug document
        await db["drugs"].update_one(
            {"_id": ObjectId(drug_id)},
            {
                "$set": {
                    "field_values": normalized_field_values,
                    **flat_fields,
                    "updated_at": datetime.utcnow()
                },
                "$unset": {
                    "brochure_url": "",
                    "brochure_public_id": "",
                    "brochure_uploaded_at": ""
                }
            }
        )
    else:
        # Fallback: just remove flat fields
        await db["drugs"].update_one(
            {"_id": ObjectId(drug_id)},
            {
                "$unset": {
                    "brochure_url": "",
                    "brochure_public_id": "",
                    "brochure_uploaded_at": ""
                },
                "$set": {
                    "updated_at": datetime.utcnow()
                }
            }
        )
    
    return {"message": "Brochure deleted successfully"}


async def download_drug_brochure(drug_id: str):
    """
    Stream brochure PDF with proper download headers.
    Fetches the file from Cloudinary and streams it with Content-Disposition: attachment.
    """
    import httpx
    from fastapi.responses import StreamingResponse
    
    db = get_database()
    
    # Validate drug exists
    if not ObjectId.is_valid(drug_id):
        raise HTTPException(status_code=400, detail="Invalid drug ID")
    
    drug = await db["drugs"].find_one({"_id": ObjectId(drug_id), "is_active": True})
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
    
    # Find brochure_url and drug_name
    brochure_url = None
    drug_name = "brochure"
    
    if "field_values" in drug:
        for fv in drug["field_values"]:
            if fv.get("key") == "brochure_url" and fv.get("value"):
                brochure_url = fv["value"]
            elif fv.get("key") == "drug_name" and fv.get("value"):
                drug_name = fv["value"]
    
    # Check flat fields for backward compatibility
    if not brochure_url and drug.get("brochure_url"):
        brochure_url = drug["brochure_url"]
    
    if not drug_name and drug.get("drug_name"):
        drug_name = drug["drug_name"]
    
    if not brochure_url:
        raise HTTPException(status_code=404, detail="No brochure found for this drug")
    
    # Sanitize drug_name for filename (remove special characters)
    safe_drug_name = "".join(c for c in drug_name if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_drug_name = safe_drug_name.replace(' ', '_')
    filename = f"{safe_drug_name}_brochure.pdf"
    
    # Fetch the file from Cloudinary and stream it
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(brochure_url, timeout=30.0)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to fetch brochure from cloud storage"
                )
            
            # Return streaming response with proper headers
            return StreamingResponse(
                iter([response.content]),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Type": "application/pdf",
                    "Cache-Control": "no-cache"
                }
            )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download brochure: {str(e)}"
        )



# ============ BULK UPLOAD SERVICES ============

async def download_drug_template() -> StreamingResponse:
    """Generate and download CSV template with 12 fixed fields"""
    
    # Define the 12 fixed field columns
    columns = [
        "drug_name",
        "brand_name",
        "drug_class",
        "manufacturer",
        "symptoms",
        "indications",
        "mechanism_of_action",
        "dosage_strength",
        "dosage_form",
        "route",
        "side_effects",
        "reference_url"
    ]
    
    # Create DataFrame with a sample row to show expected format
    sample_row = {
        "drug_name": "Paracetamol",
        "brand_name": "Crocin",
        "drug_class": "Analgesic",
        "manufacturer": "GSK Pharmaceuticals",
        "symptoms": "Fever, Headache, Body Pain",
        "indications": "Mild to moderate pain, Fever reduction",
        "mechanism_of_action": "Inhibits prostaglandin synthesis in the CNS",
        "dosage_strength": "500mg",
        "dosage_form": "Tablet",
        "route": "Oral",
        "side_effects": "Nausea, Skin rash (rare)",
        "reference_url": "https://www.drugs.com/paracetamol.html"
    }
    df = pd.DataFrame([sample_row], columns=columns)
    
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


async def bulk_upload_drugs(file: UploadFile, current_user: Dict) -> Dict[str, Any]:
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
        "drug_name", "brand_name", "drug_class", "manufacturer", "symptoms", "indications",
        "mechanism_of_action", "dosage_strength", "dosage_form", "route", "side_effects", "reference_url",
        "pack_type", "units_per_pack", "packs_per_box", "price_per_drug", "pack_price", "box_price", "mrp"
    ]
    
    # Validate required columns (only drug_name and symptoms are truly required)
    required_columns = ["drug_name", "symptoms"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(missing_columns)}"
        )
    
    # Check max rows limit (300)
    if len(df) > 300:
        raise HTTPException(
            status_code=400,
            detail=f"File contains {len(df)} rows. Maximum allowed is 300 rows per upload."
        )
    
    # Get or create template
    template = await db["drug_field_templates"].find_one({"is_active": True})
    
    if not template:
        # Create template using DrugFieldTemplateInDB model
        template_obj = DrugFieldTemplateInDB(
            template_name="Default Drug Template",
            fields=get_default_fixed_fields(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        result = await db["drug_field_templates"].insert_one(template_obj.model_dump())
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
        symptoms = str(row.get('symptoms', '')).strip() if pd.notna(row.get('symptoms')) else ''
        indications = str(row.get('indications', '')).strip() if pd.notna(row.get('indications')) else ''
        
        # Validate required fields (only drug_name and symptoms are required)
        if not drug_name:
            row_errors.append("drug_name is required")
        
        if not symptoms:
            row_errors.append("symptoms is required")
        
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
        
        # Check duplicate in database (fast query using flat fields)
        existing_drug = await db["drugs"].find_one({
            "is_active": True,
            "drug_name": drug_name_lower,
            "brand_name": brand_name_lower
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
            
            # Handle array type fields - split comma-separated values
            if field_def.get("type") == "array" and value:
                # Split by comma and clean up each item
                value = [item.strip() for item in value.split(",") if item.strip()]
            
            field_values.append({
                "field_id": field_def["field_id"],
                "key": col,
                "value": value
            })
        
        # Create drug document
        try:
            # Create drug using DrugInDB model
            from app.models.drug_model import DrugFieldValue
            field_values_models = [DrugFieldValue(**fv) for fv in field_values]
            
            drug = DrugInDB(
                template_id=template_id,
                field_values=field_values_models,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_active=True
            )
            
            # Convert to dict and add flat fields for DB optimization
            drug_doc = drug.model_dump()
            
            # Build flat fields for fast querying (DB optimization)
            flat_fields = build_flat_fields(field_values)
            drug_doc.update(flat_fields)  # Add flat fields for fast querying
            
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
    
    # Send bulk notification for successfully added drugs
    if successful > 0:
        # Get all doctors and MRs
        doctors_cursor = db["doctors"].find({"is_active": True}, {"_id": 1})
        mrs_cursor = db["mrs"].find({"is_active": True}, {"_id": 1})
        
        doctors_list = await doctors_cursor.to_list(None)
        mrs_list = await mrs_cursor.to_list(None)
        
        user_ids = [str(doc["_id"]) for doc in doctors_list] + [str(mr["_id"]) for mr in mrs_list]
        
        if user_ids:
            # Send a single notification about bulk upload
            await notify_drug_added(
                drug_id="bulk",
                drug_name=f"{successful} new drugs",
                manufacturer="Various",
                user_ids=user_ids
            )
    
    # Prepare response message
    if failed == 0:
        message = f"Bulk upload completed successfully. All {successful} drugs added."
    elif successful == 0:
        message = f"Bulk upload failed. All {failed} rows had errors."
    else:
        message = f"Bulk upload completed. {successful} drugs added successfully, {failed} rows failed."
    
    if custom_fields_added:
        message += f" {len(custom_fields_added)} custom fields added to template."
    
    # Log bulk upload activity
    if successful > 0:
        await log_activity(
            action_type=ActivityLogAction.DRUG_BULK_UPLOAD,
            actor=current_user,
            target_type=TargetType.DRUG,
            target_id=None,
            target_name=None,
            details={
                "total_rows": total_rows,
                "successful": successful,
                "failed": failed,
                "custom_fields_added": len(custom_fields_added),
                "filename": file.filename
            },
            severity=LogSeverity.INFO
        )
    
    return {
        "total_rows": total_rows,
        "successful": successful,
        "failed": failed,
        "custom_fields_added": custom_fields_added,
        "errors": errors,
        "message": message
    }
