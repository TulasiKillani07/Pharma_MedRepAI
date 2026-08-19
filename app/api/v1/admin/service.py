"""
Admin management service - Business logic for admin management.
"""

from datetime import datetime
from typing import List, Dict, Any
from fastapi import HTTPException, status
from app.database import get_database
from app.core.security import hash_password
from bson import ObjectId
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)


async def create_department_admin(
    username: str,
    email: str,
    password: str,
    full_name: str,
    phone: str,
    department: str,
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a department admin (HR, Finance, IT).
    Only general admin can create department admins.
    
    Args:
        username: Global unique username (same across Proxzar, DOBO, DRX, MRX)
        email: Admin email
        password: Plain text password
        full_name: Admin full name
        phone: Phone number
        department: Department code (hr, finance, it)
        current_user: Current authenticated general admin
    
    Returns:
        dict: Success message with admin details
    
    Raises:
        HTTPException: If email/username already exists, department is invalid, or access limit reached
    """
    db = get_database()
    
    # Check access limit for admin users
    company_doc = await db.company.find_one({})
    if company_doc:
        max_admin_users = company_doc.get("max_admin_users", 2)
        
        # Count current active non-general admins (department admins only)
        current_admin_count = await db.company_admins.count_documents({
            "is_active": True,
            "department": {"$ne": "general"}  # Exclude general admin from count
        })
        
        if current_admin_count >= max_admin_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Admin user limit reached. Maximum allowed: {max_admin_users}. Current: {current_admin_count}. Please contact support to increase your license limit."
            )
    
    # Check if username already exists
    existing_username = await db.company_admins.find_one({"username": username})
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    existing_user = await db.company_admins.find_one({"email": email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate department exists and is active
    dept = await db.departments.find_one({"code": department.lower(), "is_active": True})
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department '{department}' not found or inactive"
        )
    
    # Hash password
    password_hash = hash_password(password)
    
    # Create admin using AdminInDB model
    from app.models.admin_model import AdminInDB
    admin = AdminInDB(
        username=username,
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        phone=phone,
        department=department.lower(),
        role="ADMIN",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # Convert to dict and add DB-specific field
    admin_doc = admin.model_dump()
    admin_doc["created_by"] = current_user["_id"]  # DB-specific field: track who created this admin
    
    # Insert admin into database
    result = await db.company_admins.insert_one(admin_doc)
    
    logger.info(f"Department admin created: {email} (department: {department}) by {current_user.get('full_name', 'Unknown')}")
    
    return {
        "message": "Department admin created successfully",
        "admin_id": str(result.inserted_id),
        "email": email,
        "department": department
    }


async def get_all_admins(
    current_user: Dict[str, Any],
    include_inactive: bool = False
) -> List[Dict[str, Any]]:
    """
    Get all admins (general admin only).
    
    Args:
        current_user: Current authenticated general admin
        include_inactive: Whether to include inactive admins
    
    Returns:
        list: List of admin documents
    """
    db = get_database()
    
    query = {} if include_inactive else {"is_active": True}
    
    admins = await db.company_admins.find(query).sort("created_at", -1).to_list(None)
    
    # Format response
    admin_list = []
    for admin in admins:
        admin_list.append({
            "id": str(admin["_id"]),
            "email": admin["email"],
            "full_name": admin["full_name"],
            "phone": admin["phone"],
            "department": admin.get("department", "general"),
            "is_active": admin.get("is_active", True),
            "created_at": admin["created_at"]
        })
    
    return admin_list


async def update_admin_department(
    admin_id: str,
    new_department: str,
    current_user: Dict[str, Any]
) -> Dict[str, str]:
    """
    Update admin's department (general admin only).
    
    Args:
        admin_id: Admin ID to update
        new_department: New department code
        current_user: Current authenticated general admin
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If admin not found or department invalid
    """
    db = get_database()
    
    # Check if admin exists
    admin = await db.company_admins.find_one({"_id": ObjectId(admin_id)})
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    # Validate department exists and is active (if not general)
    if new_department != "general":
        dept = await db.departments.find_one({"code": new_department.lower(), "is_active": True})
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department '{new_department}' not found or inactive"
            )
    
    # Update department
    await db.company_admins.update_one(
        {"_id": ObjectId(admin_id)},
        {
            "$set": {
                "department": new_department.lower(),
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    logger.info(f"Admin department updated: {admin['email']} → {new_department}")
    
    return {"message": f"Admin department updated to {new_department}"}


async def deactivate_admin(
    admin_id: str,
    current_user: Dict[str, Any]
) -> Dict[str, str]:
    """
    Deactivate admin (general admin only).
    Cannot deactivate yourself.
    
    Args:
        admin_id: Admin ID to deactivate
        current_user: Current authenticated general admin
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If admin not found or trying to deactivate self
    """
    db = get_database()
    
    # Check if trying to deactivate self
    if admin_id == current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    # Check if admin exists
    admin = await db.company_admins.find_one({"_id": ObjectId(admin_id)})
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    # Deactivate
    await db.company_admins.update_one(
        {"_id": ObjectId(admin_id)},
        {
            "$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    logger.info(f"Admin deactivated: {admin['email']}")
    
    return {"message": f"Admin {admin['email']} deactivated successfully"}


async def reactivate_admin(
    admin_id: str,
    current_user: Dict[str, Any]
) -> Dict[str, str]:
    """
    Reactivate admin (general admin only).
    
    Args:
        admin_id: Admin ID to reactivate
        current_user: Current authenticated general admin
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If admin not found
    """
    db = get_database()
    
    # Check if admin exists
    admin = await db.company_admins.find_one({"_id": ObjectId(admin_id)})
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    # Reactivate
    await db.company_admins.update_one(
        {"_id": ObjectId(admin_id)},
        {
            "$set": {
                "is_active": True,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    logger.info(f"Admin reactivated: {admin['email']}")
    
    return {"message": f"Admin {admin['email']} reactivated successfully"}
