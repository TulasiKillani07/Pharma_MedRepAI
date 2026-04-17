"""
Notification Business Logic
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from bson import ObjectId
from app.database import get_database
from fastapi import HTTPException
from app.models.notification_model import NotificationType
import math


async def create_notification(
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    data: Dict[str, Any]
) -> str:
    """
    Create a notification for a user.
    
    Args:
        user_id: Recipient user ID
        notification_type: Type of notification (use NotificationType constants)
        title: Notification title
        message: Notification message
        data: Type-specific data (IDs, names, etc.)
    
    Returns:
        str: Created notification ID
    """
    db = get_database()
    
    notification = {
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "data": data,
        "is_read": False,
        "read_at": None,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=30)  # Auto-delete after 30 days
    }
    
    result = await db.notifications.insert_one(notification)
    return str(result.inserted_id)


async def create_bulk_notifications(
    user_ids: List[str],
    notification_type: str,
    title: str,
    message: str,
    data: Dict[str, Any]
) -> int:
    """
    Create notifications for multiple users (bulk operation).
    
    Args:
        user_ids: List of recipient user IDs
        notification_type: Type of notification
        title: Notification title
        message: Notification message
        data: Type-specific data
    
    Returns:
        int: Number of notifications created
    """
    db = get_database()
    
    notifications = []
    for user_id in user_ids:
        notification = {
            "user_id": user_id,
            "type": notification_type,
            "title": title,
            "message": message,
            "data": data,
            "is_read": False,
            "read_at": None,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=30)
        }
        notifications.append(notification)
    
    if notifications:
        result = await db.notifications.insert_many(notifications)
        return len(result.inserted_ids)
    
    return 0


async def get_notifications(
    current_user: Dict,
    page: int = 1,
    limit: int = 20,
    unread_only: bool = False
) -> Dict[str, Any]:
    """
    Get paginated notifications for current user.
    
    Args:
        current_user: Current authenticated user
        page: Page number (1-indexed)
        limit: Notifications per page
        unread_only: If True, return only unread notifications
    
    Returns:
        dict: Paginated notifications with metadata
    """
    db = get_database()
    user_id = current_user["_id"]
    
    # Build query
    query = {"user_id": user_id}
    if unread_only:
        query["is_read"] = False
    
    # Get total count
    total = await db.notifications.count_documents(query)
    
    # Get unread count
    unread_count = await db.notifications.count_documents({
        "user_id": user_id,
        "is_read": False
    })
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = math.ceil(total / limit) if total > 0 else 1
    
    # Get notifications
    cursor = db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit)
    notifications = await cursor.to_list(length=limit)
    
    # Format response
    formatted_notifications = []
    for notif in notifications:
        formatted_notifications.append({
            "notification_id": str(notif["_id"]),
            "user_id": notif["user_id"],
            "type": notif["type"],
            "title": notif["title"],
            "message": notif["message"],
            "data": notif["data"],
            "is_read": notif["is_read"],
            "read_at": notif.get("read_at"),
            "created_at": notif["created_at"]
        })
    
    return {
        "notifications": formatted_notifications,
        "total": total,
        "unread_count": unread_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def get_unread_count(current_user: Dict) -> int:
    """
    Get count of unread notifications for current user.
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        int: Number of unread notifications
    """
    db = get_database()
    user_id = current_user["_id"]
    
    count = await db.notifications.count_documents({
        "user_id": user_id,
        "is_read": False
    })
    
    return count


async def mark_as_read(
    notification_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Mark a notification as read.
    
    Args:
        notification_id: Notification ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If notification not found or unauthorized
    """
    db = get_database()
    user_id = current_user["_id"]
    
    # Check if notification exists and belongs to user
    notification = await db.notifications.find_one({
        "_id": ObjectId(notification_id),
        "user_id": user_id
    })
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Mark as read
    await db.notifications.update_one(
        {"_id": ObjectId(notification_id)},
        {
            "$set": {
                "is_read": True,
                "read_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": "Notification marked as read"}


async def mark_all_as_read(current_user: Dict) -> Dict[str, Any]:
    """
    Mark all notifications as read for current user.
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        dict: Success message with count
    """
    db = get_database()
    user_id = current_user["_id"]
    
    result = await db.notifications.update_many(
        {
            "user_id": user_id,
            "is_read": False
        },
        {
            "$set": {
                "is_read": True,
                "read_at": datetime.utcnow()
            }
        }
    )
    
    return {
        "message": "All notifications marked as read",
        "count": result.modified_count
    }


async def delete_notification(
    notification_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Delete a notification.
    
    Args:
        notification_id: Notification ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If notification not found or unauthorized
    """
    db = get_database()
    user_id = current_user["_id"]
    
    result = await db.notifications.delete_one({
        "_id": ObjectId(notification_id),
        "user_id": user_id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"message": "Notification deleted successfully"}


async def clear_all_notifications(current_user: Dict) -> Dict[str, Any]:
    """
    Delete all notifications for current user.
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        dict: Success message with count
    """
    db = get_database()
    user_id = current_user["_id"]
    
    result = await db.notifications.delete_many({"user_id": user_id})
    
    return {
        "message": "All notifications cleared",
        "count": result.deleted_count
    }
