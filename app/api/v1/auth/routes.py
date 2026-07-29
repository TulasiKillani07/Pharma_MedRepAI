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
    **Purpose:** Authenticate user and return JWT token.

    **Access:** ADMIN and MR only. Doctor login is blocked (use DRX Doctor Platform).

    **Request Body:**
    ```json
    {
      "email": "admin@xyzpharma.com",
      "password": "Welcome@123",
      "role": "ADMIN"
    }
    ```

    **Response:**
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIs...",
      "token_type": "bearer",
      "expires_in": 3600,
      "user": {
        "id": "507f1f77bcf86cd799439011",
        "email": "admin@xyzpharma.com",
        "full_name": "Admin User",
        "role": "ADMIN"
      },
      "must_change_password": false
    }
    ```

    **Roles:** `ADMIN`, `MR`
    - `DOCTOR` role returns 403 — doctors must use DRX platform.

    **Use the access_token in subsequent requests:**
    ```
    Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
    ```
    """
    return await login_user(login_request.email, login_request.password, login_request.role, request)


@router.post("/register/admin", response_model=MessageResponse, summary="Register Admin")
async def register_admin_endpoint(request: RegisterAdminRequest):
    """
    **Purpose:** Register a new company admin (self-registration for first admin).

    **Access:** Public (no auth required)

    **Request Body:**
    ```json
    {
      "email": "admin@xyzpharma.com",
      "password": "SecurePass123!",
      "full_name": "John Admin",
      "phone": "+919876543210",
      "company_name": "XYZ Pharma"
    }
    ```

    **Response:**
    ```json
    {
      "message": "Admin registered successfully",
      "user_id": "507f1f77bcf86cd799439011"
    }
    ```

    **Notes:**
    - Only one admin can self-register (first admin)
    - Additional admins are created by the General Admin via admin management
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
    **Purpose:** Get current authenticated user information.

    **Access:** Admin and MR only (requires JWT token)

    **Request Body:** None

    **Response:**
    ```json
    {
      "_id": "507f1f77bcf86cd799439011",
      "email": "admin@xyzpharma.com",
      "full_name": "Admin User",
      "role": "ADMIN",
      "is_active": true,
      "created_at": "2026-01-01T00:00:00"
    }
    ```
    """
    return current_user


@router.post("/logout", summary="Logout")
async def logout(request: Request, current_user: dict = Depends(get_current_user)):
    """
    **Purpose:** Log user logout activity. JWT is stateless — frontend deletes token.

    **Access:** Admin and MR only

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Logged out successfully" }
    ```
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
    **Purpose:** Change password for authenticated users (Admin or MR).

    **Access:** Admin and MR only

    **Request Body:**
    ```json
    {
      "current_password": "OldPass123!",
      "new_password": "NewSecurePass123!",
      "confirm_password": "NewSecurePass123!"
    }
    ```

    **Response:**
    ```json
    {
      "message": "Password changed successfully",
      "access_token": "eyJhbGciOiJIUzI1NiIs...",
      "token_type": "bearer",
      "expires_in": 3600
    }
    ```

    **Password Requirements:** Min 8 chars, uppercase, lowercase, number, special character.
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
    **Purpose:** Request password reset by sending OTP to email.

    **Access:** Public (no auth required). Roles: ADMIN, MR only.

    **Request Body:**
    ```json
    {
      "email": "admin@xyzpharma.com",
      "role": "ADMIN"
    }
    ```

    **Response:**
    ```json
    {
      "message": "If an account exists with this email, you will receive a password reset OTP",
      "expires_in": 900
    }
    ```

    **Notes:**
    - Returns generic message even if email doesn't exist (prevents enumeration)
    - OTP expires in 15 minutes
    - DOCTOR role is blocked — doctors use DRX platform
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
    **Purpose:** Reset password using OTP received via email.

    **Access:** Public (no auth required). Roles: ADMIN, MR only.

    **Request Body:**
    ```json
    {
      "email": "admin@xyzpharma.com",
      "role": "ADMIN",
      "otp": "123456",
      "new_password": "MyNewSecurePass123!",
      "confirm_password": "MyNewSecurePass123!"
    }
    ```

    **Response:**
    ```json
    { "message": "Password reset successfully. You can now login with your new password." }
    ```

    **Errors:**
    - 400: Invalid or expired OTP
    - 400: Passwords don't match

    **Password Requirements:** Min 8 chars, uppercase, lowercase, number, special character.
    """
    from app.api.v1.auth.service import reset_password_with_otp
    
    return await reset_password_with_otp(
        email=request_data.email,
        role=request_data.role,
        otp=request_data.otp,
        new_password=request_data.new_password,
        request=request
    )
