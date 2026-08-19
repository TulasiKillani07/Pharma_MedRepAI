"""
Authentication routes - API endpoints for MRX authentication.

MRX uses Proxzar as its only authentication provider.
Local email/password login is deprecated.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from app.api.v1.auth.schemas import (
    RegisterAdminRequest,
    MessageResponse,
)
from app.api.v1.auth.service import register_admin
from app.core.auth import get_current_user


# Create router for auth endpoints
router = APIRouter()


# ============================================================================
# DEPRECATED ENDPOINTS — Authentication is now handled by Proxzar
# ============================================================================

_PROXZAR_DEPRECATION_MSG = "MRX authentication is now handled by Proxzar. Please authenticate through Proxzar OAuth."
_PASSWORD_DEPRECATION_MSG = "Password management is handled by Proxzar."


@router.post("/login", summary="[DEPRECATED] Login", include_in_schema=False)
async def login():
    """
    DEPRECATED: MRX no longer issues its own JWTs.
    Authentication is handled by Proxzar OAuth.
    """
    return JSONResponse(
        status_code=status.HTTP_410_GONE,
        content={"detail": _PROXZAR_DEPRECATION_MSG}
    )


@router.post("/reset-password", summary="[DEPRECATED] Reset Password", include_in_schema=False)
async def reset_password_endpoint():
    """
    DEPRECATED: Password management is handled by Proxzar.
    """
    return JSONResponse(
        status_code=status.HTTP_410_GONE,
        content={"detail": _PASSWORD_DEPRECATION_MSG}
    )


@router.post("/forgot-password", summary="[DEPRECATED] Forgot Password", include_in_schema=False)
async def forgot_password_endpoint():
    """
    DEPRECATED: Password management is handled by Proxzar.
    """
    return JSONResponse(
        status_code=status.HTTP_410_GONE,
        content={"detail": _PASSWORD_DEPRECATION_MSG}
    )


@router.post("/forgot-password/verify", summary="[DEPRECATED] Reset Password with OTP", include_in_schema=False)
async def reset_password_with_otp_endpoint():
    """
    DEPRECATED: Password management is handled by Proxzar.
    """
    return JSONResponse(
        status_code=status.HTTP_410_GONE,
        content={"detail": _PASSWORD_DEPRECATION_MSG}
    )


# ============================================================================
# ACTIVE ENDPOINTS
# ============================================================================

@router.post("/register/admin", response_model=MessageResponse, summary="Register Admin")
async def register_admin_endpoint(request: RegisterAdminRequest):
    """
    **Purpose:** Register a new company admin (self-registration for first admin).

    **Access:** Public (no auth required)

    **Request Body:**
    ```json
    {
      "username": "john_admin",
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
    - Username must match the actual Proxzar global username
    """
    return await register_admin(
        username=request.username,
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

    **Access:** Admin and MR only (requires Proxzar JWT token)

    **Headers:**
    ```
    Authorization: Bearer <Proxzar JWT>
    ```

    **Response:**
    ```json
    {
      "_id": "507f1f77bcf86cd799439011",
      "username": "john_admin",
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

    **Access:** Admin and MR only (requires Proxzar JWT)

    **Response:**
    ```json
    { "message": "Logged out successfully" }
    ```
    """
    from app.api.v1.activity_logs.helpers import log_activity
    from app.models.activity_log_model import ActivityLogAction, ActorRole, TargetType, LogSeverity

    # Determine target type and actor role based on user role
    role = current_user.get("role")
    if role == "MR":
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
