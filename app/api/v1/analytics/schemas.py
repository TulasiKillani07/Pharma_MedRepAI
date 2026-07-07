"""
Analytics Response Schemas
These are NOT stored in DB. They define the response shape for Swagger docs.
All data is computed on-the-fly from prescription_commitments.
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class DashboardResponse(BaseModel):
    """KPI dashboard cards"""
    committed_revenue: float = Field(..., description="Total committed revenue")
    net_revenue: float = Field(..., description="Revenue after discounts (approved only)")
    discount_given: float = Field(..., description="Total discount loss")
    pending_revenue: float = Field(..., description="Revenue waiting for approval")
    mom_growth: float = Field(..., description="Month-over-month growth %")
    total_commitments: int
    pending_approvals: int
    approved: int
    rejected: int
    approved_today: int
    rejected_today: int
    active_mrs: int
    active_doctors: int
    active_drugs: int


class DrugAnalyticsItem(BaseModel):
    """Single drug analytics row"""
    drug_id: str
    drug_name: str
    commitments: int
    committed_quantity: int
    rx_per_month: int
    committed_revenue: float
    net_revenue: float
    avg_discount: float
    approval_rate: float


class MRAnalyticsItem(BaseModel):
    """Single MR analytics row"""
    mr_id: str
    mr_name: str
    visits: int
    commitments: int
    conversion_rate: float
    committed_revenue: float
    net_revenue: float
    avg_revenue_per_visit: float
    avg_discount: float
    active_doctors: int


class DoctorAnalyticsItem(BaseModel):
    """Single doctor analytics row"""
    doctor_id: str
    doctor_name: str
    commitments: int
    committed_revenue: float
    net_revenue: float
    avg_discount: float
    most_prescribed_drug: Optional[str] = None
    mr_name: Optional[str] = None


class RegionAnalyticsItem(BaseModel):
    """Single region analytics row"""
    name: str
    commitments: int
    committed_revenue: float
    net_revenue: float
    doctors: int
    mrs: int


class TrendPoint(BaseModel):
    """Single month data point"""
    month: str


class RevenueTrend(TrendPoint):
    committed: float
    net: float


class CommitmentTrend(TrendPoint):
    count: int


class ApprovalTrend(TrendPoint):
    approved: int
    rejected: int


class TrendsResponse(BaseModel):
    """Monthly trends"""
    revenue_trend: List[dict]
    commitment_trend: List[dict]
    approval_trend: List[dict]
