"""
Admin management schemas - Request/Response models for admin management endpoints.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.core.validators import PhoneValidator, NameValidator, EmailValidator


class CreateDepartmentAdminRequest(BaseModel):
    """
    Schema for general admin creating a department admin (HR, Finance, IT).
    """
    email: EmailStr = Field(..., description="Admin email address")
    password: str = Field(..., min_length=8, max_length=72, description="Password (8-72 characters)")
    full_name: str = Field(..., description="Full name")
    phone: str = Field(..., description="Phone number")
    department: str = Field(..., description="Department code (hr, finance, it)")
    
    # Validators
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return EmailValidator.normalize(v)
    
    @field_validator('full_name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        return NameValidator.validate(v, min_length=2, max_length=100)
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        result = PhoneValidator.validate(v)
        if result is None:
            raise ValueError('Phone number is required')
        return result
    
    @field_validator('department')
    @classmethod
    def validate_department(cls, v: str) -> str:
        allowed_departments = ["hr", "finance", "it"]
        if v.lower() not in allowed_departments:
            raise ValueError(f'Department must be one of: {", ".join(allowed_departments)}')
        return v.lower()
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "hr.admin@xyzpharma.com",
                "password": "SecurePass123",
                "full_name": "Sarah HR Manager",
                "phone": "+919876543210",
                "department": "hr"
            }
        }


class AdminResponse(BaseModel):
    """
    Schema for admin details response.
    """
    id: str
    email: str
    full_name: str
    phone: str
    department: str
    is_active: bool
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "email": "hr.admin@xyzpharma.com",
                "full_name": "Sarah HR Manager",
                "phone": "+919876543210",
                "department": "hr",
                "is_active": True,
                "created_at": "2026-05-13T10:00:00"
            }
        }


class AdminListResponse(BaseModel):
    """
    Schema for list of admins.
    """
    total: int
    admins: List[AdminResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 3,
                "admins": []
            }
        }


class CreateAdminResponse(BaseModel):
    """
    Response after creating admin.
    """
    message: str
    admin_id: str
    email: str
    department: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Department admin created successfully",
                "admin_id": "507f1f77bcf86cd799439011",
                "email": "hr.admin@xyzpharma.com",
                "department": "hr"
            }
        }


class UpdateAdminDepartmentRequest(BaseModel):
    """
    Schema for updating admin's department.
    """
    department: str = Field(..., description="New department code (general, hr, finance, it)")
    
    @field_validator('department')
    @classmethod
    def validate_department(cls, v: str) -> str:
        allowed_departments = ["general", "hr", "finance", "it"]
        if v.lower() not in allowed_departments:
            raise ValueError(f'Department must be one of: {", ".join(allowed_departments)}')
        return v.lower()
    
    class Config:
        json_schema_extra = {
            "example": {
                "department": "finance"
            }
        }


class MessageResponse(BaseModel):
    """
    Generic message response.
    """
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operation successful"
            }
        }
