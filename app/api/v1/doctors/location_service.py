"""
Doctor Location Management Service
"""
from datetime import datetime
from typing import Dict, List, Any, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from app.database import get_database
from app.utils.geo_utils import geocode_search, are_locations_close
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)


async def add_doctor_location(
    doctor_id: str,
    name: str,
    address: Optional[str],
    latitude: float,
    longitude: float,
    location_type: str,
    geofence_radius: int,
    admin_user: Dict[str, Any]
) -> Dict[str, Any]:
    """Add a new location to doctor's profile."""
    db = get_database()
    
    # Validate doctor exists
    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=400, detail="Invalid doctor ID")
    
    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    # Check if location already exists (within 50m)
    existing_locations = doctor.get("locations", [])
    for loc in existing_locations:
        if are_locations_close(latitude, longitude, loc["latitude"], loc["longitude"], threshold_meters=50):
            raise HTTPException(
                status_code=400,
                detail=f"Location already exists: {loc['name']} (within 50m)"
            )
    
    # Create new location
    new_location = {
        "id": str(ObjectId()),
        "type": location_type,
        "name": name,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
        "is_active": True,
        "geofence_radius": geofence_radius,
        "added_by": admin_user["_id"],
        "added_at": datetime.utcnow(),
        "suggested_from_usage": False
    }
    
    # Add to doctor's locations
    await db.doctors.update_one(
        {"_id": ObjectId(doctor_id)},
        {"$push": {"locations": new_location}}
    )
    
    logger.info(f"Added location '{name}' to doctor {doctor_id}")
    
    return {
        "message": "Location added successfully",
        "location": new_location
    }


async def get_doctor_locations(doctor_id: str) -> Dict[str, Any]:
    """Get all locations for a doctor."""
    db = get_database()
    
    # Clean doctor_id (remove spaces)
    doctor_id = doctor_id.strip()
    
    if not ObjectId.is_valid(doctor_id):
        logger.error(f"Invalid doctor ID format: {doctor_id}")
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid doctor ID format: {doctor_id}. Must be a valid MongoDB ObjectId (24 hex characters)"
        )
    
    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        logger.error(f"Doctor not found: {doctor_id}")
        raise HTTPException(
            status_code=404, 
            detail=f"Doctor not found with ID: {doctor_id}"
        )
    
    locations = doctor.get("locations", [])
    
    logger.info(f"Retrieved {len(locations)} locations for doctor {doctor_id}")
    
    return {
        "total": len(locations),
        "locations": locations
    }


async def update_doctor_location(
    doctor_id: str,
    location_id: str,
    updates: Dict[str, Any]
) -> Dict[str, str]:
    """
    Update a doctor's location.
    
    This function handles all location updates including:
    - Editing location details (name, address, coordinates, geofence)
    - Deactivating location (is_active: false)
    - Reactivating location (is_active: true)
    """
    db = get_database()
    
    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=400, detail="Invalid doctor ID")
    
    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    # Find location
    locations = doctor.get("locations", [])
    location_found = False
    
    for i, loc in enumerate(locations):
        if loc["id"] == location_id:
            location_found = True
            # Update fields
            for key, value in updates.items():
                if value is not None:
                    locations[i][key] = value
            break
    
    if not location_found:
        raise HTTPException(status_code=404, detail="Location not found")
    
    # Update in database
    await db.doctors.update_one(
        {"_id": ObjectId(doctor_id)},
        {"$set": {"locations": locations}}
    )
    
    logger.info(f"Updated location {location_id} for doctor {doctor_id}")
    
    return {"message": "Location updated successfully"}


async def search_locations(
    query: str, 
    limit: int = 5,
    user_latitude: Optional[float] = None,
    user_longitude: Optional[float] = None
) -> Dict[str, Any]:
    """Search locations using geocoding."""
    results = await geocode_search(
        query, 
        limit=limit,
        user_latitude=user_latitude,
        user_longitude=user_longitude
    )
    
    return {
        "total": len(results),
        "results": results
    }


async def get_location_suggestions(doctor_id: str) -> Dict[str, Any]:
    """Get location suggestions for a doctor."""
    db = get_database()
    
    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=400, detail="Invalid doctor ID")
    
    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    suggestions = doctor.get("location_suggestions", [])
    
    return {
        "total": len(suggestions),
        "suggestions": suggestions
    }


async def approve_location_suggestion(
    doctor_id: str,
    suggestion_id: str,
    admin_user: Dict[str, Any],
    notes: Optional[str] = None,
    geofence_radius: int = 100
) -> Dict[str, str]:
    """Approve a location suggestion and convert to permanent location."""
    db = get_database()
    
    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=400, detail="Invalid doctor ID")
    
    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    # Find suggestion
    suggestions = doctor.get("location_suggestions", [])
    suggestion = None
    suggestion_index = None
    
    for i, sug in enumerate(suggestions):
        if sug["id"] == suggestion_id:
            if sug["status"] != "pending_review":
                raise HTTPException(status_code=400, detail=f"Suggestion is already {sug['status']}")
            suggestion = sug
            suggestion_index = i
            break
    
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    
    # Create permanent location from suggestion
    new_location = {
        "id": str(ObjectId()),
        "type": "secondary",
        "name": suggestion["name"],
        "address": suggestion.get("address"),
        "latitude": suggestion["latitude"],
        "longitude": suggestion["longitude"],
        "is_active": True,
        "geofence_radius": geofence_radius,
        "added_by": admin_user["_id"],
        "added_at": datetime.utcnow(),
        "suggested_from_usage": True
    }
    
    # Mark suggestion as approved
    suggestions[suggestion_index]["status"] = "approved"
    suggestions[suggestion_index]["admin_action"] = {
        "action_by": admin_user["_id"],
        "action_at": datetime.utcnow(),
        "notes": notes
    }
    
    # Update doctor
    await db.doctors.update_one(
        {"_id": ObjectId(doctor_id)},
        {
            "$push": {"locations": new_location},
            "$set": {"location_suggestions": suggestions}
        }
    )
    
    logger.info(f"Approved suggestion {suggestion_id} for doctor {doctor_id}")
    
    return {
        "message": "Location suggestion approved and added to permanent locations",
        "location_id": new_location["id"]
    }


async def reject_location_suggestion(
    doctor_id: str,
    suggestion_id: str,
    admin_user: Dict[str, Any],
    notes: str
) -> Dict[str, str]:
    """Reject a location suggestion."""
    db = get_database()
    
    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=400, detail="Invalid doctor ID")
    
    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    # Find suggestion
    suggestions = doctor.get("location_suggestions", [])
    suggestion_found = False
    
    for i, sug in enumerate(suggestions):
        if sug["id"] == suggestion_id:
            if sug["status"] != "pending_review":
                raise HTTPException(status_code=400, detail=f"Suggestion is already {sug['status']}")
            
            # Mark as rejected
            suggestions[i]["status"] = "rejected"
            suggestions[i]["admin_action"] = {
                "action_by": admin_user["_id"],
                "action_at": datetime.utcnow(),
                "notes": notes
            }
            suggestion_found = True
            break
    
    if not suggestion_found:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    
    # Update doctor
    await db.doctors.update_one(
        {"_id": ObjectId(doctor_id)},
        {"$set": {"location_suggestions": suggestions}}
    )
    
    logger.info(f"Rejected suggestion {suggestion_id} for doctor {doctor_id}")
    
    return {"message": "Location suggestion rejected"}
