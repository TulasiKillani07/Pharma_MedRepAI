"""
SFE (Sales Force Effectiveness) request/response schemas.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum
from app.models.sfe_models import DoctorClass, DoctorMood



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




# ============================================================================
# VISIT COMPLETION EXTENSION
# ============================================================================

class RxCommitmentRequest(BaseModel):
    """Prescription commitment data"""
    drug_id: str = Field(..., description="Drug ID")
    rx_per_month: int = Field(..., ge=1, le=1000, description="Expected prescriptions per month")
    
    class Config:
        json_schema_extra = {
            "example": {
                "drug_id": "507f1f77bcf86cd799439011",
                "rx_per_month": 15
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
                    "drug_id": "507f1f77bcf86cd799439011",
                    "rx_per_month": 15
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
# COMPANY SETTINGS (VISIT TARGETS)
# ============================================================================

class ClassificationTargetsResponse(BaseModel):
    """Classification targets response"""
    classification_targets: Dict[str, int] = Field(..., description="Visit targets per classification")
    updated_at: Optional[datetime] = None
    updated_by: Optional[Dict[str, str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "classification_targets": {
                    "A": 4,
                    "B": 3,
                    "C": 2
                },
                "updated_at": "2026-05-20T12:00:00",
                "updated_by": {
                    "name": "vamsi vakada"
                }
            }
        }


class ClassificationTargetsUpdateRequest(BaseModel):
    """Request to update classification targets"""
    classification_targets: Dict[str, int] = Field(..., description="Visit targets for A, B, C classifications")
    
    @field_validator('classification_targets')
    @classmethod
    def validate_targets(cls, v: Dict[str, int]) -> Dict[str, int]:
        """Validate classification targets"""
        # Check all required keys present
        required_keys = {"A", "B", "C"}
        if set(v.keys()) != required_keys:
            raise ValueError('classification_targets must have exactly keys A, B, and C')
        
        # Validate each value
        for key, value in v.items():
            if not isinstance(value, int):
                raise ValueError(f'Value for class {key} must be an integer')
            if value < 1 or value > 30:
                raise ValueError(f'Value for class {key} must be between 1 and 30')
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "classification_targets": {
                    "A": 4,
                    "B": 3,
                    "C": 2
                }
            }
        }


# ============================================================================
# MCR (MONTHLY CALL REPORT)
# ============================================================================

class MCRVisitDetail(BaseModel):
    """Individual visit detail within MCR"""
    visit_id: str
    scheduled_date: Optional[Any] = None
    completed_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    location: Optional[str | dict] = None  # Supports both old format (string) and new format (dict)
    purpose: Optional[str] = None
    doctor_mood: Optional[str] = None
    products_discussed: Optional[List[Any]] = None
    samples_given: Optional[int] = None
    outcome: Optional[str] = None
    feedback: Optional[str] = None
    rx_commitment: Optional[bool] = None
    expected_rx_per_month: Optional[int] = None
    competitor_info: Optional[str] = None
    follow_up_date: Optional[Any] = None
    notes: Optional[str] = None


class MCRDoctorVisited(BaseModel):
    """Doctor who was visited - includes full visit details"""
    doctor_id: str
    doctor_name: str
    classification: Optional[str] = None
    visits_count: int
    last_visit_date: datetime
    visits: Optional[List[MCRVisitDetail]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "doctor_id": "507f1f77bcf86cd799439011",
                "doctor_name": "Dr. Arjun Sharma",
                "classification": "A",
                "visits_count": 3,
                "last_visit_date": "2026-05-15T14:30:00",
                "visits": [
                    {
                        "visit_id": "6a0edec2...",
                        "completed_at": "2026-05-15T14:30:00",
                        "duration_minutes": 28,
                        "location": "Apollo Hospital",
                        "purpose": "Drug Promotion",
                        "doctor_mood": "positive",
                        "products_discussed": [{"id": "drug_id_1", "name": "Amlodipine 5mg"}],
                        "samples_given": 3,
                        "outcome": "Doctor interested in product",
                        "rx_commitment": True,
                        "expected_rx_per_month": 10,
                        "competitor_info": "Cipla — Amlokind 5mg",
                        "follow_up_date": "2026-06-01",
                        "notes": "Doctor wants clinical trial data"
                    }
                ]
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
    """Create RCPA commitment — MR provides only visit + drug + quantity"""
    visit_id: str = Field(..., description="Completed visit ID")
    drug_id: str = Field(..., description="Drug ID")
    committed_quantity: int = Field(..., ge=1, description="Quantity in sales_units (e.g. 20 strips)")
    rx_per_month: int = Field(..., ge=1, le=1000, description="Expected prescriptions per month")
    requested_discount: float = Field(default=0.0, ge=0, le=100, description="Discount % requested (0 = no discount)")

    class Config:
        json_schema_extra = {
            "example": {
                "visit_id": "507f1f77bcf86cd799439031",
                "drug_id": "507f1f77bcf86cd799439021",
                "committed_quantity": 20,
                "rx_per_month": 15,
                "requested_discount": 5
            }
        }


class RCPAUpdateRequest(BaseModel):
    """Update existing RCPA commitment — all commitment fields editable"""
    drug_id: Optional[str] = Field(None, description="Change drug")
    committed_quantity: Optional[int] = Field(None, ge=1, description="Updated quantity in sales_units")
    rx_per_month: Optional[int] = Field(None, ge=1, le=1000, description="Updated prescriptions per month")
    requested_discount: Optional[float] = Field(None, ge=0, le=100, description="Updated discount request")
    
    class Config:
        json_schema_extra = {
            "example": {
                "drug_id": "507f1f77bcf86cd799439021",
                "committed_quantity": 25,
                "rx_per_month": 20,
                "requested_discount": 8
            }
        }


class RCPAApproveDiscountRequest(BaseModel):
    """Approve discount — optionally adjust quantity"""
    approved_discount: float = Field(..., ge=0, le=100, description="Approved discount %")
    approved_quantity: Optional[int] = Field(None, ge=1, description="Adjusted quantity (if different from committed)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "approved_discount": 4.5,
                "approved_quantity": 18
            }
        }


class EligibleVisitResponse(BaseModel):
    """A completed visit eligible for RCPA commitment"""
    visit_id: str
    visit_title: Optional[str] = None
    doctor_id: str
    doctor_name: str
    doctor_location: Optional[dict] = None
    visit_date: Optional[str] = None


class EligibleVisitsListResponse(BaseModel):
    """List of eligible visits"""
    total: int
    visits: List[EligibleVisitResponse]


class RCPACommitmentResponse(BaseModel):
    """Single RCPA commitment"""
    id: str
    visit_id: str
    visit_title: Optional[str] = None
    mr_id: str
    mr_name: str
    doctor_id: str
    doctor_name: str
    doctor_location: Optional[dict] = None
    drug_id: str
    drug_name: str
    committed_quantity: int
    quantity_unit: str
    rx_per_month: int
    selling_price: float
    max_discount_percent: float
    committed_revenue: float
    requested_discount: float = 0.0
    approved_discount: Optional[float] = None
    net_revenue: Optional[float] = None
    approval_status: str = "PENDING"
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    month: int
    year: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439041",
                "visit_id": "507f1f77bcf86cd799439031",
                "visit_title": "Apollo Hospital - Dr. Sneha - 03 Jul",
                "mr_id": "507f1f77bcf86cd799439013",
                "mr_name": "Rajesh Kumar",
                "doctor_id": "507f1f77bcf86cd799439011",
                "doctor_name": "Dr. Sneha",
                "doctor_location": {
                    "name": "Apollo Hospital",
                    "area": "Jubilee Hills",
                    "district": "Hyderabad",
                    "state": "Telangana"
                },
                "drug_id": "507f1f77bcf86cd799439021",
                "drug_name": "Amlovas 5mg",
                "committed_quantity": 20,
                "quantity_unit": "Strip",
                "rx_per_month": 15,
                "selling_price": 80,
                "max_discount_percent": 15,
                "committed_revenue": 1600,
                "requested_discount": 5,
                "approved_discount": None,
                "net_revenue": None,
                "approval_status": "PENDING",
                "month": 7,
                "year": 2026,
                "created_at": "2026-07-03T10:00:00"
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
                "commitments": []
            }
        }


class RCPAProductSummary(BaseModel):
    """RCPA summary by drug"""
    drug_id: str
    drug_name: str
    rx_per_month: int
    doctors_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "drug_id": "507f1f77bcf86cd799439021",
                "drug_name": "Amlovas 5mg",
                "rx_per_month": 200,
                "doctors_count": 12
            }
        }


class RCPATerritorySummary(BaseModel):
    """RCPA summary by territory"""
    territory: str
    rx_per_month: int
    doctors_count: int
    products_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "territory": "Visakhapatnam",
                "rx_per_month": 180,
                "doctors_count": 15,
                "products_count": 5
            }
        }


class RCPASummaryResponse(BaseModel):
    """RCPA summary for admin"""
    total_rx_per_month: int
    total_commitments: int
    total_doctors: int
    total_drugs: int
    by_drug: List[RCPAProductSummary]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_rx_per_month": 1200,
                "total_commitments": 85,
                "total_doctors": 65,
                "total_products": 8,
                "by_product": [
                    {
                        "product_id": "507f1f77bcf86cd799439021",
                        "product_name": "Amlovas 5mg",
                        "rx_per_month": 450,
                        "doctors_count": 25
                    }
                ],
                "by_territory": [
                    {
                        "territory": "Visakhapatnam",
                        "rx_per_month": 350,
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
    rx_per_month: int
    
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
                "rx_per_month": 180
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
    rx_per_month: int
    
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
                "rx_per_month": 900
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
    total_rx_per_month: int
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
                "total_rx_per_month": 3500,
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
                        "rx_per_month": 250
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
                        "rx_per_month": 50
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
                        "rx_per_month": 1200
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
                    "rx_per_month": 180
                },
                "performance_trend": [
                    {"month": 1, "mcr": 80.0, "mvc": 70.0},
                    {"month": 2, "mcr": 82.0, "mvc": 71.0},
                    {"month": 3, "mcr": 83.0, "mvc": 72.0}
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
