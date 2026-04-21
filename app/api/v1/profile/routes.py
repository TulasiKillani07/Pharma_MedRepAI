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


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile_endpoint(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get your own complete profile.
    
    **Access:** Doctor, MR, Admin, Manager
    
    **Purpose:**
    View your complete profile including all private and public fields.
    
    **Flow:**
    1. User opens "My Profile" section
    2. System retrieves complete profile
    3. Returns all fields including email, phone, license number (doctors)
    
    **Response (Doctor/MR):**
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
    
    **Response (Admin/Manager):**
    ```json
    {
        "user_id": "admin123",
        "email": "admin@xyzpharma.com",
        "full_name": "John Admin",
        "phone": "+919876543210",
        "role": "ADMIN",
        "admin_bio": "CEO of XYZ Pharma",
        "admin_avatar_url": "https://example.com/avatars/admin.jpg",
        "bio": null,
        "avatar_url": null,
        "location": null,
        "experience_years": null,
        "specialization": null,
        "hospital": null,
        "license_number": null,
        "territory": null,
        "is_active": true,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-04-15T10:00:00"
    }
    ```
    
    **Note:** Admin/Manager profiles do NOT include company fields. 
    Use `GET /api/v1/profile/company` to view company information.
    
    **Use Cases:**
    - View own profile
    - Check profile completeness
    - See all personal information
    """
    return await service.get_my_profile(current_user)


@router.put("/me")
async def update_my_profile_endpoint(
    profile_data: ProfileUpdateRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Update your own profile.
    
    **Access:** Doctor, MR, Admin, Manager
    
    **Purpose:**
    Update your personal profile information (bio, avatar, location, etc.).
    
    **Flow:**
    1. User edits profile fields
    2. System validates changes
    3. Updates profile in database
    4. Returns success message
    
    **Request Body (Doctor/MR):**
    ```json
    {
        "full_name": "Dr. Sarah Sharma",
        "phone": "+919876543210",
        "bio": "Cardiologist with 10 years of experience",
        "avatar_url": "https://example.com/avatars/sarah.jpg",
        "location": "Mumbai, Maharashtra",
        "experience_years": 10,
        "specialization": "Cardiology",
        "hospital": "Apollo Hospital"
    }
    ```
    
    **Request Body (Admin/Manager):**
    ```json
    {
        "full_name": "John Admin",
        "phone": "+919876543210",
        "admin_bio": "CEO of XYZ Pharma",
        "admin_avatar_url": "https://example.com/avatars/admin.jpg"
    }
    ```
    
    **Note:** Admin/Manager cannot update company fields here. 
    Use `PUT /api/v1/profile/company` to update company information.
    
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
    - Admin/Manager cannot update doctor/MR fields
    - Doctor/MR cannot update admin fields
    - **Company fields CANNOT be updated here** - use `PUT /api/v1/profile/company` instead
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


@router.get("/{user_id}", response_model=PublicProfileResponse)
async def get_user_profile_endpoint(
    user_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    View another user's public profile.
    
    **Access:** Doctor, MR, Admin, Manager
    
    **Purpose:**
    View public profile information of another user.
    
    **Flow:**
    1. User clicks on another user's name/profile
    2. System checks permissions
    3. Returns public profile information
    
    **Admin/Manager Access:**
    - Admin/Manager can view ALL doctors and MRs profiles
    - No connection check required for admin/manager
    - Useful for managing company employees
    
    **Doctor/MR Access:**
    - Can view other doctors and MRs
    - Connection status shown
    - Cannot view blocked users
    
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
    - `"connected"` - You are connected (Doctor/MR viewing)
    - `"pending"` - Connection request pending (Doctor/MR viewing)
    - `"not_connected"` - Not connected (Doctor/MR viewing)
    - `"company_staff_view"` - Admin/Manager viewing employee profile (no connection needed)
    
    **Rules:**
    - Admin/Manager can view ALL doctors and MRs (no restrictions)
    - Doctors/MRs cannot view blocked users
    - Cannot view own profile (use GET /profile/me)
    
    **Use Cases:**
    - Admin/Manager: View employee profiles for management
    - Doctor/MR: View user profile before connecting
    - Check connected user's details
    - See user's specialization/territory
    - View user's bio and experience
    
    **Errors:**
    - 400: Trying to view own profile
    - 403: User is blocked (Doctor/MR only) or insufficient permissions
    - 404: User not found
    """
    return await service.get_user_profile(user_id, current_user)



@router.put("/company")
async def update_company_profile_endpoint(
    company_data: CompanyUpdateRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Update company profile (Admin & Manager with different permissions).
    
    **Access:** Admin & Manager (with restrictions)
    
    **Permissions:**
    
    **ADMIN can update:**
    - ✅ Company name
    - ✅ Company logo & description
    - ✅ GST & PAN numbers
    - ✅ Full address (address, city, state, country, pincode)
    - ✅ Website, industry, founded year, size
    
    **MANAGER can update:**
    - ✅ Company logo & description
    - ✅ City, state, country
    - ✅ Website, industry, founded year, size
    - ❌ Company name (Admin only)
    - ❌ GST & PAN numbers (Admin only)
    - ❌ Full address & pincode (Admin only)
    
    **Purpose:**
    Update company information with role-based access control.
    
    **Flow:**
    1. Admin/Manager opens "Company Settings"
    2. Edits allowed fields based on role
    3. System validates permissions
    4. Updates company profile
    5. All employees see updated info
    
    **Request Body (Admin - all fields):**
    ```json
    {
        "company_name": "XYZ Pharmaceuticals Ltd",
        "company_logo_url": "https://example.com/logo.png",
        "company_description": "Leading pharmaceutical company",
        "company_address": "123 Main St, Mumbai",
        "company_city": "Mumbai",
        "company_state": "Maharashtra",
        "company_country": "India",
        "company_pincode": "400001",
        "company_website": "https://xyzpharma.com",
        "company_industry": "Pharmaceuticals",
        "company_founded_year": 2010,
        "company_size": "100-500",
        "company_gst_number": "GST123456",
        "company_pan_number": "PAN123456"
    }
    ```
    
    **Request Body (Manager - limited fields):**
    ```json
    {
        "company_logo_url": "https://example.com/new-logo.png",
        "company_description": "Updated company description",
        "company_website": "https://newwebsite.com",
        "company_city": "Mumbai",
        "company_state": "Maharashtra"
    }
    ```
    
    **Response:**
    ```json
    {
        "message": "Company profile updated successfully"
    }
    ```
    
    **Rules:**
    - All fields are optional
    - Manager attempting to update restricted fields → 403 error
    - Updates single company document
    - Changes visible to all employees immediately
    
    **Use Cases:**
    - Admin: Update company name, legal info (GST/PAN)
    - Manager: Update branding (logo, description)
    - Both: Update public info (website, industry)
    
    **Errors:**
    - 403: Manager trying to update admin-only fields (name, GST, PAN, address)
    - 403: Doctor/MR trying to update company
    - 404: Company not found
    
    **Example Error (Manager updating name):**
    ```json
    {
        "detail": "Manager cannot update company_name. Only admin can update company name, GST, PAN, and address."
    }
    ```
    """
    # Convert Pydantic model to dict, excluding unset fields
    update_data = company_data.model_dump(exclude_unset=True)
    
    return await service.update_company_profile(update_data, current_user)
