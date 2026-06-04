"""
Authentication dependencies for FastAPI routes.
These functions are used to protect routes and get the current user.
"""
from bson import ObjectId

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
from app.core.security import decode_access_token
from app.core.roles import UserRole, get_collection_name
from app.database import get_database


# HTTP Bearer token scheme (Authorization: Bearer <token>)
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Get the current authenticated user from JWT token.
    This function is used as a dependency in protected routes.
    
    Args:
        credentials: HTTP Authorization header with Bearer token
    
    Returns:
        Dict containing user information from database
    
    Raises:
        HTTPException: If token is invalid or user not found
    
    Example usage in routes:
        @router.get("/profile")
        async def get_profile(current_user = Depends(get_current_user)):
            return {"user": current_user}
    
    Flow:
    1. Extract token from Authorization header
    2. Decode and verify token
    3. Get user role from token
    4. Search in correct collection based on role
    5. Return user data
    """
    # Extract the token from credentials
    token = credentials.credentials
    
    # Decode the token
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user information from token
    user_id: str = payload.get("sub")
    role: str = payload.get("role")
    department: str = payload.get("department")  # Extract department from token
    
    if user_id is None or role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get the correct collection based on role
    try:
        user_role = UserRole(role)
        collection_name = get_collection_name(user_role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid role in token",
        )
    
    # Get user from database
    db = get_database()
    collection = db[collection_name]
    
    user = await collection.find_one({"_id": ObjectId(user_id)})
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    
    # Convert ObjectId to string for JSON serialization
    user["_id"] = str(user["_id"])
    user["role"] = role  # Add role to user object
    
    # Add department to user object if present in token (for admins)
    if department:
        user["department"] = department
    
    return user


async def require_role(required_role: UserRole, current_user: Dict = Depends(get_current_user)) -> Dict:
    """
    Dependency to require a specific role.
    
    Args:
        required_role: The role required to access the route
        current_user: Current authenticated user
    
    Returns:
        Dict containing user information
    
    Raises:
        HTTPException: If user doesn't have required role
    
    Example usage:
        @router.post("/drugs")
        async def create_drug(current_user = Depends(lambda: require_role(UserRole.ADMIN))):
            return {"message": "Drug created"}
    """
    if current_user.get("role") != required_role.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Required role: {required_role.value}",
        )
    return current_user


# Convenience functions for specific roles
async def require_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    """
    Require ADMIN role.
    
    Example:
        @router.post("/drugs")
        async def create_drug(current_user = Depends(require_admin)):
            return {"message": "Only admins can create drugs"}
    """
    return await require_role(UserRole.ADMIN, current_user)


async def require_doctor(current_user: Dict = Depends(get_current_user)) -> Dict:
    """
    Require DOCTOR role.
    
    Example:
        @router.post("/posts")
        async def create_post(current_user = Depends(require_doctor)):
            return {"message": "Only doctors can create posts"}
    """
    return await require_role(UserRole.DOCTOR, current_user)


async def require_mr(current_user: Dict = Depends(get_current_user)) -> Dict:
    """
    Require MR role.
    
    Example:
        @router.get("/doctor-list")
        async def get_doctors(current_user = Depends(require_mr)):
            return {"message": "Only MRs can view doctor list"}
    """
    return await require_role(UserRole.MR, current_user)


async def require_doctor_or_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    """
    Require DOCTOR or ADMIN role (for network features).
    Blocks MRs from accessing network features.
    
    Example:
        @router.post("/network/connections/send")
        async def send_connection(current_user = Depends(require_doctor_or_admin)):
            return {"message": "Only doctors and admins can use network features"}
    """
    user_role = current_user.get("role")
    if user_role not in [UserRole.DOCTOR.value, UserRole.ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Network features are only available for doctors",
        )
    return current_user
