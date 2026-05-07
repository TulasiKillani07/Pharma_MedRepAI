"""
Drug and Drug Field Template Request/Response Schemas
"""

from typing import Optional, List, Any
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
    pass


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
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        populate_by_name = True


# ============ DRUG SCHEMAS ============

class DrugFieldValueInput(BaseModel):
    """Schema for drug field value input"""
    field_id: str
    key: str
    value: Any


class DrugCreate(BaseModel):
    """Schema for creating a new drug"""
    template_id: Optional[str] = None  # Optional - will use default template if not provided
    field_values: List[DrugFieldValueInput]


class DrugUpdate(BaseModel):
    """Schema for updating a drug"""
    field_values: List[DrugFieldValueInput]
    is_active: Optional[bool] = None  # Allow updating active status


class DrugFieldValueResponse(BaseModel):
    """Schema for drug field value response"""
    field_id: str
    key: str
    value: Any


class DrugResponse(BaseModel):
    """Schema for drug response"""
    id: str = Field(alias="_id")
    template_id: Optional[str] = None  # Optional for backward compatibility
    field_values: Optional[List[DrugFieldValueResponse]] = None  # Optional for backward compatibility
    created_at: Optional[datetime] = None  # Optional for backward compatibility
    updated_at: Optional[datetime] = None
    is_active: Optional[bool] = True

    class Config:
        populate_by_name = True
        extra = "allow"  # Allow flat fields like drug_name, symptoms, etc.


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
