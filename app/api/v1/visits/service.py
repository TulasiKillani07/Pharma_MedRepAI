"""
Visit service - Business logic for visit operations.
"""
from datetime import datetime, date
import calendar
import asyncio

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status, Request
from bson import ObjectId
from app.database import get_database
from app.config import settings
from app.api.v1.notifications.helpers import (
    notify_visit_scheduled,
    notify_visit_rescheduled,
    notify_visit_completed,
    notify_visit_cancelled
)
from app.models.visit_model import VisitInDB, VisitStatus
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)
from app.api.v1.activity_logs.helpers import log_activity
from app.models.activity_log_model import ActivityLogAction, ActorRole, TargetType, LogSeverity
from app.utils.serializers import convert_objectids_to_strings, serialize_mongo_document


def get_company_database():
    """Get company database."""
    return get_database()


async def schedule_visit(
    doctor_id: str,
    title: str,
    scheduled_date: date,
    scheduled_time: str,
    purpose: str,
    location: str | dict,  # UPDATED: Accept both string (old) and dict (new)
    notes: Optional[str],
    current_user: Dict[str, Any],
    request: Optional[Request] = None
) -> Dict[str, Any]:
    """
    Schedule a new visit.
    MR can only schedule with their assigned doctors.
    
    UPDATED: Now supports both old location format (string) and new format (dict with type)
    
    Args:
        doctor_id: Doctor's ID
        scheduled_date: Visit date
        scheduled_time: Visit time
        purpose: Purpose of visit
        location: Visit location (string for backward compatibility, dict for new format)
        notes: Additional notes
        current_user: Current authenticated MR
    
    Returns:
        dict: Success message and visit ID
    
    Raises:
        HTTPException: If validation fails
    """
    company_db = get_company_database()
    mr_id = current_user["_id"]
    
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
    
    # NEW: Validate location format if dict
    visit_location = location
    if isinstance(location, dict):
        location_type = location.get("type")
        
        if location_type == "permanent":
            # Validate location_id exists in doctor's locations
            location_id = location.get("location_id")
            if not location_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="location_id required for permanent location"
                )
            
            # Check if location exists and is active
            doctor_locations = doctor.get("locations", [])
            location_found = False
            for loc in doctor_locations:
                if loc["id"] == location_id and loc.get("is_active", True):
                    location_found = True
                    # Cache location name if not provided
                    if not location.get("location_name"):
                        visit_location = location.copy()
                        visit_location["location_name"] = loc["name"]
                    break
            
            if not location_found:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected location not found or inactive"
                )
        
        elif location_type == "temporary":
            # Validate temporary location has required fields
            temp_loc = location.get("temporary_location")
            if not temp_loc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="temporary_location required for temporary type"
                )
            
            required_fields = ["reason", "name", "latitude", "longitude"]
            for field in required_fields:
                if field not in temp_loc:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"temporary_location.{field} is required"
                    )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid location type: {location_type}"
            )
    
    # Create visit (supports both old string and new dict format)
    visit = VisitInDB(
        mr_id=mr_id,
        mr_name=mr["name"],
        doctor_id=doctor_id,
        doctor_name=doctor["name"],
        title=title,
        scheduled_date=scheduled_date,
        scheduled_time=scheduled_time,
        purpose=purpose,
        location=visit_location,  # Can be string or dict
        notes=notes,
        status=VisitStatus.SCHEDULED
    )
    
    # Convert to dict and adjust date for MongoDB
    visit_doc = visit.model_dump()
    visit_doc["scheduled_date"] = datetime.combine(scheduled_date, datetime.min.time())
    
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
    
    # Log activity
    await log_activity(
        action_type=ActivityLogAction.VISIT_SCHEDULED,
        actor=current_user,
        target_type=TargetType.VISIT,
        target_id=str(result.inserted_id),
        target_name=f"Visit with {doctor['name']}",
        details={
            "doctor_id": doctor_id,
            "doctor_name": doctor["name"],
            "scheduled_date": scheduled_date.strftime("%Y-%m-%d"),
            "scheduled_time": scheduled_time,
            "purpose": purpose
        },
        severity=LogSeverity.INFO,
        request=request
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
) -> Dict[str, Any]:
    """
    Get visits with filters.
    Admin sees all visits, MR sees only their own.
    For MR users, also calculates visit targets for current month.
    
    Args:
        current_user: Current authenticated user
        status_filter: Filter by status
        date_from: Start date filter
        date_to: End date filter
        doctor_id: Filter by doctor
        mr_id: Filter by MR (admin only)
    
    Returns:
        dict: {total, visits, targets} - targets only for MR users
    """
    company_db = get_company_database()
    user_role = current_user.get("role")
    user_id = current_user.get("_id")
    
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
    
    # Collect all product IDs from reports to resolve names in one batch query
    all_product_ids = set()
    for visit in visits:
        report = visit.get("report")
        if report and report.get("products_discussed"):
            for pid in report["products_discussed"]:
                pid_str = str(pid) if not isinstance(pid, str) else pid
                if ObjectId.is_valid(pid_str):
                    all_product_ids.add(pid_str)
        if visit.get("products_promoted"):
            for pid in visit["products_promoted"]:
                pid_str = str(pid) if not isinstance(pid, str) else pid
                if ObjectId.is_valid(pid_str):
                    all_product_ids.add(pid_str)
    
    # Fetch all products in one query
    drug_map = {}
    if all_product_ids:
        product_object_ids = [ObjectId(pid) for pid in all_product_ids]
        products = await company_db.drugs.find({"_id": {"$in": product_object_ids}}).to_list(length=None)
        for product in products:
            pid = str(product["_id"])
            drug_name = product.get("drug_name", "")
            if not drug_name and product.get("field_values"):
                for field in product["field_values"]:
                    if field.get("key") == "drug_name":
                        drug_name = field.get("value", "Unknown Drug")
                        break
                    elif field.get("key") in ["name", "product_name", "brand_name"]:
                        drug_name = field.get("value", "Unknown Drug")
                        break
            drug_map[pid] = drug_name or "Unknown Drug"
    
    # Convert ObjectId to string and resolve product names
    for i, visit in enumerate(visits):
        visit["id"] = str(visit.pop("_id"))
        
        # Recursively convert any ObjectIds in nested fields to strings
        visits[i] = convert_objectids_to_strings(visit)
        
        # Resolve products in report
        report = visits[i].get("report")
        if report and report.get("products_discussed"):
            resolved = []
            for pid in report["products_discussed"]:
                pid_str = str(pid) if not isinstance(pid, str) else pid
                resolved.append({"id": pid_str, "name": drug_map.get(pid_str, "Unknown Drug")})
            report["products_discussed"] = resolved
    
    # Calculate targets for MR users only
    targets = []
    if user_role == "MR":
        targets = await calculate_visit_targets(user_id, company_db)
    
    return {
        "total": len(visits),
        "visits": visits,
        "targets": targets
    }


