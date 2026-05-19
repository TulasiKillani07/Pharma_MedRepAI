"""
SFE (Sales Force Effectiveness) Models
Database schemas for SFE-related collections.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
from bson import ObjectId


# ============================================================================
# ENUMS
# ============================================================================

class DoctorClass(str, Enum):
    """Doctor classification based on prescription potential"""
    A = "A"  # High prescriber - 4 visits/month
    B = "B"  # Medium prescriber - 2 visits/month
    C = "C"  # Low prescriber - 1 visit/month


class DoctorMood(str, Enum):
    """Doctor's receptiveness during visit"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class CommitmentConfidence(str, Enum):
    """Confidence level of prescription commitment"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CommitmentStatus(str, Enum):
    """Status of prescription commitment"""
    ACTIVE = "active"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


# ============================================================================
# DOCTOR ASSIGNMENT & CLASSIFICATION
# ============================================================================

class DoctorAssignment(BaseModel):
    """
    Doctor assignment to MR with classification.
    
    Collection: doctor_assignments
    Indexes:
    - (mr_id, doctor_id) - unique compound
    - mr_id
    - doctor_id
    - classification
    """
    mr_id: str = Field(..., description="MR user ID")
    mr_name: str = Field(..., description="MR name")
    doctor_id: str = Field(..., description="Doctor user ID")
    doctor_name: str = Field(..., description="Doctor name")
    classification: DoctorClass = Field(default=DoctorClass.C, description="Doctor class (A/B/C)")
    visit_frequency: int = Field(..., description="Required visits per month")
    territory: Optional[str] = Field(None, description="Territory")
    zone: Optional[str] = Field(None, description="Zone")
    state: Optional[str] = Field(None, description="State")
    assigned_by: str = Field(..., description="Admin who assigned")
    assigned_at: datetime = Field(default_factory=datetime.utcnow, description="Assignment timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    @field_validator('mr_id', 'doctor_id', 'assigned_by')
    @classmethod
    def validate_object_id(cls, v: str) -> str:
        """Validate IDs are valid ObjectId format"""
        try:
            ObjectId(v)
            return v
        except Exception:
            raise ValueError(f'Invalid ObjectId format: {v}')
    
    @field_validator('visit_frequency')
    @classmethod
    def validate_frequency(cls, v: int) -> int:
        """Validate visit frequency is positive"""
        if v < 1:
            raise ValueError('Visit frequency must be at least 1')
        if v > 30:
            raise ValueError('Visit frequency cannot exceed 30 per month')
        return v
    
    class Config:
        extra = "forbid"


# ============================================================================
# SFE CONFIGURATION
# ============================================================================

class SFEConfig(BaseModel):
    """
    Company-level SFE configuration.
    
    Collection: sfe_config
    Note: Single document per company
    """
    company_id: str = Field(default="default", description="Company ID (default for single company)")
    visit_frequency_config: dict = Field(
        default={
            "A": 4,  # A-class doctors: 4 visits/month
            "B": 2,  # B-class doctors: 2 visits/month
            "C": 1   # C-class doctors: 1 visit/month
        },
        description="Visit frequency per doctor class"
    )
    updated_by: Optional[str] = Field(None, description="Admin who last updated")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    class Config:
        extra = "forbid"


# ============================================================================
# PRESCRIPTION COMMITMENT (RCPA)
# ============================================================================

class PrescriptionCommitment(BaseModel):
    """
    Doctor's commitment to prescribe company products.
    
    Collection: prescription_commitments
    Indexes:
    - mr_id
    - doctor_id
    - product_id
    - territory
    - status
    - created_at
    """
    mr_id: str = Field(..., description="MR user ID")
    mr_name: str = Field(..., description="MR name")
    doctor_id: str = Field(..., description="Doctor user ID")
    doctor_name: str = Field(..., description="Doctor name")
    product_id: str = Field(..., description="Product/Drug ID")
    product_name: str = Field(..., description="Product/Drug name")
    rx_per_week: int = Field(..., ge=1, description="Expected prescriptions per week")
    confidence: CommitmentConfidence = Field(default=CommitmentConfidence.MEDIUM, description="Confidence level")
    status: CommitmentStatus = Field(default=CommitmentStatus.ACTIVE, description="Commitment status")
    visit_id: Optional[str] = Field(None, description="Visit ID where commitment was made")
    territory: Optional[str] = Field(None, description="Territory")
    zone: Optional[str] = Field(None, description="Zone")
    state: Optional[str] = Field(None, description="State")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    @field_validator('mr_id', 'doctor_id', 'product_id')
    @classmethod
    def validate_object_id(cls, v: str) -> str:
        """Validate IDs are valid ObjectId format"""
        try:
            ObjectId(v)
            return v
        except Exception:
            raise ValueError(f'Invalid ObjectId format: {v}')
    
    @field_validator('visit_id')
    @classmethod
    def validate_visit_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate visit ID if provided"""
        if v is None:
            return v
        try:
            ObjectId(v)
            return v
        except Exception:
            raise ValueError(f'Invalid ObjectId format: {v}')
    
    class Config:
        extra = "forbid"


