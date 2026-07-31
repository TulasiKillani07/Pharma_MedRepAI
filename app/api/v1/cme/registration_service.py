"""
CME Event Registration Business Logic
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from bson import ObjectId
import secrets
import string
from app.database import get_database
from app.models.cme_registration_model import CMERegistrationInDB, RegistrationStatus
from app.api.v1.notifications.helpers import notify_cme_registration_confirmed, notify_cme_registration_cancelled_user
from app.api.v1.email.service import send_cme_registration_confirmation_email
from app.api.v1.activity_logs.helpers import log_activity
from app.models.activity_log_model import ActivityLogAction, TargetType, LogSeverity
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)


def generate_registration_passcode() -> str:
    """Generate a 6-character alphanumeric passcode for offline event registration"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(6))


async def register_for_cme(event_id: str, current_user: Dict) -> Dict[str, Any]:
    """Register a doctor for a CME event"""
    db = get_database()
    
    # Validate event_id
    if not ObjectId.is_valid(event_id):
        raise HTTPException(status_code=400, detail="Invalid event ID")
    
    # Check if user is a doctor
    if current_user.get("role") != "DOCTOR":
        raise HTTPException(status_code=403, detail="Only doctors can register for CME events")
    
    doctor_id = current_user.get("_id")  # Use _id instead of sub
    
    # Get event details
    event = await db["cme_events"].find_one({"_id": ObjectId(event_id)})
    if not event:
        raise HTTPException(status_code=404, detail="CME event not found")
    
    # Check if event is upcoming
    if event.get("status") != "upcoming":
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot register for {event.get('status')} events. Only upcoming events are open for registration."
        )
    
    # Check if already registered
    existing_registration = await db["cme_registrations"].find_one({
        "cme_id": event_id,
        "doctor_id": doctor_id
    })
    
    if existing_registration:
        raise HTTPException(status_code=400, detail="You are already registered for this event")
    
    # Check capacity
    if event.get("max_attendees"):
        active_registrations_count = await db["cme_registrations"].count_documents({
            "cme_id": event_id,
            "registration_status": "registered"
        })
        
        if active_registrations_count >= event["max_attendees"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Event is full. Maximum capacity of {event['max_attendees']} attendees reached."
            )
    
    # Get doctor details
    doctor = await db["doctors"].find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    # Generate passcode for offline events
    passcode = None
    if event.get("event_mode") == "offline":
        passcode = generate_registration_passcode()
    
    # Create registration
    registration = CMERegistrationInDB(
        cme_id=event_id,
        doctor_id=doctor_id,
        doctor_name=doctor.get("name", ""),
        doctor_email=doctor.get("email", ""),
        registration_status=RegistrationStatus.REGISTERED,
        registration_passcode=passcode
    )
    
    result = await db["cme_registrations"].insert_one(registration.model_dump())
    
    # Send confirmation email
    event_date_str = event["event_date"].strftime("%B %d, %Y") if event.get("event_date") else ""
    event_time_str = event.get("event_time", "")
    
    try:
        await send_cme_registration_confirmation_email(
            to_email=doctor.get("email"),
            doctor_name=doctor.get("name", ""),
            event_title=event.get("title", ""),
            event_date=event_date_str,
            event_time=event_time_str,
            event_type=event.get("event_type", ""),
            event_mode=event.get("event_mode", ""),
            speaker=event.get("speaker", ""),
            meeting_link=event.get("meeting_link"),
            platform=event.get("platform"),
            venue_name=event.get("venue_name"),
            address=event.get("address"),
            registration_passcode=passcode
        )
    except Exception as e:
        # Log email failure but don't fail registration
        logger.error(f"Failed to send registration confirmation email: {e}")
    
    # Send in-app notification
    await notify_cme_registration_confirmed(
        doctor_id=doctor_id,
        cme_id=event_id,
        cme_title=event.get("title", ""),
        event_date=event["event_date"].strftime("%Y-%m-%d") if event.get("event_date") else "",
        event_time=event_time_str
    )
    
    # Log activity
    await log_activity(
        action_type=ActivityLogAction.CME_REGISTERED,
        actor=current_user,
        target_type=TargetType.CME_EVENT,
        target_id=event_id,
        target_name=event.get("title"),
        details={
            "event_date": event_date_str,
            "event_time": event_time_str
        },
        severity=LogSeverity.INFO
    )
    
    return await get_registration_by_id(str(result.inserted_id))