async def calculate_visit_targets(mr_id: str, db) -> List[Dict[str, Any]]:
    """
    Calculate visit targets for an MR's assigned doctors for current month.
    Optimized with parallel database queries for better performance.
    
    Args:
        mr_id: MR user ID
        db: Database connection
    
    Returns:
        list: List of target objects with doctor info, classification, required, and completed counts
    """
    
    # Get current month date range
    now = datetime.utcnow()
    start_of_month = datetime(now.year, now.month, 1)
    last_day = calendar.monthrange(now.year, now.month)[1]
    end_of_month = datetime(now.year, now.month, last_day, 23, 59, 59)
    
    # Fetch MR and SFE settings in parallel
    mr, sfe_settings = await asyncio.gather(
        db.mrs.find_one({"_id": ObjectId(mr_id)}),
        db.sfe_settings.find_one({"company_id": "default"})
    )
    
    if not mr or not mr.get("assigned_doctors"):
        return []
    
    assigned_doctor_ids = mr["assigned_doctors"]
    classification_targets = sfe_settings.get("classification_targets", {"A": 2, "B": 1, "C": 1}) if sfe_settings else {"A": 2, "B": 1, "C": 1}
    
    # Fetch all doctors in ONE query using $in (much faster than loop)
    doctor_object_ids = [ObjectId(doc_id) for doc_id in assigned_doctor_ids if ObjectId.is_valid(doc_id)]
    doctors_cursor = db.doctors.find({"_id": {"$in": doctor_object_ids}})
    doctors = await doctors_cursor.to_list(length=None)
    
    # Create doctor map for quick lookup
    doctor_map = {str(doc["_id"]): doc for doc in doctors}
    
    # Count completed visits for all doctors in parallel
    count_tasks = [
        db.visits.count_documents({
            "mr_id": mr_id,
            "doctor_id": doctor_id,
            "status": "completed",
            "completed_at": {
                "$gte": start_of_month,
                "$lte": end_of_month
            }
        })
        for doctor_id in assigned_doctor_ids
    ]
    completed_counts = await asyncio.gather(*count_tasks)
    
    # Build targets list
    targets = []
    for i, doctor_id in enumerate(assigned_doctor_ids):
        doctor = doctor_map.get(doctor_id)
        if not doctor:
            continue
        
        classification = doctor.get("classification", "C")
        required = classification_targets.get(classification, 1)
        
        targets.append({
            "doctor_id": doctor_id,
            "doctor_name": doctor.get("name", doctor.get("full_name", "Unknown")),
            "classification": classification,
            "required": required,
            "completed": completed_counts[i]
        })
    
    return targets


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
    user_id = current_user.get("_id")
    
    if user_role == "MR" and visit["mr_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own visits"
        )
    
    # Convert ObjectId to string
    visit["id"] = str(visit.pop("_id"))
    
    # Recursively convert any ObjectIds in nested fields to strings
    visit = convert_objectids_to_strings(visit)
    
    # Resolve product names from report
    report = visit.get("report")
    if report and report.get("products_discussed"):
        # Collect all product IDs
        product_ids = set()
        for pid in report["products_discussed"]:
            pid_str = str(pid) if not isinstance(pid, str) else pid
            if ObjectId.is_valid(pid_str):
                product_ids.add(pid_str)
        
        # Fetch all products in one query
        drug_map = {}
        if product_ids:
            product_object_ids = [ObjectId(pid) for pid in product_ids]
            products = await company_db.drugs.find({"_id": {"$in": product_object_ids}}).to_list(length=None)
            for product in products:
                pid = str(product["_id"])
                drug_name = product.get("drug_name", "")
                if not drug_name and product.get("field_values"):
                    for field in product["field_values"]:
                        if field.get("key") == "drug_name":
                            drug_name = field.get("value", "Unknown Drug")
                            break
                        elif field.get("key") in ["name", "product_name", "brand_name"]:
                            drug_name = field.get("value", "Unknown Drug")
                            break
                drug_map[pid] = drug_name or "Unknown Drug"
        
        # Replace product IDs with {id, name} objects
        resolved_products = []
        for pid in report["products_discussed"]:
            pid_str = str(pid) if not isinstance(pid, str) else pid
            resolved_products.append({
                "id": pid_str,
                "name": drug_map.get(pid_str, "Unknown Drug")
            })
        report["products_discussed"] = resolved_products
    
    # Also resolve legacy products_promoted field if exists
    if visit.get("products_promoted"):
        product_ids = set()
        for pid in visit["products_promoted"]:
            pid_str = str(pid) if not isinstance(pid, str) else pid
            if ObjectId.is_valid(pid_str):
                product_ids.add(pid_str)
        
        drug_map = {}
        if product_ids:
            product_object_ids = [ObjectId(pid) for pid in product_ids]
            products = await company_db.drugs.find({"_id": {"$in": product_object_ids}}).to_list(length=None)
            for product in products:
                pid = str(product["_id"])
                drug_name = product.get("drug_name", "")
                if not drug_name and product.get("field_values"):
                    for field in product["field_values"]:
                        if field.get("key") == "drug_name":
                            drug_name = field.get("value", "Unknown Drug")
                            break
                        elif field.get("key") in ["name", "product_name", "brand_name"]:
                            drug_name = field.get("value", "Unknown Drug")
                            break
                drug_map[pid] = drug_name or "Unknown Drug"
        
        resolved_products = []
        for pid in visit["products_promoted"]:
            pid_str = str(pid) if not isinstance(pid, str) else pid
            resolved_products.append({
                "id": pid_str,
                "name": drug_map.get(pid_str, "Unknown Drug")
            })
        visit["products_promoted"] = resolved_products
    
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
    current_user: Dict[str, Any],
    request: Optional[Request] = None,
    # SFE fields
    products_promoted: Optional[List[str]] = None,
    samples_given: Optional[int] = None,
    doctor_mood: Optional[str] = None,
    competitor_info: Optional[str] = None,
    followup_date: Optional[date] = None,
    gps_lat: Optional[float] = None,
    gps_lng: Optional[float] = None
) -> Dict[str, str]:
    """
    Complete a visit with SFE data.
    Only scheduled visits can be completed.
    
    Args:
        visit_id: Visit's ID
        outcome: Visit outcome
        feedback: Additional feedback
        current_user: Current authenticated MR
        products_promoted: List of product IDs promoted
        samples_given: Number of samples distributed
        doctor_mood: Doctor's receptiveness (positive/neutral/negative)
        competitor_info: Competitor information
        followup_date: Next follow-up date
        gps_lat: GPS latitude
        gps_lng: GPS longitude
    
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
    user_id = current_user.get("_id")
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
    
    # Prepare update data
    update_data = {
        "status": VisitStatus.COMPLETED,
        "outcome": outcome,
        "feedback": feedback,
        "completed_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Add SFE fields if provided
    if products_promoted is not None:
        update_data["products_promoted"] = products_promoted
    if samples_given is not None:
        update_data["samples_given"] = samples_given
    if doctor_mood is not None:
        update_data["doctor_mood"] = doctor_mood
    if competitor_info is not None:
        update_data["competitor_info"] = competitor_info
    if followup_date is not None:
        update_data["followup_date"] = datetime.combine(followup_date, datetime.min.time())
    if gps_lat is not None:
        update_data["gps_lat"] = gps_lat
    if gps_lng is not None:
        update_data["gps_lng"] = gps_lng
    
    # Update visit
    await company_db.visits.update_one(
        {"_id": ObjectId(visit_id)},
        {"$set": update_data}
    )
    
    # Handle follow-up visit creation
    if followup_date:
        # Auto-create next scheduled visit
        from app.models.visit_model import VisitInDB, VisitStatus
        
        followup_visit = VisitInDB(
            mr_id=visit["mr_id"],
            mr_name=visit["mr_name"],
            doctor_id=visit["doctor_id"],
            doctor_name=visit["doctor_name"],
            title=f"Follow-up: {visit.get('title', visit.get('purpose', 'Visit'))}",
            scheduled_date=followup_date,
            scheduled_time=visit["scheduled_time"],  # Use same time as previous visit
            purpose=f"Follow-up from visit on {visit['scheduled_date'].strftime('%Y-%m-%d')}",
            location=visit["location"],
            notes=f"Auto-scheduled follow-up",
            status=VisitStatus.SCHEDULED
        )
        
        followup_doc = followup_visit.model_dump()
        followup_doc["scheduled_date"] = datetime.combine(followup_date, datetime.min.time())
        
        await company_db.visits.insert_one(followup_doc)
    
    # Send notification to MR (self-notification for confirmation)
    await notify_visit_completed(
        mr_id=user_id,
        visit_id=visit_id,
        doctor_name=visit["doctor_name"],
        doctor_id=visit["doctor_id"],
        completed_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    )
    
    # Log activity
    activity_details = {
        "doctor_id": visit["doctor_id"],
        "doctor_name": visit["doctor_name"],
        "outcome": outcome,
        "scheduled_date": visit["scheduled_date"].strftime("%Y-%m-%d")
    }
    
    if products_promoted:
        activity_details["products_promoted_count"] = len(products_promoted)
    if samples_given:
        activity_details["samples_given"] = samples_given
    
    await log_activity(
        action_type=ActivityLogAction.VISIT_COMPLETED,
        actor=current_user,
        target_type=TargetType.VISIT,
        target_id=visit_id,
        target_name=f"Visit with {visit['doctor_name']}",
        details=activity_details,
        severity=LogSeverity.INFO,
        request=request
    )
    
    return {"message": "Visit completed successfully"}


async def cancel_visit(
    visit_id: str,
    reason: str,
    current_user: Dict[str, Any],
    request: Optional[Request] = None
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
                "status": VisitStatus.CANCELLED,
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
    
    # Log activity
    await log_activity(
        action_type=ActivityLogAction.VISIT_CANCELLED,
        actor=current_user,
        target_type=TargetType.VISIT,
        target_id=visit_id,
        target_name=f"Visit with {visit['doctor_name']}",
        details={
            "doctor_id": visit["doctor_id"],
            "doctor_name": visit["doctor_name"],
            "reason": reason,
            "scheduled_date": visit["scheduled_date"].strftime("%Y-%m-%d")
        },
        severity=LogSeverity.WARNING,
        request=request
    )
    
    return {"message": "Visit cancelled successfully"}



# ============================================================================
# NEW FUNCTIONS FOR CHECK-IN/CHECK-OUT/REPORT FLOW
# ============================================================================

async def check_in_visit(
    visit_id: str,
    latitude: float,
    longitude: float,
    current_user: Dict[str, Any],
    request: Optional[Request] = None
) -> Dict[str, Any]:
    """
    Check in to a visit with GPS coordinates.
    
    Validations:
    - Visit must be in scheduled status
    - MR must not have another visit with status=checked_in
    - MR must not have more than 2 pending reports (status=checked_out)
    - Visit must belong to this MR
    
    Args:
        visit_id: Visit's ID
        latitude: GPS latitude
        longitude: GPS longitude
        current_user: Current authenticated MR
        request: FastAPI request object
    
    Returns:
        dict: Success message, visit_id, and check_in_time
    
    Raises:
        HTTPException: If validation fails
    """
    company_db = get_company_database()
    user_id = current_user.get("_id")
    
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
    if visit["mr_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only check in to your own visits"
        )
    
    # Check status
    if visit["status"] != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot check in to {visit['status']} visit. Only scheduled visits can be checked in."
        )
    
    # Rule 1: Check if MR has another checked_in visit
    existing_checkin = await company_db.visits.find_one({
        "mr_id": user_id,
        "status": "checked_in"
    })
    
    if existing_checkin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check out of your current visit first. Only one active check-in allowed at a time."
        )
    
    # Rule 2: Check pending reports (max 2 checked_out visits)
    pending_reports_count = await company_db.visits.count_documents({
        "mr_id": user_id,
        "status": "checked_out"
    })
    
    if pending_reports_count >= 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submit pending reports before checking in (max 2 allowed). You have 2 pending reports."
        )
    
    # Perform check-in
    check_in_time = datetime.utcnow()
    
    await company_db.visits.update_one(
        {"_id": ObjectId(visit_id)},
        {
            "$set": {
                "status": VisitStatus.CHECKED_IN,
                "check_in": {
                    "timestamp": check_in_time,
                    "latitude": latitude,
                    "longitude": longitude
                },
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Log activity
    if request:
        await log_activity(
            action_type=ActivityLogAction.VISIT_SCHEDULED,  # Using existing action
            actor=current_user,
            target_type=TargetType.VISIT,
            target_id=visit_id,
            target_name=f"Check-in at {visit['doctor_name']}",
            details={
                "action": "check_in",
                "doctor_id": visit["doctor_id"],
                "doctor_name": visit["doctor_name"],
                "location": visit["location"],
                "gps": f"{latitude},{longitude}"
            },
            severity=LogSeverity.INFO,
            request=request
        )
    
    return {
        "message": "Checked in successfully",
        "visit_id": visit_id,
        "check_in_time": check_in_time
    }


async def check_out_visit(
    visit_id: str,
    latitude: float,
    longitude: float,
    current_user: Dict[str, Any],
    request: Optional[Request] = None
) -> Dict[str, Any]:
    """
    Check out from a visit with GPS coordinates.
    
    Validations:
    - Visit must be in checked_in status
    - Visit must belong to this MR
    
    Args:
        visit_id: Visit's ID
        latitude: GPS latitude at check-out
        longitude: GPS longitude at check-out
        current_user: Current authenticated MR
        request: FastAPI request object
    
    Returns:
        dict: Success message, visit_id, duration_minutes, and distance from location
    
    Raises:
        HTTPException: If validation fails
    """
    company_db = get_company_database()
    user_id = current_user.get("_id")
    
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
    if visit["mr_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only check out from your own visits"
        )
    
    # Check status
    if visit["status"] != "checked_in":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot check out from {visit['status']} visit. Only checked-in visits can be checked out."
        )
    
    # Calculate duration
    check_in_time = visit.get("check_in", {}).get("timestamp")
    if not check_in_time:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Check-in timestamp not found"
        )
    
    check_out_time = datetime.utcnow()
    duration_minutes = int((check_out_time - check_in_time).total_seconds() / 60)
    
    # Resolve visit location and calculate distance from actual location
    from app.api.v1.visits.geofence_service import resolve_visit_location
    from app.utils.geo_utils import calculate_distance
    
    try:
        location_info = await resolve_visit_location(visit, company_db)
        
        # Calculate distance from actual location (same as check-in)
        distance_meters = calculate_distance(
            latitude, longitude,
            location_info["latitude"], location_info["longitude"]
        )
        distance_km = round(distance_meters / 1000, 2)
        
        # Determine geofence status
        geofence_radius = location_info.get("geofence_radius", settings.GEOFENCE_RADIUS)
        geofence_status = "inside" if distance_meters <= geofence_radius else "outside"
        
    except Exception as e:
        # If location resolution fails, proceed without distance calculation
        distance_km = None
        geofence_status = None
    
    # Prepare check-out data
    check_out_data = {
        "timestamp": check_out_time,
        "latitude": latitude,
        "longitude": longitude
    }
    
    if distance_km is not None:
        check_out_data["distance_from_location"] = distance_km
        check_out_data["geofence_status"] = geofence_status
    
    # Perform check-out
    await company_db.visits.update_one(
        {"_id": ObjectId(visit_id)},
        {
            "$set": {
                "status": VisitStatus.CHECKED_OUT,
                "check_out": check_out_data,
                "duration_minutes": duration_minutes,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Log activity
    if request:
        await log_activity(
            action_type=ActivityLogAction.VISIT_SCHEDULED,  # Using existing action
            actor=current_user,
            target_type=TargetType.VISIT,
            target_id=visit_id,
            target_name=f"Check-out from {visit['doctor_name']}",
            details={
                "action": "check_out",
                "doctor_id": visit["doctor_id"],
                "doctor_name": visit["doctor_name"],
                "duration_minutes": duration_minutes,
                "distance_km": distance_km,
                "geofence_status": geofence_status,
                "gps": f"{latitude},{longitude}"
            },
            severity=LogSeverity.INFO,
            request=request
        )
    
    response = {
        "message": "Checked out successfully",
        "visit_id": visit_id,
        "duration_minutes": duration_minutes
    }
    
    if distance_km is not None:
        response["distance_km"] = distance_km
        response["geofence_status"] = geofence_status
    
    return response


async def submit_visit_report(
    visit_id: str,
    report_data: Dict[str, Any],
    current_user: Dict[str, Any],
    request: Optional[Request] = None
) -> Dict[str, Any]:
    """
    Submit visit report (DCR - Daily Call Report).
    This is when the visit counts toward monthly targets.
    
    Validations:
    - Visit must be in checked_out status
    - Visit must belong to this MR
    - outcome is required
    - doctor_mood must be valid (positive/neutral/negative)
    - products_discussed must be from MR's assigned drugs
    
    Args:
        visit_id: Visit's ID
        report_data: Report data dictionary
        current_user: Current authenticated MR
        request: FastAPI request object
    
    Returns:
        dict: Success message, visit_id, and status
    
    Raises:
        HTTPException: If validation fails
    """
    company_db = get_company_database()
    user_id = current_user.get("_id")
    
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
    if visit["mr_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only submit reports for your own visits"
        )
    
    # Check status
    if visit["status"] != "checked_out":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit report for {visit['status']} visit. Only checked-out visits can have reports submitted."
        )
    
    # Validate products_discussed are from MR's assigned drugs
    if report_data.get("products_discussed"):
        mr = await company_db.mrs.find_one({"_id": ObjectId(user_id)})
        if mr:
            assigned_drugs = mr.get("assigned_drugs", [])
            for product_id in report_data["products_discussed"]:
                if product_id not in assigned_drugs:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Product {product_id} is not in your assigned drugs list"
                    )
    
    # Convert product IDs to ObjectIds for storage
    if report_data.get("products_discussed"):
        report_data["products_discussed"] = [
            ObjectId(pid) if ObjectId.is_valid(pid) else pid
            for pid in report_data["products_discussed"]
        ]
    
    # Convert date objects to datetime for MongoDB (MongoDB doesn't support date type)
    if report_data.get("follow_up_date"):
        if isinstance(report_data["follow_up_date"], date):
            report_data["follow_up_date"] = datetime.combine(
                report_data["follow_up_date"], datetime.min.time()
            )
    
    # Perform report submission - THIS IS WHEN IT COUNTS!
    completed_at = datetime.utcnow()
    
    await company_db.visits.update_one(
        {"_id": ObjectId(visit_id)},
        {
            "$set": {
                "status": VisitStatus.COMPLETED,  # NOW IT COUNTS TOWARD TARGET!
                "report": report_data,
                "completed_at": completed_at,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Send notification
    await notify_visit_completed(
        mr_id=user_id,
        visit_id=visit_id,
        doctor_name=visit["doctor_name"],
        doctor_id=visit["doctor_id"],
        completed_at=completed_at.strftime("%Y-%m-%d %H:%M")
    )
    
    # Log activity
    if request:
        await log_activity(
            action_type=ActivityLogAction.VISIT_COMPLETED,
            actor=current_user,
            target_type=TargetType.VISIT,
            target_id=visit_id,
            target_name=f"Report for {visit['doctor_name']}",
            details={
                "doctor_id": visit["doctor_id"],
                "doctor_name": visit["doctor_name"],
                "doctor_mood": report_data.get("doctor_mood"),
                "products_count": len(report_data.get("products_discussed", [])),
                "samples_given": report_data.get("samples_given"),
                "outcome": report_data.get("outcome", "")[:100]  # First 100 chars
            },
            severity=LogSeverity.INFO,
            request=request
        )
    
    # Auto-create follow-up visit if follow_up_date is provided
    follow_up_date = report_data.get("follow_up_date")
    if follow_up_date:
        followup_date_obj = follow_up_date if isinstance(follow_up_date, date) else follow_up_date.date() if isinstance(follow_up_date, datetime) else None
        if followup_date_obj:
            followup_visit = VisitInDB(
                mr_id=visit["mr_id"],
                mr_name=visit["mr_name"],
                doctor_id=visit["doctor_id"],
                doctor_name=visit["doctor_name"],
                title=f"Follow-up: {visit.get('title', visit.get('purpose', 'Visit'))}",
                scheduled_date=followup_date_obj,
                scheduled_time=visit.get("scheduled_time", "10:00"),
                purpose=f"Follow-up from visit on {visit.get('scheduled_date', datetime.utcnow()).strftime('%Y-%m-%d') if hasattr(visit.get('scheduled_date', ''), 'strftime') else str(visit.get('scheduled_date', ''))}",
                location=visit["location"],
                notes="Auto-scheduled follow-up from visit report",
                status=VisitStatus.SCHEDULED
            )
            followup_doc = followup_visit.model_dump()
            followup_doc["scheduled_date"] = datetime.combine(followup_date_obj, datetime.min.time())
            await company_db.visits.insert_one(followup_doc)
            logger.info(f"Auto-created follow-up visit for {visit['doctor_name']} on {followup_date_obj}")
    
    # NEW: Trigger location analysis if temporary location
    location = visit.get("location")
    if isinstance(location, dict) and location.get("type") == "temporary":
        from app.services.location_analysis import trigger_analysis_if_needed
        try:
            await trigger_analysis_if_needed(visit["doctor_id"])
            logger.info(f"Triggered location analysis for doctor {visit['doctor_id']}")
        except Exception as e:
            # Don't fail report submission if analysis fails
            logger.error(f"Location analysis failed: {str(e)}")
    
    return {
        "message": "Report submitted successfully",
        "visit_id": visit_id,
        "status": "completed"
    }


async def get_active_visit(
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get current active (checked_in) visit and pending reports count.
    
    Args:
        current_user: Current authenticated MR
    
    Returns:
        dict: {active_visit: {...} or null, pending_reports: count}
    """
    from app.utils.logger import get_medrep_logger
    logger = get_medrep_logger(__name__)
    
    company_db = get_company_database()
    user_id = current_user.get("_id")
    
    # Validate user_id exists
    if not user_id:
        logger.error(f"User ID not found in current_user: {current_user}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID not found in token"
        )
    
    logger.info(f"Getting active visit for user_id: {user_id}")
    
    try:
        # Find active checked_in visit
        active_visit = await company_db.visits.find_one({
            "mr_id": user_id,
            "status": "checked_in"
        })
        
        logger.info(f"Active visit found: {active_visit is not None}")
        
        # Count pending reports (checked_out visits)
        pending_reports_count = await company_db.visits.count_documents({
            "mr_id": user_id,
            "status": "checked_out"
        })
        
        logger.info(f"Pending reports count: {pending_reports_count}")
        
        # Format active visit response
        active_visit_data = None
        if active_visit:
            check_in_time = active_visit.get("check_in", {}).get("timestamp")
            duration_so_far = 0
            
            if check_in_time:
                duration_so_far = int((datetime.utcnow() - check_in_time).total_seconds() / 60)
            
            active_visit_data = {
                "id": str(active_visit["_id"]),
                "doctor_id": active_visit["doctor_id"],
                "doctor_name": active_visit["doctor_name"],
                "check_in_time": check_in_time,
                "location": active_visit["location"],
                "duration_so_far_minutes": duration_so_far
            }
        
        return {
            "active_visit": active_visit_data,
            "pending_reports": pending_reports_count
        }
    
    except Exception as e:
        logger.error(f"Error in get_active_visit: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active visit: {str(e)}"
        )


