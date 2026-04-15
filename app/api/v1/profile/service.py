"""
Profile Business Logic
"""

from datetime import datetime
from typing import Dict, Any, Optional
from bson import ObjectId
from app.database import get_database
from fastapi import HTTPException


async def get_my_profile(current_user: Dict) -> Dict[str, Any]:
    """
    Get current user's complete profile.
    Admin/Manager profiles are separate from company info.
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        dict: Complete profile with all fields
    """
    db = get_database()
    
    user_id = current_user["_id"]
    role = current_user["role"]
    
    # Get user from appropriate collection
    if role == "DOCTOR":
        user = await db["doctors"].find_one({"_id": ObjectId(user_id)})
    elif role == "MR":
        user = await db["mrs"].find_one({"_id": ObjectId(user_id)})
    elif role in ["ADMIN", "MANAGER"]:
        user = await db["company_admins"].find_one({"_id": ObjectId(user_id)})
    else:
        raise HTTPException(status_code=403, detail="Invalid role")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Format response (include all fields)
    profile = {
        "user_id": str(user["_id"]),
        "email": user.get("email", ""),
        "full_name": user.get("full_name" if role in ["ADMIN", "MANAGER"] else "name", ""),
        "phone": user.get("phone", ""),
        "role": role,
        "is_active": user.get("is_active", True),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at")
    }
    
    # Add role-specific fields
    if role == "DOCTOR":
        profile["bio"] = user.get("bio")
        profile["avatar_url"] = user.get("avatar_url")
        profile["location"] = user.get("location")
        profile["experience_years"] = user.get("experience_years")
        profile["specialization"] = user.get("specialization")
        profile["hospital"] = user.get("hospital")
        profile["license_number"] = user.get("license_number")
        profile["territory"] = None
        profile["admin_bio"] = None
        profile["admin_avatar_url"] = None
        
    elif role == "MR":
        profile["bio"] = user.get("bio")
        profile["avatar_url"] = user.get("avatar_url")
        profile["location"] = user.get("location")
        profile["experience_years"] = user.get("experience_years")
        profile["specialization"] = None
        profile["hospital"] = None
        profile["license_number"] = None
        profile["territory"] = user.get("territory")
        profile["admin_bio"] = None
        profile["admin_avatar_url"] = None
        
    elif role in ["ADMIN", "MANAGER"]:
        # Admin/Manager personal fields only (company info fetched separately)
        profile["bio"] = None
        profile["avatar_url"] = None
        profile["location"] = None
        profile["experience_years"] = None
        profile["specialization"] = None
        profile["hospital"] = None
        profile["license_number"] = None
        profile["territory"] = None
        profile["admin_bio"] = user.get("admin_bio")
        profile["admin_avatar_url"] = user.get("admin_avatar_url")
    
    return profile


