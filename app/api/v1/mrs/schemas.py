"""
MR (Medical Representative) request/response schemas.
Defines the structure of data for MR operations.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime
from app.core.validators import PhoneValidator, NameValidator, EmailValidator, TerritoryValidator


class MRCreateRequest(BaseModel):
    """
    Schema for creating a new MR (Admin only).
    Password is optional - if not provided, default password will be used.
    Zone, State, Territory are required for communications targeting.
    
    Phone Number Format:
    - Accepts both formats: 9876543210 OR +919876543210
    - 10-digit numbers are automatically converted to +919876543210
    - International numbers must include country code (e.g., +14155552671)
    """
    name: str = Field(..., min_length=2, max_length=100, description="MR's full name")
    email: EmailStr = Field(..., description="MR's email address")
    password: Optional[str] = Field(None, min_length=8, max_length=72, description="Password (optional, default: Welcome@123)")
    phone: str = Field(..., description="Phone number: 9876543210 or +919876543210")
    
    # Geographic fields (required for communications targeting) - Fixed values with dropdowns
    zone: Literal["South"] = Field(default="South", description="Zone (currently only South supported)")
    state: Literal["Telangana", "Andhra Pradesh"] = Field(..., description="State")
    territory: Literal["Hyderabad", "Visakhapatnam"] = Field(..., description="Territory")
    
    assigned_doctors: Optional[List[str]] = Field(default=[], description="List of assigned doctor IDs")
    assigned_drugs: Optional[List[str]] = Field(default=[], description="List of assigned drug/product IDs")
    
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
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Rajesh Kumar",
                "email": "rajesh@xyzpharma.com",
                "phone": "9876543210",
                "zone": "South",
                "state": "Telangana",
                "territory": "Hyderabad",
                "assigned_doctors": [],
                "assigned_drugs": []
            }
        }


class MRUpdateRequest(BaseModel):
    """
    Schema for updating MR information (Admin only).
    All fields are optional - only provided fields will be updated.
    """
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = None
    zone: Optional[Literal["South"]] = None
    state: Optional[Literal["Telangana", "Andhra Pradesh"]] = None
    territory: Optional[Literal["Hyderabad", "Visakhapatnam"]] = None
    assigned_doctors: Optional[List[str]] = None
    assigned_drugs: Optional[List[str]] = None
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
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "+919876543211",
                "state": "Andhra Pradesh",
                "territory": "Visakhapatnam",
                "assigned_doctors": ["507f1f77bcf86cd799439011"],
                "assigned_drugs": ["507f1f77bcf86cd799439021"],
                "is_active": True
            }
        }


class AssignedDoctorInfo(BaseModel):
    """
    Schema for assigned doctor information.
    """
    id: str
    name: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439012",
                "name": "Dr. Sarah Sharma"
            }
        }


class AssignedDrugInfo(BaseModel):
    """
    Schema for assigned drug/product information.
    """
    id: str
    name: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439021",
                "name": "Amlovas 5mg"
            }
        }


class MRResponse(BaseModel):
    """
    Schema for MR response (without password).
    """
    id: str = Field(..., description="MR's unique ID")
    name: str
    email: EmailStr
    phone: str
    zone: str
    state: str
    territory: str
    assigned_doctors: List[AssignedDoctorInfo]
    assigned_drugs: List[AssignedDrugInfo]
    is_active: bool
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "name": "Rajesh Kumar",
                "email": "rajesh@xyzpharma.com",
                "phone": "+919876543210",
                "zone": "South",
                "state": "Telangana",
                "territory": "Hyderabad",
                "assigned_doctors": [
                    {
                        "id": "507f1f77bcf86cd799439012",
                        "name": "Dr. Sarah Sharma"
                    }
                ],
                "assigned_drugs": [
                    {
                        "id": "507f1f77bcf86cd799439021",
                        "name": "Amlovas 5mg"
                    }
                ],
                "is_active": True,
                "created_at": "2024-03-30T10:00:00"
            }
        }


class MRListResponse(BaseModel):
    """
    Schema for list of MRs.
    """
    total: int = Field(..., description="Total number of MRs")
    mrs: List[MRResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 2,
                "mrs": [
                    {
                        "id": "507f1f77bcf86cd799439011",
                        "name": "Rajesh Kumar",
                "email": "rajesh@xyzpharma.com",
                        "territory": "Mumbai North",
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


class MRCreateResponse(BaseModel):
    """
    Response for MR creation.
    """
    message: str
    mr_id: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "MR added successfully",
                "mr_id": "507f1f77bcf86cd799439011"
            }
        }


class MRUpdateResponse(BaseModel):
    """
    Response for MR update with updated fields.
    """
    message: str
    updated_fields: dict
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "MR updated successfully",
                "updated_fields": {
                    "phone": "+919876543211",
                    "territory": "Mumbai South"
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
    Response for bulk MR upload.
    """
    total_rows: int = Field(..., description="Total rows in file (excluding header)")
    successful: int = Field(..., description="Number of MRs successfully added")
    failed: int = Field(..., description="Number of rows that failed validation")
    errors: List[BulkUploadErrorDetail] = Field(default=[], description="List of errors for failed rows")
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
                "message": "Bulk upload completed. 95 MRs added successfully, 5 rows failed."
            }
        }


class MRFilterItem(BaseModel):
    """
    Schema for filtered MR item (minimal info for selection).
    """
    id: str = Field(..., description="MR's unique ID")
    name: str = Field(..., description="MR's full name")
    email: EmailStr = Field(..., description="MR's email")
    phone: str = Field(..., description="MR's phone number")
    zone: str = Field(..., description="MR's zone")
    state: str = Field(..., description="MR's state")
    territory: str = Field(..., description="MR's territory")
    is_active: bool = Field(..., description="Whether MR is active")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "name": "Rajesh Kumar",
                "email": "rajesh@xyzpharma.com",
                "phone": "+919876543210",
                "zone": "South",
                "state": "Telangana",
                "territory": "Hyderabad",
                "is_active": True
            }
        }


class MRFilterResponse(BaseModel):
    """
    Response for filtered MR list.
    """
    total: int = Field(..., description="Total number of MRs matching filters")
    mrs: List[MRFilterItem] = Field(..., description="List of filtered MRs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 5,
                "mrs": [
                    {
                        "id": "507f1f77bcf86cd799439011",
                        "name": "Rajesh Kumar",
                        "email": "rajesh@xyzpharma.com",
                        "phone": "+919876543210",
                        "zone": "South",
                        "state": "Telangana",
                        "territory": "Hyderabad",
                        "is_active": True
                    },
                    {
                        "id": "507f1f77bcf86cd799439012",
                        "name": "Priya Sharma",
                        "email": "priya@xyzpharma.com",
                        "phone": "+919876543211",
                        "zone": "South",
                        "state": "Telangana",
                        "territory": "Hyderabad",
                        "is_active": True
                    }
                ]
            }
        }
