"""
Group model - MongoDB schema for groups collection.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class GroupCreate(BaseModel):
    """Schema for creating a group"""
    group_name: str = Field(..., min_length=3, max_length=100, description="Group name")
    group_description: Optional[str] = Field(None, max_length=500, description="Group description")
    member_ids: Optional[List[str]] = Field(default=[], description="Initial member IDs to add")
    
    class Config:
        json_schema_extra = {
            "example": {
                "group_name": "Cardiology Team",
                "group_description": "Discussion group for cardiology specialists",
                "member_ids": ["user123", "user456"]
            }
        }


class GroupUpdate(BaseModel):
    """Schema for updating group info"""
    group_name: Optional[str] = Field(None, min_length=3, max_length=100, description="Group name")
    group_description: Optional[str] = Field(None, max_length=500, description="Group description")
    
    class Config:
        json_schema_extra = {
            "example": {
                "group_name": "Cardiology Specialists",
                "group_description": "Updated description"
            }
        }


class MemberInfo(BaseModel):
    """Schema for group member info"""
    user_id: str = Field(..., description="User ID")
    name: str = Field(..., description="User name")
    role: str = Field(..., description="User role")
    is_admin: bool = Field(..., description="Is user an admin")
    joined_at: datetime = Field(..., description="When user joined")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "name": "Dr. Sarah Sharma",
                "role": "DOCTOR",
                "is_admin": True,
                "joined_at": "2024-04-13T10:00:00"
            }
        }


class GroupResponse(BaseModel):
    """Schema for group response"""
    group_id: str = Field(..., description="Group ID")
    group_name: str = Field(..., description="Group name")
    group_description: Optional[str] = Field(None, description="Group description")
    created_by: str = Field(..., description="Creator user ID")
    members_count: int = Field(..., description="Number of members")
    admins_count: int = Field(..., description="Number of admins")
    created_at: datetime = Field(..., description="Group creation time")
    message: Optional[str] = Field(None, description="Additional message")
    failed_members: Optional[List[dict]] = Field(None, description="Members that failed to be added")
    
    class Config:
        json_schema_extra = {
            "example": {
                "group_id": "group123",
                "group_name": "Cardiology Team",
                "group_description": "Discussion group for cardiology specialists",
                "created_by": "user123",
                "members_count": 5,
                "admins_count": 2,
                "created_at": "2024-04-13T10:00:00",
                "message": "Group created with 4 of 5 requested members",
                "failed_members": [
                    {
                        "user_id": "user999",
                        "reason": "Not connected"
                    }
                ]
            }
        }


class GroupDetailResponse(BaseModel):
    """Schema for detailed group response"""
    group_id: str = Field(..., description="Group ID")
    group_name: str = Field(..., description="Group name")
    group_description: Optional[str] = Field(None, description="Group description")
    created_by: str = Field(..., description="Creator user ID")
    admins: List[str] = Field(..., description="Admin user IDs")
    members: List[MemberInfo] = Field(..., description="List of members")
    members_count: int = Field(..., description="Number of members")
    created_at: datetime = Field(..., description="Group creation time")
    you_left_at: Optional[datetime] = Field(None, description="When you left the group (if applicable)")
    status: Optional[str] = Field(None, description="Your status in group (left/active)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "group_id": "group123",
                "group_name": "Cardiology Team",
                "group_description": "Discussion group",
                "created_by": "user123",
                "admins": ["user123", "user456"],
                "members": [
                    {
                        "user_id": "user123",
                        "name": "Dr. Sarah Sharma",
                        "role": "DOCTOR",
                        "is_admin": True,
                        "joined_at": "2024-04-13T10:00:00"
                    }
                ],
                "members_count": 5,
                "created_at": "2024-04-13T10:00:00"
            }
        }


class GroupListItem(BaseModel):
    """Schema for group in list"""
    group_id: str = Field(..., description="Group ID")
    group_name: str = Field(..., description="Group name")
    last_message: Optional[str] = Field(None, description="Last message preview")
    last_message_at: Optional[datetime] = Field(None, description="Last message time")
    unread_count: int = Field(..., description="Unread messages count")
    members_count: int = Field(..., description="Number of members")
    status: str = Field(default="active", description="Group status: active or left")
    you_left_at: Optional[datetime] = Field(None, description="When you left (if status=left)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "group_id": "group123",
                "group_name": "Cardiology Team",
                "last_message": "Great discussion today!",
                "last_message_at": "2024-04-13T16:45:00",
                "unread_count": 5,
                "members_count": 5,
                "status": "active"
            }
        }


class GroupListResponse(BaseModel):
    """Schema for groups list"""
    groups: List[GroupListItem] = Field(..., description="List of groups")
    total: int = Field(..., description="Total number of groups")
    
    class Config:
        json_schema_extra = {
            "example": {
                "groups": [
                    {
                        "group_id": "group123",
                        "group_name": "Cardiology Team",
                        "last_message": "Great discussion!",
                        "last_message_at": "2024-04-13T16:45:00",
                        "unread_count": 5,
                        "members_count": 5
                    }
                ],
                "total": 3
            }
        }


class AddMembersRequest(BaseModel):
    """Schema for adding members to group"""
    user_ids: List[str] = Field(..., min_length=1, max_length=10, description="User IDs to add (max 10)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_ids": ["user789", "user012"]
            }
        }


class AddMembersResponse(BaseModel):
    """Schema for add members response"""
    message: str = Field(..., description="Success message")
    added: int = Field(..., description="Number of members added")
    failed: List[dict] = Field(default=[], description="Failed additions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Members added successfully",
                "added": 2,
                "failed": []
            }
        }


class GroupMessageCreate(BaseModel):
    """Schema for creating a group message"""
    content: str = Field(..., min_length=1, max_length=2000, description="Message content")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "Hello everyone! Meeting at 3 PM today."
            }
        }


class GroupMessageResponse(BaseModel):
    """Schema for group message response"""
    message_id: str = Field(..., description="Message ID")
    group_id: str = Field(..., description="Group ID")
    sender_id: str = Field(..., description="Sender user ID")
    sender_name: str = Field(..., description="Sender name")
    sender_role: str = Field(..., description="Sender role")
    content: str = Field(..., description="Message content")
    message_type: str = Field(default="text", description="Message type")
    shared_post: Optional[dict] = Field(None, description="Shared post data")
    read_by_count: int = Field(..., description="Number of users who read")
    created_at: datetime = Field(..., description="Message creation time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "msg123",
                "group_id": "group123",
                "sender_id": "user123",
                "sender_name": "Dr. Sarah Sharma",
                "sender_role": "DOCTOR",
                "content": "Hello everyone!",
                "message_type": "text",
                "shared_post": None,
                "read_by_count": 3,
                "created_at": "2024-04-13T17:00:00"
            }
        }


class GroupMessageListResponse(BaseModel):
    """Schema for paginated group messages"""
    messages: List[GroupMessageResponse] = Field(..., description="List of messages")
    total: int = Field(..., description="Total number of messages")
    page: int = Field(..., description="Current page")
    limit: int = Field(..., description="Messages per page")
    total_pages: int = Field(..., description="Total pages")
