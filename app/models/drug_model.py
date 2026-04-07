"""
Drug and Drug Field Template Models
"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class DrugFieldDefinition(BaseModel):
    """Individual field definition in a template"""
    field_id: str
    key: str
    type: str  # "text", "textarea", "number", "select", "boolean", "date"
    is_fixed: bool
    required: bool = False
    visible: bool = True
    order: int
    options: Optional[List[str]] = None
    is_active: bool = True  # For soft delete of dynamic fields


class DrugFieldTemplate(BaseModel):
    """Template defining structure for drugs"""
    template_name: str
    fields: List[DrugFieldDefinition]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True


class DrugFieldValue(BaseModel):
    """Individual field value in a drug"""
    field_id: str
    key: str
    value: Any


class Drug(BaseModel):
    """Drug document"""
    template_id: str
    field_values: List[DrugFieldValue]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
