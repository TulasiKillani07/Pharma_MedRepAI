"""
Main API Router for version 1.
This file combines all feature routes into a single router.
"""

from fastapi import APIRouter
from app.api.v1.auth.routes import router as auth_router
from app.api.v1.doctors.routes import router as doctors_router
from app.api.v1.mrs.routes import router as mrs_router
from app.api.v1.visits.routes import router as visits_router
from app.api.v1.drugs.routes import router as drugs_router
from app.api.v1.cme.routes import router as cme_router
from app.api.v1.dashboard.routes import router as dashboard_router
from app.api.v1.profile.routes import router as profile_router
from app.api.v1.notifications.routes import router as notifications_router
from app.api.v1.activity_logs.routes import router as activity_logs_router
from app.api.v1.search.routes import router as search_router
from app.api.v1.ai.routes import router as ai_router
from app.api.v1.communications.routes import router as communications_router
from app.api.v1.departments.routes import router as departments_router
from app.api.v1.grievances.routes import router as grievances_router
from app.api.v1.admin.routes import router as admin_router
from app.api.v1.sfe.routes import router as sfe_router


# Create main API router
api_router = APIRouter()


# Include all feature routers

# Authentication routes (login, register)
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# Doctor management routes
api_router.include_router(doctors_router, prefix="/doctors", tags=["Doctors"])

# MR management routes
api_router.include_router(mrs_router, prefix="/mrs", tags=["Medical Representatives"])

# Visit scheduling routes
api_router.include_router(visits_router, prefix="/visits", tags=["Visits"])

# Drug management routes
api_router.include_router(drugs_router, prefix="/drugs", tags=["Drugs"])

# CME events routes
api_router.include_router(cme_router, prefix="/cme", tags=["CME Events"])

# Dashboard routes
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])

# Profile routes
api_router.include_router(profile_router, prefix="/profile", tags=["Profile"])

# Notification routes
api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])

# Activity logs routes (Admin only)
api_router.include_router(activity_logs_router, prefix="/admin/activity-logs", tags=["Admin - Activity Logs"])

# Intelligent search routes
api_router.include_router(search_router, prefix="/search", tags=["Intelligent Search"])

# AI Report Analyzer routes
api_router.include_router(ai_router, prefix="/ai", tags=["AI Report Analyzer"])

# Communications routes (One-way Admin → MR broadcast)
api_router.include_router(communications_router, prefix="/communications", tags=["Communications"])

# Departments routes (Admin only - department management)
api_router.include_router(departments_router, prefix="/departments", tags=["Departments"])

# Grievances routes (MR creates, Admin responds)
api_router.include_router(grievances_router, prefix="/grievances", tags=["Grievances"])

# Admin management routes (General Admin only - create/manage department admins)
api_router.include_router(admin_router, prefix="/admin", tags=["Admin Management"])

# SFE (Sales Force Effectiveness) routes
api_router.include_router(sfe_router, tags=["SFE - Sales Force Effectiveness"])

# RCPA Analytics routes (Admin only - revenue, drugs, MRs, doctors, regions, trends)
from app.api.v1.analytics.routes import router as analytics_router
api_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics - RCPA"])

# Integration APIs (Service JWT only — backend-to-backend with DRX)
from app.api.v1.integration.routes import router as integration_router
api_router.include_router(integration_router, prefix="/integration", tags=["Integration (Service-to-Service)"])
