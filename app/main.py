"""
MedRepAI - Main Application Entry Point
This is where the FastAPI application is created and configured.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection
from app.api.v1.router import api_router
from app.utils.logger import get_medrep_logger
from app.utils.json_response import CustomJSONResponse

# Initialize logger
logger = get_medrep_logger(__name__)


# Create FastAPI application instance
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""# MedRep AI - Pharmaceutical Sales Force Automation Platform

## Authentication Architecture

MRX uses **Proxzar** (`https://oauth2.proxzar.ai`) as its **sole authentication provider**.

There is no MRX-issued user JWT. All authentication is via Proxzar-issued RS256 tokens verified against the Proxzar JWKS endpoint.

---

### How to authenticate:

1. Obtain a JWT from Proxzar OAuth (`https://oauth2.proxzar.ai`)
2. Include it in every request:
   ```
   Authorization: Bearer <Proxzar JWT>
   ```

### Token structure:

```json
{
  "sub": "rahul_mehta",
  "iss": "https://oauth2.proxzar.ai",
  "aud": ["DRX", "MRX", "TMS"],
  "role": "MR",
  "exp": 1787140344
}
```

### Token verification (performed by MRX):

| Check | Expected |
|-------|----------|
| Signature | RS256 verified via Proxzar JWKS |
| `iss` | `https://oauth2.proxzar.ai` |
| `aud` | Must include `MRX` |
| `kid` | Must match a key in JWKS |
| `exp` | Must not be expired |
| `sub` | Global username (looked up in MRX database) |

---

## Roles & Access

### User-facing endpoints (`/auth/me`, `/doctors`, `/mrs`, `/drugs`, `/visits`, etc.):

| Role | Access | Collection |
|------|--------|------------|
| `ADMIN` | Full platform access | `company_admins.username` |
| `MR` | Medical Representative access | `mrs.username` |
| `DOCTOR` | **Rejected** (doctors use DRX) | — |

### Integration endpoints (`/integration/*`):

| Role | Access | Collection |
|------|--------|------------|
| `ADMIN` | Allowed | `company_admins.username` |
| `MR` | Allowed | `mrs.username` |
| `DOCTOR` | Allowed (DRX forwards doctor tokens) | `doctors.username` |
| Service JWT | Allowed (background/machine-to-machine) | — |

---

## DRX ↔ MRX Communication

### User-driven (DRX → MRX):
DRX forwards the **same Proxzar JWT** received from the logged-in user. MRX independently verifies it via Proxzar JWKS.

### User-driven (MRX → DRX):
MRX forwards the **same Proxzar JWT** to DRX. DRX independently verifies it.

### Background/Machine-to-machine:
Uses existing Service JWT (`POST /integration/auth/service-token` with `client_id` + `client_secret`).

No `client_id`/`client_secret` needed for user-driven communication.

---

## Username (Global Identity)

All users have a `username` field — the same identity across Proxzar, DOBO, DRX, and MRX.

```
Proxzar sub = rahul_mehta
MRX username = rahul_mehta
DRX username = rahul_mehta
```

Username is **required** when creating any user (Admin, MR, or Doctor). Do not derive it from email.

---

## Deprecated Endpoints

| Endpoint | Status |
|----------|--------|
| `POST /auth/login` | `410 Gone` — use Proxzar |
| `POST /auth/reset-password` | `410 Gone` — use Proxzar |
| `POST /auth/forgot-password` | `410 Gone` — use Proxzar |
| `POST /auth/forgot-password/verify` | `410 Gone` — use Proxzar |
""",
    docs_url="/mrxdb/docs",
    redoc_url="/mrxdb/redoc",
    default_response_class=CustomJSONResponse
)

# Configure CORS (Cross-Origin Resource Sharing)
# This allows frontend applications to make requests to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins like ["https://yourfrontend.com"]
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)


# Event: Application Startup
@app.on_event("startup")
async def startup_event():
    """
    This function runs when the application starts.
    It connects to MongoDB.
    """
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await connect_to_mongo()
    logger.info("Application started successfully!")


# Event: Application Shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """
    This function runs when the application shuts down.
    It closes the MongoDB connection.
    """
    logger.info("Shutting down application...")
    await close_mongo_connection()
    logger.info("Application shut down successfully!")


# Include API routes
# All API endpoints will be prefixed with /api/v1
app.include_router(api_router, prefix="/mrxdb")


# Root route — prevents 404 when browsers hit the base URL
@app.get("/mrxdb", include_in_schema=False)
async def root():
    return {"service": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/mrxdb/docs"}


# Favicon — prevents 404 from browser favicon requests
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)


