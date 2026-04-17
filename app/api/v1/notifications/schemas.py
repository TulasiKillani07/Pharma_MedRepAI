"""
Notifications Request/Response Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class NotificationResponse(BaseModel):
    """Schema for notification response"""
    notification_id: str = Field(..., description="Notification ID")
    user_id: str = Field(..., description="Recipient user ID")
    type: str = Field(..., description="Notification type")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    data: Dict[str, Any] = Field(..., description="Type-specific data")
    is_read: bool = Field(..., description="Read status")
    read_at: Optional[datetime] = Field(None, description="When marked as read")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
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
                "is_read": False,
                "read_at": None,
                "created_at": "2024-04-16T10:00:00"
            }
        }


class NotificationListResponse(BaseModel):
    """Schema for paginated notifications list"""
    notifications: List[NotificationResponse] = Field(..., description="List of notifications")
    total: int = Field(..., description="Total number of notifications")
    unread_count: int = Field(..., description="Number of unread notifications")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Notifications per page")
    total_pages: int = Field(..., description="Total number of pages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "notifications": [
                    {
                        "notification_id": "notif123",
                        "user_id": "user123",
                        "type": "connection_request",
                        "title": "New Connection Request",
                        "message": "Dr. Sarah wants to connect",
                        "data": {
                            "connection_id": "conn123",
                            "requester_id": "user456"
                        },
                        "is_read": False,
                        "read_at": None,
                        "created_at": "2024-04-16T10:00:00"
                    }
                ],
                "total": 25,
                "unread_count": 5,
                "page": 1,
                "limit": 20,
                "total_pages": 2
            }
        }


class UnreadCountResponse(BaseModel):
    """Schema for unread count response"""
    count: int = Field(..., description="Number of unread notifications")
    
    class Config:
        json_schema_extra = {
            "example": {
                "count": 5
            }
        }


class MarkReadResponse(BaseModel):
    """Schema for mark as read response"""
    message: str = Field(..., description="Success message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Notification marked as read"
            }
        }


class MarkAllReadResponse(BaseModel):
    """Schema for mark all as read response"""
    message: str = Field(..., description="Success message")
    count: int = Field(..., description="Number of notifications marked as read")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "All notifications marked as read",
                "count": 10
            }
        }


class DeleteResponse(BaseModel):
    """Schema for delete notification response"""
    message: str = Field(..., description="Success message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Notification deleted successfully"
            }
        }


class ClearAllResponse(BaseModel):
    """Schema for clear all notifications response"""
    message: str = Field(..., description="Success message")
    count: int = Field(..., description="Number of notifications deleted")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "All notifications cleared",
                "count": 25
            }
        }
