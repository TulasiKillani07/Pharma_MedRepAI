"""
Authentication request/response schemas.
These define the structure of data for login, register, and token responses.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from app.core.roles import UserRole
from app.core.validators import PhoneValidator, NameValidator, EmailValidator


class LoginRequest(BaseModel):
    """
    Schema for login request.
    User selects role in UI, then enters email and password.
    """
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")
    role: UserRole = Field(..., description="User role: ADMIN, DOCTOR, or MR")
    
    # Validators
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return EmailValidator.normalize(v)
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "doctor@example.com",
                "password": "SecurePass123",
                "role": "DOCTOR"
            }
        }


class TokenResponse(BaseModel):
    """
    Schema for token response after successful login.
    """
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: dict = Field(..., description="User information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
                "user": {
                    "id": "507f1f77bcf86cd799439011",
                    "email": "doctor@example.com",
                    "full_name": "Dr. John Doe",
                    "role": "DOCTOR"
                }
            }
        }


class RegisterAdminRequest(BaseModel):
    """
    Schema for admin registration (self-registration for first admin).
    """
    email: EmailStr = Field(..., description="Admin email address")
    password: str = Field(..., min_length=8, max_length=72, description="Password (8-72 characters)")
    full_name: str = Field(..., description="Full name")
    phone: str = Field(..., description="Phone number in international format (e.g., +919876543210)")
    company_name: str = Field(..., description="Company name")
    
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
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "admin@xyzpharma.com",
                "password": "SecurePass123",
                "full_name": "John Admin",
                "phone": "+1234567890",
                "company_name": "XYZ Pharma"
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
