"""
Department schemas - Request/Response models for department API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DepartmentCreateRequest(BaseModel):
    """Schema for creating a new department"""
    code: str = Field(..., min_length=2, max_length=50, description="Unique department code (lowercase, no spaces)")
    name: str = Field(..., min_length=2, max_length=100, description="Department display name")
    description: Optional[str] = Field(None, max_length=500, description="Department description")
    order: int = Field(..., ge=1, description="Display order")
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": "operations",
                "name": "Operations & Logistics",
                "description": "Sample delivery, promotional materials",
                "order": 4
            }
        }


class DepartmentUpdateRequest(BaseModel):
    """Schema for updating a department (all fields optional)"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    order: Optional[int] = Field(None, ge=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Operations & Supply Chain",
                "description": "Updated description",
                "is_active": True,
                "order": 5
            }
        }


class DepartmentResponse(BaseModel):
    """Schema for department response"""
    code: str
    name: str
    description: Optional[str]
    is_active: bool
    order: int
    created_at: datetime
    updated_at: datetime
    
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


class DepartmentListResponse(BaseModel):
    """Schema for list of departments"""
    total: int = Field(..., description="Total number of departments")
    departments: List[DepartmentResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 3,
                "departments": [
                    {
                        "code": "hr",
                        "name": "Human Resources",
                        "description": "Leave, transfers, performance issues",
                        "is_active": True,
                        "order": 1,
                        "created_at": "2026-05-13T10:00:00",
                        "updated_at": "2026-05-13T10:00:00"
                    },
                    {
                        "code": "finance",
                        "name": "Finance & Accounts",
                        "description": "Salary, reimbursements, incentives",
                        "is_active": True,
                        "order": 2,
                        "created_at": "2026-05-13T10:00:00",
                        "updated_at": "2026-05-13T10:00:00"
                    }
                ]
            }
        }


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operation successful"
            }
        }
