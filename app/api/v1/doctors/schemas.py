"""
Doctor request/response schemas.
Defines the structure of data for doctor operations.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
from app.core.validators import PhoneValidator, NameValidator, EmailValidator, LicenseValidator


class DoctorCreateRequest(BaseModel):
    """
    Schema for creating a new doctor (Admin only).
    Password is optional - if not provided, default password will be used.
    """
    name: str = Field(..., min_length=2, max_length=100, description="Doctor's full name")
    email: EmailStr = Field(..., description="Doctor's email address")
    password: Optional[str] = Field(None, min_length=8, max_length=72, description="Password (optional, default: Welcome@123)")
    phone: str = Field(..., description="Phone number in international format (e.g., +919876543210)")
    specialization: str = Field(..., description="Medical specialization (e.g., Cardiologist)")
    hospital: Optional[str] = Field(None, description="Hospital name")
    license_number: Optional[str] = Field(None, description="Medical license number")
    address: Optional[str] = Field(None, description="Address")
    
    # Validators
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        return NameValidator.validate(v, min_length=2, max_length=100)
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return EmailValidator.normalize(v)
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        result = PhoneValidator.validate(v)
        if result is None:
            raise ValueError('Phone number is required')
        return result
    
    @field_validator('license_number')
    @classmethod
    def validate_license(cls, v: Optional[str]) -> Optional[str]:
        return LicenseValidator.validate(v)
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Dr. Sarah Sharma",
                "email": "sharma@gmail.com",
                "phone": "+919876543210",
                "specialization": "Cardiologist",
                "hospital": "City Hospital",
                "license_number": "MH12345",
                "address": "123 Medical Street, Mumbai"
            }
        }


class DoctorUpdateRequest(BaseModel):
    """
    Schema for updating doctor information (Admin only).
    All fields are optional - only provided fields will be updated.
    """
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = None
    specialization: Optional[str] = None
    hospital: Optional[str] = None
    license_number: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None
    
    # Validators
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        return NameValidator.validate(v, min_length=2, max_length=100)
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return PhoneValidator.validate(v)
    
    @field_validator('license_number')
    @classmethod
    def validate_license(cls, v: Optional[str]) -> Optional[str]:
        return LicenseValidator.validate(v)
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "+919876543211",
                "hospital": "New City Hospital",
                "is_active": True
            }
        }


class DoctorResponse(BaseModel):
    """
    Schema for doctor response (without password).
    """
    id: str = Field(..., description="Doctor's unique ID")
    name: str
    email: EmailStr
    phone: str
    specialization: str
    hospital: Optional[str] = None
    license_number: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "name": "Dr. Sarah Sharma",
                "email": "sharma@gmail.com",
                "phone": "+919876543210",
                "specialization": "Cardiologist",
                "hospital": "City Hospital",
                "license_number": "MH12345",
                "address": "123 Medical Street, Mumbai",
                "is_active": True,
                "created_at": "2024-03-30T10:00:00"
            }
        }


class DoctorListResponse(BaseModel):
    """
    Schema for list of doctors.
    """
    total: int = Field(..., description="Total number of doctors")
    doctors: list[DoctorResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 2,
                "doctors": [
                    {
                        "id": "507f1f77bcf86cd799439011",
                        "name": "Dr. Sarah Sharma",
                        "email": "sharma@gmail.com",
                        "specialization": "Cardiologist",
                        "is_active": True
                    }
                ]
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


class DoctorCreateResponse(BaseModel):
    """
    Response for doctor creation.
    """
    message: str
    doctor_id: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Doctor added successfully",
                "doctor_id": "507f1f77bcf86cd799439011"
            }
        }


class DoctorUpdateResponse(BaseModel):
    """
    Response for doctor update with updated fields.
    """
    message: str
    updated_fields: dict
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Doctor updated successfully",
                "updated_fields": {
                    "phone": "+919876543211",
                    "hospital": "New City Hospital"
                }
            }
        }


class BulkUploadErrorDetail(BaseModel):
    """
    Schema for individual row error in bulk upload.
    """
    row: int = Field(..., description="Row number in CSV/Excel (1-indexed)")
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    error: str = Field(..., description="Error description")
    
    class Config:
        json_schema_extra = {
            "example": {
                "row": 3,
                "email": "invalid-email",
                "error": "Invalid email format"
            }
        }


class BulkUploadResponse(BaseModel):
    """
    Response for bulk doctor upload.
    """
    total_rows: int = Field(..., description="Total rows in file (excluding header)")
    successful: int = Field(..., description="Number of doctors successfully added")
    failed: int = Field(..., description="Number of rows that failed validation")
    errors: list[BulkUploadErrorDetail] = Field(default=[], description="List of errors for failed rows")
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_rows": 100,
                "successful": 95,
                "failed": 5,
                "errors": [
                    {
                        "row": 3,
                        "email": "invalid@email",
                        "error": "Invalid email format"
                    },
                    {
                        "row": 7,
                        "email": "existing@example.com",
                        "error": "Email already exists in database"
                    }
                ],
                "message": "Bulk upload completed. 95 doctors added successfully, 5 rows failed."
            }
        }
