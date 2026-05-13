"""
Communications routes - API endpoints for one-way Admin → MR communication.
"""

from fastapi import APIRouter, Depends, status, Query
from typing import Dict, Optional
from app.api.v1.communications.schemas import (
    CommunicationCreateRequest,
    CommunicationUpdateRequest,
    CommunicationCreateResponse,
    CommunicationDetailResponse,
    CommunicationAdminDetailResponse,
    MessageResponse,
    UnreadCountResponse,
    CommunicationAnalyticsResponse
)
from app.api.v1.communications.service import (
    create_communication,
    get_communications_for_mr,
    get_communication_detail_for_mr,
    get_unread_count,
    get_all_communications_admin,
    get_communication_detail_admin,
    update_communication,
    delete_communication,
    get_communication_analytics
)
from app.core.auth import get_current_user, require_admin


router = APIRouter()


# ============ ADMIN ENDPOINTS ============

@router.post("", response_model=CommunicationCreateResponse, status_code=status.HTTP_201_CREATED, summary="Create Communication")
async def create_communication_endpoint(
    request: CommunicationCreateRequest,
    current_user: Dict = Depends(require_admin)
):
    """
    Create a new communication (Admin only).
    
    **Access:** Admin only
    
    **Purpose:**
    Send targeted one-way communication to MRs. MRs cannot reply.
    
    **Targeting:**
    - No `type` field needed - backend derives from populated arrays
    - Uses OR logic: MR matches if they match ANY condition
    - Empty arrays = target all MRs
    
    **Examples:**
    
    1. **Target specific territory:**
    ```json
    {
      "title": "Hyderabad Meeting Tomorrow",
      "content": "Team meeting at 10 AM...",
      "type": "announcement",
      "priority": "high",
      "targeting": {
        "zones": [],
        "states": [],
        "territories": ["Hyderabad"],
        "specific_mrs": []
      }
    }
    ```
    
    2. **Target entire state:**
    ```json
    {
      "targeting": {
        "zones": [],
        "states": ["Telangana"],
        "territories": [],
        "specific_mrs": []
      }
    }
    ```
    
    3. **Target all MRs:**
    ```json
    {
      "targeting": {
        "zones": [],
        "states": [],
        "territories": [],
        "specific_mrs": []
      }
    }
    ```
    
    4. **Target specific MRs:**
    ```json
    {
      "targeting": {
        "zones": [],
        "states": [],
        "territories": [],
        "specific_mrs": ["mr_id_1", "mr_id_2"]
      }
    }
    ```
    
    **Response:**
    ```json
    {
      "message": "Communication sent successfully",
      "communication_id": "507f1f77bcf86cd799439011",
      "targeted_mrs": 15
    }
    ```
    """
    return await create_communication(
        title=request.title,
        content=request.content,
        comm_type=request.type,
        priority=request.priority,
        targeting=request.targeting.model_dump(),
        attachments=[att.model_dump() for att in request.attachments],
        expires_at=request.expires_at,
        current_user=current_user
    )


