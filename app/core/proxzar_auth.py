"""
Proxzar OAuth2 JWKS verification for MRX.

MRX authenticates users exclusively via Proxzar-issued JWTs.
This module fetches Proxzar's public keys (JWKS), caches them,
and verifies incoming tokens using RS256 signature validation.

Verification checks:
- JWT signature (RS256, using Proxzar public key matched by kid)
- Issuer (must be PROXZAR_ISSUER)
- Audience (PROXZAR_AUDIENCE must be present in aud)
- Expiration (token must not be expired)
"""

import time
from typing import Dict, Any, Optional

import httpx
from jose import jwt, JWTError, jwk
from jose.utils import base64url_decode
from fastapi import HTTPException, status

from app.config import settings
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)


class ProxzarJWKSClient:
    """
    Fetches and caches Proxzar JWKS keys.
    
    - Keys are cached in memory for PROXZAR_JWKS_CACHE_TTL seconds.
    - If a token contains an unknown kid, refetch JWKS once before rejecting.
    """

    def __init__(self):
        self._jwks: Optional[Dict[str, Any]] = None
        self._jwks_fetched_at: float = 0.0

    @property
    def _cache_expired(self) -> bool:
        return (time.time() - self._jwks_fetched_at) > settings.PROXZAR_JWKS_CACHE_TTL

    async def _fetch_jwks(self) -> Dict[str, Any]:
        """Fetch JWKS from Proxzar endpoint."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(settings.PROXZAR_JWKS_URL)
                response.raise_for_status()
                jwks_data = response.json()
                self._jwks = jwks_data
                self._jwks_fetched_at = time.time()
                logger.info("Proxzar JWKS fetched successfully")
                return jwks_data
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch Proxzar JWKS: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable"
            )

    async def get_jwks(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get cached JWKS or fetch fresh if expired/forced."""
        if self._jwks is None or self._cache_expired or force_refresh:
            return await self._fetch_jwks()
        return self._jwks

    async def get_signing_key(self, kid: str) -> Optional[Dict[str, Any]]:
        """
        Find the signing key matching the given kid.
        If not found in cache, refetch once.
        """
        jwks = await self.get_jwks()
        
        # Search for matching kid
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return key
        
        # kid not found — key rotation may have happened, refetch once
        jwks = await self.get_jwks(force_refresh=True)
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return key
        
        # Still not found
        return None


# Singleton instance
_jwks_client = ProxzarJWKSClient()


async def verify_proxzar_jwt(token: str) -> Dict[str, Any]:
    """
    Verify a Proxzar-issued JWT using JWKS.
    
    Steps:
    1. Read unverified header to get kid and alg
    2. Fetch matching public key from JWKS
    3. Verify signature, expiration, issuer, audience
    4. Return verified payload
    
    Args:
        token: Raw JWT string from Authorization header
    
    Returns:
        Dict with verified claims (sub, role, iss, aud, exp, etc.)
    
    Raises:
        HTTPException(401): If token is invalid, expired, or verification fails
        HTTPException(503): If JWKS endpoint is unreachable
    """
    # Step 1: Read unverified header to get kid
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    kid = unverified_header.get("kid")
    alg = unverified_header.get("alg", "RS256")
    
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing kid header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Step 2: Get matching signing key from JWKS
    signing_key = await _jwks_client.get_signing_key(kid)
    
    if signing_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signing key not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Step 3: Verify the token
    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[alg],
            audience=settings.PROXZAR_AUDIENCE,
            issuer=settings.PROXZAR_ISSUER,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTClaimsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token claims validation failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signature verification failed",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Step 4: Validate required claims are present
    sub = payload.get("sub")
    role = payload.get("role")
    
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing role claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload
