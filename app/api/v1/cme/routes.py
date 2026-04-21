"""
CME Event Management Endpoints
"""

from fastapi import APIRouter, Depends, Query, status
from typing import Optional, Dict, Any
from app.core.auth import require_admin, get_current_user
from app.api.v1.cme.schemas import (
    CMEEventCreate, CMEEventUpdate, CMEEventResponse, CMEEventListResponse
)
from app.api.v1.cme import service


router = APIRouter()


# ============ ADMIN ENDPOINTS (Create, Update, Delete) ============

@router.post("", response_model=CMEEventResponse, status_code=status.HTTP_201_CREATED)
async def create_cme_event_endpoint(event_data: CMEEventCreate, current_user: Dict = Depends(require_admin)):
    """
    Create a new CME (Continuing Medical Education) event.
    
    **Access:** Admin only
    
    **Purpose:** 
    Admin creates educational events for doctors to attend and earn CME credits.
    
    **Flow:**
    1. Admin provides event details (title, date, time, location, speaker)
    2. Admin sets initial status (default: "upcoming")
    3. Event is stored in database with event_recording = null
    4. Doctors can view the event
    5. Admin must manually update status to "completed", "cancelled", or "rescheduled"
    6. Recording can ONLY be added later via UPDATE endpoint after marking as "completed"
    
    **Usage - Online Event (Zoom):**
    ```
    POST /api/v1/cme
    Headers: Authorization: Bearer <admin_token>
    {
        "title": "Hypertension Management Webinar",
        "description": "Learn latest guidelines for hypertension management",
        "event_date": "2024-05-15",
        "event_time": "10:00 AM - 12:00 PM",
        "event_type": "Webinar",
        "max_attendees": 500,
        "event_mode": "online",
        "platform": "Zoom",
        "meeting_link": "https://zoom.us/j/123456789",
        "speaker": "Dr. John Smith, MD",
        "status": "upcoming"
    }
    ```
    
    **Usage - Online Event (Other Platform):**
    ```
    POST /api/v1/cme
    Headers: Authorization: Bearer <admin_token>
    {
        "title": "Cardiology Conference",
        "description": "Annual cardiology conference",
        "event_date": "2024-06-10",
        "event_time": "9:00 AM - 5:00 PM",
        "event_type": "Conference",
        "max_attendees": 1000,
        "event_mode": "online",
        "platform": "Other",
        "platform_name": "Cisco Webex",
        "meeting_link": "https://webex.com/meet/conference123",
        "speaker": "Dr. Sarah Johnson, MD",
        "status": "upcoming"
    }
    ```
    
    **Usage - Offline Event:**
    ```
    POST /api/v1/cme
    Headers: Authorization: Bearer <admin_token>
    {
        "title": "Diabetes Care Workshop",
        "description": "Hands-on workshop for diabetes management",
        "event_date": "2024-05-20",
        "event_time": "2:00 PM - 5:00 PM",
        "event_type": "Workshop",
        "max_attendees": 50,
        "event_mode": "offline",
        "venue_name": "Grand Hotel Mumbai",
        "address": "123 Marine Drive, Mumbai, Maharashtra 400001",
        "speaker": "Dr. Priya Sharma, MD",
        "status": "upcoming"
    }
    ```
    
    **Event Mode Fields:**
    - event_mode: "online" or "offline" (required)
    
    **Online Mode (event_mode = "online") requires:**
    - platform: "Zoom", "Teams", "Google Meet", or "Other" (required)
    - platform_name: Custom platform name (required only if platform = "Other")
    - meeting_link: Meeting URL (required)
    
    **Offline Mode (event_mode = "offline") requires:**
    - venue_name: Name of the venue (required)
    - address: Full address of the venue (required)
    
    **Note:** event_recording field is NOT accepted during creation. It must be added later via UPDATE.
    
    **Response - Online Event:**
    ```
    {
        "_id": "event123abc",
        "title": "Hypertension Management Webinar",
        "description": "Learn latest guidelines for hypertension management",
        "event_date": "2024-05-15T00:00:00",
        "event_time": "10:00 AM - 12:00 PM",
        "event_type": "Webinar",
        "max_attendees": 500,
        "event_mode": "online",
        "platform": "Zoom",
        "platform_name": null,
        "meeting_link": "https://zoom.us/j/123456789",
        "venue_name": null,
        "address": null,
        "speaker": "Dr. John Smith, MD",
        "status": "upcoming",
        "event_recording": null,
        "created_at": "2024-04-27T10:00:00",
        "updated_at": "2024-04-27T10:00:00"
    }
    ```
    
    **Response - Offline Event:**
    ```
    {
        "_id": "event456def",
        "title": "Diabetes Care Workshop",
        "description": "Hands-on workshop for diabetes management",
        "event_date": "2024-05-20T00:00:00",
        "event_time": "2:00 PM - 5:00 PM",
        "event_type": "Workshop",
        "max_attendees": 50,
        "event_mode": "offline",
        "platform": null,
        "platform_name": null,
        "meeting_link": null,
        "venue_name": "Grand Hotel Mumbai",
        "address": "123 Marine Drive, Mumbai, Maharashtra 400001",
        "speaker": "Dr. Priya Sharma, MD",
        "status": "upcoming",
        "event_recording": null,
        "created_at": "2024-04-27T10:00:00",
        "updated_at": "2024-04-27T10:00:00"
    }
    ```
    
    **Status Logic:**
    - Default: "upcoming"
    - Admin must manually change to: "completed", "cancelled", "rescheduled"
    - No auto-calculation based on date
    
    **Recording Logic:**
    - event_recording is always null on creation
    - Can only be added via PUT /api/v1/cme/{id} after status is "completed"
    """
    return await service.create_cme_event(event_data, current_user)