@router.get("/admin", summary="List All Communications (Admin)")
async def list_communications_admin(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    type: Optional[str] = Query(None, description="Filter by type"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: Dict = Depends(require_admin)
):
    """
    Get list of all communications (Admin view).
    
    **Access:** Admin only
    
    **Query Parameters:**
    - page: Page number (default 1)
    - limit: Items per page (default 20, max 50)
    - type: Filter by type (announcement, alert, target, training)
    - priority: Filter by priority (low, medium, high, urgent)
    - is_active: Filter by active status (true/false)
    
    **Response:**
    ```json
    {
      "total": 50,
      "page": 1,
      "limit": 20,
      "total_pages": 3,
      "communications": [...]
    }
    ```
    """
    return await get_all_communications_admin(
        page=page,
        limit=limit,
        comm_type=type,
        priority=priority,
        is_active=is_active
    )


@router.get("/{communication_id}/admin", response_model=CommunicationAdminDetailResponse, summary="Get Communication Details (Admin)")
async def get_communication_admin(
    communication_id: str,
    current_user: Dict = Depends(require_admin)
):
    """
    Get full communication details (Admin view).
    
    **Access:** Admin only
    
    **Response:**
    Includes all fields including targeting, attachments, active status, etc.
    """
    return await get_communication_detail_admin(communication_id)


@router.put("/{communication_id}", response_model=MessageResponse, summary="Update Communication")
async def update_communication_endpoint(
    communication_id: str,
    request: CommunicationUpdateRequest,
    current_user: Dict = Depends(require_admin)
):
    """
    Update communication (Admin only).
    
    **Access:** Admin only
    
    **Note:** All fields are optional. Only provided fields will be updated.
    
    **Example:**
    ```json
    {
      "title": "Updated Title",
      "priority": "urgent"
    }
    ```
    """
    update_data = request.model_dump(exclude_unset=True)
    
    # Convert targeting to dict if present
    if "targeting" in update_data and update_data["targeting"]:
        update_data["targeting"] = update_data["targeting"]
    
    return await update_communication(communication_id, update_data, current_user)


@router.delete("/{communication_id}", response_model=MessageResponse, summary="Deactivate Communication")
async def delete_communication_endpoint(
    communication_id: str,
    current_user: Dict = Depends(require_admin)
):
    """
    Deactivate communication (soft delete, Admin only).
    
    **Access:** Admin only
    
    **Note:** This is a soft delete. Communication is marked as inactive but remains in database.
    MRs will no longer see this communication.
    
    **Response:**
    ```json
    {
      "message": "Communication deactivated successfully"
    }
    ```
    """
    return await delete_communication(communication_id, current_user)


@router.get("/{communication_id}/analytics", response_model=CommunicationAnalyticsResponse, summary="Get Communication Analytics")
async def get_analytics_endpoint(
    communication_id: str,
    current_user: Dict = Depends(require_admin)
):
    """
    Get read analytics for a communication (Admin only).
    
    **Access:** Admin only
    
    **Purpose:**
    See who read and who didn't read the communication.
    
    **Response:**
    ```json
    {
      "communication_id": "507f1f77bcf86cd799439011",
      "title": "Hyderabad Meeting Tomorrow",
      "total_targeted": 15,
      "total_read": 12,
      "read_percentage": 80.0,
      "read_by": [
        {
          "mr_id": "mr_123",
          "mr_name": "Rajesh Kumar",
          "territory": "Hyderabad",
          "state": "Telangana",
          "read_at": "2024-03-30T11:00:00"
        }
      ],
      "not_read_by": [
        {
          "mr_id": "mr_456",
          "mr_name": "Priya Sharma",
          "territory": "Hyderabad",
          "state": "Telangana",
          "read_at": null
        }
      ]
    }
    ```
    
    **Use Case:**
    Admin can see "12/15 read (80%)" and identify who hasn't read yet.
    """
    return await get_communication_analytics(communication_id)


# ============ MR ENDPOINTS ============

@router.get("", summary="List Communications (MR)")
async def list_communications_mr(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    type: Optional[str] = Query(None, description="Filter by type"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get list of communications for current MR.
    
    **Access:** MR only
    
    **Auto-filtering:**
    - Only shows communications targeted to this MR
    - Based on MR's zone, state, territory
    - Excludes expired communications
    
    **Sorting:**
    - Priority: urgent → high → medium → low
    - Then by: created_at (newest first)
    
    **Query Parameters:**
    - page: Page number (default 1)
    - limit: Items per page (default 20, max 50)
    - type: Filter by type (announcement, alert, target, training)
    - priority: Filter by priority (low, medium, high, urgent)
    - is_read: Filter by read status (true/false)
    
    **Response:**
    ```json
    {
      "total": 10,
      "page": 1,
      "limit": 20,
      "total_pages": 1,
      "communications": [
        {
          "id": "507f1f77bcf86cd799439011",
          "title": "Hyderabad Meeting Tomorrow",
          "type": "announcement",
          "priority": "high",
          "preview": "Team meeting at 10 AM...",
          "is_read": false,
          "created_at": "2024-03-30T10:00:00",
          "created_by_name": "Admin"
        }
      ]
    }
    ```
    """
    # Block non-MR users
    if current_user.get("role") != "MR":
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only for MRs"
        )
    
    return await get_communications_for_mr(
        current_user=current_user,
        page=page,
        limit=limit,
        comm_type=type,
        priority=priority,
        is_read=is_read
    )


@router.get("/unread/count", response_model=UnreadCountResponse, summary="Get Unread Count")
async def get_unread_count_endpoint(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get count of unread communications for current MR.
    
    **Access:** MR only
    
    **Purpose:**
    Show unread badge count in UI (e.g., "5 unread").
    
    **Response:**
    ```json
    {
      "unread_count": 5
    }
    ```
    """
    # Block non-MR users
    if current_user.get("role") != "MR":
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only for MRs"
        )
    
    return await get_unread_count(current_user)


@router.get("/{communication_id}", response_model=CommunicationDetailResponse, summary="Get Communication Details (MR)")
async def get_communication_mr(
    communication_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get full communication details for MR.
    
    **Access:** MR only
    
    **Auto-marking as read:**
    - If MR hasn't read this communication, it will be marked as read automatically
    - Read timestamp is recorded for analytics
    
    **Access control:**
    - MR can only access communications targeted to them
    - Returns 403 if communication is not targeted to this MR
    
    **Response:**
    ```json
    {
      "id": "507f1f77bcf86cd799439011",
      "title": "Hyderabad Meeting Tomorrow",
      "content": "Full content here...",
      "type": "announcement",
      "priority": "high",
      "targeting": {...},
      "attachments": [...],
      "expires_at": "2024-12-31T23:59:59",
      "created_at": "2024-03-30T10:00:00",
      "created_by_name": "Admin",
      "is_read": true
    }
    ```
    """
    # Block non-MR users
    if current_user.get("role") != "MR":
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only for MRs"
        )
    
    return await get_communication_detail_for_mr(communication_id, current_user)
