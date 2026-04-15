"""
Profile API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict
from app.core.auth import get_current_user
from app.api.v1.profile.schemas import (
    ProfileUpdateRequest,
    ProfileResponse,
    PublicProfileResponse
)
from app.api.v1.profile import service


router = APIRouter()


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile_endpoint(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get your own complete profile.
    
    **Access:** Doctor, MR only
    
    **Purpose:**
    View your complete profile including all private and public fields.
    
    **Flow:**
    1. User opens "My Profile" section
    2. System retrieves complete profile
    3. Returns all fields including email, phone, license number
    
    **Response:**
    ```json
    {
        "user_id": "507f1f77bcf86cd799439011",
        "email": "sarah@example.com",
        "full_name": "Dr. Sarah Sharma",
        "phone": "+919876543210",
        "role": "DOCTOR",
        "bio": "Cardiologist with 10 years of experience",
        "avatar_url": "https://example.com/avatars/sarah.jpg",
        "location": "Mumbai, Maharashtra",
        "experience_years": 10,
        "specialization": "Cardiology",
        "hospital": "Apollo Hospital",
        "license_number": "MH12345",
        "is_active": true,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-04-14T10:00:00"
    }
    ```
    
    **Use Cases:**
    - View own profile
    - Check profile completeness
    - See all personal information
    """
    return await service.get_my_profile(current_user)


@router.put("/me")
async def update_my_profile_endpoint(
    profile_data: ProfileUpdateRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Update your own profile.
    
    **Access:** Doctor, MR only
    
    **Purpose:**
    Update your profile information including bio, avatar, location, etc.
    
    **Flow:**
    1. User edits profile fields
    2. System validates changes
    3. Updates profile in database
    4. Returns success message
    
    **Request Body:**
    ```json
    {
        "full_name": "Dr. Sarah Sharma",
        "phone": "+919876543210",
        "bio": "Cardiologist with 10 years of experience specializing in interventional cardiology",
        "avatar_url": "https://example.com/avatars/sarah.jpg",
        "location": "Mumbai, Maharashtra",
        "experience_years": 10,
        "specialization": "Cardiology",
        "hospital": "Apollo Hospital"
    }
    ```
    
    **Response:**
    ```json
    {
        "message": "Profile updated successfully"
    }
    ```
    
    **Rules:**
    - All fields are optional (only send fields you want to update)
    - Cannot update: email, role, license_number
    - Doctors cannot update MR-specific fields (territory)
    - MRs cannot update doctor-specific fields (specialization, hospital)
    - To remove avatar: send `"avatar_url": null`
    - Full name: 2-100 characters
    - Bio: max 500 characters
    - Phone: 10-20 characters
    - Experience: 0-70 years
    
    **Use Cases:**
    - Update profile information
    - Add/update bio
    - Change profile picture
    - Update contact details
    - Remove avatar (send null)
    
    **Examples:**
    
    Update bio only:
    ```json
    {
        "bio": "Updated bio text"
    }
    ```
    
    Update avatar:
    ```json
    {
        "avatar_url": "https://example.com/new-avatar.jpg"
    }
    ```
    
    Remove avatar:
    ```json
    {
        "avatar_url": null
    }
    ```
    
    Update multiple fields:
    ```json
    {
        "full_name": "Dr. Sarah Sharma",
        "bio": "New bio",
        "location": "Delhi",
        "experience_years": 12
    }
    ```
    """
    # Convert Pydantic model to dict, excluding unset fields
    update_data = profile_data.model_dump(exclude_unset=True)
    
    return await service.update_my_profile(update_data, current_user)


@router.get("/{user_id}", response_model=PublicProfileResponse)
async def get_user_profile_endpoint(
    user_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    View another user's public profile.
    
    **Access:** Doctor, MR only
    
    **Purpose:**
    View public profile information of another user.
    
    **Flow:**
    1. User clicks on another user's name/profile
    2. System checks connection status
    3. Returns public profile information
    
    **Path Parameters:**
    - `user_id`: User ID to view
    
    **Response:**
    ```json
    {
        "user_id": "507f1f77bcf86cd799439011",
        "full_name": "Dr. Sarah Sharma",
        "role": "DOCTOR",
        "bio": "Cardiologist with 10 years of experience",
        "avatar_url": "https://example.com/avatars/sarah.jpg",
        "location": "Mumbai, Maharashtra",
        "experience_years": 10,
        "specialization": "Cardiology",
        "hospital": "Apollo Hospital",
        "is_connected": true,
        "connection_status": "connected"
    }
    ```
    
    **Public Fields (visible to others):**
    - Name, role, bio, avatar, location, experience
    - Specialization, hospital (doctors)
    - Territory (MRs)
    - Connection status
    
    **Private Fields (NOT visible):**
    - Email, phone, license number
    
    **Connection Status:**
    - `"connected"` - You are connected
    - `"pending"` - Connection request pending
    - `"not_connected"` - Not connected
    
    **Rules:**
    - Cannot view blocked users
    - Cannot view own profile (use GET /profile/me)
    - All profiles are public (anyone can view basic info)
    
    **Use Cases:**
    - View user profile before connecting
    - Check connected user's details
    - See user's specialization/territory
    - View user's bio and experience
    
    **Errors:**
    - 400: Trying to view own profile
    - 403: User is blocked or insufficient permissions
    - 404: User not found
    """
    return await service.get_user_profile(user_id, current_user)
