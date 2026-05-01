"""
Authentication routes - API endpoints for login and registration.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.api.v1.auth.schemas import (
    LoginRequest,
    TokenResponse,
    RegisterAdminRequest,
    MessageResponse,
    ChangePasswordFirstLoginRequest,
    ChangePasswordResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordWithOTPRequest
)
from app.api.v1.auth.service import login_user, register_admin
from app.core.auth import get_current_user


# Create router for auth endpoints
router = APIRouter()


@router.post("/login", response_model=TokenResponse, summary="Login")
async def login(login_request: LoginRequest, request: Request):
    """
    Login endpoint - Authenticate user and return JWT token.
    
    **Flow:**
    1. User selects role in UI (ADMIN, DOCTOR, or MR)
    2. User enters email and password
    3. Backend searches in the correct collection based on role
    4. Backend verifies password
    5. Backend returns JWT token
    
    **Usage:**
    ```
    POST /api/v1/auth/login
    {
        "email": "doctor@example.com",
        "password": "SecurePass123",
        "role": "DOCTOR"
    }
    ```
    
    **Response:**
    ```
    {
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
    ```
    
    **Use the access_token in subsequent requests:**
    ```
    Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    ```
    """
    return await login_user(login_request.email, login_request.password, login_request.role, request)


@router.post("/register/admin", response_model=MessageResponse, summary="Register Admin")
async def register_admin_endpoint(request: RegisterAdminRequest):
    """
    Register a new company admin (self-registration).
    
    **Note:** This is for the first admin to register.
    In production, you might want to:
    - Restrict this endpoint after first admin is created
    - Require an invitation code
    - Add email verification
    
    **Usage:**
    ```
    POST /api/v1/auth/register/admin
    {
        "email": "admin@xyzpharma.com",
        "password": "SecurePass123",
        "full_name": "John Admin",
        "phone": "+1234567890",
        "company_name": "XYZ Pharma"
    }
    ```
    
    **Response:**
    ```
    {
        "message": "Admin registered successfully",
        "user_id": "507f1f77bcf86cd799439011"
    }
    ```
    
    **After registration, use the login endpoint to get a token.**
    """
    return await register_admin(
        email=request.email,
        password=request.password,
        full_name=request.full_name,
        phone=request.phone,
        company_name=request.company_name
    )


@router.get("/me", summary="Get Current User")
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user information.
    
    **This is a protected route - requires JWT token.**
    
    **Usage:**
    ```
    GET /api/v1/auth/me
    Headers: {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```
    
    **Response:**
    ```
    {
        "_id": "507f1f77bcf86cd799439011",
        "email": "doctor@example.com",
        "full_name": "Dr. John Doe",
        "role": "DOCTOR",
        "specialization": "Cardiology",
        "is_active": true,
        "created_at": "2024-01-01T00:00:00"
    }
    ```
    
    **Use this endpoint to:**
    - Verify token is valid
    - Get user profile information
    - Check user role and permissions
    """
    return current_user


