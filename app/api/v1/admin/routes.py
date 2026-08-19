"""
Admin management routes - API endpoints for managing admins.
Only general admin can access these endpoints.
"""

from fastapi import APIRouter, Depends, Query, status, HTTPException
from typing import Dict, Any
from app.core.auth import require_admin
from app.api.v1.admin.schemas import (
    CreateDepartmentAdminRequest,
    CreateAdminResponse,
    AdminListResponse,
    AdminResponse,
    UpdateAdminDepartmentRequest,
    MessageResponse
)
from app.api.v1.admin.service import (
    create_department_admin,
    get_all_admins,
    update_admin_department,
    deactivate_admin,
    reactivate_admin
)


router = APIRouter()


def require_general_admin(current_user: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    """
    Dependency to require general admin.
    Only general admin can manage other admins.
    """
    if current_user.get("department", "general") != "general":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only general admin can manage admins"
        )
    return current_user


@router.post(
    "/create-department-admin",
    response_model=CreateAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create department admin (General Admin Only)",
    description="General admin creates a new department admin (HR, Finance, IT)"
)
async def create_new_department_admin(
    request: CreateDepartmentAdminRequest,
    current_user: Dict[str, Any] = Depends(require_general_admin)
):
    """
    Create a new department admin.
    
    **Access:** General admin only
    
    **Request Body:**
    - email: Admin email address
    - password: Password (8-72 characters)
    - full_name: Full name
    - phone: Phone number
    - department: Department code (hr, finance, it)
    
    **Returns:**
    - Success message with admin details
    
    **Example:**
    ```json
    {
      "email": "hr.admin@xyzpharma.com",
      "password": "SecurePass123",
      "full_name": "Sarah HR Manager",
      "phone": "+919876543210",
      "department": "hr"
    }
    ```
    """
    result = await create_department_admin(
        username=request.username,
        email=request.email,
        password=request.password,
        full_name=request.full_name,
        phone=request.phone,
        department=request.department,
        current_user=current_user
    )
    
    return result


@router.get(
    "/list",
    response_model=AdminListResponse,
    summary="List all admins (General Admin Only)",
    description="Get list of all admins with their departments"
)
async def list_all_admins(
    include_inactive: bool = Query(False, description="Include inactive admins"),
    current_user: Dict[str, Any] = Depends(require_general_admin)
):
    """
    Get list of all admins.
    
    **Access:** General admin only
    
    **Query Parameters:**
    - include_inactive: Include inactive admins (default: False)
    
    **Returns:**
    - List of admins with their details
    """
    admins = await get_all_admins(
        current_user=current_user,
        include_inactive=include_inactive
    )
    
    return {
        "total": len(admins),
        "admins": admins
    }


@router.put(
    "/{admin_id}/department",
    response_model=MessageResponse,
    summary="Update admin department (General Admin Only)",
    description="Change an admin's department assignment"
)
async def update_admin_dept(
    admin_id: str,
    request: UpdateAdminDepartmentRequest,
    current_user: Dict[str, Any] = Depends(require_general_admin)
):
    """
    Update admin's department.
    
    **Access:** General admin only
    
    **Path Parameters:**
    - admin_id: Admin ID to update
    
    **Request Body:**
    - department: New department code (general, hr, finance, it)
    
    **Returns:**
    - Success message
    """
    result = await update_admin_department(
        admin_id=admin_id,
        new_department=request.department,
        current_user=current_user
    )
    
    return result


@router.delete(
    "/{admin_id}",
    response_model=MessageResponse,
    summary="Deactivate admin (General Admin Only)",
    description="Deactivate an admin account"
)
async def deactivate_admin_account(
    admin_id: str,
    current_user: Dict[str, Any] = Depends(require_general_admin)
):
    """
    Deactivate an admin account.
    
    **Access:** General admin only
    
    **Path Parameters:**
    - admin_id: Admin ID to deactivate
    
    **Returns:**
    - Success message
    
    **Note:** Cannot deactivate your own account
    """
    result = await deactivate_admin(
        admin_id=admin_id,
        current_user=current_user
    )
    
    return result


@router.post(
    "/{admin_id}/reactivate",
    response_model=MessageResponse,
    summary="Reactivate admin (General Admin Only)",
    description="Reactivate a deactivated admin account"
)
async def reactivate_admin_account(
    admin_id: str,
    current_user: Dict[str, Any] = Depends(require_general_admin)
):
    """
    Reactivate an admin account.
    
    **Access:** General admin only
    
    **Path Parameters:**
    - admin_id: Admin ID to reactivate
    
    **Returns:**
    - Success message
    """
    result = await reactivate_admin(
        admin_id=admin_id,
        current_user=current_user
    )
    
    return result
