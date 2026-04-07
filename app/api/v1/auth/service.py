"""
Authentication service - Business logic for login and registration.
"""

from datetime import datetime
from fastapi import HTTPException, status
from app.database import get_database
from app.core.security import hash_password, verify_password, create_access_token
from app.core.roles import UserRole, get_collection_name
from app.config import settings
from bson import ObjectId


async def login_user(email: str, password: str, role: UserRole) -> dict:
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
    
    print(f"🔍 Login attempt - Email: {email}, Role: {role}, Collection: {collection_name}, Database: {settings.DATABASE_NAME}")
    
    # Find user by email
    user = await collection.find_one({"email": email})
    
    if not user:
        print(f"❌ User not found in {settings.DATABASE_NAME}.{collection_name} collection")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    print(f"✅ User found: {user.get('name') or user.get('full_name')}")
    
    # Verify password
    password_valid = verify_password(password, user["password_hash"])
    print(f"🔑 Password verification: {password_valid}")
    
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
    
    # Create JWT token
    token_data = {
        "sub": str(user["_id"]),  # Subject (user ID)
        "email": user["email"],
        "role": role.value,
        "collection": collection_name
    }
    
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
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        "user": user_info
    }


async def register_admin(email: str, password: str, full_name: str, phone: str, company_name: str) -> dict:
    """
    Register a new company admin.
    
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
    In production, you might want to restrict this or require an invitation code.
    """
    db = get_database()
    collection = db.company_admins
    
    # Check if email already exists
    existing_user = await collection.find_one({"email": email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Hash password
    password_hash = hash_password(password)
    
    # Create admin document
    admin_doc = {
        "email": email,
        "password_hash": password_hash,
        "full_name": full_name,
        "phone": phone,
        "company_name": company_name,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Insert into database
    result = await collection.insert_one(admin_doc)
    
    return {
        "message": "Admin registered successfully",
        "user_id": str(result.inserted_id)
    }
