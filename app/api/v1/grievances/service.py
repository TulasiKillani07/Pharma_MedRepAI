"""
Grievance service - Business logic for grievance management.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from app.database import get_database
from app.models.grievance_model import GrievanceStatus, GrievancePriority
from bson import ObjectId


async def generate_ticket_id(department: str) -> str:
    """
    Generate unique ticket ID in format: DEPT-YYYY-NNN
    Example: HR-2026-001, FIN-2026-042
    
    Args:
        department: Department code (hr, finance, it)
    
    Returns:
        str: Generated ticket ID
    """
    db = get_database()
    
    # Get current year
    current_year = datetime.utcnow().year
    
    # Get department prefix (uppercase first 2-3 letters)
    dept_prefix = department.upper()[:3]
    
    # Count existing tickets for this department and year
    pattern = f"^{dept_prefix}-{current_year}-"
    count = await db.grievances.count_documents({
        "ticket_id": {"$regex": pattern}
    })
    
    # Generate next number (001, 002, etc.)
    next_number = count + 1
    
    # Format: DEPT-YYYY-NNN
    ticket_id = f"{dept_prefix}-{current_year}-{next_number:03d}"
    
    return ticket_id


async def create_grievance(
    department: str,
    subject: str,
    description: str,
    priority: GrievancePriority,
    current_user: Dict[str, Any]
) -> Dict[str, str]:
    """
    Create a new grievance (MR only).
    
    Args:
        department: Department code
        subject: Grievance subject
        description: Detailed description
        priority: Priority level
        current_user: Current authenticated MR
    
    Returns:
        dict: Success message with ticket_id
    
    Raises:
        HTTPException: If department not found or inactive
    """
    db = get_database()
    
    # Validate department exists and is active
    dept = await db.departments.find_one({"code": department.lower(), "is_active": True})
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department '{department}' not found or inactive"
        )
    
    # Generate ticket ID
    ticket_id = await generate_ticket_id(department.lower())
    
    # Create grievance document
    grievance_doc = {
        "ticket_id": ticket_id,
        "department": department.lower(),
        "subject": subject,
        "description": description,
        "priority": priority.value,
        "status": GrievanceStatus.OPEN.value,
        "created_by": current_user["_id"],
        "created_by_name": current_user.get("name", "Unknown"),
        "created_by_email": current_user.get("email", ""),
        "mr_territory": current_user.get("territory"),
        "mr_state": current_user.get("state"),
        "admin_response": None,
        "responded_by": None,
        "responded_by_name": None,
        "responded_at": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "resolved_at": None,
        "is_active": True
    }
    
    await db.grievances.insert_one(grievance_doc)
    
    print(f"[SUCCESS] Grievance created: {ticket_id} by MR {current_user['_id']}")
    
    return {
        "message": "Grievance submitted successfully",
        "ticket_id": ticket_id
    }


async def get_my_grievances(
    current_user: Dict[str, Any],
    page: int = 1,
    limit: int = 20,
    status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get MR's own grievances with pagination.
    
    Args:
        current_user: Current authenticated MR
        page: Page number (1-indexed)
        limit: Items per page
        status_filter: Filter by status (optional)
        priority_filter: Filter by priority (optional)
    
    Returns:
        dict: Paginated list of grievances
    """
    db = get_database()
    
    # Build query
    query = {
        "created_by": current_user["_id"],
        "is_active": True
    }
    
    if status_filter:
        query["status"] = status_filter
    
    if priority_filter:
        query["priority"] = priority_filter
    
    # Count total
    total = await db.grievances.count_documents(query)
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit
    
    # Get grievances
    grievances = await db.grievances.find(query)\
        .sort("created_at", -1)\
        .skip(skip)\
        .limit(limit)\
        .to_list(None)
    
    # Format response
    grievance_list = []
    for g in grievances:
        grievance_list.append({
            "ticket_id": g["ticket_id"],
            "department": g["department"],
            "subject": g["subject"],
            "priority": g["priority"],
            "status": g["status"],
            "created_at": g["created_at"],
            "responded_at": g.get("responded_at")
        })
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "grievances": grievance_list
    }


