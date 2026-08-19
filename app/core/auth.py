"""
Authentication dependencies for FastAPI routes.

MRX authenticates users exclusively via Proxzar-issued JWTs.
The get_current_user dependency verifies the Proxzar token using JWKS,
then resolves the MRX user by username from the appropriate collection.

MRX login roles: ADMIN, MR
DOCTOR role is rejected (doctors use DRX platform).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any

from app.core.proxzar_auth import verify_proxzar_jwt
from app.core.roles import UserRole, get_collection_name
from app.database import get_database


# HTTP Bearer token scheme (Authorization: Bearer <token>)
security = HTTPBearer()

# MRX login roles — DOCTOR is not an MRX login role
MRX_LOGIN_ROLES = {UserRole.ADMIN.value, UserRole.MR.value}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Get the current authenticated user from a Proxzar JWT.

    Flow:
    1. Extract Bearer token
    2. Verify token using Proxzar JWKS (signature, issuer, audience, expiration)
    3. Extract verified sub (username) and role
    4. Reject DOCTOR role (not an MRX login role)
    5. Lookup user by username in the role-specific collection
    6. Check user is active
    7. Return current_user dict (same shape as before for backward compat)

    Args:
        credentials: HTTP Authorization header with Bearer token

    Returns:
        Dict containing user information from database

    Raises:
        HTTPException 401: Invalid/expired token or user not found
        HTTPException 403: DOCTOR role or inactive user
    """
    token = credentials.credentials

    # Step 1-2: Verify Proxzar JWT (raises 401/503 on failure)
    payload = await verify_proxzar_jwt(token)

    # Step 3: Extract verified claims
    username: str = payload.get("sub")
    role: str = payload.get("role")

    # Step 4: Reject DOCTOR — not an MRX login role
    if role not in MRX_LOGIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' is not permitted to access MRX. Doctors use DRX.",
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

    # Step 5: Lookup user by username
    db = get_database()
    collection = db[collection_name]

    user = await collection.find_one({"username": username})

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found in MRX",
        )

    # Step 6: Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Step 7: Build current_user (same shape as existing authorization expects)
    user["_id"] = str(user["_id"])
    user["role"] = role

    # Add department for admins (from DB, not token)
    if role == UserRole.ADMIN.value:
        user.setdefault("department", "general")

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


async def require_mr(current_user: Dict = Depends(get_current_user)) -> Dict:
    """
    Require MR role.

    Example:
        @router.get("/doctor-list")
        async def get_doctors(current_user = Depends(require_mr)):
            return {"message": "Only MRs can view doctor list"}
    """
    return await require_role(UserRole.MR, current_user)
