"""
Drug and Drug Field Template Models
"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from bson import ObjectId


class DrugFieldType(str, Enum):
    """Drug field type constants"""
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    SELECT = "select"
    BOOLEAN = "boolean"
    DATE = "date"


class DrugFieldDefinition(BaseModel):
    """Individual field definition in a template"""
    field_id: str = Field(..., description="Unique field identifier")
    key: str = Field(..., description="Field key/name")
    type: DrugFieldType = Field(..., description="Field data type")
    is_fixed: bool = Field(..., description="Whether field is fixed or dynamic")
    required: bool = Field(default=False, description="Whether field is required")
    visible: bool = Field(default=True, description="Whether field is visible")
    order: int = Field(..., ge=0, description="Display order")
    options: Optional[List[str]] = Field(None, description="Options for select type")
    is_active: bool = Field(default=True, description="Soft delete flag")


class DrugFieldTemplateInDB(BaseModel):
    """
    Write model for drug field template document (INSERT operations)
    
    Collection: drug_field_templates
    Indexes:
    - template_name
    - is_active
    """
    template_name: str = Field(..., min_length=1, max_length=100, description="Template name")
    fields: List[DrugFieldDefinition] = Field(default_factory=list, description="Field definitions")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    is_active: bool = Field(default=True, description="Soft delete flag")
    
    class Config:
        extra = "forbid"


class DrugFieldTemplateDocument(DrugFieldTemplateInDB):
    """Read model for drug field template document"""
    class Config:
        extra = "allow"


class DrugFieldValue(BaseModel):
    """Individual field value in a drug"""
    field_id: str = Field(..., description="Field identifier")
    key: str = Field(..., description="Field key/name")
    value: Any = Field(..., description="Field value")


class DrugInDB(BaseModel):
    """
    Write model for drug document (INSERT operations)
    
    Collection: drugs
    Indexes:
    - template_id
    - is_active
    - field_values (for searching)
    """
    template_id: str = Field(..., description="Template ID")
    field_values: List[DrugFieldValue] = Field(default_factory=list, description="Field values")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    is_active: bool = Field(default=True, description="Soft delete flag")
    
    @field_validator('template_id')
    @classmethod
    def validate_template_id(cls, v: str) -> str:
        """Validate template_id is valid ObjectId format"""
        try:
            ObjectId(v)
            return v
        except Exception:
            raise ValueError(f'Invalid ObjectId format: {v}')
    
    class Config:
        extra = "forbid"


class DrugDocument(DrugInDB):
    """Read model for drug document"""
    class Config:
        extra = "allow"