async def cancel_check_in(
    visit_id: str,
    reason: str,
    current_user: Dict[str, Any],
    request: Optional[Request] = None
) -> Dict[str, Any]:
    """
    Cancel check-in and revert visit to scheduled status.
    Saves audit trail of cancellation.
    
    Validations:
    - Visit must be in checked_in status
    - Visit must belong to this MR
    - reason is required
    
    Args:
        visit_id: Visit's ID
        reason: Reason for cancelling check-in
        current_user: Current authenticated MR
        request: FastAPI request object
    
    Returns:
        dict: Success message, visit_id, and status
    
    Raises:
        HTTPException: If validation fails
    """
    company_db = get_company_database()
    user_id = current_user.get("_id")
    
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
    if visit["mr_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel check-in for your own visits"
        )
    
    # Check status
    if visit["status"] != "checked_in":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel check-in for {visit['status']} visit. Only checked-in visits can have check-in cancelled."
        )
    
    # Save cancellation audit trail
    cancellation_data = {
        "timestamp": datetime.utcnow(),
        "reason": reason,
        "original_check_in": visit.get("check_in")
    }
    
    # Revert to scheduled status
    await company_db.visits.update_one(
        {"_id": ObjectId(visit_id)},
        {
            "$set": {
                "status": VisitStatus.SCHEDULED,  # Back to scheduled!
                "check_in_cancelled": cancellation_data,
                "updated_at": datetime.utcnow()
            },
            "$unset": {
                "check_in": ""  # Remove check_in data
            }
        }
    )
    
    # Log activity
    if request:
        await log_activity(
            action_type=ActivityLogAction.VISIT_CANCELLED,
            actor=current_user,
            target_type=TargetType.VISIT,
            target_id=visit_id,
            target_name=f"Cancelled check-in for {visit['doctor_name']}",
            details={
                "action": "cancel_check_in",
                "doctor_id": visit["doctor_id"],
                "doctor_name": visit["doctor_name"],
                "reason": reason
            },
            severity=LogSeverity.WARNING,
            request=request
        )
    
    return {
        "message": "Check-in cancelled successfully",
        "visit_id": visit_id,
        "status": "scheduled"
    }
