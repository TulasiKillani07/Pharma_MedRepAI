"""
Integration Routes — Service-to-Service APIs for MRX (MedRep Backend)
Protected by Service JWT (not Admin/MR JWT)

Architecture:
  - MRX trusts exactly ONE caller: DRX (Doctor Platform)
  - No service_clients collection — credentials verified directly from .env
  - DRX authenticates via: client_id + client_secret → Service JWT
  - Service JWT signed with SERVICE_JWT_SECRET (isolated from user JWTs)

Inbound (DRX → MRX):
  DRX → POST /integration/auth/service-token → MRX Service JWT
  DRX → Bearer <service_jwt> → GET /integration/drugs, /integration/cme

Outbound (MRX → DRX):
  MRX → drx_client.py → DRX Integration APIs
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from bson import ObjectId
from app.config import settings
from app.database import get_database
from app.core.security import verify_password
from app.core.service_auth import create_service_token, require_service_auth, SERVICE_TOKEN_EXPIRE_MINUTES
from app.core.auth import require_admin
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════════════════════════

class ServiceTokenRequest(BaseModel):
    client_id: str = Field(..., description="Service client_id")
    client_secret: str = Field(..., description="Service client_secret")


class ServiceTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(description="Token lifetime in seconds")


# ══════════════════════════════════════════════════════════════
# Service Token Endpoint — Single trusted caller (DRX)
# ══════════════════════════════════════════════════════════════

@router.post("/auth/service-token", response_model=ServiceTokenResponse,
             summary="Get MRX Service Token")
async def get_service_token(request: ServiceTokenRequest):
    """
    **Purpose:** Exchange client_id + client_secret for a short-lived MRX Service JWT.

    **Access:** DRX backend only (single trusted caller)

    **Request Body:**
    ```json
    {
      "client_id": "drx_doctor_platform",
      "client_secret": "drx-calls-mrx-secret..."
    }
    ```

    **Response:**
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIs...",
      "token_type": "Bearer",
      "expires_in": 900
    }
    ```

    **Validations:**
    - client_id must match INBOUND_CLIENT_ID from env
    - client_secret is hashed and compared against INBOUND_CLIENT_SECRET_HASH

    **Token lifetime:** 15 minutes

    **Why no DB lookup?** MRX is a single-company backend. Only one external caller
    (DRX) is trusted. Credentials live in env — no need for a multi-client collection.
    **Why hash?** Even if .env is leaked, the actual secret isn't exposed.
    """
    # Verify client_id
    if request.client_id != settings.DRX_TO_MRX_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Verify client_secret against stored hash (like password verification)
    if not verify_password(request.client_secret, settings.DRX_TO_MRX_SECRET_HASH):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Generate service token
    token = create_service_token(
        organization_id="drx",
        organization_name="DRX",
        client_id=request.client_id
    )

    logger.info(f"Service token issued for inbound caller: {request.client_id}")

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": SERVICE_TOKEN_EXPIRE_MINUTES * 60
    }


# ══════════════════════════════════════════════════════════════
# Protected Integration APIs (Service JWT only — DRX calls these)
# ══════════════════════════════════════════════════════════════

@router.get("/drugs", summary="List Drugs (Service API)")
async def list_drugs_integration(
    search: Optional[str] = Query(None, description="Search by drug name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    org_context=Depends(require_service_auth)
):
    """
    **Purpose:** List drugs in this MRX instance (used by DRX to show drugs to doctors).

    **Access:** Service JWT only (backend-to-backend)

    **Query:** `search` — partial match on drug_name

    **Response:** List of drugs with packaging info.
    """
    db = get_database()

    query = {"is_active": True}
    if search:
        query["drug_name"] = {"$regex": search, "$options": "i"}

    drugs = await db.drugs.find(query, {
        "drug_name": 1,
        "generic_name": 1,
        "brand_name": 1,
        "manufacturer": 1,
        "therapeutic_category": 1,
        "dosage_form": 1,
        "strength": 1,
        "route_of_administration": 1,
        "indication": 1,
        "contraindications": 1,
        "side_effects": 1,
        "packaging": 1,
        "brochure_url": 1,
        "prescription_required": 1,
        "schedule": 1
    }).skip(skip).limit(limit).to_list(length=limit)

    # Convert _id to string id
    for drug in drugs:
        drug["id"] = str(drug.pop("_id"))

    total = await db.drugs.count_documents(query)

    return {
        "total": total,
        "drugs": drugs,
        "caller": org_context["client_id"]
    }


@router.get("/drugs/{drug_id}", summary="Get Drug Detail (Service API)")
async def get_drug_integration(
    drug_id: str,
    org_context=Depends(require_service_auth)
):
    """
    **Purpose:** Get single drug details (used by DRX for doctor prescription view).

    **Access:** Service JWT only (backend-to-backend)

    **Response:** Drug detail with packaging info.
    """
    db = get_database()

    if not ObjectId.is_valid(drug_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid drug ID")

    drug = await db.drugs.find_one(
        {"_id": ObjectId(drug_id), "is_active": True},
        {"password_hash": 0}
    )

    if not drug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drug not found")

    drug["id"] = str(drug.pop("_id"))
    return drug


@router.get("/cme", summary="List CME Events (Service API)")
async def list_cme_integration(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter: UPCOMING, ONGOING, COMPLETED"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    org_context=Depends(require_service_auth)
):
    """
    **Purpose:** List CME events (used by DRX to show events doctors can register for).

    **Access:** Service JWT only (backend-to-backend)

    **Response:** List of CME events with basic info.
    """
    db = get_database()

    query = {"is_active": True}
    if status_filter:
        query["status"] = status_filter

    events = await db.cme_events.find(query, {
        "_id": 0,
        "title": 1,
        "description": 1,
        "event_date": 1,
        "end_date": 1,
        "venue": 1,
        "city": 1,
        "state": 1,
        "specialization": 1,
        "status": 1,
        "max_participants": 1,
        "registered_count": 1
    }).sort("event_date", -1).skip(skip).limit(limit).to_list(length=limit)

    total = await db.cme_events.count_documents(query)

    return {
        "total": total,
        "events": events,
        "caller": org_context["client_id"]
    }


# ══════════════════════════════════════════════════════════════
# Outbound — MRX calling DRX (Admin utility endpoints)
# ══════════════════════════════════════════════════════════════

@router.get("/drx/health", summary="DRX Connection Health Check (Admin)")
async def drx_health_check(current_user=Depends(require_admin)):
    """
    **Purpose:** Verify MRX can authenticate with DRX and reach its Integration APIs.

    **Access:** Admin only

    **Response:**
    ```json
    {
      "status": "ok",
      "drx_url": "http://localhost:8002",
      "token_valid": true
    }
    ```
    """
    from app.services.drx_client import drx_client
    return await drx_client.health_check()


@router.get("/drx/doctors/search", summary="Search Doctors on DRX (Admin)")
async def search_drx_doctors(
    q: str = Query("", description="Search by name or doctor_gid"),
    current_user=Depends(require_admin)
):
    """
    **Purpose:** Search doctors on DRX Doctor Platform (proxy through MRX for admin use).

    **Access:** Admin only

    **Response:** List of matching doctors from DRX.
    """
    from app.services.drx_client import drx_client

    if not drx_client.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DRX integration not configured. Set DRX_CLIENT_ID and DRX_CLIENT_SECRET in .env"
        )

    try:
        return await drx_client.search_doctors(query=q)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/drx/doctors/{doctor_gid}", summary="Get Doctor from DRX (Admin)")
async def get_drx_doctor(
    doctor_gid: str,
    current_user=Depends(require_admin)
):
    """
    **Purpose:** Get a doctor's profile from DRX by their GID.

    **Access:** Admin only

    **Response:** Doctor profile from DRX (no sensitive data).
    """
    from app.services.drx_client import drx_client

    if not drx_client.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DRX integration not configured. Set DRX_CLIENT_ID and DRX_CLIENT_SECRET in .env"
        )

    try:
        return await drx_client.get_doctor(doctor_gid=doctor_gid)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
