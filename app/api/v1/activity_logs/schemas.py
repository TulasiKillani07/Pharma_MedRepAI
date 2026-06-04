"""
Activity Logs API Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ActivityLogResponse(BaseModel):
    """Response schema for a single activity log"""
    log_id: str
    action_type: str
    message: str = Field(..., description="Human-readable description of what happened")
    actor_id: str
    actor_name: str
    actor_role: str
    target_type: str
    target_id: Optional[str]
    target_name: Optional[str]
    action_details: Dict[str, Any]
    severity: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "log_id": "507f1f77bcf86cd799439011",
                "action_type": "visit_scheduled",
                "message": "Rajesh Kumar scheduled a visit with Dr. Sneha Sharma",
                "actor_id": "507f1f77bcf86cd799439012",
                "actor_name": "Rajesh Kumar",
                "actor_role": "MR",
                "target_type": "visit",
                "target_id": "507f1f77bcf86cd799439013",
                "target_name": None,
                "action_details": {
                    "doctor_id": "507f1f77bcf86cd799439014",
                    "doctor_name": "Dr. Sneha Sharma",
                    "scheduled_date": "2026-05-25",
                    "scheduled_time": "10:00",
                    "purpose": "Drug Promotion"
                },
                "severity": "info",
                "ip_address": "183.82.41.52",
                "user_agent": "Mozilla/5.0...",
                "created_at": "2026-05-25T10:05:45"
            }
        }


class ActivityLogListResponse(BaseModel):
    """Response schema for paginated activity logs"""
    logs: List[ActivityLogResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "logs": [],
                "total": 150,
                "page": 1,
                "limit": 20,
                "total_pages": 8
            }
        }


class ActivityStatsResponse(BaseModel):
    """Response schema for activity statistics"""
    total_logs: int
    today_logs: int = 0
    by_action_type: Dict[str, int]
    by_severity: Dict[str, int]
    by_target_type: Dict[str, int]
    by_actor: List[Dict[str, Any]] = []
    recent_critical: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_logs": 1500,
                "today_logs": 45,
                "by_action_type": {
                    "visit_completed": 320,
                    "visit_scheduled": 280,
                    "user_created": 50,
                    "drug_created": 30,
                    "failed_login": 10
                },
                "by_severity": {
                    "info": 1400,
                    "warning": 80,
                    "critical": 20
                },
                "by_target_type": {
                    "visit": 600,
                    "doctor": 100,
                    "mr": 80,
                    "drug": 60
                },
                "by_actor": [
                    {
                        "actor_id": "6a0d9eb8...",
                        "actor_name": "Rajesh Kumar",
                        "actor_role": "MR",
                        "count": 120
                    },
                    {
                        "actor_id": "6a0d9fa2...",
                        "actor_name": "Admin",
                        "actor_role": "ADMIN",
                        "count": 85
                    }
                ],
                "recent_critical": 5
            }
        }
