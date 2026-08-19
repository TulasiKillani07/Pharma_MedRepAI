"""
Proxzar authentication dependency for MRX integration endpoints.

All DRX ↔ MRX communication uses Proxzar JWTs.
DRX forwards the user's Proxzar token, MRX independently verifies it via JWKS.

Accepts roles: ADMIN, MR, DOCTOR
(Integration endpoints allow DOCTOR because DRX forwards doctor tokens for drug/CME viewing.)
"""

from typing import Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.proxzar_auth import verify_proxzar_jwt
from app.core.roles import UserRole, get_collection_name
from app.database import get_database
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)

_integration_security = HTTPBearer()

# Integration endpoints accept all Proxzar roles
INTEGRATION_ALLOWED_ROLES = {UserRole.ADMIN.value, UserRole.MR.value, UserRole.DOCTOR.value}


async def require_integration_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_integration_security)
) -> Dict[str, Any]:
    """
    Proxzar JWT authentication for integration endpoints.

    Verifies the token via Proxzar JWKS, resolves the MRX user by username.

    Returns:
        Dict with caller context:
        {"auth_type": "proxzar", "sub": username, "role": role, "client_id": "proxzar_user:<username>", "user": current_user}
    """
    token = credentials.credentials

    # Verify Proxzar JWT (raises HTTPException on failure)
    payload = await verify_proxzar_jwt(token)

    username: str = payload.get("sub")
    role: str = payload.get("role")

    # Validate role is allowed on integration endpoints
    if role not in INTEGRATION_ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' is not permitted to access MRX integration endpoints.",
        )

    # For DOCTOR role: no MRX database lookup needed.
    # Doctors are managed on DRX — MRX just trusts the verified Proxzar token.
    if role == UserRole.DOCTOR.value:
        return {
            "auth_type": "proxzar",
            "sub": username,
            "role": role,
            "client_id": f"proxzar_user:{username}",
            "user": {"username": username, "role": role}
        }

    # For ADMIN/MR: resolve user by username in MRX database
    try:
        user_role = UserRole(role)
        collection_name = get_collection_name(user_role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid role in token",
        )

    db = get_database()
    user = await db[collection_name].find_one({"username": username})

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found in MRX",
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Build user dict
    user["_id"] = str(user["_id"])
    user["role"] = role
    if role == UserRole.ADMIN.value:
        user.setdefault("department", "general")

    return {
        "auth_type": "proxzar",
        "sub": username,
        "role": role,
        "client_id": f"proxzar_user:{username}",
        "user": user
    }
