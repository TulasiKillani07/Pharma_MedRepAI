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
                "action_type": "user_created",
                "actor_id": "507f1f77bcf86cd799439012",
                "actor_name": "Admin User",
                "actor_role": "ADMIN",
                "target_type": "doctor",
                "target_id": "507f1f77bcf86cd799439013",
                "target_name": "Dr. John Doe",
                "action_details": {
                    "email": "doctor@example.com",
                    "specialization": "Cardiology"
                },
                "severity": "info",
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0...",
                "created_at": "2024-05-15T10:30:00Z"
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
    by_action_type: Dict[str, int]
    by_severity: Dict[str, int]
    by_target_type: Dict[str, int]
    recent_critical: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_logs": 1500,
                "by_action_type": {
                    "user_created": 50,
                    "post_deleted": 25,
                    "failed_login": 10
                },
                "by_severity": {
                    "info": 1400,
                    "warning": 80,
                    "critical": 20
                },
                "by_target_type": {
                    "doctor": 100,
                    "mr": 80,
                    "post": 50
                },
                "recent_critical": 5
            }
        }