async def get_grievance_detail(
    ticket_id: str,
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get grievance details (MR can only view their own).
    
    Args:
        ticket_id: Ticket ID
        current_user: Current authenticated MR
    
    Returns:
        dict: Grievance details
    
    Raises:
        HTTPException: If grievance not found or not owned by MR
    """
    db = get_database()
    
    # Get grievance
    grievance = await db.grievances.find_one({
        "ticket_id": ticket_id,
        "created_by": current_user["_id"],
        "is_active": True
    })
    
    if not grievance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grievance not found"
        )
    
    # Format response
    return {
        "ticket_id": grievance["ticket_id"],
        "department": grievance["department"],
        "subject": grievance["subject"],
        "description": grievance["description"],
        "priority": grievance["priority"],
        "status": grievance["status"],
        "created_by_name": grievance["created_by_name"],
        "created_by_email": grievance["created_by_email"],
        "mr_territory": grievance.get("mr_territory"),
        "mr_state": grievance.get("mr_state"),
        "created_at": grievance["created_at"],
        "admin_response": grievance.get("admin_response"),
        "responded_by_name": grievance.get("responded_by_name"),
        "responded_at": grievance.get("responded_at"),
        "resolved_at": grievance.get("resolved_at")
    }


async def get_all_grievances_admin(
    current_user: Dict[str, Any],
    page: int = 1,
    limit: int = 20,
    status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    department_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get all grievances for admin (filtered by department if not general admin).
    
    Args:
        current_user: Current authenticated admin
        page: Page number (1-indexed)
        limit: Items per page
        status_filter: Filter by status (optional)
        priority_filter: Filter by priority (optional)
        department_filter: Filter by department (optional)
    
    Returns:
        dict: Paginated list of grievances
    """
    db = get_database()
    
    # Build query
    query = {"is_active": True}
    
    # Department-based access control
    admin_dept = current_user.get("department", "general")
    if admin_dept != "general":
        # Department admin sees only their department's grievances
        query["department"] = admin_dept
    elif department_filter:
        # General admin can filter by department
        query["department"] = department_filter
    
    if status_filter:
        query["status"] = status_filter
    
    if priority_filter:
        query["priority"] = priority_filter
    
    # Count total
    total = await db.grievances.count_documents(query)
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit
    
    # Get grievances
    grievances = await db.grievances.find(query)\
        .sort([("status", 1), ("priority", -1), ("created_at", -1)])\
        .skip(skip)\
        .limit(limit)\
        .to_list(None)
    
    # Format response
    grievance_list = []
    for g in grievances:
        grievance_list.append({
            "ticket_id": g["ticket_id"],
            "department": g["department"],
            "subject": g["subject"],
            "priority": g["priority"],
            "status": g["status"],
            "created_at": g["created_at"],
            "responded_at": g.get("responded_at")
        })
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "grievances": grievance_list
    }