@router.put("/{event_id}", response_model=CMEEventResponse)
async def update_cme_event_endpoint(event_id: str, event_data: CMEEventUpdate, current_user: Dict = Depends(require_admin)):
    """
    Update a CME event.
    
    **Access:** Admin only
    
    **Purpose:**
    Admin can update event details, cancel events, reschedule events, or add recordings after completion.
    
    **Flow:**
    1. Admin provides event_id and fields to update
    2. Backend validates the update
    3. If status is being set to "completed", event_recording can be added
    4. Event is updated in database
    5. Admin must manually update status - no auto-calculation
    
    **Usage - Update event details:**
    ```
    PUT /api/v1/cme/event123abc
    Headers: Authorization: Bearer <admin_token>
    {
        "title": "Updated Title",
        "event_date": "2024-05-20"
    }
    ```
    
    **Usage - Change online event to offline:**
    ```
    PUT /api/v1/cme/event123abc
    {
        "event_mode": "offline",
        "venue_name": "Grand Hotel Mumbai",
        "address": "123 Marine Drive, Mumbai, Maharashtra 400001"
    }
    ```
    
    **Usage - Update meeting link for online event:**
    ```
    PUT /api/v1/cme/event123abc
    {
        "meeting_link": "https://zoom.us/j/987654321"
    }
    ```
    
    **Usage - Cancel event:**
    ```
    PUT /api/v1/cme/event123abc
    {
        "status": "cancelled"
    }
    ```
    
    **Usage - Add recording after event completion:**
    ```
    PUT /api/v1/cme/event123abc
    {
        "status": "completed",
        "event_recording": "https://zoom.us/rec/play/xyz123"
    }
    ```
    
    **Response - Online Event:**
    ```
    {
        "_id": "event123abc",
        "title": "Updated Title",
        "description": "Learn latest guidelines",
        "event_date": "2024-05-20T00:00:00",
        "event_time": "10:00 AM - 12:00 PM",
        "event_type": "Webinar",
        "max_attendees": 500,
        "event_mode": "online",
        "platform": "Zoom",
        "platform_name": null,
        "meeting_link": "https://zoom.us/j/987654321",
        "venue_name": null,
        "address": null,
        "speaker": "Dr. John Smith, MD",
        "status": "upcoming",
        "event_recording": null,
        "created_at": "2024-04-27T10:00:00",
        "updated_at": "2024-04-27T11:00:00"
    }
    ```
    
    **Response - Offline Event:**
    ```
    {
        "_id": "event456def",
        "title": "Diabetes Care Workshop",
        "description": "Hands-on workshop",
        "event_date": "2024-05-20T00:00:00",
        "event_time": "2:00 PM - 5:00 PM",
        "event_type": "Workshop",
        "max_attendees": 50,
        "event_mode": "offline",
        "platform": null,
        "platform_name": null,
        "meeting_link": null,
        "venue_name": "Grand Hotel Mumbai",
        "address": "123 Marine Drive, Mumbai, Maharashtra 400001",
        "speaker": "Dr. Priya Sharma, MD",
        "status": "upcoming",
        "event_recording": null,
        "created_at": "2024-04-27T10:00:00",
        "updated_at": "2024-04-27T11:00:00"
    }
    ```
    
    **Important Rules:**
    - event_recording can ONLY be added when status is "completed"
    - Status must be manually updated by admin
    - No auto-calculation based on date
    """
    return await service.update_cme_event(event_id, event_data, current_user)


# ============ DOCTOR ENDPOINTS (View Only) ============

