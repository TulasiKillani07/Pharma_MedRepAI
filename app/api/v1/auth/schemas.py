"""
Authentication request/response schemas.
These define the structure of data for login, register, and token responses.
"""

from pydantic import BaseModel, EmailStr, Field
from app.core.roles import UserRole


class LoginRequest(BaseModel):
    """
    Schema for login request.
    User selects role in UI, then enters email and password.
    """
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")
    role: UserRole = Field(..., description="User role: ADMIN, DOCTOR, or MR")
    
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
    phone: str = Field(..., description="Phone number")
    company_name: str = Field(..., description="Company name")
    
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
