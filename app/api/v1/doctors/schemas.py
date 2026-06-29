"""
Doctor request/response schemas.
Defines the structure of data for doctor operations.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Literal
from datetime import datetime
from app.core.validators import PhoneValidator, NameValidator, EmailValidator, LicenseValidator


class DoctorCreateRequest(BaseModel):
    """
    Schema for creating a new doctor (Admin only).
    Password is optional - if not provided, default password will be used.
    Classification is mandatory for SFE (Sales Force Effectiveness) tracking.
    
    Phone Number Format:
    - Accepts both formats: 9876543210 OR +919876543210
    - 10-digit numbers are automatically converted to +919876543210
    - International numbers must include country code (e.g., +14155552671)
    
    Doctor Classification (SFE):
    - Class A: High-value doctors, requires 2 visits per month
    - Class B: Medium-value doctors, requires 1 visit per month
    - Class C: Low-value doctors, requires 1 visit per 2 months
    """
    name: str = Field(..., min_length=2, max_length=100, description="Doctor's full name")
    email: EmailStr = Field(..., description="Doctor's email address")
    password: Optional[str] = Field(None, min_length=8, max_length=72, description="Password (optional, default: Welcome@123)")
    phone: str = Field(..., description="Phone number: 9876543210 or +919876543210")
    specialization: str = Field(..., description="Medical specialization (e.g., Cardiologist)")
    classification: Literal["A", "B", "C"] = Field(..., description="Doctor classification for SFE: A (2 visits/month), B (1 visit/month), C (1 visit/2 months)")
    hospital: Optional[str] = Field(None, description="Hospital name")
    license_number: Optional[str] = Field(None, description="Medical license number")
    
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
                "phone": "9876543210",
                "specialization": "Cardiologist",
                "classification": "A",
                "hospital": "City Hospital",
                "license_number": "MH12345"
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
    classification: Optional[Literal["A", "B", "C"]] = Field(None, description="Doctor classification: A, B, or C")
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
    classification: str = Field(..., description="Doctor classification: A, B, or C")
    hospital: Optional[str] = None
    license_number: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    added_by: Optional[dict] = Field(None, description="Who added this doctor: {role, id, name, department}")
    approved_by: Optional[dict] = Field(None, description="Who approved (if MR request): {role, id, name, department}")
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "name": "Dr. Sarah Sharma",
                "email": "sharma@gmail.com",
                "phone": "+919876543210",
                "specialization": "Cardiologist",
                "classification": "A",
                "hospital": "City Hospital",
                "license_number": "MH12345",
                "address": "123 Medical Street, Mumbai",
                "is_active": True,
                "added_by": {
                    "role": "ADMIN",
                    "id": "admin_id",
                    "name": "Admin Name",
                    "department": "general"
                },
                "approved_by": None,
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



# ============================================================================
# DOCTOR REQUEST SCHEMAS (MR Request → Admin Approval Workflow)
# ============================================================================

class DoctorRequestCreate(BaseModel):
    """
    Schema for MR to request adding a new doctor.
    MR provides doctor details, admin must approve before doctor is created.
    Classification is mandatory for SFE tracking.
    """
    name: str = Field(..., min_length=2, max_length=100, description="Doctor's full name")
    email: EmailStr = Field(..., description="Doctor's email address")
    phone: str = Field(..., description="Phone number: 9876543210 or +919876543210")
    specialization: str = Field(..., min_length=2, max_length=100, description="Medical specialization")
    classification: Literal["A", "B", "C"] = Field(..., description="Doctor classification: A (2 visits/month), B (1 visit/month), C (1 visit/2 months)")
    hospital: Optional[str] = Field(None, max_length=200, description="Hospital name")
    license_number: Optional[str] = Field(None, max_length=50, description="Medical license number")
    address: Optional[str] = Field(None, max_length=500, description="Full address")
    
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
                "name": "Dr. Amit Patel",
                "email": "amit.patel@hospital.com",
                "phone": "9876543210",
                "specialization": "Cardiologist",
                "classification": "A",
                "hospital": "Apollo Hospital",
                "license_number": "MH12345",
                "address": "123 Medical Street, Mumbai"
            }
        }


class DoctorRequestResponse(BaseModel):
    """
    Schema for doctor request response.
    """
    request_id: str = Field(..., description="Request ID")
    requested_by: str = Field(..., description="MR user ID")
    requested_by_name: str = Field(..., description="MR name")
    requested_by_email: str = Field(..., description="MR email")
    status: str = Field(..., description="Request status: pending, approved, rejected")
    
    # Doctor details
    name: str
    email: EmailStr
    phone: str
    specialization: str
    classification: Optional[str] = Field(default="C", description="Doctor classification: A, B, or C (defaults to C if not specified)")
    hospital: Optional[str] = None
    license_number: Optional[str] = None
    address: Optional[str] = None
    
    # Approval metadata
    reviewed_by: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    doctor_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "507f1f77bcf86cd799439099",
                "requested_by": "507f1f77bcf86cd799439011",
                "requested_by_name": "Rajesh Kumar",
                "requested_by_email": "rajesh@xyzpharma.com",
                "status": "pending",
                "name": "Dr. Amit Patel",
                "email": "amit.patel@hospital.com",
                "phone": "+919876543210",
                "specialization": "Cardiologist",
                "classification": "A",
                "hospital": "Apollo Hospital",
                "license_number": "MH12345",
                "address": "123 Medical Street, Mumbai",
                "reviewed_by": None,
                "reviewed_by_name": None,
                "reviewed_at": None,
                "rejection_reason": None,
                "doctor_id": None,
                "created_at": "2024-03-30T10:00:00",
                "updated_at": "2024-03-30T10:00:00"
            }
        }


class DoctorRequestListResponse(BaseModel):
    """
    Schema for list of doctor requests.
    """
    total: int = Field(..., description="Total number of requests")
    requests: list[DoctorRequestResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 5,
                "requests": [
                    {
                        "request_id": "507f1f77bcf86cd799439099",
                        "requested_by_name": "Rajesh Kumar",
                        "status": "pending",
                        "name": "Dr. Amit Patel",
                        "specialization": "Cardiologist",
                        "created_at": "2024-03-30T10:00:00"
                    }
                ]
            }
        }


class DoctorRequestCreateResponse(BaseModel):
    """
    Response for doctor request creation.
    """
    message: str
    request_id: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Doctor request submitted successfully. Waiting for admin approval.",
                "request_id": "507f1f77bcf86cd799439099"
            }
        }


class DoctorRequestRejectRequest(BaseModel):
    """
    Schema for rejecting a doctor request.
    """
    rejection_reason: str = Field(..., min_length=10, max_length=500, description="Reason for rejection")
    
    class Config:
        json_schema_extra = {
            "example": {
                "rejection_reason": "Doctor already exists in the system with a different email address."
            }
        }


class DoctorRequestApproveResponse(BaseModel):
    """
    Response for doctor request approval.
    """
    message: str
    doctor_id: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Doctor request approved and doctor account created successfully",
                "doctor_id": "507f1f77bcf86cd799439011"
            }
        }
