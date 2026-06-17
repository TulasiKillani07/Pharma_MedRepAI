"""
Geolocation utilities for distance calculation and geocoding.
"""
import httpx
from math import radians, sin, cos, sqrt, atan2
from typing import Dict, List, Optional, Any
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate distance between two GPS coordinates using Haversine formula.
    
    Args:
        lat1: Latitude of first point
        lng1: Longitude of first point
        lat2: Latitude of second point
        lng2: Longitude of second point
    
    Returns:
        float: Distance in meters
    
    Example:
        >>> calculate_distance(17.4401, 78.3489, 17.4435, 78.3772)
        3156.42  # meters
    """
    R = 6371000  # Earth radius in meters
    
    # Convert to radians
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lng = radians(lng2 - lng1)
    
    # Haversine formula
    a = sin(delta_lat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lng/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c
    
    return round(distance, 2)


def are_locations_close(
    lat1: float, 
    lng1: float, 
    lat2: float, 
    lng2: float, 
    threshold_meters: int = 50
) -> bool:
    """
    Check if two locations are within threshold distance.
    
    Args:
        lat1: Latitude of first point
        lng1: Longitude of first point
        lat2: Latitude of second point
        lng2: Longitude of second point
        threshold_meters: Maximum distance in meters (default: 50)
    
    Returns:
        bool: True if within threshold, False otherwise
    
    Example:
        >>> are_locations_close(17.4401, 78.3489, 17.4402, 78.3490, threshold_meters=100)
        True
    """
    distance = calculate_distance(lat1, lng1, lat2, lng2)
    return distance <= threshold_meters


async def geocode_search(
    query: str, 
    limit: int = 5,
    user_latitude: Optional[float] = None,
    user_longitude: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Search for locations using Nominatim geocoding API.
    
    Args:
        query: Search query (e.g., "Apollo Hospital Hyderabad")
        limit: Maximum number of results (default: 5)
        user_latitude: Optional user's current latitude for location bias
        user_longitude: Optional user's current longitude for location bias
    
    Returns:
        List of location results with lat, lng, display_name, address
    
    Example:
        >>> results = await geocode_search("Apollo Hospital", user_latitude=17.4, user_longitude=78.4)
        >>> results[0]
        {
            "display_name": "Apollo Hospital, Road 45, Jubilee Hills, Hyderabad",
            "latitude": 17.4401,
            "longitude": 78.3489,
            "address": {
                "road": "Road 45",
                "suburb": "Jubilee Hills",
                "city": "Hyderabad",
                "state": "Telangana",
                "country": "India"
            }
        }
    """
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": limit,
            "addressdetails": 1
        }
        
        # Add location bias if provided (prioritizes results near user)
        if user_latitude is not None and user_longitude is not None:
            params["viewbox"] = f"{user_longitude-0.5},{user_latitude-0.5},{user_longitude+0.5},{user_latitude+0.5}"
            params["bounded"] = "0"  # Don't restrict, just prioritize
        
        headers = {
            "User-Agent": "MedRepAI/1.0"  # Required by Nominatim
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            results = response.json()
        
        # Transform results
        locations = []
        for result in results:
            locations.append({
                "display_name": result.get("display_name", ""),
                "latitude": float(result.get("lat", 0)),
                "longitude": float(result.get("lon", 0)),
                "address": result.get("address", {}),
                "type": result.get("type", ""),
                "importance": result.get("importance", 0)
            })
        
        logger.info(f"Geocode search for '{query}' returned {len(locations)} results")
        return locations
    
    except httpx.HTTPError as e:
        logger.error(f"Geocoding HTTP error: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Geocoding error: {str(e)}")
        return []


async def reverse_geocode(latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
    """
    Reverse geocode: Get address from GPS coordinates.
    
    Args:
        latitude: Latitude
        longitude: Longitude
    
    Returns:
        Location details with display_name and address, or None if failed
    
    Example:
        >>> location = await reverse_geocode(17.4401, 78.3489)
        >>> location["display_name"]
        "Road 45, Jubilee Hills, Hyderabad, Telangana, India"
    """
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "addressdetails": 1
        }
        headers = {
            "User-Agent": "MedRepAI/1.0"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()
        
        if "error" in result:
            logger.warning(f"Reverse geocode error: {result['error']}")
            return None
        
        location = {
            "display_name": result.get("display_name", ""),
            "latitude": float(result.get("lat", latitude)),
            "longitude": float(result.get("lon", longitude)),
            "address": result.get("address", {})
        }
        
        logger.info(f"Reverse geocode for ({latitude}, {longitude}) successful")
        return location
    
    except httpx.HTTPError as e:
        logger.error(f"Reverse geocoding HTTP error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Reverse geocoding error: {str(e)}")
        return None
