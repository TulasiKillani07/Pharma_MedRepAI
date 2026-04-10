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
from app.api.v1.feed.routes import router as feed_router

# Import routers from each feature as we create them
# from app.api.v1.feed.routes import router as feed_router
# from app.api.v1.chat.routes import router as chat_router


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
api_router.include_router(feed_router, prefix="/network/feed", tags=["Network - Feed"])
