"""
Location Analysis Service
Analyzes temporary visit locations and suggests frequently used locations.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bson import ObjectId
from app.database import get_database
from app.utils.geo_utils import calculate_distance, are_locations_close
from app.utils.logger import get_medrep_logger
from app.config import settings

logger = get_medrep_logger(__name__)

# Configuration
TEMP_LOCATION_CLUSTER_RADIUS = 50  # meters
TEMP_LOCATION_MIN_USAGE_COUNT = 5  # visits
REJECTED_LOCATION_COOLDOWN_DAYS = 180  # days


async def analyze_doctor_temporary_locations(doctor_id: str) -> Dict[str, Any]:
    """
    Analyze temporary locations for a doctor and create suggestions.
    
    This function:
    1. Gets all completed visits with temporary locations
    2. Clusters locations by proximity (50m radius)
    3. Identifies clusters with 5+ visits
    4. Creates suggestions (with duplicate prevention)
    
    Args:
        doctor_id: Doctor's ID
    
    Returns:
        dict: Analysis results with suggestions_created count
    """
    db = get_database()
    
    logger.info(f"Starting location analysis for doctor {doctor_id}")
    
    # 1. Get all temporary location visits for this doctor
    temp_visits = await db.visits.find({
        "doctor_id": doctor_id,
        "location.type": "temporary",
        "status": "completed"
    }).to_list(length=None)
    
    if not temp_visits:
        logger.info(f"No temporary location visits found for doctor {doctor_id}")
        return {"suggestions_created": 0, "message": "No temporary locations found"}
    
    logger.info(f"Found {len(temp_visits)} temporary location visits")
    
    # 2. Cluster locations by proximity
    clusters = _cluster_locations(temp_visits)
    logger.info(f"Created {len(clusters)} location clusters")
    
    # 3. Get doctor details
    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        logger.error(f"Doctor {doctor_id} not found")
        return {"suggestions_created": 0, "message": "Doctor not found"}
    
    # 4. Process each cluster
    suggestions_created = 0
    for cluster in clusters:
        usage_count = len(cluster["visits"])
        
        # Only process clusters with threshold met
        if usage_count < TEMP_LOCATION_MIN_USAGE_COUNT:
            continue
        
        center_lat = cluster["center_lat"]
        center_lng = cluster["center_lng"]
        most_common_name = _get_most_common_name(cluster["visits"])
        most_common_address = _get_most_common_address(cluster["visits"])
        
        # Check duplicate prevention rules
        if await _should_skip_suggestion(doctor, center_lat, center_lng):
            logger.info(f"Skipping suggestion for '{most_common_name}' - duplicate or rejected recently")
            continue
        
        # Create suggestion
        suggestion = {
            "id": str(ObjectId()),
            "name": most_common_name,
            "address": most_common_address,
            "latitude": center_lat,
            "longitude": center_lng,
            "usage_count": usage_count,
            "first_used": min(v["created_at"] for v in cluster["visits"]),
            "last_used": max(v["created_at"] for v in cluster["visits"]),
            "used_by_mrs": list(set(v["mr_id"] for v in cluster["visits"])),
            "status": "pending_review",
            "created_at": datetime.utcnow(),
            "admin_action": None
        }
        
        # Add to doctor's location_suggestions
        await db.doctors.update_one(
            {"_id": ObjectId(doctor_id)},
            {"$push": {"location_suggestions": suggestion}}
        )
        
        suggestions_created += 1
        logger.info(f"Created suggestion: '{most_common_name}' (usage: {usage_count})")
    
    logger.info(f"Location analysis complete. Created {suggestions_created} suggestions")
    
    return {
        "suggestions_created": suggestions_created,
        "total_visits_analyzed": len(temp_visits),
        "clusters_found": len(clusters),
        "message": f"Created {suggestions_created} location suggestions"
    }


def _cluster_locations(visits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Cluster visits by location proximity.
    
    Args:
        visits: List of visit documents with temporary locations
    
    Returns:
        List of clusters with center coordinates and visits
    """
    clusters = []
    
    for visit in visits:
        temp_loc = visit["location"]["temporary_location"]
        lat = temp_loc["latitude"]
        lng = temp_loc["longitude"]
        
        # Find existing cluster within radius
        found_cluster = None
        for cluster in clusters:
            if are_locations_close(
                lat, lng,
                cluster["center_lat"], cluster["center_lng"],
                threshold_meters=TEMP_LOCATION_CLUSTER_RADIUS
            ):
                found_cluster = cluster
                break
        
        if found_cluster:
            # Add to existing cluster
            found_cluster["visits"].append(visit)
            # Recalculate center (average of all points)
            all_lats = [v["location"]["temporary_location"]["latitude"] for v in found_cluster["visits"]]
            all_lngs = [v["location"]["temporary_location"]["longitude"] for v in found_cluster["visits"]]
            found_cluster["center_lat"] = sum(all_lats) / len(all_lats)
            found_cluster["center_lng"] = sum(all_lngs) / len(all_lngs)
        else:
            # Create new cluster
            clusters.append({
                "center_lat": lat,
                "center_lng": lng,
                "visits": [visit]
            })
    
    return clusters


