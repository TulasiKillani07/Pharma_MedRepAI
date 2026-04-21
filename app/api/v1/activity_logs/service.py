"""
Activity Logs Business Logic
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from app.database import get_database
from fastapi import HTTPException


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
        logs.append({
            "log_id": str(log["_id"]),
            "action_type": log["action_type"],
            "actor_id": log["actor_id"],
            "actor_name": log["actor_name"],
            "actor_role": log["actor_role"],
            "target_type": log["target_type"],
            "target_id": log.get("target_id"),
            "target_name": log.get("target_name"),
            "action_details": log.get("action_details", {}),
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
    
    # Recent critical logs (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_critical = await db.activity_logs.count_documents({
        "severity": "critical",
        "created_at": {"$gte": yesterday}
    })
    
    return {
        "total_logs": total_logs,
        "by_action_type": by_action_type,
        "by_severity": by_severity,
        "by_target_type": by_target_type,
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
