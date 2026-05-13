"""
Communications routes - API endpoints for one-way Admin → MR communication.
"""

from fastapi import APIRouter, Depends, status, Query, UploadFile, File, HTTPException, Form
from typing import Dict, Optional, List
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
    get_communication_analytics,
    create_communication_with_files
)
from app.core.auth import get_current_user, require_admin


router = APIRouter()


# ============ ADMIN ENDPOINTS ============

@router.post("", response_model=CommunicationCreateResponse, status_code=status.HTTP_201_CREATED, summary="Create Communication")
async def create_communication_endpoint(
    title: str = Form(..., description="Communication title"),
    content: str = Form(..., description="Communication content"),
    type: str = Form(..., description="Communication type: announcement, alert, target, training"),
    priority: str = Form(..., description="Priority: low, medium, high, urgent"),
    targeting: str = Form(..., description="Targeting criteria as JSON string"),
    link: Optional[str] = Form(None, description="Optional external link (URL)"),
    expires_at: Optional[str] = Form(None, description="Expiry date in ISO format (optional)"),
    files: List[UploadFile] = File(default=[], description="Attachment files (optional, max 5 files)"),
    current_user: Dict = Depends(require_admin)
):
    """
    Create a new communication with optional file attachments (Admin only).
    
    **Access:** Admin only
    
    **Purpose:**
    Send targeted one-way communication to MRs with optional file attachments.
    Files are automatically uploaded to Cloudinary.
    
    **Request Format:** multipart/form-data
    
    **Form Fields:**
    - title: Communication title (required)
    - content: Communication content (required)
    - type: Communication type (required) - announcement, alert, target, training
    - priority: Priority level (required) - low, medium, high, urgent
    - targeting: Targeting criteria as JSON string (required)
    - expires_at: Expiry date in ISO format (optional)
    - files: Attachment files (optional, max 5 files, 10MB each)
    
    **Targeting JSON Format:**
    ```json
    {
      "zones": ["South"],
      "states": ["Telangana"],
      "territories": ["Hyderabad"],
      "specific_mrs": []
    }
    ```
    
    **Supported File Types:**
    - Documents: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, TXT
    - Images: JPG, PNG, GIF, WEBP, SVG
    - Archives: ZIP, RAR
    - Max 5 files, 10MB each
    
    **Example (Swagger UI):**
    1. Fill in title, content, type, priority
    2. Enter targeting as JSON string: {"zones":[],"states":["Telangana"],"territories":[],"specific_mrs":[]}
    3. Optionally add expires_at: 2026-12-31T23:59:59
    4. Optionally upload files (click "Choose Files")
    5. Click "Execute"
    
    **Response:**
    ```json
    {
      "message": "Communication sent successfully",
      "communication_id": "507f1f77bcf86cd799439011",
      "targeted_mrs": 15,
      "attachments": [
        {
          "file_name": "agenda.pdf",
          "file_url": "https://res.cloudinary.com/...",
          "file_type": "pdf",
          "file_size": 1024000
        }
      ]
    }
    ```
    
    **Note:** Files are uploaded automatically during communication creation.
    """
    return await create_communication_with_files(
        title=title,
        content=content,
        comm_type=type,
        priority=priority,
        targeting_json=targeting,
        link=link,
        expires_at_str=expires_at,
        files=files,
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
