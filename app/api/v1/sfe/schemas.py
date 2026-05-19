"""
SFE (Sales Force Effectiveness) request/response schemas.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum
from app.models.sfe_models import DoctorClass, DoctorMood, CommitmentConfidence



# ============================================================================
# ENUMS (Re-export for API use)
# ============================================================================

class DoctorClassEnum(str, Enum):
    """Doctor classification"""
    A = "A"
    B = "B"
    C = "C"


class DoctorMoodEnum(str, Enum):
    """Doctor mood during visit"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class CommitmentConfidenceEnum(str, Enum):
    """Confidence level"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ============================================================================
# VISIT COMPLETION EXTENSION
# ============================================================================

class RxCommitmentRequest(BaseModel):
    """Prescription commitment data"""
    product_id: str = Field(..., description="Product/Drug ID")
    rx_per_week: int = Field(..., ge=1, le=1000, description="Expected prescriptions per week")
    confidence: CommitmentConfidenceEnum = Field(default=CommitmentConfidenceEnum.MEDIUM, description="Confidence level")
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_id": "507f1f77bcf86cd799439011",
                "rx_per_week": 15,
                "confidence": "high"
            }
        }


class VisitCompleteExtendedRequest(BaseModel):
    """Extended visit completion request with SFE fields"""
    # Original fields
    outcome: str = Field(..., min_length=10, max_length=1000, description="Visit outcome summary")
    feedback: Optional[str] = Field(None, max_length=1000, description="Additional feedback")
    
    # SFE fields
    products_promoted: List[str] = Field(default_factory=list, description="List of product IDs promoted")
    samples_given: int = Field(default=0, ge=0, le=1000, description="Number of samples distributed")
    doctor_mood: Optional[DoctorMoodEnum] = Field(None, description="Doctor's receptiveness")
    competitor_info: Optional[str] = Field(None, max_length=500, description="Competitor information")
    followup_date: Optional[date] = Field(None, description="Next follow-up date (YYYY-MM-DD)")
    rx_commitment: Optional[RxCommitmentRequest] = Field(None, description="Prescription commitment")
    gps_lat: Optional[float] = Field(None, ge=-90, le=90, description="GPS latitude")
    gps_lng: Optional[float] = Field(None, ge=-180, le=180, description="GPS longitude")
    
    @field_validator('followup_date')
    @classmethod
    def validate_followup_date(cls, v: Optional[date]) -> Optional[date]:
        """Validate follow-up date is in the future"""
        if v and v < date.today():
            raise ValueError('Follow-up date must be in the future')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "outcome": "Successfully presented new product line. Doctor showed interest in Amlovas 5mg.",
                "feedback": "Doctor requested follow-up meeting next month",
                "products_promoted": ["507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012"],
                "samples_given": 10,
                "doctor_mood": "positive",
                "competitor_info": "Doctor mentioned competitor's new diabetes drug",
                "followup_date": "2026-06-15",
                "rx_commitment": {
                    "product_id": "507f1f77bcf86cd799439011",
                    "rx_per_week": 15,
                    "confidence": "high"
                },
                "gps_lat": 17.3850,
                "gps_lng": 78.4867
            }
        }


# ============================================================================
# DOCTOR CLASSIFICATION
# ============================================================================

class DoctorClassifyRequest(BaseModel):
    """Request to classify a doctor"""
    classification: DoctorClassEnum = Field(..., description="Doctor class (A/B/C)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "classification": "A"
            }
        }


class DoctorClassificationResponse(BaseModel):
    """Doctor classification details"""
    doctor_id: str
    doctor_name: str
    mr_id: str
    mr_name: str
    classification: str
    visit_frequency: int
    territory: Optional[str] = None
    zone: Optional[str] = None
    state: Optional[str] = None
    assigned_at: datetime
    updated_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "doctor_id": "507f1f77bcf86cd799439011",
                "doctor_name": "Dr. Arjun Sharma",
                "mr_id": "507f1f77bcf86cd799439012",
                "mr_name": "Rajesh Kumar",
                "classification": "A",
                "visit_frequency": 4,
                "territory": "Visakhapatnam",
                "zone": "South",
                "state": "Andhra Pradesh",
                "assigned_at": "2026-05-01T10:00:00",
                "updated_at": "2026-05-19T15:30:00"
            }
        }


# ============================================================================
# SFE CONFIG
# ============================================================================

class SFEConfigResponse(BaseModel):
    """SFE configuration response"""
    visit_frequency_config: dict = Field(..., description="Visit frequency per class")
    updated_by: Optional[str] = None
    updated_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "visit_frequency_config": {
                    "A": 4,
                    "B": 2,
                    "C": 1
                },
                "updated_by": "admin_id",
                "updated_at": "2026-05-19T10:00:00"
            }
        }


class SFEConfigUpdateRequest(BaseModel):
    """Request to update SFE config"""
    A: int = Field(..., ge=1, le=30, description="Visits per month for A-class doctors")
    B: int = Field(..., ge=1, le=30, description="Visits per month for B-class doctors")
    C: int = Field(..., ge=1, le=30, description="Visits per month for C-class doctors")
    
    class Config:
        json_schema_extra = {
            "example": {
                "A": 4,
                "B": 2,
                "C": 1
            }
        }


# ============================================================================
# MCR (MONTHLY CALL REPORT)
# ============================================================================

class MCRDoctorVisited(BaseModel):
    """Doctor who was visited"""
    doctor_id: str
    doctor_name: str
    classification: Optional[str] = None
    visits_count: int
    last_visit_date: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "doctor_id": "507f1f77bcf86cd799439011",
                "doctor_name": "Dr. Arjun Sharma",
                "classification": "A",
                "visits_count": 3,
                "last_visit_date": "2026-05-15T14:30:00"
            }
        }


class MCRDoctorNotVisited(BaseModel):
    """Doctor who was not visited"""
    doctor_id: str
    doctor_name: str
    classification: Optional[str] = None
    last_visited: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "doctor_id": "507f1f77bcf86cd799439012",
                "doctor_name": "Dr. Priya Reddy",
                "classification": "B",
                "last_visited": "2026-04-20T10:15:00"
            }
        }


class MCRResponse(BaseModel):
    """MCR (Monthly Call Report) response"""
    mr_id: str
    mr_name: str
    month: int
    year: int
    total_assigned: int
    doctors_visited: int
    doctors_not_visited: int
    mcr_percentage: float
    visited: List[MCRDoctorVisited]
    not_visited: List[MCRDoctorNotVisited]
    
    class Config:
        json_schema_extra = {
            "example": {
                "mr_id": "507f1f77bcf86cd799439013",
                "mr_name": "Rajesh Kumar",
                "month": 5,
                "year": 2026,
                "total_assigned": 50,
                "doctors_visited": 42,
                "doctors_not_visited": 8,
                "mcr_percentage": 84.0,
                "visited": [
                    {
                        "doctor_id": "507f1f77bcf86cd799439011",
                        "doctor_name": "Dr. Arjun Sharma",
                        "classification": "A",
                        "visits_count": 3,
                        "last_visit_date": "2026-05-15T14:30:00"
                    }
                ],
                "not_visited": [
                    {
                        "doctor_id": "507f1f77bcf86cd799439012",
                        "doctor_name": "Dr. Priya Reddy",
                        "classification": "B",
                        "last_visited": "2026-04-20T10:15:00"
                    }
                ]
            }
        }


# ============================================================================
# MVC (MONTHLY VISIT COVERAGE)
# ============================================================================

class MVCDoctorDetail(BaseModel):
    """Doctor visit coverage detail"""
    doctor_id: str
    doctor_name: str
    classification: Optional[str] = None
    required_visits: int
    actual_visits: int
    status: str  # "covered", "under", "missed"
    compliance_percentage: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "doctor_id": "507f1f77bcf86cd799439011",
                "doctor_name": "Dr. Arjun Sharma",
                "classification": "A",
                "required_visits": 4,
                "actual_visits": 4,
                "status": "covered",
                "compliance_percentage": 100.0
            }
        }


class MVCResponse(BaseModel):
    """MVC (Monthly Visit Coverage) response"""
    mr_id: str
    mr_name: str
    month: int
    year: int
    total_assigned: int
    fully_covered: int
    under_covered: int
    not_visited: int
    mvc_percentage: float
    avg_compliance: float
    doctors: List[MVCDoctorDetail]
    
    class Config:
        json_schema_extra = {
            "example": {
                "mr_id": "507f1f77bcf86cd799439013",
                "mr_name": "Rajesh Kumar",
                "month": 5,
                "year": 2026,
                "total_assigned": 50,
                "fully_covered": 36,
                "under_covered": 10,
                "not_visited": 4,
                "mvc_percentage": 72.0,
                "avg_compliance": 85.5,
                "doctors": [
                    {
                        "doctor_id": "507f1f77bcf86cd799439011",
                        "doctor_name": "Dr. Arjun Sharma",
                        "classification": "A",
                        "required_visits": 4,
                        "actual_visits": 4,
                        "status": "covered",
                        "compliance_percentage": 100.0
                    },
                    {
                        "doctor_id": "507f1f77bcf86cd799439012",
                        "doctor_name": "Dr. Sneha Patel",
                        "classification": "A",
                        "required_visits": 4,
                        "actual_visits": 2,
                        "status": "under",
                        "compliance_percentage": 50.0
                    },
                    {
                        "doctor_id": "507f1f77bcf86cd799439013",
                        "doctor_name": "Dr. Priya Reddy",
                        "classification": "C",
                        "required_visits": 1,
                        "actual_visits": 0,
                        "status": "missed",
                        "compliance_percentage": 0.0
                    }
                ]
            }
        }


# ============================================================================
# RCPA (PRESCRIPTION COMMITMENTS)
# ============================================================================

class RCPACreateRequest(BaseModel):
    """Manual RCPA commitment creation"""
    doctor_id: str = Field(..., description="Doctor ID")
    product_id: str = Field(..., description="Product/Drug ID")
    rx_per_week: int = Field(..., ge=1, le=1000, description="Expected prescriptions per week")
    confidence: CommitmentConfidenceEnum = Field(default=CommitmentConfidenceEnum.MEDIUM, description="Confidence level")
    visit_id: Optional[str] = Field(None, description="Associated visit ID (if from visit)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "doctor_id": "507f1f77bcf86cd799439011",
                "product_id": "507f1f77bcf86cd799439021",
                "rx_per_week": 15,
                "confidence": "high",
                "visit_id": "507f1f77bcf86cd799439031"
            }
        }


class RCPAUpdateRequest(BaseModel):
    """Update existing RCPA commitment"""
    rx_per_week: Optional[int] = Field(None, ge=1, le=1000, description="Updated prescriptions per week")
    confidence: Optional[CommitmentConfidenceEnum] = Field(None, description="Updated confidence level")
    status: Optional[str] = Field(None, description="Status: active, fulfilled, cancelled")
    
    class Config:
        json_schema_extra = {
            "example": {
                "rx_per_week": 20,
                "confidence": "high",
                "status": "active"
            }
        }


class RCPACommitmentResponse(BaseModel):
    """Single RCPA commitment"""
    id: str
    mr_id: str
    mr_name: str
    doctor_id: str
    doctor_name: str
    product_id: str
    product_name: str
    rx_per_week: int
    confidence: str
    status: str
    visit_id: Optional[str] = None
    territory: Optional[str] = None
    zone: Optional[str] = None
    state: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439041",
                "mr_id": "507f1f77bcf86cd799439013",
                "mr_name": "Rajesh Kumar",
                "doctor_id": "507f1f77bcf86cd799439011",
                "doctor_name": "Dr. Arjun Sharma",
                "product_id": "507f1f77bcf86cd799439021",
                "product_name": "Amlovas 5mg",
                "rx_per_week": 15,
                "confidence": "high",
                "status": "active",
                "visit_id": "507f1f77bcf86cd799439031",
                "territory": "Visakhapatnam",
                "zone": "South",
                "state": "Andhra Pradesh",
                "created_at": "2026-05-18T14:30:00",
                "updated_at": "2026-05-19T10:15:00"
            }
        }


class RCPAListResponse(BaseModel):
    """List of RCPA commitments"""
    total: int
    commitments: List[RCPACommitmentResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 25,
                "commitments": [
                    {
                        "id": "507f1f77bcf86cd799439041",
                        "mr_id": "507f1f77bcf86cd799439013",
                        "mr_name": "Rajesh Kumar",
                        "doctor_id": "507f1f77bcf86cd799439011",
                        "doctor_name": "Dr. Arjun Sharma",
                        "product_id": "507f1f77bcf86cd799439021",
                        "product_name": "Amlovas 5mg",
                        "rx_per_week": 15,
                        "confidence": "high",
                        "status": "active",
                        "territory": "Visakhapatnam",
                        "created_at": "2026-05-18T14:30:00"
                    }
                ]
            }
        }


class RCPAProductSummary(BaseModel):
    """RCPA summary by product"""
    product_id: str
    product_name: str
    rx_per_week: int
    doctors_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_id": "507f1f77bcf86cd799439021",
                "product_name": "Amlovas 5mg",
                "rx_per_week": 200,
                "doctors_count": 12
            }
        }


class RCPATerritorySummary(BaseModel):
    """RCPA summary by territory"""
    territory: str
    rx_per_week: int
    doctors_count: int
    products_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "territory": "Visakhapatnam",
                "rx_per_week": 180,
                "doctors_count": 15,
                "products_count": 5
            }
        }


class RCPASummaryResponse(BaseModel):
    """RCPA summary for admin"""
    total_rx_per_week: int
    total_commitments: int
    total_doctors: int
    total_products: int
    by_product: List[RCPAProductSummary]
    by_territory: List[RCPATerritorySummary]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_rx_per_week": 1200,
                "total_commitments": 85,
                "total_doctors": 65,
                "total_products": 8,
                "by_product": [
                    {
                        "product_id": "507f1f77bcf86cd799439021",
                        "product_name": "Amlovas 5mg",
                        "rx_per_week": 450,
                        "doctors_count": 25
                    }
                ],
                "by_territory": [
                    {
                        "territory": "Visakhapatnam",
                        "rx_per_week": 350,
                        "doctors_count": 20,
                        "products_count": 6
                    }
                ]
            }
        }


# ============================================================================
# SFE DASHBOARD
# ============================================================================

class MRPerformance(BaseModel):
    """Individual MR performance metrics"""
    mr_id: str
    mr_name: str
    territory: Optional[str] = None
    zone: Optional[str] = None
    state: Optional[str] = None
    mcr_percentage: float
    mvc_percentage: float
    avg_compliance: float
    total_assigned: int
    doctors_visited: int
    rcpa_commitments: int
    rx_per_week: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "mr_id": "507f1f77bcf86cd799439013",
                "mr_name": "Rajesh Kumar",
                "territory": "Visakhapatnam",
                "zone": "South",
                "state": "Andhra Pradesh",
                "mcr_percentage": 84.0,
                "mvc_percentage": 72.0,
                "avg_compliance": 85.5,
                "total_assigned": 50,
                "doctors_visited": 42,
                "rcpa_commitments": 25,
                "rx_per_week": 180
            }
        }


class TerritoryPerformance(BaseModel):
    """Territory-level aggregated metrics"""
    territory: str
    mrs_count: int
    avg_mcr: float
    avg_mvc: float
    total_doctors: int
    total_visits: int
    total_commitments: int
    rx_per_week: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "territory": "Visakhapatnam",
                "mrs_count": 5,
                "avg_mcr": 82.5,
                "avg_mvc": 75.0,
                "total_doctors": 250,
                "total_visits": 850,
                "total_commitments": 120,
                "rx_per_week": 900
            }
        }


class SFEAlert(BaseModel):
    """SFE performance alert"""
    mr_id: str
    mr_name: str
    territory: Optional[str] = None
    alert_type: str  # "critical_mcr", "critical_mvc", "declining_trend", "no_commitments"
    severity: str  # "critical", "warning"
    message: str
    metric_value: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "mr_id": "507f1f77bcf86cd799439014",
                "mr_name": "Suresh Patel",
                "territory": "Mumbai",
                "alert_type": "critical_mcr",
                "severity": "critical",
                "message": "MCR below 60% (45.0%)",
                "metric_value": 45.0
            }
        }


class SFEDashboardResponse(BaseModel):
    """Complete SFE dashboard"""
    month: int
    year: int
    total_mrs: int
    avg_mcr_pct: float
    avg_mvc_pct: float
    total_doctors: int
    total_visits: int
    total_commitments: int
    total_rx_per_week: int
    leaderboard: List[MRPerformance]
    underperformers: List[MRPerformance]
    by_territory: List[TerritoryPerformance]
    alerts: List[SFEAlert]
    
    class Config:
        json_schema_extra = {
            "example": {
                "month": 5,
                "year": 2026,
                "total_mrs": 15,
                "avg_mcr_pct": 82.0,
                "avg_mvc_pct": 76.0,
                "total_doctors": 750,
                "total_visits": 2500,
                "total_commitments": 450,
                "total_rx_per_week": 3500,
                "leaderboard": [
                    {
                        "mr_id": "507f1f77bcf86cd799439013",
                        "mr_name": "Rajesh Kumar",
                        "territory": "Visakhapatnam",
                        "mcr_percentage": 95.0,
                        "mvc_percentage": 88.0,
                        "avg_compliance": 92.0,
                        "total_assigned": 50,
                        "doctors_visited": 48,
                        "rcpa_commitments": 30,
                        "rx_per_week": 250
                    }
                ],
                "underperformers": [
                    {
                        "mr_id": "507f1f77bcf86cd799439014",
                        "mr_name": "Suresh Patel",
                        "territory": "Mumbai",
                        "mcr_percentage": 45.0,
                        "mvc_percentage": 30.0,
                        "avg_compliance": 40.0,
                        "total_assigned": 60,
                        "doctors_visited": 27,
                        "rcpa_commitments": 5,
                        "rx_per_week": 50
                    }
                ],
                "by_territory": [
                    {
                        "territory": "Visakhapatnam",
                        "mrs_count": 5,
                        "avg_mcr": 88.0,
                        "avg_mvc": 80.0,
                        "total_doctors": 250,
                        "total_visits": 900,
                        "total_commitments": 150,
                        "rx_per_week": 1200
                    }
                ],
                "alerts": [
                    {
                        "mr_id": "507f1f77bcf86cd799439014",
                        "mr_name": "Suresh Patel",
                        "territory": "Mumbai",
                        "alert_type": "critical_mcr",
                        "severity": "critical",
                        "message": "MCR below 60% (45.0%)",
                        "metric_value": 45.0
                    }
                ]
            }
        }


class MRDrillDownResponse(BaseModel):
    """Detailed drill-down for individual MR"""
    mr_id: str
    mr_name: str
    territory: Optional[str] = None
    zone: Optional[str] = None
    state: Optional[str] = None
    month: int
    year: int
    mcr_data: Dict[str, Any]
    mvc_data: Dict[str, Any]
    rcpa_summary: Dict[str, Any]
    performance_trend: List[Dict[str, Any]]
    
    class Config:
        json_schema_extra = {
            "example": {
                "mr_id": "507f1f77bcf86cd799439013",
                "mr_name": "Rajesh Kumar",
                "territory": "Visakhapatnam",
                "zone": "South",
                "state": "Andhra Pradesh",
                "month": 5,
                "year": 2026,
                "mcr_data": {
                    "mcr_percentage": 84.0,
                    "total_assigned": 50,
                    "doctors_visited": 42
                },
                "mvc_data": {
                    "mvc_percentage": 72.0,
                    "avg_compliance": 85.5,
                    "fully_covered": 36
                },
                "rcpa_summary": {
                    "total_commitments": 25,
                    "rx_per_week": 180
                },
                "performance_trend": [
                    {"month": 1, "mcr": 80.0, "mvc": 70.0},
                    {"month": 2, "mcr": 82.0, "mvc": 71.0},
                    {"month": 3, "mcr": 83.0, "mvc": 72.0}
                ]
            }
        }


# ============================================================================
# CHEMIST CHECK
# ============================================================================

class ChemistCheckCreateRequest(BaseModel):
    """Create chemist check observation"""
    chemist_name: str = Field(..., min_length=2, max_length=200, description="Chemist/Pharmacy name")
    chemist_location: str = Field(..., min_length=2, max_length=500, description="Location/Address")
    product_id: str = Field(..., description="Product/Drug ID")
    stock_available: int = Field(..., ge=0, le=10000, description="Stock quantity available")
    sold_this_week: int = Field(..., ge=0, le=1000, description="Units sold this week")
    notes: Optional[str] = Field(None, max_length=500, description="Additional observations")
    gps_lat: Optional[float] = Field(None, ge=-90, le=90, description="GPS latitude")
    gps_lng: Optional[float] = Field(None, ge=-180, le=180, description="GPS longitude")
    
    class Config:
        json_schema_extra = {
            "example": {
                "chemist_name": "Apollo Pharmacy",
                "chemist_location": "Near Dr. Arjun's clinic, MG Road",
                "product_id": "507f1f77bcf86cd799439021",
                "stock_available": 30,
                "sold_this_week": 20,
                "notes": "High demand, restock needed soon",
                "gps_lat": 17.3850,
                "gps_lng": 78.4867
            }
        }


class ChemistCheckResponse(BaseModel):
    """Single chemist check observation"""
    id: str
    mr_id: str
    mr_name: str
    chemist_name: str
    chemist_location: str
    product_id: str
    product_name: str
    stock_available: int
    sold_this_week: int
    notes: Optional[str] = None
    territory: Optional[str] = None
    zone: Optional[str] = None
    state: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    date: datetime
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439051",
                "mr_id": "507f1f77bcf86cd799439013",
                "mr_name": "Rajesh Kumar",
                "chemist_name": "Apollo Pharmacy",
                "chemist_location": "Near Dr. Arjun's clinic, MG Road",
                "product_id": "507f1f77bcf86cd799439021",
                "product_name": "Amlovas 5mg",
                "stock_available": 30,
                "sold_this_week": 20,
                "notes": "High demand, restock needed soon",
                "territory": "Visakhapatnam",
                "zone": "South",
                "state": "Andhra Pradesh",
                "gps_lat": 17.3850,
                "gps_lng": 78.4867,
                "date": "2026-05-19T00:00:00",
                "created_at": "2026-05-19T16:30:00"
            }
        }


class ChemistCheckListResponse(BaseModel):
    """List of chemist checks"""
    total: int
    checks: List[ChemistCheckResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 15,
                "checks": [
                    {
                        "id": "507f1f77bcf86cd799439051",
                        "mr_id": "507f1f77bcf86cd799439013",
                        "mr_name": "Rajesh Kumar",
                        "chemist_name": "Apollo Pharmacy",
                        "chemist_location": "Near Dr. Arjun's clinic",
                        "product_id": "507f1f77bcf86cd799439021",
                        "product_name": "Amlovas 5mg",
                        "stock_available": 30,
                        "sold_this_week": 20,
                        "territory": "Visakhapatnam",
                        "date": "2026-05-19T00:00:00",
                        "created_at": "2026-05-19T16:30:00"
                    }
                ]
            }
        }


class ChemistProductSummary(BaseModel):
    """Product availability summary"""
    product_id: str
    product_name: str
    total_stock: int
    total_sold_this_week: int
    chemists_count: int
    avg_stock_per_chemist: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_id": "507f1f77bcf86cd799439021",
                "product_name": "Amlovas 5mg",
                "total_stock": 450,
                "total_sold_this_week": 280,
                "chemists_count": 15,
                "avg_stock_per_chemist": 30.0
            }
        }


class ChemistTerritorySummary(BaseModel):
    """Territory-wise chemist summary"""
    territory: str
    total_stock: int
    total_sold: int
    chemists_count: int
    products_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "territory": "Visakhapatnam",
                "total_stock": 600,
                "total_sold": 350,
                "chemists_count": 20,
                "products_count": 8
            }
        }


class ChemistCheckSummaryResponse(BaseModel):
    """Chemist check summary for admin"""
    total_checks: int
    total_chemists: int
    total_stock: int
    total_sold_this_week: int
    by_product: List[ChemistProductSummary]
    by_territory: List[ChemistTerritorySummary]
    low_stock_alerts: List[Dict[str, Any]]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_checks": 85,
                "total_chemists": 45,
                "total_stock": 2500,
                "total_sold_this_week": 1800,
                "by_product": [
                    {
                        "product_id": "507f1f77bcf86cd799439021",
                        "product_name": "Amlovas 5mg",
                        "total_stock": 450,
                        "total_sold_this_week": 280,
                        "chemists_count": 15,
                        "avg_stock_per_chemist": 30.0
                    }
                ],
                "by_territory": [
                    {
                        "territory": "Visakhapatnam",
                        "total_stock": 600,
                        "total_sold": 350,
                        "chemists_count": 20,
                        "products_count": 8
                    }
                ],
                "low_stock_alerts": [
                    {
                        "chemist_name": "Apollo Pharmacy",
                        "product_name": "Amlovas 5mg",
                        "stock_available": 5,
                        "territory": "Visakhapatnam"
                    }
                ]
            }
        }


# ============================================================================
# GENERIC RESPONSES
# ============================================================================

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operation successful"
            }
        }
