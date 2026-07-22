"""
DRX Integration Client — Service-to-Service communication with Doctor Platform.

Responsibilities:
  - Request Service JWT from DRX
  - Cache Service JWT in memory until expiry
  - Refresh expired token automatically
  - Send authenticated requests to DRX Integration APIs
  - Handle timeouts, retries, and authentication failures

No business logic lives here. This is a pure communication layer.

Usage:
    from app.services.drx_client import drx_client

    # Search doctors on DRX
    result = await drx_client.search_doctors(query="Dr. Arjun")

    # Get doctor by GID
    doctor = await drx_client.get_doctor(doctor_gid="PRXDOC482915")
"""

import time
from typing import Optional, Dict, Any, List
import httpx
from app.config import settings
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)


class DRXClientError(Exception):
    """Raised when DRX client encounters an unrecoverable error."""
    def __init__(self, message: str, status_code: int = 0):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class DRXClient:
    """
    Reusable DRX Integration Client.
    
    Token lifecycle:
      1. No token → request new one
      2. Token exists but expired → request new one
      3. DRX returns 401 → clear cache, request new one, retry once
      4. Token valid → use it
    """

    def __init__(self):
        self._token: Optional[str] = None
        self._token_expires_at: float = 0  # Unix timestamp
        self._token_buffer_seconds: int = 60  # Refresh 60s before actual expiry

    @property
    def base_url(self) -> str:
        return settings.MRX_TO_DRX_URL.rstrip("/")

    @property
    def is_configured(self) -> bool:
        """Check if DRX credentials are configured."""
        return bool(settings.MRX_TO_DRX_CLIENT_ID and settings.MRX_TO_DRX_SECRET)

    def _is_token_valid(self) -> bool:
        """Check if cached token is still valid (with buffer)."""
        if not self._token:
            return False
        return time.time() < (self._token_expires_at - self._token_buffer_seconds)

    async def _request_token(self) -> str:
        """
        Request a new Service JWT from DRX.
        POST {DRX_URL}/drx/api/v1/integration/auth/service-token
        """
        if not self.is_configured:
            raise DRXClientError(
                "DRX integration not configured. Set DRX_URL, DRX_CLIENT_ID, DRX_CLIENT_SECRET in .env"
            )

        url = f"{self.base_url}/drx/api/v1/integration/auth/service-token"

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.post(url, json={
                    "client_id": settings.MRX_TO_DRX_CLIENT_ID,
                    "client_secret": settings.MRX_TO_DRX_SECRET
                })
            except httpx.ConnectError:
                raise DRXClientError(f"Cannot connect to DRX at {self.base_url}", status_code=503)
            except httpx.TimeoutException:
                raise DRXClientError(f"DRX token request timed out", status_code=504)

        if response.status_code == 200:
            data = response.json()
            self._token = data["access_token"]
            self._token_expires_at = time.time() + data["expires_in"]
            logger.info(f"DRX service token obtained (expires_in: {data['expires_in']}s)")
            return self._token
        elif response.status_code == 401:
            raise DRXClientError("DRX authentication failed — invalid client_id or client_secret", status_code=401)
        elif response.status_code == 403:
            raise DRXClientError("DRX organization is inactive", status_code=403)
        else:
            raise DRXClientError(f"DRX token request failed: {response.status_code} {response.text}", status_code=response.status_code)

    async def _get_token(self) -> str:
        """Get a valid token — cached or fresh."""
        if self._is_token_valid():
            return self._token
        return await self._request_token()

    def _clear_token(self):
        """Clear cached token (on 401 from DRX)."""
        self._token = None
        self._token_expires_at = 0

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_body: Optional[Dict] = None,
        retry_on_401: bool = True
    ) -> Dict[str, Any]:
        """
        Send an authenticated request to DRX Integration API.
        Automatically refreshes token on 401 (once).
        """
        token = await self._get_token()
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_body
                )
            except httpx.ConnectError:
                raise DRXClientError(f"Cannot connect to DRX at {url}", status_code=503)
            except httpx.TimeoutException:
                raise DRXClientError(f"DRX request timed out: {method} {path}", status_code=504)

        # If 401 and we haven't retried yet → refresh token and retry once
        if response.status_code == 401 and retry_on_401:
            logger.warning("DRX returned 401 — refreshing service token and retrying")
            self._clear_token()
            return await self._request(method, path, params, json_body, retry_on_401=False)

        if response.status_code >= 400:
            raise DRXClientError(
                f"DRX API error: {response.status_code} {response.text}",
                status_code=response.status_code
            )

        return response.json()

    # ══════════════════════════════════════════════════════════
    # Public API Methods
    # ══════════════════════════════════════════════════════════

    async def search_doctors(self, query: str = "") -> Dict[str, Any]:
        """
        Search doctors on DRX.
        GET /drx/api/v1/integration/doctors/search?q=<query>
        
        Returns: {"total": int, "doctors": [...], "organization": str}
        """
        return await self._request("GET", "/drx/api/v1/integration/doctors/search", params={"q": query})

    async def get_doctor(self, doctor_gid: str) -> Dict[str, Any]:
        """
        Get doctor profile by GID from DRX.
        GET /drx/api/v1/integration/doctors/{doctor_gid}
        
        Returns: Doctor profile dict (no password_hash, no internal _id)
        """
        return await self._request("GET", f"/drx/api/v1/integration/doctors/{doctor_gid}")

    async def register_doctor(self, name: str, email: str, phone: str) -> Dict[str, Any]:
        """
        Register a doctor on DRX. If email exists, returns existing GID (no duplicate).
        POST /drx/api/v1/integration/doctors/register
        
        Returns: {"status": "created"|"exists", "doctor_gid": "PRXDOC...", "message": "..."}
        """
        return await self._request("POST", "/drx/api/v1/integration/doctors/register", json_body={
            "name": name,
            "email": email,
            "phone": phone
        })

    async def health_check(self) -> Dict[str, Any]:
        """
        Verify DRX connectivity and credentials.
        Attempts to obtain a service token and run a basic search.
        
        Returns: {"status": "ok", "drx_url": str, "token_valid": bool}
        """
        if not self.is_configured:
            return {
                "status": "not_configured",
                "drx_url": self.base_url,
                "message": "DRX_CLIENT_ID and DRX_CLIENT_SECRET not set"
            }

        try:
            await self._get_token()
            return {
                "status": "ok",
                "drx_url": self.base_url,
                "token_valid": True
            }
        except DRXClientError as e:
            return {
                "status": "error",
                "drx_url": self.base_url,
                "message": e.message
            }


# ══════════════════════════════════════════════════════════════
# Singleton instance — import this throughout MRX
# ══════════════════════════════════════════════════════════════
drx_client = DRXClient()
