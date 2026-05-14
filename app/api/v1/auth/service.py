"""
Authentication service - Business logic for login and registration.
"""

from datetime import datetime, timedelta
from fastapi import HTTPException, status, Request
from app.database import get_database
from app.core.security import hash_password, verify_password, create_access_token
from app.core.roles import UserRole, get_collection_name
from app.config import settings
from bson import ObjectId
from typing import Optional
from app.api.v1.activity_logs.helpers import log_activity
from app.models.activity_log_model import ActivityLogAction, ActorRole, TargetType, LogSeverity


async def login_user(email: str, password: str, role: UserRole, request: Optional[Request] = None) -> dict:
    """
    Authenticate user and return JWT token.
    
    Args:
        email: User's email address
        password: User's plain text password
        role: User's role (ADMIN, DOCTOR, or MR)
    
    Returns:
        dict: Contains access_token, token_type, expires_in, and user info
    
    Raises:
        HTTPException: If credentials are invalid
    
    Flow:
    1. Get the correct collection based on role
    2. Find user by email in that collection
    3. Verify password
    4. Create JWT token
    5. Return token and user info
    """
    db = get_database()
    
    # Get the correct collection based on role
    collection_name = get_collection_name(role)
    collection = db[collection_name]
    
    print(f"[AUTH] Login attempt - Email: {email}, Role: {role}, Collection: {collection_name}, Database: {settings.DATABASE_NAME}")
    
    # Find user by email
    user = await collection.find_one({"email": email})
    
    if not user:
        print(f"[AUTH] User not found in {settings.DATABASE_NAME}.{collection_name} collection")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    print(f"[AUTH] User found: {user.get('name') or user.get('full_name')}")
    
    # Verify password
    password_valid = verify_password(password, user["password_hash"])
    print(f"[AUTH] Password verification: {password_valid}")
    
    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    
    # Check if this is first login (BEFORE updating the field)
    is_first_login = not user.get("first_login_completed", False)
    
    # Decide whether to show password change prompt
    # Show prompt only on FIRST login (not on subsequent logins)
    must_change_password = False
    if role in [UserRole.DOCTOR, UserRole.MR]:
        if is_first_login:
            must_change_password = True
    
    # Update first_login_completed flag (AFTER checking)
    if is_first_login and role in [UserRole.DOCTOR, UserRole.MR]:
        await collection.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "first_login_completed": True,
                    "first_login_at": datetime.utcnow()
                }
            }
        )
    
    # Create JWT token
    token_data = {
        "sub": str(user["_id"]),  # Subject (user ID)
        "email": user["email"],
        "role": role.value,
        "collection": collection_name
    }
    
    # Add department to token if user is admin
    if role == UserRole.ADMIN:
        token_data["department"] = user.get("department", "general")
    
    access_token = create_access_token(data=token_data)
    
    # Prepare user info (without password)
    # Handle different field names for different roles
    name_field = user.get("full_name") or user.get("name", "Unknown")
    
    user_info = {
        "id": str(user["_id"]),
        "email": user["email"],
        "name": name_field,
        "role": role.value
    }
    
    # Add department to user info if admin
    if role == UserRole.ADMIN:
        user_info["department"] = user.get("department", "general")
    
    # Log successful login
    actor_dict = {
        "_id": str(user["_id"]),
        "name": name_field,
        "role": role.value
    }
    
    # Determine target type based on role
    if role == UserRole.DOCTOR:
        target_type = TargetType.DOCTOR
        actor_role = ActorRole.DOCTOR
    elif role == UserRole.MR:
        target_type = TargetType.MR
        actor_role = ActorRole.MR
    else:  # ADMIN
        target_type = TargetType.SYSTEM
        actor_role = ActorRole.ADMIN
    
    await log_activity(
        action_type=ActivityLogAction.USER_LOGIN,
        actor=actor_dict,
        target_type=target_type,
        target_id=str(user["_id"]),
        target_name=name_field,
        details={"email": email, "role": role.value},
        severity=LogSeverity.INFO,
        request=request
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        "user": user_info,
        "must_change_password": must_change_password
    }


async def register_admin(email: str, password: str, full_name: str, phone: str, company_name: str) -> dict:
    """
    Register a new company admin and update company name.
    
    Args:
        email: Admin email
        password: Plain text password
        full_name: Admin full name
        phone: Phone number
        company_name: Company name
    
    Returns:
        dict: Success message and user ID
    
    Raises:
        HTTPException: If email already exists
    
    Note: This is for self-registration of the first admin.
    Updates the single company document with the provided company name.
    """
    db = get_database()
    
    # Check if email already exists
    existing_user = await db.company_admins.find_one({"email": email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Hash password
    password_hash = hash_password(password)
    
    # Create admin document (NO company_name here - it's in separate collection)
    admin_doc = {
        "email": email,
        "password_hash": password_hash,
        "full_name": full_name,
        "phone": phone,
        "department": "general",  # Default to general department
        "role": "ADMIN",  # Explicitly set role
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Insert admin into database
    result = await db.company_admins.insert_one(admin_doc)
    
    # Update company name in the separate company collection
    await db.company.update_one(
        {},  # Match the single company document
        {
            "$set": {
                "company_name": company_name,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {
        "message": "Admin registered successfully",
        "user_id": str(result.inserted_id)
    }



async def change_password_first_login(
    current_password: str,
    new_password: str,
    current_user: dict
) -> dict:
    """
    Reset/change password for authenticated users.
    User can change password anytime - on first login or later.
    
    Args:
        current_password: Current password
        new_password: New password
        current_user: Current authenticated user from JWT
    
    Returns:
        dict: Success message and new JWT token
    
    Raises:
        HTTPException: If current password is wrong
    """
    db = get_database()
    
    # Get user role
    role = current_user.get("role")
    
    # Get collection based on role
    from app.core.roles import UserRole, get_collection_name
    user_role = UserRole(role)
    collection_name = get_collection_name(user_role)
    collection = db[collection_name]
    
    # Get user from database
    user = await collection.find_one({"_id": ObjectId(current_user["_id"])})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify current password
    if not verify_password(current_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Hash new password
    new_password_hash = hash_password(new_password)
    
    # Update user in database
    update_data = {
        "password_hash": new_password_hash,
        "updated_at": datetime.utcnow()
    }
    
    # Set password changed flag if it exists (for tracking first change)
    if "is_password_changed" in user:
        update_data["is_password_changed"] = True
        update_data["password_changed_at"] = datetime.utcnow()
    
    await collection.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": update_data}
    )
    
    # Create new JWT token
    token_data = {
        "sub": current_user["_id"],
        "email": current_user["email"],
        "role": role,
        "collection": collection_name
    }
    
    access_token = create_access_token(data=token_data)
    
    # Log activity
    name_field = user.get("full_name") or user.get("name", "Unknown")
    
    if role == "DOCTOR":
        target_type = TargetType.DOCTOR
    elif role == "MR":
        target_type = TargetType.MR
    else:  # ADMIN
        target_type = TargetType.SYSTEM
    
    await log_activity(
        action_type=ActivityLogAction.USER_UPDATED,
        actor=current_user,
        target_type=target_type,
        target_id=current_user["_id"],
        target_name=name_field,
        details={"action": "password_changed"},
        severity=LogSeverity.INFO
    )
    
    return {
        "message": "Password changed successfully",
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }



import random
import string


def generate_otp() -> str:
    """
    Generate a 6-digit OTP code.
    
    Returns:
        str: 6-digit OTP code
    """
    return ''.join(random.choices(string.digits, k=6))


async def request_password_reset(email: str, role: UserRole) -> dict:
    """
    Request password reset by sending OTP to email.
    
    Args:
        email: User's email address
        role: User's role (ADMIN, DOCTOR, or MR)
    
    Returns:
        dict: Success message and expiration time
    
    Note: Returns generic success message even if user doesn't exist (security best practice)
    """
    db = get_database()
    
    # Get collection based on role
    collection_name = get_collection_name(role)
    collection = db[collection_name]
    
    # Check if user exists
    user = await collection.find_one({"email": email})
    
    # If user doesn't exist, return generic success message (don't reveal if email exists)
    if not user:
        print(f"[WARNING] Password reset requested for non-existent email: {email} (role: {role.value})")
        return {
            "message": "If an account exists with this email, you will receive a password reset OTP",
            "expires_in": 900  # 15 minutes
        }
    
    # Generate 6-digit OTP
    otp = generate_otp()
    
    # Calculate expiration time (15 minutes from now)
    created_at = datetime.utcnow()
    expires_at = created_at + timedelta(minutes=15)
    
    # Invalidate any existing unused OTPs for this email+role
    await db.password_reset_tokens.update_many(
        {
            "email": email,
            "role": role.value,
            "is_used": False
        },
        {
            "$set": {
                "is_used": True,
                "used_at": datetime.utcnow()
            }
        }
    )
    
    # Store OTP in database
    reset_token = {
        "email": email,
        "role": role.value,
        "otp": otp,
        "created_at": created_at,
        "expires_at": expires_at,
        "is_used": False,
        "used_at": None
    }
    
    await db.password_reset_tokens.insert_one(reset_token)
    
    # Send OTP via email
    from app.api.v1.email.service import send_password_reset_otp_email
    
    name_field = user.get("full_name") or user.get("name", "User")
    
    try:
        await send_password_reset_otp_email(
            to_email=email,
            name=name_field,
            otp=otp
        )
        print(f"[SUCCESS] Password reset OTP sent to {email}")
    except Exception as e:
        print(f"[ERROR] Failed to send password reset OTP to {email}: {str(e)}")
    
    # Return generic success message
    return {
        "message": "If an account exists with this email, you will receive a password reset OTP",
        "expires_in": 900  # 15 minutes in seconds
    }


async def reset_password_with_otp(
    email: str,
    role: UserRole,
    otp: str,
    new_password: str,
    request: Optional[Request] = None
) -> dict:
    """
    Reset password using OTP.
    
    Args:
        email: User's email address
        role: User's role (ADMIN, DOCTOR, or MR)
        otp: 6-digit OTP code
        new_password: New password
        request: Optional request object for IP tracking
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If OTP is invalid or expired
    """
    db = get_database()
    
    # Find valid OTP token
    reset_token = await db.password_reset_tokens.find_one({
        "email": email,
        "role": role.value,
        "otp": otp,
        "is_used": False,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    
    # Get user from database
    collection_name = get_collection_name(role)
    collection = db[collection_name]
    
    user = await collection.find_one({"email": email})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Hash new password
    new_password_hash = hash_password(new_password)
    
    # Update user password
    update_data = {
        "password_hash": new_password_hash,
        "updated_at": datetime.utcnow()
    }
    
    # Set password changed flag if it exists
    if "is_password_changed" in user:
        update_data["is_password_changed"] = True
        update_data["password_changed_at"] = datetime.utcnow()
    
    await collection.update_one(
        {"_id": user["_id"]},
        {"$set": update_data}
    )
    
    # Mark OTP as used
    await db.password_reset_tokens.update_one(
        {"_id": reset_token["_id"]},
        {
            "$set": {
                "is_used": True,
                "used_at": datetime.utcnow()
            }
        }
    )
    
    # Get IP address
    ip_address = "Unknown"
    if request:
        ip_address = request.client.host if request.client else "Unknown"
    
    # Send confirmation email
    from app.api.v1.email.service import send_password_reset_confirmation_email
    
    name_field = user.get("full_name") or user.get("name", "User")
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    try:
        await send_password_reset_confirmation_email(
            to_email=email,
            name=name_field,
            timestamp=timestamp,
            ip_address=ip_address
        )
        print(f"[SUCCESS] Password reset confirmation sent to {email}")
    except Exception as e:
        print(f"[ERROR] Failed to send confirmation email to {email}: {str(e)}")
    
    # Log activity
    actor_dict = {
        "_id": str(user["_id"]),
        "name": name_field,
        "role": role.value
    }
    
    if role == UserRole.DOCTOR:
        target_type = TargetType.DOCTOR
    elif role == UserRole.MR:
        target_type = TargetType.MR
    else:  # ADMIN
        target_type = TargetType.SYSTEM
    
    await log_activity(
        action_type=ActivityLogAction.USER_UPDATED,
        actor=actor_dict,
        target_type=target_type,
        target_id=str(user["_id"]),
        target_name=name_field,
        details={"action": "password_reset_with_otp", "ip_address": ip_address},
        severity=LogSeverity.WARNING,
        request=request
    )
    
    return {
        "message": "Password reset successfully. You can now login with your new password."
    }
