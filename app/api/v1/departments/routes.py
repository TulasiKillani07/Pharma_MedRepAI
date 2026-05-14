"""
Department routes - API endpoints for department management.
Only general admins can manage departments.
"""

from fastapi import APIRouter, Depends, status
from typing import Dict, Any
from app.core.auth import require_admin
from app.api.v1.departments.schemas import (
    DepartmentCreateRequest,
    DepartmentUpdateRequest,
    DepartmentResponse,
    DepartmentListResponse,
    MessageResponse
)
from app.api.v1.departments.service import (
    get_all_departments,
    create_department,
    update_department,
    deactivate_department
)


router = APIRouter()


@router.get(
    "",
    response_model=DepartmentListResponse,
    summary="Get all departments",
    description="Get list of all departments. Only active departments by default."
)
async def list_departments(
    include_inactive: bool = False,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Get all departments.
    
    Query Parameters:
    - include_inactive: Include inactive departments (default: False)
    
    Returns:
    - List of departments sorted by order
    """
    departments = await get_all_departments(include_inactive=include_inactive)
    
    return {
        "total": len(departments),
        "departments": departments
    }


@router.post(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new department",
    description="Create a new department. Only general admins can create departments."
)
async def create_new_department(
    request: DepartmentCreateRequest,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Create a new department.
    
    Request Body:
    - code: Unique department code (lowercase, no spaces)
    - name: Department display name
    - description: Optional description
    - order: Display order
    
    Returns:
    - Success message
    """
    # Check if user is general admin
    if current_user.get("department", "general") != "general":
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only general admins can create departments"
        )
    
    result = await create_department(
        code=request.code,
        name=request.name,
        description=request.description,
        order=request.order,
        current_user=current_user
    )
    
    return result


@router.put(
    "/{code}",
    response_model=MessageResponse,
    summary="Update department",
    description="Update department details. Only general admins can update departments."
)
async def update_existing_department(
    code: str,
    request: DepartmentUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Update department details.
    
    Path Parameters:
    - code: Department code
    
    Request Body (all optional):
    - name: Updated name
    - description: Updated description
    - is_active: Active status
    - order: Display order
    
    Returns:
    - Success message
    """
    # Check if user is general admin
    if current_user.get("department", "general") != "general":
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only general admins can update departments"
        )
    
    update_data = request.model_dump(exclude_unset=True)
    
    result = await update_department(
        code=code,
        update_data=update_data,
        current_user=current_user
    )
    
    return result


@router.delete(
    "/{code}",
    response_model=MessageResponse,
    summary="Deactivate department",
    description="Deactivate a department (soft delete). Only general admins can deactivate departments."
)
async def delete_department(
    code: str,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Deactivate a department (soft delete).
    
    Path Parameters:
    - code: Department code
    
    Returns:
    - Success message
    """
    # Check if user is general admin
    if current_user.get("department", "general") != "general":
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only general admins can deactivate departments"
        )
    
    result = await deactivate_department(
        code=code,
        current_user=current_user
    )
    
    return result
