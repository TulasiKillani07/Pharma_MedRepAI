"""
MedRepAI - Main Application Entry Point
This is where the FastAPI application is created and configured.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection
from app.api.v1.router import api_router
from app.utils.logger import get_medrep_logger
from datetime import datetime
import json

# Initialize logger
logger = get_medrep_logger(__name__)


# Custom JSON encoder for datetime serialization
class CustomJSONResponse(JSONResponse):
    """Custom JSON response that handles datetime serialization"""
    
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            default=self.json_encoder_default
        ).encode("utf-8")
    
    @staticmethod
    def json_encoder_default(obj):
        """Custom JSON encoder for datetime objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# Create FastAPI application instance
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
# MedRep AI - Pharmaceutical Sales Force Automation Platform

A comprehensive platform for managing pharmaceutical sales operations, connecting Medical Representatives (MRs), Doctors, and Administrators.

---

## 🔐 Authentication & Authorization

### Roles
- **ADMIN**: Company administrators with full system access
- **MR**: Medical Representatives managing doctor relationships
- **DOCTOR**: Healthcare professionals receiving product information

### Auth Endpoints
- `POST /api/v1/auth/login` - Login with email/password, returns JWT token
- `POST /api/v1/auth/change-password` - Change password (first login required)
- `GET /api/v1/profile/me` - Get current user profile (role-specific response)

---

## 👥 User Management

### MR Management (Admin Only)
- `POST /api/v1/mrs` - Add new MR with assigned doctors and drugs
- `GET /api/v1/mrs` - List all MRs with assigned doctor/drug details
- `GET /api/v1/mrs/{mr_id}` - Get MR details
- `PUT /api/v1/mrs/{mr_id}` - Update MR (phone, territory, assigned doctors/drugs)
- `DELETE /api/v1/mrs/{mr_id}` - Deactivate MR
- `POST /api/v1/mrs/bulk-upload` - Bulk upload MRs from CSV/Excel
- `GET /api/v1/mrs/download-template` - Download CSV template
- `GET /api/v1/mrs/filter` - Filter MRs by zone/state/territory

**New Features:**
- ✅ **assigned_drugs**: Admin can assign multiple drugs/products to each MR
- ✅ **Geographic fields**: zone, state, territory for communications targeting

### Doctor Management

#### Admin Operations
- `POST /api/v1/doctors` - Add new doctor (Admin only)
- `GET /api/v1/doctors` - List all doctors
- `GET /api/v1/doctors/available` - List unassigned doctors (Admin only)
- `GET /api/v1/doctors/{doctor_id}` - Get doctor details
- `PUT /api/v1/doctors/{doctor_id}` - Update doctor
- `DELETE /api/v1/doctors/{doctor_id}` - Deactivate doctor (Admin only)
- `POST /api/v1/doctors/bulk-upload` - Bulk upload doctors from CSV/Excel
- `GET /api/v1/doctors/download-template` - Download CSV template

#### 🆕 Doctor Approval Workflow (MR → Admin)
- `POST /api/v1/doctors/request` - **MR requests to add doctor** (requires admin approval)
- `GET /api/v1/doctors/requests` - View doctor requests (Admin: all, MR: own)
- `POST /api/v1/doctors/requests/{request_id}/approve` - **Admin approves** (creates doctor account)
- `POST /api/v1/doctors/requests/{request_id}/reject` - **Admin rejects** (with reason)

**Workflow:**
1. MR submits doctor details → Admin receives notification
2. Admin reviews request → Approves or Rejects
3. If approved: Doctor account created, invitation email sent
4. MR receives notification of decision

---

## 💊 Drug/Product Management (Admin Only)
- `POST /api/v1/drugs` - Add new drug/product
- `GET /api/v1/drugs` - List all drugs
- `GET /api/v1/drugs/{drug_id}` - Get drug details
- `PUT /api/v1/drugs/{drug_id}` - Update drug
- `DELETE /api/v1/drugs/{drug_id}` - Delete drug

---

## 📅 Visit Management

