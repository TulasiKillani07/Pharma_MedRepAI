"""
Profile API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict
from app.core.auth import get_current_user
from app.api.v1.profile.schemas import (
    ProfileUpdateRequest,
    ProfileResponse,
    PublicProfileResponse,
    CompanyProfileResponse,
    CompanyUpdateRequest
)
from app.api.v1.profile import service


router = APIRouter()


@router.get(
    "/me",
    response_model=ProfileResponse,
    responses={
        200: {
            "description": "Profile retrieved successfully. Response varies by role.",
            "content": {
                "application/json": {
                    "examples": {
                        "doctor": {
                            "summary": "Doctor Profile",
                            "description": "Profile response for a Doctor user",
                            "value": {
                                "user_id": "507f1f77bcf86cd799439011",
                                "email": "sarah@example.com",
                                "full_name": "Dr. Sarah Sharma",
                                "phone": "+919876543210",
                                "role": "DOCTOR",
                                "bio": "Cardiologist with 10 years of experience",
                                "avatar_url": "https://example.com/avatars/sarah.jpg",
                                "location": "Mumbai, Maharashtra",
                                "experience_years": 10.5,
                                "specialization": "Cardiology",
                                "hospital": "Apollo Hospital",
                                "license_number": "MH12345",
                                "territory": None,
                                "zone": None,
                                "state": None,
                                "admin_bio": None,
                                "admin_avatar_url": None,
                                "department": None,
                                "is_active": True,
                                "created_at": "2024-01-01T00:00:00",
                                "updated_at": "2024-04-14T10:00:00"
                            }
                        },
                        "mr": {
                            "summary": "MR Profile",
                            "description": "Profile response for a Medical Representative user",
                            "value": {
                                "user_id": "507f1f77bcf86cd799439012",
                                "email": "rajesh@example.com",
                                "full_name": "Rajesh Kumar",
                                "phone": "+919876543211",
                                "role": "MR",
                                "bio": "Medical Representative with 5 years experience",
                                "avatar_url": "https://example.com/avatars/rajesh.jpg",
                                "location": "Hyderabad, Telangana",
                                "experience_years": 5.0,
                                "specialization": None,
                                "hospital": None,
                                "license_number": None,
                                "territory": "Hyderabad",
                                "zone": "South",
                                "state": "Telangana",
                                "admin_bio": None,
                                "admin_avatar_url": None,
                                "department": None,
                                "is_active": True,
                                "created_at": "2024-01-01T00:00:00",
                                "updated_at": "2024-04-14T10:00:00"
                            }
                        },
                        "admin": {
                            "summary": "Admin Profile",
                            "description": "Profile response for an Admin user",
                            "value": {
                                "user_id": "507f1f77bcf86cd799439013",
                                "email": "admin@xyzpharma.com",
                                "full_name": "John Admin",
                                "phone": "+919876543212",
                                "role": "ADMIN",
                                "bio": None,
                                "avatar_url": None,
                                "location": None,
                                "experience_years": None,
                                "specialization": None,
                                "hospital": None,
                                "license_number": None,
                                "territory": None,
                                "zone": None,
                                "state": None,
                                "admin_bio": "CEO of XYZ Pharma",
                                "admin_avatar_url": "https://example.com/avatars/admin.jpg",
                                "department": "general",
                                "is_active": True,
                                "created_at": "2024-01-01T00:00:00",
                                "updated_at": "2024-04-14T10:00:00"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def get_my_profile_endpoint(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get your own complete profile.
    
    **Access:** Doctor, MR, Admin
    
    **Purpose:** View your complete profile including all private and public fields.
    
    **Response varies by role:**
    
    - **DOCTOR**: Includes specialization, hospital, license_number
    - **MR**: Includes territory, zone, state
    - **ADMIN**: Includes admin_bio, admin_avatar_url, department
    
    **Use the "Example Value" dropdown above to see role-specific responses.**
    """
    return await service.get_my_profile(current_user)


