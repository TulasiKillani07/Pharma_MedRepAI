"""
Activity Logs Business Logic
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from app.database import get_database
from fastapi import HTTPException


def generate_log_message(action_type: str, actor_name: str, target_name: Optional[str], details: Dict[str, Any]) -> str:
    """
    Generate a human-readable message from log data.
    
    Examples:
      "Rajesh Kumar scheduled a visit with Dr. Sneha"
      "Admin created MR Suresh Patel"
      "Rajesh Kumar completed a visit with Dr. Ashok"
    """
    actor = actor_name or "Unknown"
    target = target_name or ""
    
    # Visit actions
    if action_type == "visit_scheduled":
        doctor = details.get("doctor_name", target or "a doctor")
        return f"{actor} scheduled a visit with {doctor}"
    
    if action_type == "visit_completed":
        doctor = details.get("doctor_name", target or "a doctor")
        return f"{actor} completed a visit with {doctor}"
    
    if action_type == "visit_cancelled":
        doctor = details.get("doctor_name", target or "a doctor")
        return f"{actor} cancelled a visit with {doctor}"
    
    # User management
    if action_type == "user_created":
        name = target or details.get("email", "a user")
        return f"{actor} created {name}"
    
    if action_type == "user_updated":
        name = target or "a user"
        return f"{actor} updated {name}"
    
    if action_type == "user_activated":
        name = target or "a user"
        return f"{actor} activated {name}"
    
    if action_type == "user_deactivated":
        name = target or "a user"
        return f"{actor} deactivated {name}"
    
    if action_type == "user_deleted":
        name = target or "a user"
        return f"{actor} deleted {name}"
    
    # Drug management
    if action_type == "drug_created":
        name = target or "a drug"
        return f"{actor} added drug {name}"
    
    if action_type == "drug_updated":
        name = target or "a drug"
        return f"{actor} updated drug {name}"
    
    if action_type == "drug_deleted":
        name = target or "a drug"
        return f"{actor} deleted drug {name}"
    
    if action_type == "drug_bulk_upload":
        count = details.get("successful", "")
        return f"{actor} bulk uploaded {count} drugs" if count else f"{actor} bulk uploaded drugs"
    
    # CME
    if action_type == "cme_created":
        name = target or "a CME event"
        return f"{actor} created CME event: {name}"
    
    if action_type == "cme_updated":
        name = target or "a CME event"
        return f"{actor} updated CME event: {name}"
    
    if action_type == "cme_deleted":
        name = target or "a CME event"
        return f"{actor} deleted CME event: {name}"
    
    if action_type == "cme_registered":
        name = target or "a CME event"
        return f"{actor} registered for CME event: {name}"
    
    if action_type == "cme_registration_cancelled":
        name = target or "a CME event"
        return f"{actor} cancelled registration for CME: {name}"
    
    # Content moderation
    if action_type == "post_deleted":
        return f"{actor} deleted a post"
    
    if action_type == "comment_deleted":
        return f"{actor} deleted a comment"
    
    if action_type == "user_reported":
        name = target or "a user"
        return f"{actor} reported {name}"
    
    if action_type == "content_flagged":
        return f"{actor} flagged content"
    
    # Bulk operations
    if action_type == "bulk_upload_doctors":
        count = details.get("successful", "")
        return f"{actor} bulk uploaded {count} doctors" if count else f"{actor} bulk uploaded doctors"
    
    if action_type == "bulk_upload_mrs":
        count = details.get("successful", "")
        return f"{actor} bulk uploaded {count} MRs" if count else f"{actor} bulk uploaded MRs"
    
    # Authentication
    if action_type == "user_login":
        return f"{actor} logged in"
    
    if action_type == "user_logout":
        return f"{actor} logged out"
    
    if action_type == "admin_login":
        return f"{actor} (admin) logged in"
    
    if action_type == "admin_logout":
        return f"{actor} (admin) logged out"
    
    if action_type == "password_changed":
        return f"{actor} changed their password"
    
    if action_type == "failed_login":
        return f"Failed login attempt for {actor}"
    
    # Fallback
    readable = action_type.replace("_", " ").title()
    return f"{actor}: {readable}" + (f" — {target}" if target else "")


async def get_activity_logs(
    page: int = 1,
    limit: int = 20,
    action_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    target_type: Optional[str] = None,
    severity: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get paginated activity logs with filters.
    
    Args:
        page: Page number
        limit: Logs per page
        action_type: Filter by action type
        actor_id: Filter by actor ID
        target_type: Filter by target type
        severity: Filter by severity
        date_from: Filter from date
        date_to: Filter to date
    
    Returns:
        dict: Paginated activity logs
    """
    db = get_database()
    
    # Validate and limit page size
    if limit > 100:
        limit = 100
    if page < 1:
        page = 1
    
    # Build query
    query = {}
    
    if action_type:
        query["action_type"] = action_type
    
    if actor_id:
        query["actor_id"] = actor_id
    
    if target_type:
        query["target_type"] = target_type
    
    if severity:
        query["severity"] = severity
    
    # Date range filter
    if date_from or date_to:
        date_query = {}
        if date_from:
            date_query["$gte"] = date_from
        if date_to:
            date_query["$lte"] = date_to
        if date_query:
            query["created_at"] = date_query
    
    # Get total count
    total = await db.activity_logs.count_documents(query)
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get logs
    logs_cursor = db.activity_logs.find(query).sort("created_at", -1).skip(skip).limit(limit)
    logs_list = await logs_cursor.to_list(limit)
    
    # Format logs
    logs = []
    for log in logs_list:
        action_details = log.get("action_details", {})
        logs.append({
            "log_id": str(log["_id"]),
            "action_type": log["action_type"],
            "message": generate_log_message(
                action_type=log["action_type"],
                actor_name=log.get("actor_name", ""),
                target_name=log.get("target_name"),
                details=action_details
            ),
            "actor_id": log["actor_id"],
            "actor_name": log["actor_name"],
            "actor_role": log["actor_role"],
            "target_type": log["target_type"],
            "target_id": log.get("target_id"),
            "target_name": log.get("target_name"),
            "action_details": action_details,
            "severity": log["severity"],
            "ip_address": log.get("ip_address"),
            "user_agent": log.get("user_agent"),
            "created_at": log["created_at"]
        })
    
    return {
        "logs": logs,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def get_activity_stats() -> Dict[str, Any]:
    """
    Get activity statistics.
    
    Returns:
        dict: Activity statistics
    """
    db = get_database()
    
    # Total logs
    total_logs = await db.activity_logs.count_documents({})
    
    # Today's logs
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_logs = await db.activity_logs.count_documents({
        "created_at": {"$gte": today_start}
    })
    
    # Group by action_type
    action_type_pipeline = [
        {"$group": {"_id": "$action_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    action_type_results = await db.activity_logs.aggregate(action_type_pipeline).to_list(None)
    by_action_type = {item["_id"]: item["count"] for item in action_type_results}
    
    # Group by severity
    severity_pipeline = [
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
    ]
    severity_results = await db.activity_logs.aggregate(severity_pipeline).to_list(None)
    by_severity = {item["_id"]: item["count"] for item in severity_results}
    
    # Group by target_type
    target_type_pipeline = [
        {"$group": {"_id": "$target_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    target_type_results = await db.activity_logs.aggregate(target_type_pipeline).to_list(None)
    by_target_type = {item["_id"]: item["count"] for item in target_type_results}
    
    # Top actors (most active users)
    actor_pipeline = [
        {"$group": {
            "_id": "$actor_id",
            "actor_name": {"$first": "$actor_name"},
            "actor_role": {"$first": "$actor_role"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    actor_results = await db.activity_logs.aggregate(actor_pipeline).to_list(None)
    by_actor = [
        {
            "actor_id": item["_id"],
            "actor_name": item["actor_name"],
            "actor_role": item["actor_role"],
            "count": item["count"]
        }
        for item in actor_results
    ]
    
    # Recent critical logs (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_critical = await db.activity_logs.count_documents({
        "severity": "critical",
        "created_at": {"$gte": yesterday}
    })
    
    return {
        "total_logs": total_logs,
        "today_logs": today_logs,
        "by_action_type": by_action_type,
        "by_severity": by_severity,
        "by_target_type": by_target_type,
        "by_actor": by_actor,
        "recent_critical": recent_critical
    }


async def export_activity_logs(
    action_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    target_type: Optional[str] = None,
    severity: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> str:
    """
    Export activity logs as CSV.
    
    Args:
        action_type: Filter by action type
        actor_id: Filter by actor ID
        target_type: Filter by target type
        severity: Filter by severity
        date_from: Filter from date
        date_to: Filter to date
    
    Returns:
        str: CSV content
    """
    import csv
    import json
    from io import StringIO
    
    db = get_database()
    
    # Build query (same as get_activity_logs)
    query = {}
    
    if action_type:
        query["action_type"] = action_type
    
    if actor_id:
        query["actor_id"] = actor_id
    
    if target_type:
        query["target_type"] = target_type
    
    if severity:
        query["severity"] = severity
    
    if date_from or date_to:
        date_query = {}
        if date_from:
            date_query["$gte"] = date_from
        if date_to:
            date_query["$lte"] = date_to
        if date_query:
            query["created_at"] = date_query
    
    # Get all logs (limit to 10000 for safety)
    logs_cursor = db.activity_logs.find(query).sort("created_at", -1).limit(10000)
    logs_list = await logs_cursor.to_list(10000)
    
    # Build CSV using csv.DictWriter
    output = StringIO()
    
    fieldnames = [
        "Timestamp",
        "Action Type",
        "Actor Name",
        "Actor Role",
        "Target Type",
        "Target Name",
        "Severity",
        "IP Address",
        "User Agent",
        "Details"
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator='\r\n')
    writer.writeheader()
    
    # Write each log as a row
    for log in logs_list:
        writer.writerow({
            "Timestamp": log["created_at"].strftime("%Y-%m-%d %H:%M:%S") if log.get("created_at") else "",
            "Action Type": log.get("action_type", ""),
            "Actor Name": log.get("actor_name", ""),
            "Actor Role": log.get("actor_role", ""),
            "Target Type": log.get("target_type", ""),
            "Target Name": log.get("target_name", ""),
            "Severity": log.get("severity", ""),
            "IP Address": log.get("ip_address", ""),
            "User Agent": log.get("user_agent", ""),
            "Details": json.dumps(log.get("action_details", {}))
        })
    
    return output.getvalue()