### Basic Visit Operations
- `POST /api/v1/visits` - Schedule visit (MR → Doctor)
- `GET /api/v1/visits` - List visits (filtered by role)
- `GET /api/v1/visits/{visit_id}` - Get visit details
- `PUT /api/v1/visits/{visit_id}` - Update visit
- `DELETE /api/v1/visits/{visit_id}` - Cancel visit

### 🆕 SFE-Enhanced Visit Completion
- `POST /api/v1/visits/{visit_id}/complete` - Complete visit with SFE data
  - Products promoted
  - Samples given
  - Doctor mood/receptiveness
  - Competitor information
  - Follow-up date
  - Prescription commitment
  - GPS location

---

## 📊 Sales Force Effectiveness (SFE)

### Doctor Classification & Assignment
- `POST /api/v1/sfe/doctor-assignments` - Classify doctor (A/B/C) and set visit frequency
- `GET /api/v1/sfe/doctor-assignments` - List MR's assigned doctors with classifications
- `PUT /api/v1/sfe/doctor-assignments/{assignment_id}` - Update classification
- `GET /api/v1/sfe/doctor-assignments/summary` - Get classification summary

**Doctor Classes:**
- **Class A**: High-value, 2 visits/month required
- **Class B**: Medium-value, 1 visit/month required
- **Class C**: Low-value, 1 visit/2 months required

### MCR (Monthly Call Report)
- `GET /api/v1/sfe/mcr` - Calculate doctor coverage percentage
  - Formula: (Unique doctors visited / Total assigned) × 100
  - Filters: month, year, mr_id, territory

### MVC (Monthly Visit Coverage)
- `GET /api/v1/sfe/mvc` - Calculate visit frequency compliance
  - Formula: (Doctors with required visits / Total assigned) × 100
  - Tracks if doctors received required visits per classification

### RCPA (Prescription Commitments)
- `POST /api/v1/sfe/prescription-commitments` - Record doctor's prescription commitment
- `GET /api/v1/sfe/prescription-commitments` - List commitments
- `PUT /api/v1/sfe/prescription-commitments/{commitment_id}` - Update commitment
- `GET /api/v1/sfe/prescription-commitments/summary` - Aggregate commitment data

### SFE Dashboard
- `GET /api/v1/sfe/dashboard` - Company-wide SFE overview
  - MCR/MVC leaderboards
  - Territory performance
  - Top performers
  - Alerts (low coverage, missed visits)
- `GET /api/v1/sfe/dashboard/mr/{mr_id}` - Individual MR drill-down

### Chemist Check (Field Stock Verification)
- `POST /api/v1/sfe/chemist-checks` - Record pharmacy stock observation
- `GET /api/v1/sfe/chemist-checks` - List chemist checks
- `GET /api/v1/sfe/chemist-checks/summary` - Stock availability analysis

---

## 🎓 CME (Continuing Medical Education)

### CME Management (Admin)
- `POST /api/v1/cme` - Create CME event
- `GET /api/v1/cme` - List CME events
- `GET /api/v1/cme/{cme_id}` - Get CME details
- `PUT /api/v1/cme/{cme_id}` - Update CME
- `DELETE /api/v1/cme/{cme_id}` - Cancel CME

### CME Registration (Doctor)
- `POST /api/v1/cme/{cme_id}/register` - Register for CME
- `POST /api/v1/cme/{cme_id}/cancel-registration` - Cancel registration
- `GET /api/v1/cme/my-registrations` - View my registrations

---

## 📱 Social Network Features

### Connections (Doctor ↔ Doctor)
- `POST /api/v1/connections/request` - Send connection request
- `POST /api/v1/connections/accept/{request_id}` - Accept request
- `POST /api/v1/connections/reject/{request_id}` - Reject request
- `GET /api/v1/connections` - List connections
- `GET /api/v1/connections/requests` - List pending requests
- `DELETE /api/v1/connections/{connection_id}` - Remove connection

### Feed (Posts, Likes, Comments)
- `POST /api/v1/feed/posts` - Create post
- `GET /api/v1/feed/posts` - View feed
- `POST /api/v1/feed/posts/{post_id}/like` - Like post
- `POST /api/v1/feed/posts/{post_id}/comment` - Comment on post
- `DELETE /api/v1/feed/posts/{post_id}` - Delete post

---

