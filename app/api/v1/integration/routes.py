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
from datetime import datetime
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

    # Return all fields except internal brochure fields
    drugs = await db.drugs.find(query, {
        "brochure_public_id": 0,
        "brochure_uploaded_at": 0,
        "search_text": 0
    }).skip(skip).limit(limit).to_list(length=limit)

    # Convert _id to string id
    for drug in drugs:
        drug["id"] = str(drug.pop("_id"))
        # Remove field_values if flat fields exist (avoid duplication)
        if "drug_name" in drug and "field_values" in drug:
            drug.pop("field_values", None)

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
        {"brochure_public_id": 0, "brochure_uploaded_at": 0, "search_text": 0}
    )

    if not drug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drug not found")

    drug["id"] = str(drug.pop("_id"))
    # Remove field_values if flat fields exist (avoid duplication)
    if "drug_name" in drug and "field_values" in drug:
        drug.pop("field_values", None)

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

    query = {}
    if status_filter:
        query["status"] = status_filter

    events = await db.cme_events.find(query, {
        "title": 1,
        "description": 1,
        "event_date": 1,
        "event_time": 1,
        "event_type": 1,
        "event_mode": 1,
        "platform": 1,
        "meeting_link": 1,
        "venue_name": 1,
        "address": 1,
        "speaker": 1,
        "status": 1,
        "max_attendees": 1,
    }).sort("event_date", -1).skip(skip).limit(limit).to_list(length=limit)

    for event in events:
        event["id"] = str(event.pop("_id"))

    total = await db.cme_events.count_documents(query)

    return {
        "total": total,
        "events": events,
        "caller": org_context["client_id"]
    }


@router.post("/cme/register", summary="Register Doctor for CME (Service API)")
async def register_cme_integration(
    request: dict,
    org_context=Depends(require_service_auth)
):
    """
    **Purpose:** DRX registers a doctor for a CME event. MRX owns the registration.

    **Access:** Service JWT only (backend-to-backend)

    **Request Body:**
    ```json
    {
      "doctor_gid": "PRXDOC482915",
      "doctor_name": "Dr. Arjun Mehta",
      "event_id": "6a605fe9f22a70a3c51b62c9"
    }
    ```

    **Response:**
    ```json
    { "status": "registered", "message": "Doctor registered for CME event" }
    ```
    """
    db = get_database()

    doctor_gid = request.get("doctor_gid", "")
    doctor_name = request.get("doctor_name", "")
    event_id = request.get("event_id", "")

    if not doctor_gid or not event_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="doctor_gid and event_id are required")

    if not ObjectId.is_valid(event_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid event_id")

    # Validate event exists
    event = await db.cme_events.find_one({"_id": ObjectId(event_id)})
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CME event not found")

    # Check duplicate registration
    existing = await db.cme_registrations.find_one({
        "cme_id": event_id,
        "doctor_gid": doctor_gid
    })
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already registered for this event")

    # Check capacity
    if event.get("max_attendees"):
        count = await db.cme_registrations.count_documents({"cme_id": event_id, "registration_status": "registered"})
        if count >= event["max_attendees"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Event is full — no capacity")

    # Store registration
    registration = {
        "cme_id": event_id,
        "doctor_gid": doctor_gid,
        "doctor_name": doctor_name,
        "registration_status": "registered",
        "registered_at": datetime.utcnow(),
        "registered_via": "drx",
        "created_at": datetime.utcnow()
    }
    try:
        result = await db.cme_registrations.insert_one(registration)
    except Exception as e:
        if "duplicate" in str(e).lower() or "E11000" in str(e):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already registered for this event")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Registration failed: {str(e)}")

    return {
        "status": "registered",
        "registration_id": str(result.inserted_id),
        "message": f"Doctor registered for '{event.get('title', '')}'"
    }


@router.get("/cme/my-registrations", summary="Get Doctor's CME Registrations (Service API)")
async def get_my_cme_integration(
    doctor_gid: str = Query(..., description="Doctor GID"),
    org_context=Depends(require_service_auth)
):
    """
    **Purpose:** DRX fetches a doctor's CME registrations from MRX.

    **Access:** Service JWT only (backend-to-backend)

    **Response:**
    ```json
    {
      "total": 3,
      "registrations": [
        {
          "id": "...",
          "cme_id": "...",
          "event_title": "Cardiology Update 2026",
          "event_date": "2026-08-15",
          "registration_status": "registered",
          "registered_at": "2026-07-22T10:00:00"
        }
      ]
    }
    ```
    """
    db = get_database()

    registrations = await db.cme_registrations.find(
        {"doctor_gid": doctor_gid}
    ).sort("registered_at", -1).to_list(length=100)

    results = []
    for reg in registrations:
        # Get event details
        event = None
        if ObjectId.is_valid(reg.get("cme_id", "")):
            event = await db.cme_events.find_one({"_id": ObjectId(reg["cme_id"])})

        results.append({
            "id": str(reg["_id"]),
            "cme_id": reg.get("cme_id"),
            "event_title": event.get("title", "") if event else "",
            "event_date": event.get("event_date") if event else None,
            "event_time": event.get("event_time", "") if event else "",
            "event_mode": event.get("event_mode") if event else None,
            "status": event.get("status", "") if event else "",
            "registration_status": reg.get("registration_status", ""),
            "registered_at": reg.get("registered_at")
        })

    return {"total": len(results), "registrations": results}


@router.get("/dashboard", summary="Dashboard Data for Doctor (Service API)")
async def get_dashboard_integration(
    doctor_gid: str = Query(None, description="Doctor GID (optional, for doctor-specific data)"),
    org_context=Depends(require_service_auth)
):
    """
    **Purpose:** Single endpoint for DRX to get all pharma-owned dashboard data in one call.

    **Access:** Service JWT only (backend-to-backend)

    **Response:**
    ```json
    {
      "recent_drugs": [...],
      "upcoming_cme": [...],
      "stats": {
        "total_drugs": 45,
        "total_cme_events": 10,
        "upcoming_cme_count": 3
      }
    }
    ```
    """
    db = get_database()

    # Recent drugs (last 5 added)
    recent_drugs = await db.drugs.find(
        {"is_active": True},
        {"drug_name": 1, "generic_name": 1, "therapeutic_category": 1, "dosage_form": 1, "strength": 1}
    ).sort("created_at", -1).limit(5).to_list(length=5)

    for drug in recent_drugs:
        drug["id"] = str(drug.pop("_id"))

    # Upcoming CME events (next 5)
    upcoming_cme = await db.cme_events.find(
        {"status": "upcoming"}
    ).sort("event_date", 1).limit(5).to_list(length=5)

    for event in upcoming_cme:
        event["id"] = str(event.pop("_id"))

    # Stats
    total_drugs = await db.drugs.count_documents({"is_active": True})
    total_cme = await db.cme_events.count_documents({})
    upcoming_count = await db.cme_events.count_documents({"status": "upcoming"})

    return {
        "recent_drugs": recent_drugs,
        "upcoming_cme": upcoming_cme,
        "stats": {
            "total_drugs": total_drugs,
            "total_cme_events": total_cme,
            "upcoming_cme_count": upcoming_count
        }
    }


# ══════════════════════════════════════════════════════════════
# Drug View Tracking (DRX pushes doctor views to MRX)
# ══════════════════════════════════════════════════════════════

@router.post("/drug-views", summary="Record Drug View (Service API)")
async def record_drug_view(
    request: dict,
    org_context=Depends(require_service_auth)
):
    """
    **Purpose:** DRX pushes drug view events so MRX admin can see analytics.

    **Access:** Service JWT only (backend-to-backend)

    **Request Body:**
    ```json
    {
      "drug_id": "6a69e619...",
      "drug_name": "Paracetamol 500mg",
      "doctor_gid": "PRXDOC596352",
      "doctor_name": "Dr. Sneha Reddy"
    }
    ```

    **Response:**
    ```json
    { "status": "recorded" }
    ```
    """
    db = get_database()

    drug_id = request.get("drug_id", "")
    drug_name = request.get("drug_name", "")
    doctor_gid = request.get("doctor_gid", "")
    doctor_name = request.get("doctor_name", "")

    if not drug_id or not doctor_gid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="drug_id and doctor_gid are required")

    await db.drug_views.insert_one({
        "drug_id": drug_id,
        "drug_name": drug_name,
        "doctor_gid": doctor_gid,
        "doctor_name": doctor_name,
        "viewed_at": datetime.utcnow()
    })

    return {"status": "recorded"}


