"""
Drug and Drug Field Template Request/Response Schemas
"""

from typing import Optional, List, Any, Dict, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# ============ FIELD DEFINITION SCHEMAS ============

class FieldDefinitionBase(BaseModel):
    """Base schema for field definition"""
    key: str
    type: str
    required: bool = False
    visible: bool = True
    order: int
    options: Optional[List[str]] = None


class FieldDefinitionCreate(FieldDefinitionBase):
    """Schema for creating a dynamic field"""
    is_fixed: bool = Field(default=False, description="If true, field cannot be deactivated")


class FieldDefinitionUpdate(BaseModel):
    """Schema for updating a field"""
    type: Optional[str] = None
    required: Optional[bool] = None
    visible: Optional[bool] = None
    order: Optional[int] = None
    options: Optional[List[str]] = None
    is_active: Optional[bool] = None  # For soft delete
    # Note: key cannot be updated


class FieldDefinitionResponse(FieldDefinitionBase):
    """Schema for field definition response"""
    field_id: str
    is_fixed: bool
    is_active: bool


# ============ PACKAGING METADATA ============

class DosagePackagingRule(BaseModel):
    """Rules for a specific dosage form — what sales units and measurement units are valid"""
    dosage_form: str
    sales_units: List[str] = Field(..., description="Valid sales unit options for this dosage form")
    measurement_units: List[str] = Field(..., description="Valid measurement unit options for this dosage form")


# ============ TEMPLATE SCHEMAS ============

class TemplateCreate(BaseModel):
    """Schema for creating a new template"""
    template_name: str


class TemplateUpdate(BaseModel):
    """Schema for updating template"""
    template_name: Optional[str] = None
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    """Schema for template response"""
    id: str = Field(alias="_id")
    template_name: str
    fields: List[FieldDefinitionResponse]
    packaging_metadata: List[DosagePackagingRule] = Field(
        default_factory=list,
        description="Packaging rules per dosage form. Frontend uses this to filter valid sales_unit and measurement_unit options."
    )
    packaging_schema: Optional[Dict] = Field(
        None,
        description="Fixed schema describing all packaging fields, their types, and rules. Frontend uses this to render the packaging form."
    )
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        populate_by_name = True
        extra = "allow"  # Allow packaging_metadata and packaging_schema injected at runtime


# ============ PACKAGING SCHEMAS ============

class DrugPackaging(BaseModel):
    """
    Flat packaging and pricing for a drug.
    Fixed schema — same fields for every drug type.
    Frontend rules determine valid sales_unit + measurement_unit per dosage_form.
    Backend stores whatever values come in — no validation of combinations needed.
    """
    sales_unit: str = Field(..., description="Sellable unit — Strip, Bottle, Tube, Vial, etc.")
    pack_quantity: int = Field(..., ge=1, description="How many measurement_units per sales_unit (e.g. 10 tablets per strip)")
    measurement_unit: str = Field(..., description="Base unit inside the pack — Tablet, Capsule, ml, g, etc.")
    selling_price: float = Field(..., ge=0, description="Price per sales_unit — used in all revenue calculations")
    max_discount_percent: float = Field(..., ge=0, le=100, description="Hard ceiling on discount for RCPA approval")
    mrp: Optional[float] = Field(None, ge=0, description="Maximum retail price — display only, not used in revenue")
    sales_units_per_box: Optional[int] = Field(None, ge=1, description="Sales units per box — only if box-level tracking needed")
    box_pricing_mode: Optional[Literal["auto", "discount", "manual"]] = Field(
        None,
        description="auto=selling_price×sales_units_per_box | discount=apply box_discount_percent | manual=use box_price directly"
    )
    box_discount_percent: Optional[float] = Field(None, ge=0, le=100, description="Only when box_pricing_mode=discount")
    box_price: Optional[float] = Field(None, ge=0, description="Only when box_pricing_mode=manual or auto-calculated")


# ============ DRUG SCHEMAS ============

class DrugFieldValueInput(BaseModel):
    """Schema for drug field value input"""
    field_id: str
    key: str
    value: Any


class DrugCreate(BaseModel):
    """Schema for creating a new drug"""
    template_id: Optional[str] = None
    field_values: List[DrugFieldValueInput]
    packaging: DrugPackaging = Field(..., description="Packaging and pricing configuration")

    class Config:
        json_schema_extra = {
            "example": {
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
        }


class DrugUpdate(BaseModel):
    """Schema for updating a drug"""
    field_values: List[DrugFieldValueInput]
    packaging: Optional[DrugPackaging] = Field(None, description="Update packaging/pricing (optional — fully replaced if provided)")
    is_active: Optional[bool] = None


class DrugFieldValueResponse(BaseModel):
    """Schema for drug field value response"""
    field_id: str
    key: str
    value: Any
    type: Optional[str] = None


class DrugResponse(BaseModel):
    """Schema for drug response"""
    id: str = Field(alias="_id")
    template_id: Optional[str] = None
    field_values: Optional[List[DrugFieldValueResponse]] = None
    packaging: Optional[DrugPackaging] = Field(None, description="Packaging and pricing configuration")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_active: Optional[bool] = True
    has_brochure: Optional[bool] = False

    class Config:
        populate_by_name = True
        extra = "allow"


class DrugListResponse(BaseModel):
    """Schema for listing drugs"""
    drugs: List[DrugResponse]
    total: int


# ============ BULK UPLOAD SCHEMAS ============

class BulkUploadErrorDetail(BaseModel):
    """Schema for individual row error in bulk upload"""
    row: int = Field(..., description="Row number in CSV/Excel (1-indexed)")
    drug_name: Optional[str] = None
    brand_name: Optional[str] = None
    error: str = Field(..., description="Error description")


class BulkUploadResponse(BaseModel):
    """Schema for bulk drug upload response"""
    total_rows: int = Field(..., description="Total rows in file (excluding header)")
    successful: int = Field(..., description="Number of drugs successfully added")
    failed: int = Field(..., description="Number of rows that failed validation")
    custom_fields_added: List[str] = Field(default=[], description="List of custom fields auto-created")
    errors: List[BulkUploadErrorDetail] = Field(default=[], description="List of errors for failed rows")
    message: str