async def get_my_registrations(
    skip: int,
    limit: int,
    current_user: Dict
) -> Dict[str, Any]:
    """Get all registrations for the logged-in doctor"""
    db = get_database()
    
    # Check if user is a doctor
    if current_user.get("role") != "DOCTOR":
        raise HTTPException(status_code=403, detail="Only doctors can view their registrations")
    
    doctor_id = current_user.get("_id")  # Use _id instead of sub
    
    # Build query - only get registered events
    query = {"doctor_id": doctor_id, "registration_status": "registered"}
    
    # Get registrations
    cursor = db["cme_registrations"].find(query).sort("registered_at", -1).skip(skip).limit(limit)
    registrations = await cursor.to_list(length=limit)
    
    # Enrich with event details
    enriched_registrations = []
    for reg in registrations:
        # Validate and convert cme_id to ObjectId
        if not ObjectId.is_valid(reg["cme_id"]):
            continue  # Skip invalid event IDs
        
        event = await db["cme_events"].find_one({"_id": ObjectId(reg["cme_id"])})
        if event:
            enriched_registrations.append({
                "_id": str(reg["_id"]),
                "cme_id": reg["cme_id"],
                "cme_title": event.get("title", ""),
                "cme_date": event.get("event_date"),
                "cme_time": event.get("event_time", ""),
                "cme_event_type": event.get("event_type", ""),
                "cme_event_mode": event.get("event_mode"),
                "cme_status": event.get("status", ""),
                "cme_meeting_link": event.get("meeting_link"),
                "cme_platform": event.get("platform"),
                "cme_venue_name": event.get("venue_name"),
                "cme_address": event.get("address"),
                "cme_speaker": event.get("speaker"),
                "doctor_id": reg["doctor_id"],
                "doctor_name": reg.get("doctor_name", ""),
                "registration_status": reg["registration_status"],
                "registration_passcode": reg.get("registration_passcode"),
                "registered_at": reg["registered_at"]
            })
    
    total = await db["cme_registrations"].count_documents(query)
    
    return {"registrations": enriched_registrations, "total": total}


async def get_registration_status(event_id: str, current_user: Dict) -> Optional[Dict[str, Any]]:
    """Check if doctor is registered for a specific event"""
    db = get_database()
    
    # Validate event_id
    if not ObjectId.is_valid(event_id):
        raise HTTPException(status_code=400, detail="Invalid event ID")
    
    # Check if user is a doctor
    if current_user.get("role") != "DOCTOR":
        raise HTTPException(status_code=403, detail="Only doctors can check registration status")
    
    doctor_id = current_user.get("_id")  # Use _id instead of sub
    
    # Get registration
    registration = await db["cme_registrations"].find_one({
        "cme_id": event_id,
        "doctor_id": doctor_id
    })
    
    if not registration:
        return None
    
    # Get event details
    event = await db["cme_events"].find_one({"_id": ObjectId(event_id)})
    
    return {
        "_id": str(registration["_id"]),
        "cme_id": registration["cme_id"],
        "cme_title": event.get("title", "") if event else "",
        "cme_date": event.get("event_date") if event else None,
        "cme_time": event.get("event_time", "") if event else "",
        "cme_event_type": event.get("event_type", "") if event else "",
        "cme_event_mode": event.get("event_mode") if event else None,
        "cme_status": event.get("status", "") if event else "",
        "cme_meeting_link": event.get("meeting_link") if event else None,
        "cme_platform": event.get("platform") if event else None,
        "cme_venue_name": event.get("venue_name") if event else None,
        "cme_address": event.get("address") if event else None,
        "cme_speaker": event.get("speaker") if event else None,
        "doctor_id": registration["doctor_id"],
        "doctor_name": registration.get("doctor_name", ""),
        "registration_status": registration["registration_status"],
        "registration_passcode": registration.get("registration_passcode"),
        "registered_at": registration["registered_at"]
    }


