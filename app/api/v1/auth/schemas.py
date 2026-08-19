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
    User selects role (ADMIN or MR) and enters credentials.
    DOCTOR role is blocked — doctors use DRX platform.
    """
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")
    role: UserRole = Field(..., description="User role: ADMIN or MR (DOCTOR returns 403)")
    
    # Validators
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return EmailValidator.normalize(v)
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "admin@xyzpharma.com",
                "password": "Welcome@123",
                "role": "ADMIN"
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
    must_change_password: bool = Field(default=False, description="Whether user must change password before accessing app")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
                "user": {
                    "id": "507f1f77bcf86cd799439011",
                    "email": "admin@xyzpharma.com",
                    "full_name": "Admin User",
                    "role": "ADMIN"
                }
            }
        }


class RegisterAdminRequest(BaseModel):
    """
    Schema for admin registration (self-registration for first admin).
    """
    username: str = Field(..., min_length=3, max_length=50, description="Global unique username (same across Proxzar, DOBO, DRX, MRX)")
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
                "username": "john_admin",
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



class ChangePasswordFirstLoginRequest(BaseModel):
    """
    Schema for resetting/changing password.
    User can change password anytime - on first login or later.
    """
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=72, description="New password (8-72 characters)")
    confirm_password: str = Field(..., description="Confirm new password")
    
    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        from app.core.validators import PasswordValidator
        return PasswordValidator.validate(v)
    
    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('Passwords do not match')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "current_password": "Abc123!@#xyz",
                "new_password": "MyNewSecurePass123!",
                "confirm_password": "MyNewSecurePass123!"
            }
        }


class ChangePasswordResponse(BaseModel):
    """
    Schema for password change response.
    Returns new token after successful password change.
    """
    message: str = Field(..., description="Success message")
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Password changed successfully",
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600
            }
        }



class ForgotPasswordRequest(BaseModel):
    """
    Schema for forgot password request.
    User provides email and role to receive OTP.
    """
    email: EmailStr = Field(..., description="User's email address")
    role: UserRole = Field(..., description="User role: ADMIN or MR (DOCTOR blocked — use DRX)")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return EmailValidator.normalize(v)
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "admin@xyzpharma.com",
                "role": "ADMIN"
            }
        }


class ForgotPasswordResponse(BaseModel):
    """
    Schema for forgot password response.
    """
    message: str = Field(..., description="Success message")
    expires_in: int = Field(..., description="OTP expiration time in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "If an account exists with this email, you will receive a password reset OTP",
                "expires_in": 900
            }
        }


class ResetPasswordWithOTPRequest(BaseModel):
    """
    Schema for resetting password with OTP.
    """
    email: EmailStr = Field(..., description="User's email address")
    role: UserRole = Field(..., description="User role: ADMIN or MR (DOCTOR blocked — use DRX)")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")
    new_password: str = Field(..., min_length=8, max_length=72, description="New password (8-72 characters)")
    confirm_password: str = Field(..., description="Confirm new password")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return EmailValidator.normalize(v)
    
    @field_validator('otp')
    @classmethod
    def validate_otp(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError('OTP must contain only digits')
        return v
    
    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        from app.core.validators import PasswordValidator
        return PasswordValidator.validate(v)
    
    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('Passwords do not match')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "admin@xyzpharma.com",
                "role": "ADMIN",
                "otp": "123456",
                "new_password": "MyNewSecurePass123!",
                "confirm_password": "MyNewSecurePass123!"
            }
        }