## 💬 Communications (Admin → MR/Doctor)
- `POST /api/v1/communications` - Send targeted communication
  - Target by role, territory, state, zone
  - Supports text, image, video, document
- `GET /api/v1/communications` - List communications
- `GET /api/v1/communications/{communication_id}` - Get communication details

---

## 🔔 Notifications
- `GET /api/v1/notifications` - Get notifications (paginated)
- `GET /api/v1/notifications/unread-count` - Get unread count
- `POST /api/v1/notifications/{notification_id}/read` - Mark as read
- `POST /api/v1/notifications/mark-all-read` - Mark all as read
- `DELETE /api/v1/notifications/{notification_id}` - Delete notification
- `DELETE /api/v1/notifications/clear-all` - Clear all notifications

**Notification Types:**
- Connection requests/accepted
- CME events/reminders
- Visit scheduled/completed
- Doctor request pending/approved/rejected
- Post interactions

---

## 📈 Dashboard & Analytics
- `GET /api/v1/dashboard` - Role-specific dashboard
  - Admin: Company-wide metrics
  - MR: Personal performance, assigned doctors
  - Doctor: CME events, connections

---

## 📋 Activity Logs (Admin Only)
- `GET /api/v1/activity-logs` - View system activity logs
  - User actions (created, updated, deactivated)
  - Bulk uploads
  - Login attempts
  - Filters: action_type, actor_role, severity, date range

---

## 🤖 AI Features
- `POST /api/v1/ai/analyze-report` - Analyze medical report with AI
- `POST /api/v1/ai/chat` - Chat with AI assistant

---

## 📊 Key Features Summary

### ✅ Recently Implemented
1. **MR assigned_drugs** - Admin assigns multiple drugs/products to MRs
2. **Doctor Approval Workflow** - MR requests → Admin approves → Doctor created
3. **SFE Module** - Complete sales force effectiveness tracking (6 slices)
4. **Geographic Targeting** - Zone/State/Territory for communications
5. **Logger System** - Centralized logging to C:\\Logs\\MedRep_AI\\app.log

### 🔒 Security Features
- JWT-based authentication
- Role-based access control (RBAC)
- Password hashing (bcrypt)
- First login password change required
- Activity logging for audit trail

### 📧 Email Features
- Invitation emails with credentials
- Bulk upload summary emails
- CME registration confirmations

---

## 🚀 Getting Started

### Authentication Flow
1. Login: `POST /api/v1/auth/login` with email/password
2. Receive JWT token in response
3. Include token in all requests: `Authorization: Bearer <token>`
4. First login: Change password via `POST /api/v1/auth/change-password`

### Example Request
```bash
# Login
curl -X POST "http://localhost:8000/api/v1/auth/login" \\
  -H "Content-Type: application/json" \\
  -d '{"email": "admin@company.com", "password": "Welcome@123"}'

# Use token in subsequent requests
curl -X GET "http://localhost:8000/api/v1/profile/me" \\
  -H "Authorization: Bearer <your_token_here>"
```

---

## 📚 Documentation
- **Swagger UI**: http://localhost:8000/docs (Interactive API testing)
- **ReDoc**: http://localhost:8000/redoc (Clean API documentation)

---

## 🏢 Database Collections
- admins, mrs, doctors - User accounts
- drugs - Product catalog
- visits - Visit scheduling and completion
- doctor_assignments - SFE doctor classifications
- prescription_commitments - RCPA data
- chemist_checks - Pharmacy stock observations
- doctor_requests - Doctor approval workflow
- cme_events, cme_registrations - CME management
- connections, connection_requests - Social network
- posts, comments, likes - Feed system
- communications - Targeted messaging
- notifications - Real-time notifications
- activity_logs - Audit trail

---

**Version**: 1.0.0  
**Environment**: Development  
**Base URL**: http://localhost:8000/api/v1
""",
    docs_url="/docs",  # Swagger UI at http://localhost:8000/docs
    redoc_url="/redoc",  # ReDoc at http://localhost:8000/redoc
    default_response_class=CustomJSONResponse  # Use custom JSON response for datetime serialization
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
app.include_router(api_router, prefix="/api/v1")


# Run the application
# Command: uvicorn app.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Auto-reload on code changes (only for development)
    )
