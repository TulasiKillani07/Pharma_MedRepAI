"""
RCPA Analytics Routes
All data sourced from prescription_commitments collection.
Nothing stored — computed on-the-fly every request.
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from app.core.auth import require_admin
from app.api.v1.analytics import service
from app.api.v1.analytics.schemas import (
    DashboardResponse, DrugAnalyticsItem, MRAnalyticsItem,
    DoctorAnalyticsItem, RegionAnalyticsItem, TrendsResponse
)

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse, summary="Dashboard KPI Cards")
async def dashboard(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020, le=2099),
    _=Depends(require_admin)
):
    """
    **Layer 1 — Dashboard Cards**
    
    Returns KPI overview:
    - committed_revenue, net_revenue, discount_given, pending_revenue
    - mom_growth (month-over-month %)
    - total_commitments, pending_approvals, approved, rejected
    - approved_today, rejected_today
    - active_mrs, active_doctors, active_drugs
    """
    return await service.get_dashboard(month, year)


@router.get("/drugs", response_model=List[DrugAnalyticsItem], summary="Drug Analytics")
async def drug_analytics(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020, le=2099),
    _=Depends(require_admin)
):
    """
    **Per-drug breakdown:**
    - drug_name, commitments, committed_quantity, rx_per_month
    - committed_revenue, net_revenue
    - avg_discount, approval_rate
    
    Sorted by committed_revenue descending.
    """
    return await service.get_drug_analytics(month, year)


@router.get("/mrs", response_model=List[MRAnalyticsItem], summary="MR Analytics")
async def mr_analytics(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020, le=2099),
    _=Depends(require_admin)
):
    """
    **Per-MR breakdown:**
    - mr_name, visits, commitments, conversion_rate
    - committed_revenue, net_revenue, avg_revenue_per_visit
    - avg_discount, active_doctors
    
    Sorted by committed_revenue descending.
    """
    return await service.get_mr_analytics(month, year)


@router.get("/doctors", response_model=List[DoctorAnalyticsItem], summary="Doctor Analytics")
async def doctor_analytics(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020, le=2099),
    _=Depends(require_admin)
):
    """
    **Per-doctor breakdown:**
    - doctor_name, commitments, committed_revenue, net_revenue
    - avg_discount, most_prescribed_drug, mr_name
    
    Sorted by committed_revenue descending.
    """
    return await service.get_doctor_analytics(month, year)


@router.get("/location-doctors", summary="Doctors by Location (Revenue Ranking)")
async def doctors_by_location(
    location: str = Query(..., description="Location name (e.g. Apollo Hospital)"),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020, le=2099),
    _=Depends(require_admin)
):
    """
    **Which doctors generated the most revenue at a specific location?**
    
    ```
    GET /analytics/regions/doctors?location=Apollo Hospital&month=7&year=2026
    ```
    
    Returns doctors ranked by revenue at that location.
    """
    return await service.get_doctors_by_location(location, month, year)


@router.get("/regions", response_model=List[RegionAnalyticsItem], summary="Region Analytics (Drill-down)")
async def region_analytics(
    level: str = Query("state", description="Drill-down level: state, district, area, hospital"),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020, le=2099),
    state: Optional[str] = Query(None, description="Filter by state (for district/area drill-down)"),
    district: Optional[str] = Query(None, description="Filter by district (for area drill-down)"),
    location_type: Optional[str] = Query(None, description="Filter by location type: hospital, solo_clinic, polyclinic"),
    _=Depends(require_admin)
):
    """
    **Region drill-down (like Tableau):**
    
    - `level=state` → Revenue by state
    - `level=district&state=Telangana` → Districts within Telangana
    - `level=area&district=Hyderabad` → Areas within Hyderabad
    - `level=hospital` → All locations by name
    - `level=hospital&location_type=solo_clinic` → Only solo clinics
    - `level=hospital&location_type=hospital` → Only hospitals
    - `level=hospital&location_type=polyclinic` → Only polyclinics
    
    Each returns: name, commitments, committed_revenue, net_revenue, doctors, mrs
    """
    return await service.get_region_analytics(level, month, year, state, district, location_type)


@router.get("/trends", response_model=TrendsResponse, summary="Monthly Trends")
async def trends(
    months: int = Query(6, ge=2, le=12, description="Number of months to show"),
    _=Depends(require_admin)
):
    """
    **Monthly trends (last N months):**
    
    - revenue_trend: [{month, committed, net}]
    - commitment_trend: [{month, count}]
    - approval_trend: [{month, approved, rejected}]
    
    Used for line/bar charts.
    """
    return await service.get_trends(months)
