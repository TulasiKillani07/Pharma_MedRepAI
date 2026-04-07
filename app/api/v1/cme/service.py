"""
CME Event Business Logic
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from bson import ObjectId
from app.database import get_database
from app.api.v1.cme.schemas import CMEEventCreate, CMEEventUpdate


async def create_cme_event(event_data: CMEEventCreate) -> Dict[str, Any]:
    """Create a new CME event"""
    db = get_database()
    
    # Validate event_mode specific fields
    if event_data.event_mode == "online":
        if not event_data.platform:
            raise HTTPException(status_code=400, detail="Platform is required for online events")
        if event_data.platform == "Other" and not event_data.platform_name:
            raise HTTPException(status_code=400, detail="Platform name is required when platform is 'Other'")
        if not event_data.meeting_link:
            raise HTTPException(status_code=400, detail="Meeting link is required for online events")
    elif event_data.event_mode == "offline":
        if not event_data.venue_name:
            raise HTTPException(status_code=400, detail="Venue name is required for offline events")
        if not event_data.address:
            raise HTTPException(status_code=400, detail="Address is required for offline events")
    else:
        raise HTTPException(status_code=400, detail="Event mode must be 'online' or 'offline'")
    
    # Convert date to datetime
    event_datetime = datetime.combine(event_data.event_date, datetime.min.time())
    
    event_doc = {
        "title": event_data.title,
        "description": event_data.description,
        "event_date": event_datetime,
        "event_time": event_data.event_time,
        "event_type": event_data.event_type,
        "max_attendees": event_data.max_attendees,
        "event_mode": event_data.event_mode,
        "platform": event_data.platform,
        "platform_name": event_data.platform_name,
        "meeting_link": event_data.meeting_link,
        "venue_name": event_data.venue_name,
        "address": event_data.address,
        "speaker": event_data.speaker,
        "status": event_data.status,
        "event_recording": None,  # Always null on creation
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db["cme_events"].insert_one(event_doc)
    event_doc["_id"] = str(result.inserted_id)
    
    return event_doc


async def get_all_cme_events(
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> Dict[str, Any]:
    """Get all CME events with filters"""
    db = get_database()
    
    # Build query
    query = {}
    if status:
        query["status"] = status
    if event_type:
        query["event_type"] = event_type
    
    cursor = db["cme_events"].find(query).sort("event_date", -1).skip(skip).limit(limit)
    events = await cursor.to_list(length=limit)
    
    # Convert ObjectId to string and handle legacy data
    for event in events:
        event["_id"] = str(event["_id"])
        
        # Handle legacy events that don't have event_mode
        if "event_mode" not in event or event["event_mode"] is None:
            # Set default values for backward compatibility
            event["event_mode"] = None
            event["platform"] = None
            event["platform_name"] = None
            event["meeting_link"] = None
            event["venue_name"] = None
            event["address"] = None
    
    total = await db["cme_events"].count_documents(query)
    
    return {"events": events, "total": total}


async def get_cme_event_by_id(event_id: str) -> Dict[str, Any]:
    """Get CME event by ID"""
    db = get_database()
    
    if not ObjectId.is_valid(event_id):
        raise HTTPException(status_code=400, detail="Invalid event ID")
    
    event = await db["cme_events"].find_one({"_id": ObjectId(event_id)})
    
    if not event:
        raise HTTPException(status_code=404, detail="CME event not found")
    
    event["_id"] = str(event["_id"])
    
    # Handle legacy events that don't have event_mode
    if "event_mode" not in event or event["event_mode"] is None:
        # Set default values for backward compatibility
        event["event_mode"] = None
        event["platform"] = None
        event["platform_name"] = None
        event["meeting_link"] = None
        event["venue_name"] = None
        event["address"] = None
    
    return event


async def update_cme_event(event_id: str, event_data: CMEEventUpdate) -> Dict[str, Any]:
    """Update a CME event"""
    db = get_database()
    
    if not ObjectId.is_valid(event_id):
        raise HTTPException(status_code=400, detail="Invalid event ID")
    
    # Get existing event
    event = await db["cme_events"].find_one({"_id": ObjectId(event_id)})
    if not event:
        raise HTTPException(status_code=404, detail="CME event not found")
    
    # Build update data
    update_data = {"updated_at": datetime.utcnow()}
    
    if event_data.title is not None:
        update_data["title"] = event_data.title
    if event_data.description is not None:
        update_data["description"] = event_data.description
    if event_data.event_date is not None:
        update_data["event_date"] = datetime.combine(event_data.event_date, datetime.min.time())
    if event_data.event_time is not None:
        update_data["event_time"] = event_data.event_time
    if event_data.event_type is not None:
        update_data["event_type"] = event_data.event_type
    if event_data.max_attendees is not None:
        update_data["max_attendees"] = event_data.max_attendees
    if event_data.speaker is not None:
        update_data["speaker"] = event_data.speaker
    if event_data.status is not None:
        update_data["status"] = event_data.status
    
    # Handle event_mode updates
    if event_data.event_mode is not None:
        update_data["event_mode"] = event_data.event_mode
    
    # Handle online mode fields
    if event_data.platform is not None:
        update_data["platform"] = event_data.platform
    if event_data.platform_name is not None:
        update_data["platform_name"] = event_data.platform_name
    if event_data.meeting_link is not None:
        update_data["meeting_link"] = event_data.meeting_link
    
    # Handle offline mode fields
    if event_data.venue_name is not None:
        update_data["venue_name"] = event_data.venue_name
    if event_data.address is not None:
        update_data["address"] = event_data.address
    
    # Validate event_recording can only be set when status is completed
    if event_data.event_recording is not None:
        # Determine final status after update
        final_status = update_data.get("status", event.get("status"))
        
        if final_status != "completed":
            raise HTTPException(
                status_code=400, 
                detail="Event recording can only be added when event status is 'completed'"
            )
        
        update_data["event_recording"] = event_data.event_recording
    
    # Update in database
    result = await db["cme_events"].update_one(
        {"_id": ObjectId(event_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="CME event not found")
    
    return await get_cme_event_by_id(event_id)