async def get_grievance_detail_admin(
    ticket_id: str,
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get grievance details for admin (with department access control).
    
    Args:
        ticket_id: Ticket ID
        current_user: Current authenticated admin
    
    Returns:
        dict: Grievance details
    
    Raises:
        HTTPException: If grievance not found or access denied
    """
    db = get_database()
    
    # Build query
    query = {
        "ticket_id": ticket_id,
        "is_active": True
    }
    
    # Department-based access control
    admin_dept = current_user.get("department", "general")
    if admin_dept != "general":
        query["department"] = admin_dept
    
    # Get grievance
    grievance = await db.grievances.find_one(query)
    
    if not grievance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grievance not found or access denied"
        )
    
    # Format response
    return {
        "ticket_id": grievance["ticket_id"],
        "department": grievance["department"],
        "subject": grievance["subject"],
        "description": grievance["description"],
        "priority": grievance["priority"],
        "status": grievance["status"],
        "created_by_name": grievance["created_by_name"],
        "created_by_email": grievance["created_by_email"],
        "mr_territory": grievance.get("mr_territory"),
        "mr_state": grievance.get("mr_state"),
        "created_at": grievance["created_at"],
        "admin_response": grievance.get("admin_response"),
        "responded_by_name": grievance.get("responded_by_name"),
        "responded_at": grievance.get("responded_at"),
        "resolved_at": grievance.get("resolved_at")
    }


async def respond_to_grievance(
    ticket_id: str,
    admin_response: str,
    new_status: GrievanceStatus,
    current_user: Dict[str, Any]
) -> Dict[str, str]:
    """
    Admin responds to a grievance and updates status.
    
    Args:
        ticket_id: Ticket ID
        admin_response: Admin's response text
        new_status: Updated status
        current_user: Current authenticated admin
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If grievance not found or access denied
    """
    db = get_database()
    
    # Build query
    query = {
        "ticket_id": ticket_id,
        "is_active": True
    }
    
    # Department-based access control
    admin_dept = current_user.get("department", "general")
    if admin_dept != "general":
        query["department"] = admin_dept
    
    # Check if grievance exists
    grievance = await db.grievances.find_one(query)
    
    if not grievance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grievance not found or access denied"
        )
    
    # Prepare update
    update_data = {
        "admin_response": admin_response,
        "status": new_status.value,
        "responded_by": current_user["_id"],
        "responded_by_name": current_user.get("name", "Admin"),
        "responded_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # If status is resolved or rejected, set resolved_at
    if new_status in [GrievanceStatus.RESOLVED, GrievanceStatus.REJECTED]:
        update_data["resolved_at"] = datetime.utcnow()
    
    # Update grievance
    await db.grievances.update_one(
        {"ticket_id": ticket_id},
        {"$set": update_data}
    )
    
    print(f"[SUCCESS] Grievance {ticket_id} updated by admin {current_user['_id']}")
    
    return {"message": f"Response submitted successfully. Status updated to {new_status.value}"}


async def get_grievance_stats(current_user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get grievance statistics for admin dashboard.
    
    Args:
        current_user: Current authenticated admin
    
    Returns:
        dict: Statistics
    """
    db = get_database()
    
    # Build base query
    query = {"is_active": True}
    
    # Department-based access control
    admin_dept = current_user.get("department", "general")
    if admin_dept != "general":
        query["department"] = admin_dept
    
    # Count by status
    total = await db.grievances.count_documents(query)
    
    open_count = await db.grievances.count_documents({**query, "status": "open"})
    in_progress_count = await db.grievances.count_documents({**query, "status": "in_progress"})
    resolved_count = await db.grievances.count_documents({**query, "status": "resolved"})
    rejected_count = await db.grievances.count_documents({**query, "status": "rejected"})
    
    # Count by department (only for general admin)
    by_department = {}
    if admin_dept == "general":
        departments = await db.departments.find({"is_active": True}).to_list(None)
        for dept in departments:
            count = await db.grievances.count_documents({
                "is_active": True,
                "department": dept["code"]
            })
            by_department[dept["code"]] = count
    else:
        by_department[admin_dept] = total
    
    # Count by priority
    low_count = await db.grievances.count_documents({**query, "priority": "low"})
    medium_count = await db.grievances.count_documents({**query, "priority": "medium"})
    high_count = await db.grievances.count_documents({**query, "priority": "high"})
    urgent_count = await db.grievances.count_documents({**query, "priority": "urgent"})
    
    return {
        "total": total,
        "open": open_count,
        "in_progress": in_progress_count,
        "resolved": resolved_count,
        "rejected": rejected_count,
        "by_department": by_department,
        "by_priority": {
            "low": low_count,
            "medium": medium_count,
            "high": high_count,
            "urgent": urgent_count
        }
    }