async def update_my_profile(
    update_data: Dict[str, Any],
    current_user: Dict
) -> Dict[str, str]:
    """
    Update current user's profile.
    
    Args:
        update_data: Fields to update
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    user_id = current_user["_id"]
    role = current_user["role"]
    
    # Build update document
    update_doc = {}
    
    # Common fields
    if update_data.get("phone") is not None:
        update_doc["phone"] = update_data["phone"]
    
    # Role-specific handling
    if role == "DOCTOR":
        if update_data.get("full_name") is not None:
            update_doc["name"] = update_data["full_name"]
        
        if update_data.get("bio") is not None:
            update_doc["bio"] = update_data["bio"]
        
        if "avatar_url" in update_data:
            update_doc["avatar_url"] = update_data["avatar_url"]
        
        if update_data.get("location") is not None:
            update_doc["location"] = update_data["location"]
        
        if update_data.get("experience_years") is not None:
            update_doc["experience_years"] = update_data["experience_years"]
        
        if update_data.get("specialization") is not None:
            update_doc["specialization"] = update_data["specialization"]
        
        if update_data.get("hospital") is not None:
            update_doc["hospital"] = update_data["hospital"]
        
        # Reject MR/Admin fields
        if update_data.get("territory") is not None:
            raise HTTPException(status_code=400, detail="Doctors cannot update territory field")
        if any(k.startswith("company_") or k.startswith("admin_") for k in update_data.keys()):
            raise HTTPException(status_code=400, detail="Doctors cannot update company/admin fields")
    
    elif role == "MR":
        if update_data.get("full_name") is not None:
            update_doc["name"] = update_data["full_name"]
        
        if update_data.get("bio") is not None:
            update_doc["bio"] = update_data["bio"]
        
        if "avatar_url" in update_data:
            update_doc["avatar_url"] = update_data["avatar_url"]
        
        if update_data.get("location") is not None:
            update_doc["location"] = update_data["location"]
        
        if update_data.get("experience_years") is not None:
            update_doc["experience_years"] = update_data["experience_years"]
        
        if update_data.get("territory") is not None:
            update_doc["territory"] = update_data["territory"]
        
        # Reject doctor/admin fields
        if update_data.get("specialization") is not None or update_data.get("hospital") is not None:
            raise HTTPException(status_code=400, detail="MRs cannot update doctor-specific fields")
        if any(k.startswith("company_") or k.startswith("admin_") for k in update_data.keys()):
            raise HTTPException(status_code=400, detail="MRs cannot update company/admin fields")
    
    elif role in ["ADMIN", "MANAGER"]:
        if update_data.get("full_name") is not None:
            update_doc["full_name"] = update_data["full_name"]
        
        # Admin/Manager personal fields only
        if update_data.get("admin_bio") is not None:
            update_doc["admin_bio"] = update_data["admin_bio"]
        
        if "admin_avatar_url" in update_data:
            update_doc["admin_avatar_url"] = update_data["admin_avatar_url"]
        
        # Reject doctor/MR fields
        if any(k in update_data for k in ["bio", "avatar_url", "location", "experience_years", "specialization", "hospital", "territory"]):
            raise HTTPException(status_code=400, detail="Admin/Manager cannot update doctor/MR-specific fields")
        
        # Reject company fields (must use PUT /profile/company instead)
        if any(k.startswith("company_") for k in update_data.keys()):
            raise HTTPException(status_code=400, detail="Cannot update company fields here. Use PUT /api/v1/profile/company instead")
    
    else:
        raise HTTPException(status_code=403, detail="Invalid role")
    
    # Check if there's anything to update
    if not update_doc:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    # Add updated_at timestamp
    update_doc["updated_at"] = datetime.utcnow()
    
    # Update in appropriate collection
    if role == "DOCTOR":
        collection = "doctors"
    elif role == "MR":
        collection = "mrs"
    else:  # ADMIN or MANAGER
        collection = "company_admins"
    
    result = await db[collection].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_doc}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Profile updated successfully"}


async def get_user_profile(
    user_id: str,
    current_user: Dict
) -> Dict[str, Any]:
    """
    Get another user's public profile.
    
    Args:
        user_id: User ID to view
        current_user: Current authenticated user
    
    Returns:
        dict: Public profile information
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Cannot view own profile through this endpoint
    if user_id == current_user["_id"]:
        raise HTTPException(
            status_code=400,
            detail="Use GET /profile/me to view your own profile"
        )
    
    # Check if current user has permission
    current_role = current_user["role"]
    if current_role not in ["DOCTOR", "MR", "ADMIN", "MANAGER"]:
        raise HTTPException(status_code=403, detail="Invalid role")
    
    # Find user in both collections
    user = await db["doctors"].find_one({"_id": ObjectId(user_id)})
    user_role = "DOCTOR"
    
    if not user:
        user = await db["mrs"].find_one({"_id": ObjectId(user_id)})
        user_role = "MR"
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check connection status (only for doctors/MRs, admin sees all)
    is_connected = False
    connection_status = "not_connected"
    
    if current_role in ["DOCTOR", "MR"]:
        requester_id = current_user["_id"]
        connection = await db["connections"].find_one({
            "$or": [
                {"requester_id": requester_id, "receiver_id": user_id},
                {"requester_id": user_id, "receiver_id": requester_id}
            ]
        })
        
        if connection:
            if connection["status"] == "accepted":
                is_connected = True
                connection_status = "connected"
            elif connection["status"] == "pending":
                connection_status = "pending"
            elif connection["status"] == "blocked":
                raise HTTPException(status_code=403, detail="Cannot view this user's profile")
    else:
        # Admin/Manager can view all profiles (no connection check)
        is_connected = True
        connection_status = "company_staff_view"
    
    # Format public profile (no email, phone, license_number)
    profile = {
        "user_id": str(user["_id"]),
        "full_name": user.get("name", ""),
        "role": user_role,
        "bio": user.get("bio"),
        "avatar_url": user.get("avatar_url"),
        "location": user.get("location"),
        "experience_years": user.get("experience_years"),
        "is_connected": is_connected,
        "connection_status": connection_status
    }
    
    # Add role-specific public fields
    if user_role == "DOCTOR":
        profile["specialization"] = user.get("specialization")
        profile["hospital"] = user.get("hospital")
        profile["territory"] = None
    elif user_role == "MR":
        profile["specialization"] = None
        profile["hospital"] = None
        profile["territory"] = user.get("territory")
    
    return profile



