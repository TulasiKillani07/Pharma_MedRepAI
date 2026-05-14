"""
Grievance schemas - Request/Response models for grievance API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.grievance_model import GrievancePriority, GrievanceStatus


# ============ REQUEST SCHEMAS ============

class GrievanceCreateRequest(BaseModel):
    """Schema for MR creating a new grievance"""
    department: str = Field(..., description="Department code (hr, finance, it)")
    subject: str = Field(..., min_length=5, max_length=200, description="Grievance subject")
    description: str = Field(..., min_length=10, max_length=2000, description="Detailed description")
    priority: GrievancePriority = Field(..., description="Priority level")
    
    class Config:
        json_schema_extra = {
            "example": {
                "department": "finance",
                "subject": "Travel reimbursement not received",
                "description": "I submitted travel claim for Mumbai trip (Claim ID: TC-2026-045) on March 1st. It's been 30 days but amount not credited.",
                "priority": "high"
            }
        }


class GrievanceResponseRequest(BaseModel):
    """Schema for admin responding to a grievance"""
    admin_response: str = Field(..., min_length=10, max_length=2000, description="Admin's response")
    status: GrievanceStatus = Field(..., description="Updated status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "admin_response": "Checked with accounts team. Your claim was approved but bank details were incorrect. Please update your bank account in profile.",
                "status": "in_progress"
            }
        }


# ============ RESPONSE SCHEMAS ============

class GrievanceListItem(BaseModel):
    """Schema for grievance in list view"""
    ticket_id: str
    department: str
    subject: str
    priority: GrievancePriority
    status: GrievanceStatus
    created_at: datetime
    responded_at: Optional[datetime]
    
    class Config:
        json_schema_extra = {
            "example": {
                "ticket_id": "FIN-2026-001",
                "department": "finance",
                "subject": "Travel reimbursement not received",
                "priority": "high",
                "status": "open",
                "created_at": "2026-05-13T10:00:00",
                "responded_at": None
            }
        }


class GrievanceDetailResponse(BaseModel):
    """Schema for full grievance details"""
    ticket_id: str
    department: str
    subject: str
    description: str
    priority: GrievancePriority
    status: GrievanceStatus
    created_by_name: str
    created_by_email: str
    mr_territory: Optional[str]
    mr_state: Optional[str]
    created_at: datetime
    admin_response: Optional[str]
    responded_by_name: Optional[str]
    responded_at: Optional[datetime]
    resolved_at: Optional[datetime]
    
    class Config:
        json_schema_extra = {
            "example": {
                "ticket_id": "FIN-2026-001",
                "department": "finance",
                "subject": "Travel reimbursement not received",
                "description": "I submitted travel claim...",
                "priority": "high",
                "status": "in_progress",
                "created_by_name": "Rajesh Kumar",
                "created_by_email": "rajesh@xyzpharma.com",
                "mr_territory": "Hyderabad",
                "mr_state": "Telangana",
                "created_at": "2026-05-13T10:00:00",
                "admin_response": "Checked with accounts team...",
                "responded_by_name": "John Admin",
                "responded_at": "2026-05-13T14:30:00",
                "resolved_at": None
            }
        }


class GrievanceListResponse(BaseModel):
    """Schema for paginated list of grievances"""
    total: int
    page: int
    limit: int
    total_pages: int
    grievances: List[GrievanceListItem]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 25,
                "page": 1,
                "limit": 20,
                "total_pages": 2,
                "grievances": []
            }
        }


class GrievanceCreateResponse(BaseModel):
    """Response after creating grievance"""
    message: str
    ticket_id: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Grievance submitted successfully",
                "ticket_id": "FIN-2026-001"
            }
        }


class GrievanceStatsResponse(BaseModel):
    """Dashboard stats for grievances"""
    total: int
    open: int
    in_progress: int
    resolved: int
    rejected: int
    by_department: dict
    by_priority: dict
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 150,
                "open": 25,
                "in_progress": 40,
                "resolved": 75,
                "rejected": 10,
                "by_department": {
                    "hr": 60,
                    "finance": 70,
                    "it": 20
                },
                "by_priority": {
                    "low": 30,
                    "medium": 60,
                    "high": 45,
                    "urgent": 15
                }
            }
        }


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operation successful"
            }
        }
