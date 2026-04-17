"""
Visit service - Business logic for visit operations.
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.config import settings
from app.api.v1.notifications.helpers import (
    notify_visit_scheduled,
    notify_visit_rescheduled,
    notify_visit_completed,
    notify_visit_cancelled
)


def get_company_database():
    """Get company database."""
    return get_database()


async def schedule_visit(
    doctor_id: str,
    scheduled_date: date,
    scheduled_time: str,
    purpose: str,
    location: str,
    notes: Optional[str],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Schedule a new visit.
    MR can only schedule with their assigned doctors.
    
    Args:
        doctor_id: Doctor's ID
        scheduled_date: Visit date
        scheduled_time: Visit time
        purpose: Purpose of visit
        location: Visit location
        notes: Additional notes
        current_user: Current authenticated MR
    
    Returns:
        dict: Success message and visit ID
    
    Raises:
        HTTPException: If validation fails
    """
    company_db = get_company_database()
    mr_id = current_user["_id"]  # Changed from "sub" to "_id"
    
    # Validate doctor ID
    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid doctor ID"
        )
    
    # Get MR details to check assigned doctors
    mr = await company_db.mrs.find_one({"_id": ObjectId(mr_id)})
    if not mr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MR not found"
        )
    
    # Check if doctor is assigned to this MR
    assigned_doctor_ids = mr.get("assigned_doctors", [])
    if doctor_id not in assigned_doctor_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only schedule visits with your assigned doctors"
        )
    
    # Get doctor details
    doctor = await company_db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    # Check if doctor already has a scheduled visit
    existing_visit = await company_db.visits.find_one({
        "doctor_id": doctor_id,
        "status": "scheduled"
    })
    
    if existing_visit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Doctor {doctor['name']} already has a scheduled visit. Please complete or cancel it first."
        )
    
    # Create visit document
    visit_doc = {
        "mr_id": mr_id,
        "mr_name": mr["name"],
        "doctor_id": doctor_id,
        "doctor_name": doctor["name"],
        "scheduled_date": datetime.combine(scheduled_date, datetime.min.time()),  # Convert date to datetime
        "scheduled_time": scheduled_time,
        "purpose": purpose,
        "location": location,
        "notes": notes,
        "status": "scheduled",
        "reschedule_history": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Insert into database
    result = await company_db.visits.insert_one(visit_doc)
    
    # Send notification to doctor
    await notify_visit_scheduled(
        doctor_id=doctor_id,
        visit_id=str(result.inserted_id),
        mr_name=mr["name"],
        mr_id=mr_id,
        scheduled_date=scheduled_date.strftime("%Y-%m-%d"),
        scheduled_time=scheduled_time,
        purpose=purpose
    )
    
    return {
        "message": "Visit scheduled successfully",
        "visit_id": str(result.inserted_id)
    }


async def get_visits(
    current_user: Dict[str, Any],
    status_filter: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    doctor_id: Optional[str] = None,
    mr_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get visits with filters.
    Admin sees all visits, MR sees only their own.
    
    Args:
        current_user: Current authenticated user
        status_filter: Filter by status
        date_from: Start date filter
        date_to: End date filter
        doctor_id: Filter by doctor
        mr_id: Filter by MR (admin only)
    
    Returns:
        list: List of visit documents
    """
    company_db = get_company_database()
    user_role = current_user.get("role")
    user_id = current_user.get("_id")  # Changed from "sub" to "_id"
    
    # Build query
    query = {}
    
    # Role-based filtering
    if user_role == "MR":
        query["mr_id"] = user_id
    elif user_role == "ADMIN" and mr_id:
        query["mr_id"] = mr_id
    
    # Status filter
    if status_filter:
        query["status"] = status_filter
    
    # Date range filter
    if date_from or date_to:
        date_query = {}
        if date_from:
            date_query["$gte"] = datetime.combine(date_from, datetime.min.time())
        if date_to:
            date_query["$lte"] = datetime.combine(date_to, datetime.max.time())
        if date_query:
            query["scheduled_date"] = date_query
    
    # Doctor filter
    if doctor_id:
        query["doctor_id"] = doctor_id
    
    # Get visits
    visits_cursor = company_db.visits.find(query).sort("scheduled_date", -1)
    visits = await visits_cursor.to_list(length=None)
    
    # Convert ObjectId to string
    for visit in visits:
        visit["id"] = str(visit.pop("_id"))
    
    return visits


async def get_visit_by_id(visit_id: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a single visit by ID.
    MR can only view their own visits, Admin can view all.
    
    Args:
        visit_id: Visit's ID
        current_user: Current authenticated user
    
    Returns:
        dict: Visit document
    
    Raises:
        HTTPException: If visit not found or unauthorized
    """
    company_db = get_company_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(visit_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid visit ID"
        )
    
    # Find visit
    visit = await company_db.visits.find_one({"_id": ObjectId(visit_id)})
    
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found"
        )
    
    # Check authorization
    user_role = current_user.get("role")
    user_id = current_user.get("_id")  # Changed from "sub" to "_id"
    
    if user_role == "MR" and visit["mr_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own visits"
        )
    
    # Convert ObjectId to string
    visit["id"] = str(visit.pop("_id"))
    
    return visit


async def reschedule_visit(
    visit_id: str,
    scheduled_date: date,
    scheduled_time: str,
    location: Optional[str],
    notes: Optional[str],
    reason: Optional[str],
    current_user: Dict[str, Any]
) -> Dict[str, str]:
    """
    Reschedule a visit.
    Only scheduled visits can be rescheduled.
    
    Args:
        visit_id: Visit's ID
        scheduled_date: New date
        scheduled_time: New time
        location: New location
        notes: Updated notes
        reason: Reason for rescheduling
        current_user: Current authenticated MR
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    company_db = get_company_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(visit_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid visit ID"
        )
    
    # Find visit
    visit = await company_db.visits.find_one({"_id": ObjectId(visit_id)})
    
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found"
        )
    
    # Check authorization
    user_id = current_user.get("_id")  # Changed from "sub" to "_id"
    if visit["mr_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only reschedule your own visits"
        )
    
    # Check status
    if visit["status"] != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reschedule {visit['status']} visit"
        )
    
    # Add to reschedule history
    history_entry = {
        "old_date": visit["scheduled_date"],
        "old_time": visit["scheduled_time"],
        "new_date": datetime.combine(scheduled_date, datetime.min.time()),  # Convert date to datetime
        "new_time": scheduled_time,
        "rescheduled_at": datetime.utcnow(),
        "reason": reason
    }
    
    # Prepare update data
    update_data = {
        "scheduled_date": datetime.combine(scheduled_date, datetime.min.time()),  # Convert date to datetime
        "scheduled_time": scheduled_time,
        "updated_at": datetime.utcnow()
    }
    
    if location is not None:
        update_data["location"] = location
    if notes is not None:
        update_data["notes"] = notes
    
    # Update visit
    await company_db.visits.update_one(
        {"_id": ObjectId(visit_id)},
        {
            "$set": update_data,
            "$push": {"reschedule_history": history_entry}
        }
    )
    
    # Send notification to doctor
    await notify_visit_rescheduled(
        doctor_id=visit["doctor_id"],
        visit_id=visit_id,
        mr_name=visit["mr_name"],
        old_date=visit["scheduled_date"].strftime("%Y-%m-%d"),
        new_date=scheduled_date.strftime("%Y-%m-%d"),
        new_time=scheduled_time,
        reason=reason
    )
    
    return {"message": "Visit rescheduled successfully"}


async def complete_visit(
    visit_id: str,
    outcome: str,
    feedback: Optional[str],
    current_user: Dict[str, Any]
) -> Dict[str, str]:
    """
    Complete a visit.
    Only scheduled visits can be completed.
    
    Args:
        visit_id: Visit's ID
        outcome: Visit outcome
        feedback: Additional feedback
        current_user: Current authenticated MR
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    company_db = get_company_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(visit_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid visit ID"
        )
    
    # Find visit
    visit = await company_db.visits.find_one({"_id": ObjectId(visit_id)})
    
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found"
        )
    
    # Check authorization
    user_id = current_user.get("_id")  # Changed from "sub" to "_id"
    if visit["mr_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only complete your own visits"
        )
    
    # Check status
    if visit["status"] != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete {visit['status']} visit"
        )
    
    # Update visit
    await company_db.visits.update_one(
        {"_id": ObjectId(visit_id)},
        {
            "$set": {
                "status": "completed",
                "outcome": outcome,
                "feedback": feedback,
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Send notification to MR (self-notification for confirmation)
    await notify_visit_completed(
        mr_id=user_id,
        visit_id=visit_id,
        doctor_name=visit["doctor_name"],
        doctor_id=visit["doctor_id"],
        completed_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    )
    
    return {"message": "Visit completed successfully"}


async def cancel_visit(
    visit_id: str,
    reason: str,
    current_user: Dict[str, Any]
) -> Dict[str, str]:
    """
    Cancel a visit.
    Only scheduled visits can be cancelled.
    
    Args:
        visit_id: Visit's ID
        reason: Cancellation reason
        current_user: Current authenticated MR
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    company_db = get_company_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(visit_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid visit ID"
        )
    
    # Find visit
    visit = await company_db.visits.find_one({"_id": ObjectId(visit_id)})
    
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found"
        )
    
    # Check authorization
    user_id = current_user.get("_id")  # Changed from "sub" to "_id"
    if visit["mr_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel your own visits"
        )
    
    # Check status
    if visit["status"] != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel {visit['status']} visit"
        )
    
    # Update visit
    await company_db.visits.update_one(
        {"_id": ObjectId(visit_id)},
        {
            "$set": {
                "status": "cancelled",
                "cancel_reason": reason,
                "cancelled_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Send notification to doctor
    await notify_visit_cancelled(
        user_id=visit["doctor_id"],
        visit_id=visit_id,
        cancelled_by_name=visit["mr_name"],
        scheduled_date=visit["scheduled_date"].strftime("%Y-%m-%d"),
        cancel_reason=reason
    )
    
    return {"message": "Visit cancelled successfully"}
