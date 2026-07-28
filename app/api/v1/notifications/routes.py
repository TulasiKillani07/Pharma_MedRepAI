"""
Notifications API Endpoints
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Dict
from app.core.auth import get_current_user
from app.api.v1.notifications.schemas import (
    NotificationListResponse,
    UnreadCountResponse,
    MarkReadResponse,
    MarkAllReadResponse,
    DeleteResponse,
    ClearAllResponse
)
from app.api.v1.notifications import service


router = APIRouter()


async def require_admin_or_mr(current_user: Dict = Depends(get_current_user)) -> Dict:
    """Only ADMIN and MR can access notifications on MRX. Doctors use DRX."""
    if current_user.get("role") not in ["ADMIN", "MR", "MANAGER"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Doctors use DRX for notifications")
    return current_user


@router.get("", response_model=NotificationListResponse)
async def get_notifications_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Notifications per page"),
    unread_only: bool = Query(False, description="Show only unread notifications"),
    current_user: Dict = Depends(require_admin_or_mr)
):
    """
    Get paginated notifications for current user.
    
    **Access:** Doctor, MR, Admin, Manager
    
    **Purpose:**
    Retrieve notifications with pagination and filtering.
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Notifications per page (default: 20, max: 100)
    - `unread_only`: If true, show only unread notifications (default: false)
    
    **Response:**
    ```json
    {
        "notifications": [
            {
                "notification_id": "notif123",
                "user_id": "user123",
                "type": "connection_request",
                "title": "New Connection Request",
                "message": "Dr. Sarah wants to connect with you",
                "data": {
                    "connection_id": "conn123",
                    "requester_id": "user456",
                    "requester_name": "Dr. Sarah Sharma",
                    "requester_role": "DOCTOR"
                },
                "is_read": false,
                "read_at": null,
                "created_at": "2024-04-16T10:00:00"
            }
        ],
        "total": 25,
        "unread_count": 5,
        "page": 1,
        "limit": 20,
        "total_pages": 2
    }
    ```
    
    **Notification Types:**
    - `connection_request` - Someone sent you a connection request
    - `connection_accepted` - Someone accepted your connection request
    - `post_liked` - Someone liked your post
    - `post_commented` - Someone commented on your post
    - `post_shared` - Someone shared a post with you
    - `new_message` - New direct message
    - `group_message` - New group message
    - `group_added` - Added to a group
    - `cme_created` - New CME event
    - `cme_reminder_1day` - CME event tomorrow
    - `cme_reminder_1hour` - CME event in 1 hour
    - `cme_recording` - CME recording available
    - `drug_added` - New drug added
    - `visit_scheduled` - Visit scheduled
    - `visit_rescheduled` - Visit rescheduled
    - `visit_completed` - Visit completed
    - `visit_cancelled` - Visit cancelled
    
    **Use Cases:**
    - Display notifications in notification center
    - Show unread notifications badge
    - Implement infinite scroll with pagination
    - Filter to show only unread notifications
    
    **Frontend Navigation:**
    Frontend should handle navigation based on `type` and `data`:
    ```javascript
    switch(notification.type) {
        case 'connection_request':
            navigate('/network/connections/requests');
            break;
        case 'post_commented':
            navigate(`/feed/posts/${notification.data.post_id}`);
            break;
        case 'new_message':
            navigate(`/chat/conversations/${notification.data.conversation_id}`);
            break;
        // ... more cases
    }
    ```
    """
    return await service.get_notifications(current_user, page, limit, unread_only)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count_endpoint(
    current_user: Dict = Depends(require_admin_or_mr)
):
    """
    Get count of unread notifications.
    
    **Access:** Doctor, MR, Admin, Manager
    
    **Purpose:**
    Get the number of unread notifications for displaying badge count.
    
    **Response:**
    ```json
    {
        "count": 5
    }
    ```
    
    **Use Cases:**
    - Display unread count badge on notification bell icon
    - Poll every 30 seconds to update badge count
    - Show "You have 5 new notifications" message
    
    **Polling Strategy:**
    ```javascript
    // Frontend: Poll every 30 seconds
    setInterval(async () => {
        const response = await fetch('/api/v1/notifications/unread-count');
        const data = await response.json();
        updateBadge(data.count);
    }, 30000);
    ```
    """
    count = await service.get_unread_count(current_user)
    return {"count": count}


@router.put("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_as_read_endpoint(
    notification_id: str,
    current_user: Dict = Depends(require_admin_or_mr)
):
    """
    Mark a notification as read.
    
    **Access:** Doctor, MR, Admin, Manager
    
    **Purpose:**
    Mark a specific notification as read when user clicks on it.
    
    **Path Parameters:**
    - `notification_id`: Notification ID to mark as read
    
    **Response:**
    ```json
    {
        "message": "Notification marked as read"
    }
    ```
    
    **Use Cases:**
    - User clicks on notification → mark as read
    - User views notification details → mark as read
    - Automatically mark as read when notification is clicked
    
    **Errors:**
    - 404: Notification not found or doesn't belong to user
    """
    return await service.mark_as_read(notification_id, current_user)


@router.put("/read-all", response_model=MarkAllReadResponse)
async def mark_all_as_read_endpoint(
    current_user: Dict = Depends(require_admin_or_mr)
):
    """
    Mark all notifications as read.
    
    **Access:** Doctor, MR, Admin, Manager
    
    **Purpose:**
    Mark all unread notifications as read at once.
    
    **Response:**
    ```json
    {
        "message": "All notifications marked as read",
        "count": 10
    }
    ```
    
    **Use Cases:**
    - User clicks "Mark all as read" button
    - Clear all unread badges
    - Bulk operation for better UX
    """
    return await service.mark_all_as_read(current_user)


@router.delete("/clear-all", response_model=ClearAllResponse)
async def clear_all_notifications_endpoint(
    current_user: Dict = Depends(require_admin_or_mr)
):
    """
    Delete all notifications.
    
    **Access:** Doctor, MR, Admin, Manager
    
    **Purpose:**
    Delete all notifications for current user at once.
    
    **Response:**
    ```json
    {
        "message": "All notifications cleared",
        "count": 25
    }
    ```
    
    **Use Cases:**
    - User clicks "Clear all" button
    - Reset notification list
    - Bulk delete operation
    
    **Warning:**
    This action cannot be undone. All notifications will be permanently deleted.
    """
    return await service.clear_all_notifications(current_user)


@router.delete("/{notification_id}", response_model=DeleteResponse)
async def delete_notification_endpoint(
    notification_id: str,
    current_user: Dict = Depends(require_admin_or_mr)
):
    """
    Delete a notification.
    
    **Access:** Doctor, MR, Admin, Manager
    
    **Purpose:**
    Delete a specific notification from user's list.
    
    **Path Parameters:**
    - `notification_id`: Notification ID to delete
    
    **Response:**
    ```json
    {
        "message": "Notification deleted successfully"
    }
    ```
    
    **Use Cases:**
    - User swipes to delete notification
    - User clicks delete button on notification
    - Remove unwanted notifications
    
    **Errors:**
    - 404: Notification not found or doesn't belong to user
    """
    return await service.delete_notification(notification_id, current_user)
