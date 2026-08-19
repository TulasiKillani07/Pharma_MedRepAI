"""
Dual-authentication dependency for MRX integration endpoints.

Accepts either:
1. Proxzar JWT (user-driven DRX → MRX calls) — verified via Proxzar JWKS
2. Service JWT (background/machine-to-machine DRX → MRX calls) — verified via SERVICE_JWT_SECRET

This allows DRX to call MRX integration endpoints using:
- The logged-in user's Proxzar token (forwarded as-is), OR
- A service token obtained via client_id + client_secret

The dependency returns a context dict with caller information.
"""

from typing import Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt as jose_jwt, JWTError

from app.config import settings
from app.core.proxzar_auth import verify_proxzar_jwt
from app.core.service_auth import decode_service_token
from app.core.roles import UserRole, get_collection_name
from app.database import get_database
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)

_integration_security = HTTPBearer()

# MRX login roles — DOCTOR is not an MRX login role
MRX_LOGIN_ROLES = {UserRole.ADMIN.value, UserRole.MR.value}


async def require_integration_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_integration_security)
) -> Dict[str, Any]:
    """
    Dual-auth dependency for integration endpoints.

    Strategy:
    1. Peek at the token header (unverified) to determine type:
       - If it has a 'kid' header → likely Proxzar RS256 JWT → verify via JWKS
       - Otherwise → try as Service JWT (HS256)
    2. If Proxzar verification succeeds → resolve MRX user, return context
    3. If Service JWT verification succeeds → return service context
    4. If neither works → 401

    Returns:
        Dict with caller context:
        - For Proxzar JWT: {"auth_type": "proxzar", "sub": username, "role": role, "user": current_user}
        - For Service JWT: {"auth_type": "service", "iss": issuer, "client_id": client_id}
    """
    token = credentials.credentials

    # Step 1: Peek at header to determine token type
    try:
        unverified_header = jose_jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Step 2: If token has 'kid' → it's a Proxzar RS256 JWT
    if unverified_header.get("kid"):
        return await _verify_as_proxzar(token)

    # Step 3: Otherwise try as Service JWT (HS256, no kid)
    return _verify_as_service(token)


async def _verify_as_proxzar(token: str) -> Dict[str, Any]:
    """Verify token as Proxzar JWT and resolve MRX user."""
    # verify_proxzar_jwt raises HTTPException on failure
    payload = await verify_proxzar_jwt(token)

    username: str = payload.get("sub")
    role: str = payload.get("role")

    # Reject DOCTOR — not an MRX login role
    if role not in MRX_LOGIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' is not permitted to access MRX. Doctors use DRX.",
        )

    # Resolve user by username
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


def _verify_as_service(token: str) -> Dict[str, Any]:
    """Verify token as MRX Service JWT."""
    payload = decode_service_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "auth_type": "service",
        "iss": payload.get("iss", "unknown"),
        "client_id": payload["client_id"]
    }
