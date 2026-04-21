"""
Activity Log Helper Functions

Easy-to-use functions for logging admin activities.
"""

from typing import Dict, Any, Optional
from fastapi import Request
from app.database import get_database
from app.models.activity_log_model import (
    ActivityLogAction,
    ActorRole,
    TargetType,
    LogSeverity,
    ActivityLogInDB
)


async def log_activity(
    action_type: ActivityLogAction,
    actor: Dict[str, Any],
    target_type: TargetType,
    target_id: Optional[str] = None,
    target_name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    severity: LogSeverity = LogSeverity.INFO,
    request: Optional[Request] = None
) -> str:
    """
    Log an admin activity.
    
    Args:
        action_type: Type of action performed
        actor: Current user dict (must have _id, name, role)
        target_type: Type of resource affected
        target_id: ID of affected resource (optional)
        target_name: Name of affected resource (optional)
        details: Additional context (optional)
        severity: Severity level (default: INFO)
        request: FastAPI Request object for IP/user-agent (optional)
    
    Returns:
        str: Created log ID
    
    Example:
        await log_activity(
            action_type=ActivityLogAction.USER_CREATED,
            actor=current_user,
            target_type=TargetType.DOCTOR,
            target_id=str(doctor_id),
            target_name=doctor_name,
            details={"email": "doctor@example.com", "specialization": "Cardiology"},
            severity=LogSeverity.INFO
        )
    """
    db = get_database()
    
    # Extract IP and user agent from request if provided
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
    
    # Create log entry
    log = ActivityLogInDB(
        action_type=action_type,
        actor_id=actor["_id"],
        actor_name=actor.get("name") or actor.get("full_name", "Unknown"),
        actor_role=ActorRole(actor.get("role", "ADMIN")),
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        action_details=details or {},
        severity=severity,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    result = await db.activity_logs.insert_one(log.model_dump())
    return str(result.inserted_id)
