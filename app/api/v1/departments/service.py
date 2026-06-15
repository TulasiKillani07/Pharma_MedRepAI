"""
Department service - Business logic for department management.
"""

from datetime import datetime
from typing import List, Dict, Any
from fastapi import HTTPException, status
from app.database import get_database
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)


async def get_all_departments(include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Get all departments.
    
    Args:
        include_inactive: Whether to include inactive departments
    
    Returns:
        list: List of department documents
    """
    db = get_database()
    
    query = {} if include_inactive else {"is_active": True}
    
    departments = await db.departments.find(query).sort("order", 1).to_list(None)
    
    # Convert ObjectId to string
    for dept in departments:
        if "_id" in dept:
            dept.pop("_id")
    
    return departments


async def create_department(
    code: str,
    name: str,
    description: str,
    order: int,
    current_user: Dict[str, Any]
) -> Dict[str, str]:
    """
    Create a new department (general admin only).
    
    Args:
        code: Department code
        name: Department name
        description: Department description
        order: Display order
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If department code already exists
    """
    db = get_database()
    
    # Check if code already exists
    existing = await db.departments.find_one({"code": code.lower()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department with code '{code}' already exists"
        )
    
    # Create department document
    dept_doc = {
        "code": code.lower(),
        "name": name,
        "description": description,
        "is_active": True,
        "order": order,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    await db.departments.insert_one(dept_doc)
    
    logger.info(f"Department created: {code}")
    
    return {"message": f"Department '{name}' created successfully"}


async def update_department(
    code: str,
    update_data: Dict[str, Any],
    current_user: Dict[str, Any]
) -> Dict[str, str]:
    """
    Update department (general admin only).
    
    Args:
        code: Department code
        update_data: Fields to update
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If department not found
    """
    db = get_database()
    
    # Check if department exists
    dept = await db.departments.find_one({"code": code.lower()})
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department '{code}' not found"
        )
    
    # Remove None values
    update_data = {k: v for k, v in update_data.items() if v is not None}
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    # Add updated_at
    update_data["updated_at"] = datetime.utcnow()
    
    # Update department
    await db.departments.update_one(
        {"code": code.lower()},
        {"$set": update_data}
    )
    
    logger.info(f"Department updated: {code}")
    
    return {"message": f"Department '{code}' updated successfully"}


async def deactivate_department(
    code: str,
    current_user: Dict[str, Any]
) -> Dict[str, str]:
    """
    Deactivate department (soft delete, general admin only).
    
    Args:
        code: Department code
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If department not found
    """
    db = get_database()
    
    # Check if department exists
    dept = await db.departments.find_one({"code": code.lower()})
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department '{code}' not found"
        )
    
    # Deactivate
    await db.departments.update_one(
        {"code": code.lower()},
        {
            "$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    logger.info(f"Department deactivated: {code}")
    
    return {"message": f"Department '{code}' deactivated successfully"}