async def get_company_profile(current_user: Dict) -> Dict[str, Any]:
    """
    Get company profile (public fields only).
    Fetches from separate 'company' collection (single document).
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        dict: Public company profile
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    role = current_user["role"]
    
    # Only doctors, MRs, and company staff can view company profile
    if role not in ["DOCTOR", "MR", "ADMIN", "MANAGER"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get THE company (only one document exists)
    company = await db["company"].find_one({})
    
    if not company:
        raise HTTPException(status_code=404, detail="Company profile not found")
    
    # Return public company fields only
    return {
        "company_name": company.get("company_name", ""),
        "company_logo_url": company.get("company_logo_url"),
        "company_description": company.get("company_description"),
        "company_city": company.get("company_city"),
        "company_state": company.get("company_state"),
        "company_country": company.get("company_country"),
        "company_website": company.get("company_website"),
        "company_industry": company.get("company_industry"),
        "company_founded_year": company.get("company_founded_year"),
        "company_size": company.get("company_size")
    }


async def update_company_profile(
    update_data: Dict[str, Any],
    current_user: Dict
) -> Dict[str, str]:
    """
    Update company profile with role-based permissions.
    - ADMIN: Can update all fields (name, GST, PAN, logo, description, etc.)
    - MANAGER: Can only update logo and description (not name, GST, PAN)
    
    Args:
        update_data: Fields to update
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails or insufficient permissions
    """
    db = get_database()
    
    role = current_user["role"]
    
    # Only ADMIN and MANAGER can update company profile
    if role not in ["ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=403,
            detail="Only admin and manager can update company profile"
        )
    
    # Define field permissions
    admin_only_fields = [
        "company_name",           # Admin only
        "company_gst_number",     # Admin only
        "company_pan_number",     # Admin only
        "company_address",        # Admin only (sensitive)
        "company_pincode",        # Admin only (sensitive)
    ]
    
    manager_allowed_fields = [
        "company_logo_url",       # Manager can update
        "company_description",    # Manager can update
        "company_city",           # Manager can update
        "company_state",          # Manager can update
        "company_country",        # Manager can update
        "company_website",        # Manager can update
        "company_industry",       # Manager can update
        "company_founded_year",   # Manager can update
        "company_size",           # Manager can update
    ]
    
    all_company_fields = admin_only_fields + manager_allowed_fields
    
    # Build update document
    update_doc = {}
    
    for field, value in update_data.items():
        if field not in all_company_fields:
            continue  # Skip unknown fields
        
        # Check permissions
        if role == "MANAGER" and field in admin_only_fields:
            raise HTTPException(
                status_code=403,
                detail=f"Manager cannot update {field}. Only admin can update company name, GST, PAN, and address."
            )
        
        update_doc[field] = value
    
    if not update_doc:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    update_doc["updated_at"] = datetime.utcnow()
    
    # Update THE company (only one document exists)
    result = await db["company"].update_one(
        {},  # Match any document (only one exists)
        {"$set": update_doc}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return {"message": "Company profile updated successfully"}