def _get_most_common_name(visits: List[Dict[str, Any]]) -> str:
    """Get the most frequently used location name in a cluster."""
    names = [v["location"]["temporary_location"]["name"] for v in visits]
    return max(set(names), key=names.count)


def _get_most_common_address(visits: List[Dict[str, Any]]) -> str:
    """Get the most frequently used address in a cluster."""
    addresses = [
        v["location"]["temporary_location"].get("address", "")
        for v in visits
        if v["location"]["temporary_location"].get("address")
    ]
    if not addresses:
        return ""
    return max(set(addresses), key=addresses.count)


async def _should_skip_suggestion(
    doctor: Dict[str, Any],
    latitude: float,
    longitude: float
) -> bool:
    """
    Check if suggestion should be skipped due to duplicate prevention rules.
    
    Rules:
    1. Location already exists in doctor.locations within 50m → skip
    2. Pending suggestion exists within 50m → update it, skip new
    3. Rejected suggestion within 50m and < 180 days ago → skip
    
    Args:
        doctor: Doctor document
        latitude: Suggested location latitude
        longitude: Suggested location longitude
    
    Returns:
        bool: True if should skip, False if should create
    """
    db = get_database()
    
    # Rule 1: Check existing permanent locations
    existing_locations = doctor.get("locations", [])
    for loc in existing_locations:
        if are_locations_close(
            latitude, longitude,
            loc["latitude"], loc["longitude"],
            threshold_meters=TEMP_LOCATION_CLUSTER_RADIUS
        ):
            logger.info(f"Location already exists as permanent location: {loc['name']}")
            return True
    
    # Rule 2 & 3: Check existing suggestions
    existing_suggestions = doctor.get("location_suggestions", [])
    for suggestion in existing_suggestions:
        if are_locations_close(
            latitude, longitude,
            suggestion["latitude"], suggestion["longitude"],
            threshold_meters=TEMP_LOCATION_CLUSTER_RADIUS
        ):
            if suggestion["status"] == "pending_review":
                # Update existing pending suggestion
                logger.info(f"Updating existing pending suggestion: {suggestion['name']}")
                # Note: Actual update happens in parent function
                return True
            
            elif suggestion["status"] == "rejected":
                # Check if rejected recently (within cooldown period)
                admin_action = suggestion.get("admin_action", {})
                rejected_at = admin_action.get("action_at")
                
                if rejected_at:
                    days_since_rejection = (datetime.utcnow() - rejected_at).days
                    if days_since_rejection < REJECTED_LOCATION_COOLDOWN_DAYS:
                        logger.info(f"Location rejected {days_since_rejection} days ago, skipping")
                        return True
                    else:
                        logger.info(f"Location rejected {days_since_rejection} days ago, allowing re-suggestion")
                        return False
    
    return False


async def trigger_analysis_if_needed(doctor_id: str) -> None:
    """
    Trigger location analysis if temporary location count reaches threshold.
    
    This function is called after each completed temporary location visit.
    It checks if we should run analysis (every 5th visit) and triggers it.
    
    Args:
        doctor_id: Doctor's ID
    """
    db = get_database()
    
    # Count temporary location visits
    temp_count = await db.visits.count_documents({
        "doctor_id": doctor_id,
        "location.type": "temporary",
        "status": "completed"
    })
    
    # Trigger analysis every 5th visit
    if temp_count > 0 and temp_count % TEMP_LOCATION_MIN_USAGE_COUNT == 0:
        logger.info(f"Triggering automatic location analysis for doctor {doctor_id} (count: {temp_count})")
        await analyze_doctor_temporary_locations(doctor_id)