@router.put(
    "/me",
    responses={
        200: {
            "description": "Profile updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Profile updated successfully"
                    }
                }
            }
        }
    }
)
async def update_my_profile_endpoint(
    profile_data: ProfileUpdateRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Update your own profile.
    
    **Access:** Doctor, MR, Admin, Manager
    
    **Purpose:** Update your personal profile information (bio, avatar, location, etc.).
    
    **Request Body varies by role:**
    
    - **DOCTOR**: Can update bio, avatar_url, location, experience_years, specialization, hospital
    - **MR**: Can update bio, avatar_url, location, experience_years, territory, zone, state
    - **ADMIN**: Can update admin_bio, admin_avatar_url
    
    **Rules:**
    - All fields are optional (only send fields you want to update)
    - Cannot update: email, role, license_number
    - Doctors cannot update MR-specific fields (territory, zone, state)
    - MRs cannot update doctor-specific fields (specialization, hospital)
    - Admin cannot update doctor/MR fields
    - Doctor/MR cannot update admin fields
    - To remove avatar: send `"avatar_url": null` or `"admin_avatar_url": null`
    - Full name: 2-100 characters
    - Bio: max 500 characters
    - Phone: 10-20 characters
    - Experience: 0-70 years
    
    **Use Cases:**
    - Update personal profile information
    - Add/update bio
    - Change profile picture
    - Update contact details
    - Remove avatar (send null)
    
    **Examples:**
    
    Update bio only (Doctor/MR):
    ```json
    {
        "bio": "Updated bio text"
    }
    ```
    
    Update admin personal info:
    ```json
    {
        "full_name": "John Smith",
        "admin_bio": "CEO with 20 years experience"
    }
    ```
    
    Remove avatar:
    ```json
    {
        "avatar_url": null
    }
    ```
    """
    # Convert Pydantic model to dict, excluding unset fields
    update_data = profile_data.model_dump(exclude_unset=True)
    
    return await service.update_my_profile(update_data, current_user, request)


@router.get("/company", response_model=CompanyProfileResponse)
async def get_company_profile_endpoint(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get company profile (public information).
    
    **Access:** Doctor, MR, Admin, Manager
    
    **Purpose:**
    View your company's public profile information.
    
    **Flow:**
    1. User opens "Company Info" section
    2. System retrieves company profile
    3. Returns public company information
    
    **Response:**
    ```json
    {
        "company_name": "XYZ Pharma",
        "company_logo_url": "https://example.com/logos/xyz.png",
        "company_description": "Leading pharmaceutical company in India",
        "company_city": "Mumbai",
        "company_state": "Maharashtra",
        "company_country": "India",
        "company_website": "https://xyzpharma.com",
        "company_industry": "Pharmaceuticals",
        "company_founded_year": 2010,
        "company_size": "50-200"
    }
    ```
    
    **Public Fields (visible to all users):**
    - Company name, logo, description
    - City, state, country
    - Website, industry
    - Founded year, company size
    
    **Private Fields (NOT visible in this endpoint):**
    - Company address, pincode
    - GST number, PAN number
    
    **Use Cases:**
    - View company information
    - Check company details
    - See company branding
    
    **Errors:**
    - 403: Insufficient permissions
    - 404: Company profile not found
    """
    return await service.get_company_profile(current_user)


@router.get(
    "/{user_id}",
    response_model=PublicProfileResponse,
    responses={
        200: {
            "description": "Public profile retrieved successfully. Response varies by role.",
            "content": {
                "application/json": {
                    "examples": {
                        "doctor": {
                            "summary": "Doctor Public Profile",
                            "description": "Public profile of a Doctor user",
                            "value": {
                                "user_id": "507f1f77bcf86cd799439011",
                                "full_name": "Dr. Sarah Sharma",
                                "role": "DOCTOR",
                                "bio": "Cardiologist with 10 years of experience",
                                "avatar_url": "https://example.com/avatars/sarah.jpg",
                                "location": "Mumbai, Maharashtra",
                                "experience_years": 10.5,
                                "specialization": "Cardiology",
                                "hospital": "Apollo Hospital",
                                "territory": None,
                                "is_connected": True,
                                "connection_status": "connected"
                            }
                        },
                        "mr": {
                            "summary": "MR Public Profile",
                            "description": "Public profile of an MR user",
                            "value": {
                                "user_id": "507f1f77bcf86cd799439012",
                                "full_name": "Rajesh Kumar",
                                "role": "MR",
                                "bio": "Medical Representative with 5 years experience",
                                "avatar_url": "https://example.com/avatars/rajesh.jpg",
                                "location": "Hyderabad, Telangana",
                                "experience_years": 5.0,
                                "specialization": None,
                                "hospital": None,
                                "territory": "Hyderabad",
                                "is_connected": False,
                                "connection_status": "not_connected"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def get_user_profile_endpoint(
    user_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    View another user's public profile.
    
    **Access:** Doctor, MR, Admin, Manager
    
    **Purpose:** View public profile information of another user.
    
    **Response varies by role:**
    
    - **DOCTOR**: Shows specialization, hospital (territory is null)
    - **MR**: Shows territory (specialization, hospital are null)
    
    **Connection Status:**
    - `"connected"` - You are connected
    - `"pending"` - Connection request pending
    - `"not_connected"` - Not connected
    - `"company_staff_view"` - Admin/Manager viewing employee
    
    **Rules:**
    - Admin/Manager can view ALL doctors and MRs
    - Doctors/MRs cannot view blocked users
    - Cannot view own profile (use GET /profile/me)
    
    **Use the "Example Value" dropdown above to see role-specific responses.**
    **Errors:**
    - 400: Trying to view own profile
    - 403: User is blocked (Doctor/MR only) or insufficient permissions
    - 404: User not found
    """
    return await service.get_user_profile(user_id, current_user)



@router.put(
    "/company",
    responses={
        200: {
            "description": "Company profile updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Company profile updated successfully"
                    }
                }
            }
        },
        403: {
            "description": "Manager trying to update admin-only fields",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Manager cannot update company_name. Only admin can update company name, GST, PAN, and address."
                    }
                }
            }
        }
    }
)
async def update_company_profile_endpoint(
    company_data: CompanyUpdateRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Update company profile (Admin & Manager with different permissions).
    
    **Access:** Admin & Manager (with restrictions)
    
    **ADMIN can update:**
    - All fields including company_name, company_gst_number, company_pan_number, company_address, company_pincode
    
    **MANAGER can update:**
    - Only public fields: logo, description, city, state, country, website, industry, founded_year, size
    - CANNOT update: company_name, GST, PAN, address, pincode
    
    **Rules:**
    - All fields are optional
    - Manager attempting to update restricted fields → 403 error
    - Changes visible to all employees immediately
    """
    # Convert Pydantic model to dict, excluding unset fields
    update_data = company_data.model_dump(exclude_unset=True)
    
    return await service.update_company_profile(update_data, current_user)
