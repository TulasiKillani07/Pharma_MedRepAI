"""
Activity Log Model - MongoDB document structure for activity_logs collection.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum


class ActivityLogAction(str, Enum):
    """Activity log action types"""
    # User Management
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    USER_DELETED = "user_deleted"
    
    # Content Moderation
    POST_DELETED = "post_deleted"
    COMMENT_DELETED = "comment_deleted"
    USER_REPORTED = "user_reported"
    CONTENT_FLAGGED = "content_flagged"
    
    # CME Management
    CME_CREATED = "cme_created"
    CME_UPDATED = "cme_updated"
    CME_DELETED = "cme_deleted"
    CME_REGISTERED = "cme_registered"
    CME_REGISTRATION_CANCELLED = "cme_registration_cancelled"
    
    # Drug Management
    DRUG_CREATED = "drug_created"
    DRUG_UPDATED = "drug_updated"
    DRUG_DELETED = "drug_deleted"
    DRUG_BULK_UPLOAD = "drug_bulk_upload"
    
    # Visit Management
    VISIT_SCHEDULED = "visit_scheduled"
    VISIT_CANCELLED = "visit_cancelled"
    VISIT_COMPLETED = "visit_completed"
    
    # Bulk Operations
    BULK_UPLOAD_DOCTORS = "bulk_upload_doctors"
    BULK_UPLOAD_MRS = "bulk_upload_mrs"
    
    # Authentication & Security
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    ADMIN_LOGIN = "admin_login"
    ADMIN_LOGOUT = "admin_logout"
    PASSWORD_CHANGED = "password_changed"
    FAILED_LOGIN = "failed_login"


class ActorRole(str, Enum):
    """Actor role types"""
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"
    DOCTOR = "DOCTOR"
    MR = "MR"


class TargetType(str, Enum):
    """Target resource types"""
    DOCTOR = "doctor"
    MR = "mr"
    POST = "post"
    COMMENT = "comment"
    CME_EVENT = "cme_event"
    DRUG = "drug"
    VISIT = "visit"
    SYSTEM = "system"


class LogSeverity(str, Enum):
    """Log severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ActivityLogInDB(BaseModel):
    """
    Write model for activity log document (INSERT operations)
    
    Collection: activity_logs
    Indexes:
    - Compound: (actor_id, created_at) DESC
    - Compound: (action_type, created_at) DESC
    - Compound: (target_type, target_id)
    - Compound: (severity, created_at) DESC
    - TTL: expires_at (90 days)
    """
    action_type: ActivityLogAction = Field(..., description="Type of action performed")
    actor_id: str = Field(..., description="ID of user who performed the action")
    actor_name: str = Field(..., description="Name of user who performed the action")
    actor_role: ActorRole = Field(..., description="Role of user who performed the action")
    target_type: TargetType = Field(..., description="Type of resource affected")
    target_id: Optional[str] = Field(None, description="ID of affected resource")
    target_name: Optional[str] = Field(None, description="Name/title of affected resource")
    action_details: Dict[str, Any] = Field(default_factory=dict, description="Additional context about the action")
    severity: LogSeverity = Field(default=LogSeverity.INFO, description="Severity level of the action")
    ip_address: Optional[str] = Field(None, description="IP address of the actor")
    user_agent: Optional[str] = Field(None, description="User agent of the actor")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When the action occurred")
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=90),
        description="When this log should be auto-deleted (90 days)"
    )
    
    class Config:
        extra = "forbid"


class ActivityLogDocument(ActivityLogInDB):
    """Read model for activity log document"""
    class Config:
        extra = "allow"
