"""
Geofencing and Location Services for Visits
"""
from datetime import datetime
from typing import Dict, Any, Optional
from bson import ObjectId
from fastapi import HTTPException, status, UploadFile
from app.database import get_database
from app.utils.geo_utils import calculate_distance
from app.utils.logger import get_medrep_logger
from app.config import settings
from app.services.cloudinary_service import upload_checkin_photo

logger = get_medrep_logger(__name__)


async def resolve_visit_location(visit: Dict[str, Any], db) -> Dict[str, Any]:
    """
    Resolve visit location coordinates (permanent or temporary).
    
    Args:
        visit: Visit document
        db: Database connection
    
    Returns:
        dict: {latitude, longitude, name, type}
    
    Raises:
        HTTPException: If location cannot be resolved
    """
    location = visit.get("location")
    
    # Handle old format (backward compatibility)
    if isinstance(location, str):
        raise HTTPException(
            status_code=400,
            detail="Visit location format is old. Please reschedule this visit with proper location."
        )
    
    # Handle new format
    location_type = location.get("type")
    
    if location_type == "permanent":
        # Get doctor's location
        doctor_id = visit.get("doctor_id")
        doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
        
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        
        location_id = location.get("location_id")
        doctor_locations = doctor.get("locations", [])
        
        # Find the location
        doctor_location = None
        for loc in doctor_locations:
            if loc["id"] == location_id:
                doctor_location = loc
                break
        
        if not doctor_location:
            raise HTTPException(
                status_code=404,
                detail="Doctor location not found. Location may have been deleted."
            )
        
        if not doctor_location.get("is_active"):
            raise HTTPException(
                status_code=400,
                detail="Doctor location is inactive. Cannot check in."
            )
        
        return {
            "latitude": doctor_location["latitude"],
            "longitude": doctor_location["longitude"],
            "name": doctor_location["name"],
            "type": "permanent",
            "geofence_radius": doctor_location.get("geofence_radius", settings.GEOFENCE_RADIUS)
        }
    
    elif location_type == "temporary":
        # Get temporary location from visit
        temp_location = location.get("temporary_location")
        
        if not temp_location:
            raise HTTPException(
                status_code=400,
                detail="Temporary location data missing"
            )
        
        return {
            "latitude": temp_location["latitude"],
            "longitude": temp_location["longitude"],
            "name": temp_location["name"],
            "type": "temporary",
            "geofence_radius": settings.GEOFENCE_RADIUS
        }
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid location type: {location_type}"
        )


async def validate_geofence(
    mr_latitude: float,
    mr_longitude: float,
    location_latitude: float,
    location_longitude: float,
    geofence_radius: int
) -> Dict[str, Any]:
    """
    Validate if MR is within geofence radius.
    
    Args:
        mr_latitude: MR's current latitude
        mr_longitude: MR's current longitude
        location_latitude: Location's latitude
        location_longitude: Location's longitude
        geofence_radius: Geofence radius in meters
    
    Returns:
        dict: {
            status: "inside" | "outside",
            distance_meters: float,
            photo_required: bool
        }
    """
    distance = calculate_distance(
        mr_latitude, mr_longitude,
        location_latitude, location_longitude
    )
    
    is_inside = distance <= geofence_radius
    
    return {
        "status": "inside" if is_inside else "outside",
        "distance_meters": round(distance, 2),
        "photo_required": not is_inside  # Photo required if outside
    }


async def handle_checkin_photo(
    photo: Optional[UploadFile],
    visit_id: str,
    photo_required: bool
) -> Optional[str]:
    """
    Handle check-in photo upload.
    
    Args:
        photo: Uploaded photo file (optional)
        visit_id: Visit ID
        photo_required: Whether photo is required
    
    Returns:
        str: Photo URL if uploaded, None otherwise
    
    Raises:
        HTTPException: If photo required but not provided
    """
    if photo_required and not photo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Photo is required for check-in (outside geofence or temporary location)"
        )
    
    if photo and photo.filename:
        # Upload photo to Cloudinary
        upload_result = await upload_checkin_photo(photo, visit_id)
        return upload_result["file_url"]
    
    return None


async def check_in_with_geofence(
    visit_id: str,
    latitude: float,
    longitude: float,
    photo: Optional[UploadFile],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Check in to visit with geofence validation and photo upload.
    
    This is the main check-in function that:
    1. Validates visit exists and belongs to MR
    2. Resolves location (permanent or temporary)
    3. Validates geofence
    4. Requires photo if outside geofence or temporary location
    5. Uploads photo to Cloudinary
    6. Saves check-in data
    
    Args:
        visit_id: Visit ID
        latitude: MR's current latitude
        longitude: MR's current longitude
        photo: Check-in photo (required if outside geofence)
        current_user: Current authenticated MR
    
    Returns:
        dict: Check-in result with geofence status
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    user_id = current_user.get("_id")
    
    # Validate visit
    if not ObjectId.is_valid(visit_id):
        raise HTTPException(status_code=400, detail="Invalid visit ID")
    
    visit = await db.visits.find_one({"_id": ObjectId(visit_id)})
    
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    
    if visit["mr_id"] != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only check in to your own visits"
        )
    
    if visit["status"] != "scheduled":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot check in to {visit['status']} visit"
        )
    
    # Check active visit rule
    existing_checkin = await db.visits.find_one({
        "mr_id": user_id,
        "status": "checked_in"
    })
    
    if existing_checkin:
        raise HTTPException(
            status_code=400,
            detail="Check out of your current visit first"
        )
    
    # Check pending reports rule
    pending_count = await db.visits.count_documents({
        "mr_id": user_id,
        "status": "checked_out"
    })
    
    if pending_count >= 2:
        raise HTTPException(
            status_code=400,
            detail="Submit pending reports before checking in (max 2 allowed)"
        )
    
    # Resolve visit location
    location_info = await resolve_visit_location(visit, db)
    
    # Validate geofence
    geofence_result = await validate_geofence(
        latitude, longitude,
        location_info["latitude"], location_info["longitude"],
        location_info["geofence_radius"]
    )
    
    # For temporary locations, always require photo
    if location_info["type"] == "temporary":
        geofence_result["photo_required"] = True
    
    # Handle photo upload
    photo_url = await handle_checkin_photo(
        photo, visit_id, geofence_result["photo_required"]
    )
    
    # Save check-in
    check_in_time = datetime.utcnow()
    
    check_in_data = {
        "timestamp": check_in_time,
        "latitude": latitude,
        "longitude": longitude,
        "geofence_status": geofence_result["status"],
        "distance_from_location": geofence_result["distance_meters"]
    }
    
    if photo_url:
        check_in_data["photo_url"] = photo_url
        check_in_data["photo_captured_at"] = check_in_time
    
    await db.visits.update_one(
        {"_id": ObjectId(visit_id)},
        {
            "$set": {
                "status": "checked_in",
                "check_in": check_in_data,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    logger.info(
        f"Check-in: visit={visit_id}, geofence={geofence_result['status']}, "
        f"distance={geofence_result['distance_meters']}m, photo={'yes' if photo_url else 'no'}"
    )
    
    return {
        "message": "Checked in successfully",
        "visit_id": visit_id,
        "check_in_time": check_in_time,
        "geofence_status": geofence_result["status"],
        "distance_meters": geofence_result["distance_meters"],
        "photo_uploaded": bool(photo_url)
    }