@router.get("", response_model=CMEEventListResponse)
async def get_cme_events_endpoint(
    current_user: Dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by status: upcoming, completed, cancelled, rescheduled"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Get all CME events with optional filters.
    
    **Access:** Doctors and Admin
    
    **Purpose:**
    Doctors view available CME events to attend. Admin views all events to manage them.
    
    **Flow:**
    1. User (Doctor/Admin) requests event list
    2. Backend checks user role (must be DOCTOR or ADMIN)
    3. Backend fetches events from database with filters
    4. Returns list of events with their current status (as set by admin)
    
    **Usage - Get all upcoming events:**
    ```
    GET /api/v1/cme?status=upcoming
    Headers: Authorization: Bearer <doctor_or_admin_token>
    ```
    
    **Usage - Get webinars only:**
    ```
    GET /api/v1/cme?event_type=Webinar
    ```
    
    **Usage - Get completed events with pagination:**
    ```
    GET /api/v1/cme?status=completed&skip=0&limit=10
    ```
    
    **Response:**
    ```
    {
        "events": [
            {
                "_id": "event123abc",
                "title": "Hypertension Management Webinar",
                "description": "Learn latest guidelines",
                "event_date": "2024-05-15T00:00:00",
                "event_time": "10:00 AM - 12:00 PM",
                "event_type": "Webinar",
                "max_attendees": 500,
                "event_mode": "online",
                "platform": "Zoom",
                "platform_name": null,
                "meeting_link": "https://zoom.us/j/123456789",
                "venue_name": null,
                "address": null,
                "speaker": "Dr. John Smith, MD",
                "status": "upcoming",
                "event_recording": null,
                "created_at": "2024-04-27T10:00:00",
                "updated_at": "2024-04-27T10:00:00"
            },
            {
                "_id": "event456def",
                "title": "Diabetes Care Workshop",
                "description": "Hands-on workshop",
                "event_date": "2024-04-20T00:00:00",
                "event_time": "2:00 PM - 5:00 PM",
                "event_type": "Workshop",
                "max_attendees": 50,
                "event_mode": "offline",
                "platform": null,
                "platform_name": null,
                "meeting_link": null,
                "venue_name": "Grand Hotel Mumbai",
                "address": "123 Marine Drive, Mumbai, Maharashtra 400001",
                "speaker": "Dr. Sarah Sharma",
                "status": "completed",
                "event_recording": "https://zoom.us/rec/xyz",
                "created_at": "2024-04-10T10:00:00",
                "updated_at": "2024-04-21T10:00:00"
            }
        ],
        "total": 2
    }
    ```
    
    **Filters:**
    - status: upcoming, completed, cancelled, rescheduled
    - event_type: Webinar, Conference, Workshop, Seminar
    - skip: Pagination offset (default: 0)
    - limit: Results per page (default: 100, max: 1000)
    
    **Note:** Status is manually set by admin, not auto-calculated
    """
    # Check if user is a doctor or admin
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "ADMIN"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Only doctors and admin can view CME events")
    
    return await service.get_all_cme_events(status, event_type, skip, limit)


@router.get("/{event_id}", response_model=CMEEventResponse)
async def get_cme_event_endpoint(
    event_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get detailed information about a specific CME event.
    
    **Access:** Doctors and Admin
    
    **Purpose:**
    View complete details of a single CME event including recording link if available.
    
    **Flow:**
    1. User (Doctor/Admin) requests specific event by ID
    2. Backend checks user role (must be DOCTOR or ADMIN)
    3. Backend fetches event from database
    4. Returns event details with status as set by admin
    
    **Usage:**
    ```
    GET /api/v1/cme/event123abc
    Headers: Authorization: Bearer <doctor_or_admin_token>
    ```
    
    **Response - Online Event:**
    ```
    {
        "_id": "event123abc",
        "title": "Hypertension Management Webinar",
        "description": "Learn latest guidelines for hypertension management including new medications and treatment protocols",
        "event_date": "2024-05-15T00:00:00",
        "event_time": "10:00 AM - 12:00 PM",
        "event_type": "Webinar",
        "max_attendees": 500,
        "event_mode": "online",
        "platform": "Zoom",
        "platform_name": null,
        "meeting_link": "https://zoom.us/j/123456789",
        "venue_name": null,
        "address": null,
        "speaker": "Dr. John Smith, MD - Cardiologist with 20 years experience",
        "status": "upcoming",
        "event_recording": null,
        "created_at": "2024-04-27T10:00:00",
        "updated_at": "2024-04-27T10:00:00"
    }
    ```
    
    **Response - Offline Event (Completed with recording):**
    ```
    {
        "_id": "event456def",
        "title": "Diabetes Care Workshop",
        "description": "Hands-on workshop for diabetes management",
        "event_date": "2024-04-20T00:00:00",
        "event_time": "2:00 PM - 5:00 PM",
        "event_type": "Workshop",
        "max_attendees": 50,
        "event_mode": "offline",
        "platform": null,
        "platform_name": null,
        "meeting_link": null,
        "venue_name": "Grand Hotel Mumbai",
        "address": "123 Marine Drive, Mumbai, Maharashtra 400001",
        "speaker": "Dr. Sarah Sharma",
        "status": "completed",
        "event_recording": "https://zoom.us/rec/play/xyz123",
        "created_at": "2024-04-10T10:00:00",
        "updated_at": "2024-04-21T10:00:00"
    }
    ```
    
    **Use Cases:**
    - Doctor wants to see full event details before registering
    - Doctor wants to watch recording of completed event
    - Admin wants to review event details
    """
    # Check if user is a doctor or admin
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "ADMIN"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Only doctors and admin can view CME events")
    
    return await service.get_cme_event_by_id(event_id)