@router.post("/logout", summary="Logout")
async def logout(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Logout endpoint - Log user logout activity.
    
    **Note:** JWT tokens are stateless, so logout is handled on the frontend by deleting the token.
    This endpoint only logs the logout activity for audit purposes.
    
    **Flow:**
    1. User clicks logout button
    2. Frontend calls this endpoint
    3. Backend logs the logout activity
    4. Frontend deletes the JWT token from storage
    5. User is redirected to login page
    
    **Usage:**
    ```
    POST /api/v1/auth/logout
    Headers: {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```
    
    **Response:**
    ```
    {
        "message": "Logged out successfully"
    }
    ```
    
    **Frontend should:**
    - Delete token from localStorage/sessionStorage
    - Clear any cached user data
    - Redirect to login page
    """
    from app.api.v1.activity_logs.helpers import log_activity
    from app.models.activity_log_model import ActivityLogAction, ActorRole, TargetType, LogSeverity
    
    # Determine target type and actor role based on user role
    role = current_user.get("role")
    if role == "DOCTOR":
        target_type = TargetType.DOCTOR
        actor_role = ActorRole.DOCTOR
    elif role == "MR":
        target_type = TargetType.MR
        actor_role = ActorRole.MR
    else:  # ADMIN
        target_type = TargetType.SYSTEM
        actor_role = ActorRole.ADMIN
    
    # Log logout activity
    await log_activity(
        action_type=ActivityLogAction.USER_LOGOUT,
        actor=current_user,
        target_type=target_type,
        target_id=current_user.get("_id"),
        target_name=current_user.get("name") or current_user.get("full_name", "Unknown"),
        details={"email": current_user.get("email"), "role": role},
        severity=LogSeverity.INFO,
        request=request
    )
    
    return {"message": "Logged out successfully"}



@router.post("/reset-password", response_model=ChangePasswordResponse, summary="Reset Password")
async def reset_password_endpoint(
    request: ChangePasswordFirstLoginRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Reset/change password for authenticated users.
    
    **Use Cases:**
    1. First login: User can change temporary password to their own password
    2. Anytime: User can change their password whenever they want
    
    **Flow:**
    1. User logs in (with temporary or current password)
    2. User goes to "Change Password" or "Reset Password" page
    3. User enters current password + new password + confirm password
    4. Backend validates and updates password
    5. Backend returns new JWT token
    6. User continues using the application
    
    **Access:** All authenticated users (Admin, Doctor, MR)
    
    **Note:** User can use this endpoint multiple times to change password.
    
    **Usage:**
    ```
    POST /api/v1/auth/reset-password
    Headers: {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    {
        "current_password": "Abc123!@#xyz",
        "new_password": "MyNewSecurePass123!",
        "confirm_password": "MyNewSecurePass123!"
    }
    ```
    
    **Response:**
    ```
    {
        "message": "Password changed successfully",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "expires_in": 3600
    }
    ```
    
    **Password Requirements:**
    - Minimum 8 characters
    - Maximum 72 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
    
    **Frontend Integration:**
    ```javascript
    // User can change password anytime from settings/profile page
    const response = await api.post('/auth/reset-password', {
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword
    }, {
        headers: { Authorization: `Bearer ${token}` }
    });
    
    // Update token
    localStorage.setItem('token', response.access_token);
    
    // Show success message
    toast.success('Password changed successfully!');
    ```
    
    **Optional First Login Flow:**
    If you want to encourage users to change password on first login:
    1. Check `is_password_changed` field in user profile
    2. Show a banner/modal suggesting password change
    3. User can choose to change now or skip
    4. User can always change later from settings
    """
    from app.api.v1.auth.service import change_password_first_login
    
    return await change_password_first_login(
        current_password=request.current_password,
        new_password=request.new_password,
        current_user=current_user
    )



@router.post("/forgot-password", response_model=ForgotPasswordResponse, summary="Forgot Password")
async def forgot_password_endpoint(request: ForgotPasswordRequest):
    """
    Request password reset by sending OTP to email.
    
    **Use Case:** User forgot their password and needs to reset it.
    
    **Flow:**
    1. User clicks "Forgot Password" on login page
    2. User enters email and selects role
    3. Backend generates 6-digit OTP
    4. OTP sent to user's email (expires in 15 minutes)
    5. User receives email with OTP
    6. User enters OTP + new password on reset page
    
    **Security:**
    - Returns generic success message even if email doesn't exist (prevents email enumeration)
    - OTP expires in 15 minutes
    - Old unused OTPs are invalidated when new one is requested
    - OTP can only be used once
    
    **Usage:**
    ```
    POST /api/v1/auth/forgot-password
    {
        "email": "doctor@example.com",
        "role": "DOCTOR"
    }
    ```
    
    **Response:**
    ```
    {
        "message": "If an account exists with this email, you will receive a password reset OTP",
        "expires_in": 900
    }
    ```
    
    **Note:** Same response is returned whether email exists or not (security best practice).
    """
    from app.api.v1.auth.service import request_password_reset
    
    return await request_password_reset(
        email=request.email,
        role=request.role
    )


@router.post("/forgot-password/verify", response_model=MessageResponse, summary="Reset Password with OTP")
async def reset_password_with_otp_endpoint(
    request_data: ResetPasswordWithOTPRequest,
    request: Request
):
    """
    Reset password using OTP received via email.
    
    **Use Case:** User received OTP via email and wants to set new password.
    
    **Flow:**
    1. User receives OTP via email (from /forgot-password endpoint)
    2. User enters OTP + new password + confirm password
    3. Backend verifies OTP (not expired, not used, matches email+role)
    4. Backend updates password
    5. Backend sends confirmation email
    6. User can login with new password
    
    **Usage:**
    ```
    POST /api/v1/auth/forgot-password/verify
    {
        "email": "doctor@example.com",
        "role": "DOCTOR",
        "otp": "123456",
        "new_password": "MyNewSecurePass123!",
        "confirm_password": "MyNewSecurePass123!"
    }
    ```
    
    **Response (Success):**
    ```
    {
        "message": "Password reset successfully. You can now login with your new password."
    }
    ```
    
    **Response (Invalid/Expired OTP):**
    ```
    {
        "detail": "Invalid or expired OTP"
    }
    ```
    
    **Password Requirements:**
    - Minimum 8 characters
    - Maximum 72 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
    
    **Frontend Integration:**
    ```javascript
    // Step 1: Request OTP
    await api.post('/auth/forgot-password', {
        email: 'doctor@example.com',
        role: 'DOCTOR'
    });
    
    // Show message: "OTP sent to your email"
    
    // Step 2: User enters OTP and new password
    await api.post('/auth/forgot-password/verify', {
        email: 'doctor@example.com',
        role: 'DOCTOR',
        otp: '123456',
        new_password: 'MyNewSecurePass123!',
        confirm_password: 'MyNewSecurePass123!'
    });
    
    // Show message: "Password reset successfully"
    // Redirect to login page
    router.push('/login');
    ```
    """
    from app.api.v1.auth.service import reset_password_with_otp
    
    return await reset_password_with_otp(
        email=request_data.email,
        role=request_data.role,
        otp=request_data.otp,
        new_password=request_data.new_password,
        request=request
    )