# ============================================================================
# CHEMIST CHECK (OPTIONAL)
# ============================================================================

class ChemistCheck(BaseModel):
    """
    MR's observation of chemist stock and sales.
    
    Collection: chemist_checks
    Indexes:
    - mr_id
    - product_id
    - territory
    - date
    """
    mr_id: str = Field(..., description="MR user ID")
    mr_name: str = Field(..., description="MR name")
    chemist_name: str = Field(..., min_length=2, max_length=200, description="Chemist/Pharmacy name")
    chemist_location: str = Field(..., min_length=2, max_length=300, description="Chemist location")
    product_id: str = Field(..., description="Product/Drug ID")
    product_name: str = Field(..., description="Product/Drug name")
    stock_available: int = Field(..., ge=0, description="Stock quantity available")
    sold_this_week: int = Field(..., ge=0, description="Quantity sold this week")
    territory: Optional[str] = Field(None, description="Territory")
    zone: Optional[str] = Field(None, description="Zone")
    state: Optional[str] = Field(None, description="State")
    notes: Optional[str] = Field(None, max_length=500, description="Additional observations")
    date: datetime = Field(default_factory=datetime.utcnow, description="Check date")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    
    @field_validator('mr_id', 'product_id')
    @classmethod
    def validate_object_id(cls, v: str) -> str:
        """Validate IDs are valid ObjectId format"""
        try:
            ObjectId(v)
            return v
        except Exception:
            raise ValueError(f'Invalid ObjectId format: {v}')
    
    class Config:
        extra = "forbid"


# ============================================================================
# EXTENDED VISIT DATA (for visit completion)
# ============================================================================

class RxCommitmentData(BaseModel):
    """Prescription commitment data captured during visit"""
    product_id: str = Field(..., description="Product/Drug ID")
    product_name: str = Field(..., description="Product/Drug name")
    rx_per_week: int = Field(..., ge=1, description="Expected prescriptions per week")
    confidence: CommitmentConfidence = Field(default=CommitmentConfidence.MEDIUM, description="Confidence level")


class VisitCompletionExtended(BaseModel):
    """
    Extended fields for visit completion (SFE data).
    These fields are added to the existing visit document.
    """
    products_promoted: List[str] = Field(default_factory=list, description="List of product IDs promoted")
    samples_given: int = Field(default=0, ge=0, description="Number of samples distributed")
    doctor_mood: Optional[DoctorMood] = Field(None, description="Doctor's receptiveness")
    competitor_info: Optional[str] = Field(None, max_length=500, description="Competitor information")
    followup_date: Optional[datetime] = Field(None, description="Next follow-up date")
    rx_commitment: Optional[RxCommitmentData] = Field(None, description="Prescription commitment")
    gps_lat: Optional[float] = Field(None, ge=-90, le=90, description="GPS latitude")
    gps_lng: Optional[float] = Field(None, ge=-180, le=180, description="GPS longitude")
    
    class Config:
        extra = "forbid"