@router.get("/drug-views/analytics", summary="Drug View Analytics (Admin)")
async def get_drug_view_analytics(
    drug_id: Optional[str] = Query(None, description="Filter by specific drug"),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(require_admin)
):
    """
    **Purpose:** Admin sees which drugs are most viewed, how many doctors viewed them, and who.

    **Access:** Admin only

    **Response:**
    ```json
    {
      "analytics": [
        {
          "drug_id": "6a69e619...",
          "drug_name": "Paracetamol 500mg",
          "total_views": 45,
          "unique_doctors": 12,
          "doctors": [
            { "doctor_gid": "PRXDOC596352", "doctor_name": "Dr. Sneha Reddy", "view_count": 5, "last_viewed": "2026-07-30T10:00:00" }
          ]
        }
      ]
    }
    ```
    """
    db = get_database()

    if drug_id:
        # Analytics for a specific drug
        pipeline = [
            {"$match": {"drug_id": drug_id}},
            {"$group": {
                "_id": {"doctor_gid": "$doctor_gid", "doctor_name": "$doctor_name"},
                "view_count": {"$sum": 1},
                "last_viewed": {"$max": "$viewed_at"}
            }},
            {"$sort": {"view_count": -1}}
        ]
        results = await db.drug_views.aggregate(pipeline).to_list(length=200)

        total_views = await db.drug_views.count_documents({"drug_id": drug_id})
        # Get drug name from first view
        sample = await db.drug_views.find_one({"drug_id": drug_id})
        drug_name = sample.get("drug_name", "") if sample else ""

        doctors = [
            {
                "doctor_gid": r["_id"]["doctor_gid"],
                "doctor_name": r["_id"]["doctor_name"],
                "view_count": r["view_count"],
                "last_viewed": r["last_viewed"]
            }
            for r in results
        ]

        return {
            "analytics": [{
                "drug_id": drug_id,
                "drug_name": drug_name,
                "total_views": total_views,
                "unique_doctors": len(doctors),
                "doctors": doctors
            }]
        }
    else:
        # Top drugs by view count
        pipeline = [
            {"$group": {
                "_id": {"drug_id": "$drug_id", "drug_name": "$drug_name"},
                "total_views": {"$sum": 1},
                "unique_doctors": {"$addToSet": "$doctor_gid"}
            }},
            {"$project": {
                "drug_id": "$_id.drug_id",
                "drug_name": "$_id.drug_name",
                "total_views": 1,
                "unique_doctors": {"$size": "$unique_doctors"}
            }},
            {"$sort": {"total_views": -1}},
            {"$limit": limit}
        ]
        results = await db.drug_views.aggregate(pipeline).to_list(length=limit)

        analytics = [
            {
                "drug_id": r["drug_id"],
                "drug_name": r["drug_name"],
                "total_views": r["total_views"],
                "unique_doctors": r["unique_doctors"]
            }
            for r in results
        ]

        return {"analytics": analytics}


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
