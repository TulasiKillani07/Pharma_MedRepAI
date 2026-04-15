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
    else:
        raise HTTPException(status_code=403, detail="Only doctors and MRs can access profiles")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Format response (include all fields)
    profile = {
        "user_id": str(user["_id"]),
        "email": user.get("email", ""),
        "full_name": user.get("name", ""),
        "phone": user.get("phone", ""),
        "role": role,
        "bio": user.get("bio"),
        "avatar_url": user.get("avatar_url"),
        "location": user.get("location"),
        "experience_years": user.get("experience_years"),
        "is_active": user.get("is_active", True),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at")
    }
    
    # Add role-specific fields
    if role == "DOCTOR":
        profile["specialization"] = user.get("specialization")
        profile["hospital"] = user.get("hospital")
        profile["license_number"] = user.get("license_number")
        profile["territory"] = None
    elif role == "MR":
        profile["specialization"] = None
        profile["hospital"] = None
        profile["license_number"] = None
        profile["territory"] = user.get("territory")
    
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
    
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(status_code=403, detail="Only doctors and MRs can update profiles")
    
    # Build update document
    update_doc = {}
    
    # Common fields
    if update_data.get("full_name") is not None:
        update_doc["name"] = update_data["full_name"]
    
    if update_data.get("phone") is not None:
        update_doc["phone"] = update_data["phone"]
    
    if update_data.get("bio") is not None:
        update_doc["bio"] = update_data["bio"]
    
    if "avatar_url" in update_data:  # Allow null to remove avatar
        update_doc["avatar_url"] = update_data["avatar_url"]
    
    if update_data.get("location") is not None:
        update_doc["location"] = update_data["location"]
    
    if update_data.get("experience_years") is not None:
        update_doc["experience_years"] = update_data["experience_years"]
    
    # Role-specific fields
    if role == "DOCTOR":
        if update_data.get("specialization") is not None:
            update_doc["specialization"] = update_data["specialization"]
        
        if update_data.get("hospital") is not None:
            update_doc["hospital"] = update_data["hospital"]
        
        # Ignore MR-specific fields
        if update_data.get("territory") is not None:
            raise HTTPException(status_code=400, detail="Doctors cannot update territory field")
    
    elif role == "MR":
        if update_data.get("territory") is not None:
            update_doc["territory"] = update_data["territory"]
        
        # Ignore doctor-specific fields
        if update_data.get("specialization") is not None or update_data.get("hospital") is not None:
            raise HTTPException(status_code=400, detail="MRs cannot update doctor-specific fields")
    
    # Check if there's anything to update
    if not update_doc:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    # Add updated_at timestamp
    update_doc["updated_at"] = datetime.utcnow()
    
    # Update in appropriate collection
    collection = "doctors" if role == "DOCTOR" else "mrs"
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
    if current_role not in ["DOCTOR", "MR"]:
        raise HTTPException(status_code=403, detail="Only doctors and MRs can view profiles")
    
    # Find user in both collections
    user = await db["doctors"].find_one({"_id": ObjectId(user_id)})
    user_role = "DOCTOR"
    
    if not user:
        user = await db["mrs"].find_one({"_id": ObjectId(user_id)})
        user_role = "MR"
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check connection status
    requester_id = current_user["_id"]
    connection = await db["connections"].find_one({
        "$or": [
            {"requester_id": requester_id, "receiver_id": user_id},
            {"requester_id": user_id, "receiver_id": requester_id}
        ]
    })
    
    is_connected = False
    connection_status = "not_connected"
    
    if connection:
        if connection["status"] == "accepted":
            is_connected = True
            connection_status = "connected"
        elif connection["status"] == "pending":
            connection_status = "pending"
        elif connection["status"] == "blocked":
            raise HTTPException(status_code=403, detail="Cannot view this user's profile")
    
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
