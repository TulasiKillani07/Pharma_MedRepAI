"""
Visit request/response schemas.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime, date
from enum import Enum
from app.core.validators import DateValidator, TimeValidator, TextValidator


class VisitStatus(str, Enum):
    """Visit status enum"""
    SCHEDULED = "scheduled"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class VisitCreateRequest(BaseModel):
    """Schema for scheduling a new visit"""
    doctor_id: str = Field(..., description="Doctor ID to visit")
    scheduled_date: date = Field(..., description="Visit date (YYYY-MM-DD)")
    scheduled_time: str = Field(..., description="Visit time (HH:MM or HH:MM AM/PM)")
    purpose: str = Field(..., min_length=5, description="Purpose of visit")
    location: str = Field(..., description="Visit location")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    # Validators
    @field_validator('scheduled_date')
    @classmethod
    def validate_date(cls, v: date) -> date:
        return DateValidator.validate_future_date(v, max_years=1)
    
    @field_validator('scheduled_time')
    @classmethod
    def validate_time(cls, v: str) -> str:
        result = TimeValidator.validate(v)
        if result is None:
            raise ValueError('Time is required')
        return result
    
    @field_validator('purpose')
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        result = TextValidator.validate(v, min_length=5, max_length=500, strip_html=True)
        if result is None:
            raise ValueError('Purpose is required')
        return result
    
    @field_validator('location')
    @classmethod
    def validate_location(cls, v: str) -> str:
        """Validate location is not empty"""
        if not v or not v.strip():
            raise ValueError('Location is required and cannot be empty')
        result = TextValidator.validate(v, min_length=1, max_length=200, strip_html=True)
        if result is None:
            raise ValueError('Location is required')
        return result
    
    @field_validator('notes')
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        return TextValidator.validate(v, max_length=1000, strip_html=True)
    
    class Config:
        json_schema_extra = {
            "example": {
                "doctor_id": "507f1f77bcf86cd799439011",
                "scheduled_date": "2024-04-15",
                "scheduled_time": "10:30",
                "purpose": "Product presentation and discussion",
                "location": "City Hospital, Room 301",
                "notes": "Bring product samples"
            }
        }


class VisitRescheduleRequest(BaseModel):
    """Schema for rescheduling a visit"""
    scheduled_date: date = Field(..., description="New visit date")
    scheduled_time: str = Field(..., description="New visit time (HH:MM or HH:MM AM/PM)")
    location: Optional[str] = Field(None, description="New location")
    notes: Optional[str] = Field(None, description="Updated notes")
    reason: Optional[str] = Field(None, description="Reason for rescheduling")
    
    # Validators
    @field_validator('scheduled_date')
    @classmethod
    def validate_date(cls, v: date) -> date:
        return DateValidator.validate_future_date(v, max_years=1)
    
    @field_validator('scheduled_time')
    @classmethod
    def validate_time(cls, v: str) -> str:
        result = TimeValidator.validate(v)
        if result is None:
            raise ValueError('Time is required')
        return result
    
    @field_validator('notes', 'reason')
    @classmethod
    def validate_text(cls, v: Optional[str]) -> Optional[str]:
        return TextValidator.validate(v, max_length=1000, strip_html=True)
    
    class Config:
        json_schema_extra = {
            "example": {
                "scheduled_date": "2024-04-16",
                "scheduled_time": "14:00",
                "location": "City Hospital, Room 302",
                "reason": "Doctor requested different time"
            }
        }


class RxCommitmentRequest(BaseModel):
    """Prescription commitment data"""
    product_id: str = Field(..., description="Product/Drug ID")
    rx_per_month: int = Field(..., ge=1, le=1000, description="Expected prescriptions per month")
    confidence: str = Field(default="medium", description="Confidence level: high/medium/low")


class VisitCompleteRequest(BaseModel):
    """Schema for completing a visit (with SFE fields)"""
    # Original fields
    outcome: str = Field(..., min_length=10, description="Visit outcome summary")
    feedback: Optional[str] = Field(None, description="Additional feedback")
    
    # SFE fields (optional for backward compatibility)
    products_promoted: Optional[List[str]] = Field(None, description="List of product IDs promoted")
    samples_given: Optional[int] = Field(None, ge=0, le=1000, description="Number of samples distributed")
    doctor_mood: Optional[str] = Field(None, description="Doctor's receptiveness: positive/neutral/negative")
    competitor_info: Optional[str] = Field(None, max_length=500, description="Competitor information")
    followup_date: Optional[date] = Field(None, description="Next follow-up date (YYYY-MM-DD)")
    rx_commitment: Optional[RxCommitmentRequest] = Field(None, description="Prescription commitment")
    gps_lat: Optional[float] = Field(None, ge=-90, le=90, description="GPS latitude")
    gps_lng: Optional[float] = Field(None, ge=-180, le=180, description="GPS longitude")
    
    # Validators
    @field_validator('outcome')
    @classmethod
    def validate_outcome(cls, v: str) -> str:
        result = TextValidator.validate(v, min_length=10, max_length=1000, strip_html=True)
        if result is None:
            raise ValueError('Outcome is required')
        return result
    
    @field_validator('feedback', 'competitor_info')
    @classmethod
    def validate_text_fields(cls, v: Optional[str]) -> Optional[str]:
        return TextValidator.validate(v, max_length=1000, strip_html=True)
    
    @field_validator('followup_date')
    @classmethod
    def validate_followup_date(cls, v: Optional[date]) -> Optional[date]:
        """Validate follow-up date is in the future"""
        if v and v < date.today():
            raise ValueError('Follow-up date must be in the future')
        return v
    
    @field_validator('doctor_mood')
    @classmethod
    def validate_doctor_mood(cls, v: Optional[str]) -> Optional[str]:
        """Validate doctor mood is valid"""
        if v and v not in ["positive", "neutral", "negative"]:
            raise ValueError('Doctor mood must be: positive, neutral, or negative')
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
                    "rx_per_month": 15,
                    "confidence": "high"
                },
                "gps_lat": 17.3850,
                "gps_lng": 78.4867
            }
        }


class VisitCancelRequest(BaseModel):
    """Schema for cancelling a visit"""
    reason: str = Field(..., min_length=5, description="Reason for cancellation")
    
    # Validators
    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v: str) -> str:
        result = TextValidator.validate(v, min_length=5, max_length=500, strip_html=True)
        if result is None:
            raise ValueError('Reason is required')
        return result
    
    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Doctor emergency, not available"
            }
        }


class RescheduleHistoryResponse(BaseModel):
    """Schema for reschedule history entry"""
    old_date: date
    old_time: str
    new_date: date
    new_time: str
    rescheduled_at: datetime
    reason: Optional[str] = None


class VisitReportResponse(BaseModel):
    """Schema for visit report data in response"""
    doctor_mood: Optional[str] = None
    products_discussed: Optional[List[Any]] = None
    samples_given: Optional[int] = None
    outcome: Optional[str] = None
    rx_commitment: Optional[bool] = None
    expected_rx_per_month: Optional[int] = None
    competitor_info: Optional[str] = None
    follow_up_date: Optional[Any] = None
    notes: Optional[str] = None


class VisitCheckInResponse(BaseModel):
    """Schema for check-in data in response"""
    timestamp: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class VisitResponse(BaseModel):
    """Schema for visit response"""
    id: str
    mr_id: str
    mr_name: str
    doctor_id: str
    doctor_name: str
    scheduled_date: date
    scheduled_time: str
    purpose: str
    location: str
    notes: Optional[str] = None
    status: VisitStatus
    
    # Check-in / Check-out data
    check_in: Optional[VisitCheckInResponse] = None
    check_out: Optional[VisitCheckInResponse] = None
    duration_minutes: Optional[int] = None
    
    # Report data (new flow)
    report: Optional[VisitReportResponse] = None
    
    # Legacy fields (old complete flow)
    outcome: Optional[str] = None
    feedback: Optional[str] = None
    
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    reschedule_history: List[RescheduleHistoryResponse] = []
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "mr_id": "507f1f77bcf86cd799439012",
                "mr_name": "Rajesh Kumar",
                "doctor_id": "507f1f77bcf86cd799439013",
                "doctor_name": "Dr. Sneha Sharma",
                "scheduled_date": "2026-05-25",
                "scheduled_time": "10:00",
                "purpose": "Drug Promotion",
                "location": "Apollo Hospital",
                "status": "completed",
                "check_in": {
                    "timestamp": "2026-05-25T10:05:32",
                    "latitude": 17.4401,
                    "longitude": 78.3489
                },
                "check_out": {
                    "timestamp": "2026-05-25T10:33:12",
                    "latitude": 17.4401,
                    "longitude": 78.3490
                },
                "duration_minutes": 28,
                "report": {
                    "doctor_mood": "positive",
                    "products_discussed": [{"id": "drug_id_1", "name": "Amlodipine 5mg"}],
                    "samples_given": 3,
                    "outcome": "Doctor interested in product",
                    "rx_commitment": True,
                    "expected_rx_per_month": 10,
                    "competitor_info": "Cipla — Amlokind 5mg",
                    "follow_up_date": "2026-06-01",
                    "notes": "Doctor wants clinical trial data"
                },
                "completed_at": "2026-05-25T10:33:12",
                "created_at": "2026-05-25T09:00:00",
                "updated_at": "2026-05-25T10:33:12"
            }
        }


class VisitListResponse(BaseModel):
    """Schema for list of visits"""
    total: int
    visits: List[VisitResponse]


class VisitTargetResponse(BaseModel):
    """Schema for visit target per doctor"""
    doctor_id: str = Field(..., description="Doctor ID")
    doctor_name: str = Field(..., description="Doctor name")
    classification: str = Field(..., description="Doctor classification (A/B/C)")
    required: int = Field(..., description="Required visits this month")
    completed: int = Field(..., description="Completed visits this month")
    
    class Config:
        json_schema_extra = {
            "example": {
                "doctor_id": "6a0d9fa2...",
                "doctor_name": "Dr. Sneha",
                "classification": "A",
                "required": 4,
                "completed": 1
            }
        }


class VisitListWithTargetsResponse(BaseModel):
    """Schema for list of visits with targets"""
    total: int
    visits: List[VisitResponse]
    targets: List[VisitTargetResponse] = Field(default_factory=list, description="Visit targets per doctor (MR only)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 10,
                "visits": [],
                "targets": [
                    {
                        "doctor_id": "6a0d9fa2...",
                        "doctor_name": "Dr. Sneha",
                        "classification": "A",
                        "required": 4,
                        "completed": 1
                    },
                    {
                        "doctor_id": "6a0da18e...",
                        "doctor_name": "Dr. Ashok",
                        "classification": "C",
                        "required": 2,
                        "completed": 0
                    }
                ]
            }
        }


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str


class VisitCreateResponse(BaseModel):
    """Response for visit creation"""
    message: str
    visit_id: str


# ============================================================================
# NEW SCHEMAS FOR CHECK-IN/CHECK-OUT/REPORT FLOW
# ============================================================================

class VisitCheckInRequest(BaseModel):
    """Schema for checking in to a visit"""
    latitude: float = Field(..., ge=-90, le=90, description="GPS latitude")
    longitude: float = Field(..., ge=-180, le=180, description="GPS longitude")
    
    class Config:
        json_schema_extra = {
            "example": {
                "latitude": 17.4401,
                "longitude": 78.3489
            }
        }


class VisitCheckOutRequest(BaseModel):
    """Schema for checking out from a visit"""
    latitude: float = Field(..., ge=-90, le=90, description="GPS latitude")
    longitude: float = Field(..., ge=-180, le=180, description="GPS longitude")
    
    class Config:
        json_schema_extra = {
            "example": {
                "latitude": 17.4401,
                "longitude": 78.3490
            }
        }


class VisitReportRequest(BaseModel):
    """Schema for submitting visit report (DCR)"""
    doctor_mood: str = Field(..., description="Doctor's receptiveness: positive/neutral/negative")
    products_discussed: List[str] = Field(..., description="List of product/drug IDs discussed")
    samples_given: int = Field(..., ge=0, le=1000, description="Number of samples distributed")
    outcome: str = Field(..., min_length=10, description="Visit outcome summary")
    rx_commitment: Optional[bool] = Field(None, description="Did doctor commit to prescribing?")
    expected_rx_per_month: Optional[int] = Field(None, ge=0, le=10000, description="Expected prescriptions per month")
    competitor_info: Optional[str] = Field(None, max_length=500, description="Competitor information")
    follow_up_date: Optional[date] = Field(None, description="Next follow-up date")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    
    # Validators
    @field_validator('doctor_mood')
    @classmethod
    def validate_doctor_mood(cls, v: str) -> str:
        """Validate doctor mood is valid"""
        if v not in ["positive", "neutral", "negative"]:
            raise ValueError('Doctor mood must be: positive, neutral, or negative')
        return v
    
    @field_validator('outcome')
    @classmethod
    def validate_outcome(cls, v: str) -> str:
        result = TextValidator.validate(v, min_length=10, max_length=1000, strip_html=True)
        if result is None:
            raise ValueError('Outcome is required and must be at least 10 characters')
        return result
    
    @field_validator('competitor_info', 'notes')
    @classmethod
    def validate_text_fields(cls, v: Optional[str]) -> Optional[str]:
        return TextValidator.validate(v, max_length=1000, strip_html=True)
    
    @field_validator('follow_up_date')
    @classmethod
    def validate_followup_date(cls, v: Optional[date]) -> Optional[date]:
        """Validate follow-up date is in the future"""
        if v and v < date.today():
            raise ValueError('Follow-up date must be in the future')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "doctor_mood": "positive",
                "products_discussed": ["507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012"],
                "samples_given": 3,
                "outcome": "Positive — Doctor interested in Amlodipine 5mg. Discussed clinical trial data.",
                "rx_commitment": True,
                "expected_rx_per_month": 10,
                "competitor_info": "Cipla — Amlokind 5mg",
                "follow_up_date": "2026-06-01",
                "notes": "Doctor wants clinical trial data"
            }
        }


class VisitCancelCheckInRequest(BaseModel):
    """Schema for cancelling check-in"""
    reason: str = Field(..., min_length=5, description="Reason for cancelling check-in")
    
    # Validators
    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v: str) -> str:
        result = TextValidator.validate(v, min_length=5, max_length=500, strip_html=True)
        if result is None:
            raise ValueError('Reason is required and must be at least 5 characters')
        return result
    
    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Doctor was called for emergency surgery"
            }
        }


class CheckInResponse(BaseModel):
    """Response for check-in"""
    message: str
    visit_id: str
    check_in_time: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Checked in successfully",
                "visit_id": "507f1f77bcf86cd799439011",
                "check_in_time": "2026-05-25T10:05:32"
            }
        }


class CheckOutResponse(BaseModel):
    """Response for check-out"""
    message: str
    visit_id: str
    duration_minutes: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Checked out successfully",
                "visit_id": "507f1f77bcf86cd799439011",
                "duration_minutes": 28
            }
        }


class ReportResponse(BaseModel):
    """Response for report submission"""
    message: str
    visit_id: str
    status: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Report submitted successfully",
                "visit_id": "507f1f77bcf86cd799439011",
                "status": "completed"
            }
        }


class ActiveVisitData(BaseModel):
    """Active visit data"""
    id: str
    doctor_id: str
    doctor_name: str
    check_in_time: datetime
    location: str
    duration_so_far_minutes: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "doctor_id": "507f1f77bcf86cd799439013",
                "doctor_name": "Dr. Sneha",
                "check_in_time": "2026-05-25T10:05:32",
                "location": "Apollo Hospital",
                "duration_so_far_minutes": 15
            }
        }


class ActiveVisitResponse(BaseModel):
    """Response for active visit query"""
    active_visit: Optional[ActiveVisitData] = None
    pending_reports: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "active_visit": {
                    "id": "507f1f77bcf86cd799439011",
                    "doctor_id": "507f1f77bcf86cd799439013",
                    "doctor_name": "Dr. Sneha",
                    "check_in_time": "2026-05-25T10:05:32",
                    "location": "Apollo Hospital",
                    "duration_so_far_minutes": 15
                },
                "pending_reports": 1
            }
        }
