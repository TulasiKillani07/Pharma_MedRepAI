"""
Authentication routes - API endpoints for login and registration.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.api.v1.auth.schemas import (
    LoginRequest,
    TokenResponse,
    RegisterAdminRequest,
    MessageResponse
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
