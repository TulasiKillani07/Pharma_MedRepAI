"""
MedRepAI - Main Application Entry Point
This is where the FastAPI application is created and configured.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback
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


# Global exception handler — catches unhandled errors, logs full traceback
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}",
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "path": request.url.path,
            "method": request.method,
            "traceback": tb
        }
    )


# Log HTTP exceptions (401, 403, 404, etc.) as warnings
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code >= 500:
        logger.error(f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}")
    elif exc.status_code >= 400:
        logger.warning(f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


# Log validation errors (422) as warnings
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
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


# ══════════════════════════════════════════════════════════════
# Logs API — Admin-only access to mrx.log via API
# ══════════════════════════════════════════════════════════════

from fastapi import Depends, Query
from app.core.auth import require_admin
from app.utils.logger import get_log_directory


@app.get("/mrxdb/logs", summary="View Application Logs (Admin)", tags=["System"])
async def get_logs(
    lines: int = Query(100, ge=1, le=5000, description="Number of lines to return (from end)"),
    search: str = Query(None, description="Filter logs containing this text (e.g. ERROR, add_mr, 500)"),
    current_user=Depends(require_admin)
):
    """
    **Purpose:** View the MRX application log file via API. No SSH needed.

    **Access:** Admin only

    **Query params:**
    - `lines` — Number of lines from end (default: 100, max: 5000)
    - `search` — Filter lines containing this text (case-insensitive)

    **Examples:**
    - Last 100 lines: `GET /mrxdb/logs`
    - Last 50 errors: `GET /mrxdb/logs?lines=50&search=ERROR`
    - Find MR issues: `GET /mrxdb/logs?search=create_mr`
    - Find 500s: `GET /mrxdb/logs?search=Unhandled exception`
    """
    log_file = get_log_directory() / "mrx.log"

    if not log_file.exists():
        return {"lines": 0, "content": [], "log_file": str(log_file), "message": "Log file not found"}

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as e:
        return {"lines": 0, "content": [], "log_file": str(log_file), "message": f"Error reading log: {str(e)}"}

    # Filter by search term if provided
    if search:
        all_lines = [line for line in all_lines if search.lower() in line.lower()]

    # Get last N lines
    result_lines = all_lines[-lines:]

    return {
        "total_lines": len(all_lines),
        "returned_lines": len(result_lines),
        "search": search,
        "log_file": str(log_file),
        "content": [line.rstrip() for line in result_lines]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8004, reload=True)
