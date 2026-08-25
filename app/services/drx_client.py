"""
DRX Integration Client — Communication with Doctor Platform.

All DRX ↔ MRX communication uses the user's Proxzar JWT.
MRX forwards the same Proxzar token it received from the user.
DRX independently verifies it via Proxzar JWKS.

No client_id, client_secret, or Service JWT involved.

Usage:
    from app.services.drx_client import drx_client

    # Search doctors on DRX (forwarding user's Proxzar token)
    result = await drx_client.search_doctors(query="Dr. Arjun", user_token=token)

    # Get doctor by GID
    doctor = await drx_client.get_doctor(doctor_gid="PRXDOC482915", user_token=token)
"""

from typing import Optional, Dict, Any
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
    DRX Integration Client.

    All requests forward the user's Proxzar JWT to DRX.
    No service token, no client credentials, no retry on 401.
    If DRX rejects the token, the error propagates to the caller.
    """

    @property
    def base_url(self) -> str:
        return settings.MRX_TO_DRX_URL.rstrip("/")

    @property
    def api_prefix(self) -> str:
        return settings.MRX_TO_DRX_API_PREFIX.rstrip("/")

    @property
    def is_configured(self) -> bool:
        """Check if DRX URL is configured."""
        return bool(settings.MRX_TO_DRX_URL)

    async def _request(
        self,
        method: str,
        path: str,
        user_token: str,
        params: Optional[Dict] = None,
        json_body: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Send a request to DRX forwarding the user's Proxzar JWT.

        No token refresh or retry on 401. If DRX rejects the token,
        the error propagates to the caller.
        """
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {user_token}"}

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

        if response.status_code >= 400:
            raise DRXClientError(
                f"DRX API error: {response.status_code} {response.text}",
                status_code=response.status_code
            )

        return response.json()

    # ══════════════════════════════════════════════════════════
    # Public API Methods
    # ══════════════════════════════════════════════════════════

    async def search_doctors(self, query: str = "", user_token: str = "") -> Dict[str, Any]:
        """
        Search doctors on DRX.
        GET {api_prefix}/doctors/search?q=<query>
        """
        return await self._request("GET", f"{self.api_prefix}/doctors/search", user_token, params={"q": query})

    async def get_doctor(self, doctor_gid: str, user_token: str = "") -> Dict[str, Any]:
        """
        Get doctor profile by GID from DRX.
        GET {api_prefix}/doctors/{doctor_gid}
        """
        return await self._request("GET", f"{self.api_prefix}/doctors/{doctor_gid}", user_token)

    async def register_doctor(self, name: str, email: str, phone: str, user_token: str = "") -> Dict[str, Any]:
        """
        Register a doctor on DRX. If email exists, returns existing GID (no duplicate).
        POST {api_prefix}/doctors/register
        """
        return await self._request("POST", f"{self.api_prefix}/doctors/register", user_token, json_body={
            "name": name,
            "email": email,
            "phone": phone
        })

    async def push_notification(self, title: str, message: str, data: Optional[Dict] = None, user_token: str = "") -> Dict[str, Any]:
        """
        Push a notification to DRX.
        POST {api_prefix}/notifications/push
        """
        body = {"title": title, "message": message}
        if data:
            body.update(data)
        return await self._request("POST", f"{self.api_prefix}/notifications/push", user_token, json_body=body)

    async def request_doctor(self, username: str, organization_gid: str, user_token: str = "") -> Dict[str, Any]:
        """
        Request a doctor from DRX to be added to MRX.
        POST {api_prefix}/doctor-requests

        MRX Admin sends this request. DRX notifies the doctor.
        If doctor accepts → DRX admin approves → doctor added to MRX.
        """
        return await self._request("POST", f"{self.api_prefix}/doctor-requests", user_token, json_body={
            "username": username,
            "organization_gid": organization_gid
        })

    async def health_check(self) -> Dict[str, Any]:
        """
        Verify DRX connectivity (basic URL check, no auth needed).
        """
        if not self.is_configured:
            return {
                "status": "not_configured",
                "drx_url": self.base_url,
                "message": "MRX_TO_DRX_URL not set"
            }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/")
                return {
                    "status": "ok",
                    "drx_url": self.base_url,
                    "reachable": response.status_code < 500
                }
        except Exception as e:
            return {
                "status": "error",
                "drx_url": self.base_url,
                "message": str(e)
            }


# ══════════════════════════════════════════════════════════════
# Singleton instance — import this throughout MRX
# ══════════════════════════════════════════════════════════════
drx_client = DRXClient()
