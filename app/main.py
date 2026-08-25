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

## Authentication

MRX uses **Proxzar** (`https://oauth2.proxzar.ai`) as its **sole authentication provider**.

### How to authenticate:

Include a Proxzar JWT in every request:
```
Authorization: Bearer <Proxzar JWT>
```

### Token claims:

| Claim | Expected |
|-------|----------|
| `iss` | `https://oauth2.proxzar.ai` |
| `aud` | Must include `MRX` |
| `sub` | Global username |
| `role` | `ADMIN`, `MR`, or `DOCTOR` |

### Roles & Access:

**User-facing endpoints** (`/auth/me`, `/doctors`, `/mrs`, `/drugs`, `/visits`, etc.):
- `ADMIN` — Full access
- `MR` — MR access
- `DOCTOR` — Rejected (use DRX)

**Integration endpoints** (`/integration/*`):
- `ADMIN`, `MR`, `DOCTOR` — All accepted (DRX forwards tokens)

**DRX outbound** (`/integration/drx/*`):
- `ADMIN` only — Search/view/request DRX doctors

---

## DRX ↔ MRX Communication

All communication uses the same Proxzar JWT. No client_id/secret/service token.

| Direction | How |
|-----------|-----|
| MRX → DRX | Forwards user's Proxzar JWT |
| DRX → MRX | Forwards user's Proxzar JWT |

---

## Doctor Request Flow (MRX → DRX)

```
MRX Admin
    ↓
POST /integration/drx/doctor-requests {"username": "rahul_mehta"}
    ↓
MRX attaches organization_gid, forwards to DRX
    ↓
DRX notifies doctor
    ↓
Doctor accepts → DRX Admin approves → Doctor added to MRX
```

---

## Deprecated Endpoints

`POST /auth/login`, `/auth/reset-password`, `/auth/forgot-password` — return `410 Gone`.
""",
    docs_url="/mrxdb/docs",
    redoc_url="/mrxdb/redoc",
    openapi_url="/mrxdb/openapi.json",
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8004, reload=True)
