"""
Department model - MongoDB schema for departments collection.
Master data for organizational departments (HR, Finance, IT, etc.)
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DepartmentInDB(BaseModel):
    """Schema for department stored in database"""
    code: str = Field(..., description="Unique department code (e.g., 'hr', 'finance', 'it')")
    name: str = Field(..., description="Department display name (e.g., 'Human Resources')")
    description: Optional[str] = Field(None, description="Department description")
    is_active: bool = Field(default=True, description="Whether department is active")
    order: int = Field(..., description="Display order in UI")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": "hr",
                "name": "Human Resources",
                "description": "Leave, transfers, performance issues",
                "is_active": True,
                "order": 1,
                "created_at": "2026-05-13T10:00:00",
                "updated_at": "2026-05-13T10:00:00"
            }
        }
