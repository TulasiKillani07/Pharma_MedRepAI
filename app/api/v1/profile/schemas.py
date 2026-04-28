"""
Profile Request/Response Schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from app.core.validators import (
    PhoneValidator, NameValidator, URLValidator, 
    TextValidator, ExperienceValidator, TerritoryValidator
)


class ProfileUpdateRequest(BaseModel):
    """Request schema for updating profile"""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100, description="Full name")
    phone: Optional[str] = Field(None, description="Phone number in international format")
    bio: Optional[str] = Field(None, max_length=500, description="About me / Bio")
    avatar_url: Optional[str] = Field(None, max_length=500, description="Profile picture URL (set to null to remove)")
    location: Optional[str] = Field(None, max_length=100, description="City/State")
    experience_years: Optional[float] = Field(None, ge=0, le=70, description="Years of experience (decimals allowed, e.g., 1.5)")
    
    # Doctor-specific fields
    specialization: Optional[str] = Field(None, max_length=100, description="Medical specialization (Doctor only)")
    hospital: Optional[str] = Field(None, max_length=200, description="Hospital/Clinic name (Doctor only)")
    
    # MR-specific fields
    territory: Optional[str] = Field(None, max_length=100, description="Territory/Region (MR only)")
    
    # Admin/Manager-specific fields (personal profile only, NOT company)
    admin_bio: Optional[str] = Field(None, max_length=500, description="Admin/Manager bio")
    admin_avatar_url: Optional[str] = Field(None, max_length=500, description="Admin/Manager avatar URL")
    
    # Validators
    @field_validator('full_name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        return NameValidator.validate(v, min_length=2, max_length=100)
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return PhoneValidator.validate(v)
    
    @field_validator('bio', 'admin_bio')
    @classmethod
    def validate_bio(cls, v: Optional[str]) -> Optional[str]:
        return TextValidator.validate(v, max_length=500, strip_html=True)
    
    @field_validator('avatar_url', 'admin_avatar_url')
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        return URLValidator.validate(v, max_length=500)
    
    @field_validator('experience_years')
    @classmethod
    def validate_experience(cls, v: Optional[float]) -> Optional[float]:
        return ExperienceValidator.validate(v, min_years=0, max_years=70)
    
    @field_validator('territory')
    @classmethod
    def validate_territory(cls, v: Optional[str]) -> Optional[str]:
        return TerritoryValidator.validate(v)
    
    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "Dr. Sarah Sharma",
                "phone": "+919876543210",
                "bio": "Cardiologist with 10 years of experience specializing in interventional cardiology",
                "avatar_url": "https://example.com/avatars/sarah.jpg",
                "location": "Mumbai, Maharashtra",
                "experience_years": 10.5,
                "specialization": "Cardiology",
                "hospital": "Apollo Hospital"
            }
        }


class ProfileResponse(BaseModel):
    """Response schema for profile (own profile - includes private fields)"""
    user_id: str
    email: str
    full_name: str
    phone: str
    role: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    experience_years: Optional[float] = None  # Changed to float to support decimals
    
    # Doctor-specific
    specialization: Optional[str] = None
    hospital: Optional[str] = None
    license_number: Optional[str] = None
    
    # MR-specific
    territory: Optional[str] = None
    
    # Admin/Manager-specific (personal profile only)
    admin_bio: Optional[str] = None
    admin_avatar_url: Optional[str] = None
    
    # Metadata
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "email": "sarah@example.com",
                "full_name": "Dr. Sarah Sharma",
                "phone": "+919876543210",
                "role": "DOCTOR",
                "bio": "Cardiologist with 10 years of experience",
                "avatar_url": "https://example.com/avatars/sarah.jpg",
                "location": "Mumbai, Maharashtra",
                "experience_years": 10.5,
                "specialization": "Cardiology",
                "hospital": "Apollo Hospital",
                "license_number": "MH12345",
                "territory": None,
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-04-14T10:00:00"
            }
        }


class PublicProfileResponse(BaseModel):
    """Response schema for viewing other user's profile (public fields only)"""
    user_id: str
    full_name: str
    role: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    experience_years: Optional[float] = None  # Changed to float to support decimals
    
    # Doctor-specific
    specialization: Optional[str] = None
    hospital: Optional[str] = None
    
    # MR-specific
    territory: Optional[str] = None
    
    # Connection info
    is_connected: bool
    connection_status: Optional[str] = None  # "connected", "pending", "not_connected"
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "full_name": "Dr. Sarah Sharma",
                "role": "DOCTOR",
                "bio": "Cardiologist with 10 years of experience",
                "avatar_url": "https://example.com/avatars/sarah.jpg",
                "location": "Mumbai, Maharashtra",
                "experience_years": 10.5,
                "specialization": "Cardiology",
                "hospital": "Apollo Hospital",
                "territory": None,
                "is_connected": True,
                "connection_status": "connected"
            }
        }


class CompanyUpdateRequest(BaseModel):
    """Request schema for updating company profile (Admin/Manager only)"""
    company_name: Optional[str] = Field(None, max_length=200, description="Company name")
    company_logo_url: Optional[str] = Field(None, max_length=500, description="Company logo URL")
    company_description: Optional[str] = Field(None, max_length=1000, description="Company description")
    company_address: Optional[str] = Field(None, max_length=300, description="Company address")
    company_city: Optional[str] = Field(None, max_length=100, description="Company city")
    company_state: Optional[str] = Field(None, max_length=100, description="Company state")
    company_country: Optional[str] = Field(None, max_length=100, description="Company country")
    company_pincode: Optional[str] = Field(None, max_length=20, description="Company pincode")
    company_website: Optional[str] = Field(None, max_length=200, description="Company website")
    company_industry: Optional[str] = Field(None, max_length=100, description="Company industry")
    company_founded_year: Optional[int] = Field(None, ge=1800, le=2100, description="Company founded year")
    company_size: Optional[str] = Field(None, max_length=50, description="Company size e.g. '50-200'")
    company_gst_number: Optional[str] = Field(None, max_length=50, description="Company GST number")
    company_pan_number: Optional[str] = Field(None, max_length=50, description="Company PAN number")
    
    # Validators
    @field_validator('company_logo_url', 'company_website')
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        return URLValidator.validate(v, max_length=500)
    
    @field_validator('company_description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        return TextValidator.validate(v, max_length=1000, strip_html=True)
    
    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "XYZ Pharma",
                "company_logo_url": "https://example.com/logo.png",
                "company_description": "Leading pharmaceutical company",
                "company_city": "Mumbai",
                "company_state": "Maharashtra"
            }
        }


class CompanyProfileResponse(BaseModel):
    """Response schema for viewing company profile (public fields only)"""
    company_name: str
    company_logo_url: Optional[str] = None
    company_description: Optional[str] = None
    company_city: Optional[str] = None
    company_state: Optional[str] = None
    company_country: Optional[str] = None
    company_website: Optional[str] = None
    company_industry: Optional[str] = None
    company_founded_year: Optional[int] = None
    company_size: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "XYZ Pharma",
                "company_logo_url": "https://example.com/logos/xyz.png",
                "company_description": "Leading pharmaceutical company in India",
                "company_city": "Mumbai",
                "company_state": "Maharashtra",
                "company_country": "India",
                "company_website": "https://xyzpharma.com",
                "company_industry": "Pharmaceuticals",
                "company_founded_year": 2010,
                "company_size": "50-200"
            }
        }