async def get_event_registrations(
    event_id: str,
    skip: int,
    limit: int
) -> Dict[str, Any]:
    """Get all registrations for a specific event (Admin only)"""
    db = get_database()
    
    # Validate event_id
    if not ObjectId.is_valid(event_id):
        raise HTTPException(status_code=400, detail="Invalid event ID")
    
    # Check if event exists
    event = await db["cme_events"].find_one({"_id": ObjectId(event_id)})
    if not event:
        raise HTTPException(status_code=404, detail="CME event not found")
    
    # Build query - only get registered events
    query = {"cme_id": event_id, "registration_status": "registered"}
    
    # Get registrations
    cursor = db["cme_registrations"].find(query).sort("registered_at", -1).skip(skip).limit(limit)
    registrations = await cursor.to_list(length=limit)
    
    # Format response
    enriched_registrations = []
    for reg in registrations:
        enriched_registrations.append({
            "_id": str(reg["_id"]),
            "cme_id": reg["cme_id"],
            "cme_title": event.get("title", ""),
            "cme_date": event.get("event_date"),
            "cme_time": event.get("event_time", ""),
            "cme_event_type": event.get("event_type", ""),
            "cme_event_mode": event.get("event_mode"),
            "cme_status": event.get("status", ""),
            "cme_meeting_link": event.get("meeting_link"),
            "cme_platform": event.get("platform"),
            "cme_venue_name": event.get("venue_name"),
            "cme_address": event.get("address"),
            "cme_speaker": event.get("speaker"),
            "doctor_id": reg["doctor_id"],
            "doctor_name": reg.get("doctor_name", ""),
            "registration_status": reg["registration_status"],
            "registration_passcode": reg.get("registration_passcode"),
            "registered_at": reg["registered_at"]
        })
    
    total = await db["cme_registrations"].count_documents(query)
    
    return {"registrations": enriched_registrations, "total": total}


async def get_event_statistics(event_id: str) -> Dict[str, Any]:
    """Get registration statistics for an event (Admin only)"""
    db = get_database()
    
    # Validate event_id
    if not ObjectId.is_valid(event_id):
        raise HTTPException(status_code=400, detail="Invalid event ID")
    
    # Check if event exists
    event = await db["cme_events"].find_one({"_id": ObjectId(event_id)})
    if not event:
        raise HTTPException(status_code=404, detail="CME event not found")
    
    # Get registration counts - only registered status exists now
    total_registrations = await db["cme_registrations"].count_documents({
        "cme_id": event_id,
        "registration_status": "registered"
    })
    active_registrations = total_registrations  # All are active since we removed cancellation
    
    # Calculate available spots and registration rate
    capacity = event.get("max_attendees")
    available_spots = None
    registration_rate = None
    
    if capacity:
        available_spots = max(0, capacity - active_registrations)
        registration_rate = f"{(active_registrations / capacity * 100):.1f}%"
    
    return {
        "total_registrations": total_registrations,
        "active_registrations": active_registrations,
        "cancelled_registrations": 0,  # No cancellations allowed
        "capacity": capacity,
        "available_spots": available_spots,
        "registration_rate": registration_rate
    }


async def get_registration_by_id(registration_id: str) -> Dict[str, Any]:
    """Get registration by ID (internal helper)"""
    db = get_database()
    
    if not ObjectId.is_valid(registration_id):
        raise HTTPException(status_code=400, detail="Invalid registration ID")
    
    registration = await db["cme_registrations"].find_one({"_id": ObjectId(registration_id)})
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    
    # Get event details
    event = await db["cme_events"].find_one({"_id": ObjectId(registration["cme_id"])})
    
    return {
        "_id": str(registration["_id"]),
        "cme_id": registration["cme_id"],
        "cme_title": event.get("title", "") if event else "",
        "cme_date": event.get("event_date") if event else None,
        "cme_time": event.get("event_time", "") if event else "",
        "cme_event_type": event.get("event_type", "") if event else "",
        "cme_event_mode": event.get("event_mode") if event else None,
        "cme_status": event.get("status", "") if event else "",
        "cme_meeting_link": event.get("meeting_link") if event else None,
        "cme_platform": event.get("platform") if event else None,
        "cme_venue_name": event.get("venue_name") if event else None,
        "cme_address": event.get("address") if event else None,
        "cme_speaker": event.get("speaker") if event else None,
        "doctor_id": registration["doctor_id"],
        "doctor_name": registration.get("doctor_name", ""),
        "registration_status": registration["registration_status"],
        "registration_passcode": registration.get("registration_passcode"),
        "registered_at": registration["registered_at"]
    }


async def get_registered_doctor_ids(event_id: str) -> List[str]:
    """Get list of doctor IDs/GIDs registered for an event (helper for notifications)"""
    db = get_database()
    
    cursor = db["cme_registrations"].find({
        "cme_id": event_id,
        "registration_status": "registered"
    }, {"doctor_id": 1, "doctor_gid": 1})
    
    registrations = await cursor.to_list(None)
    # Support both doctor_id (old) and doctor_gid (integration)
    result = []
    for reg in registrations:
        if reg.get("doctor_id"):
            result.append(reg["doctor_id"])
        elif reg.get("doctor_gid"):
            result.append(reg["doctor_gid"])
    return result
