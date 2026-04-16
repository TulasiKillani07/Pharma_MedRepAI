"""
Connection model - MongoDB schema for connections collection.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class DiscoverUser(BaseModel):
    """Schema for discovered user"""
    user_id: str = Field(..., description="User ID")
    name: str = Field(..., description="User name")
    role: str = Field(..., description="User role: DOCTOR or MR")
    specialization: Optional[str] = Field(None, description="Doctor's specialization")
    hospital: Optional[str] = Field(None, description="Doctor's hospital")
    territory: Optional[str] = Field(None, description="MR's territory")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "name": "Dr. Sarah Sharma",
                "role": "DOCTOR",
                "specialization": "Cardiology",
                "hospital": "Apollo Hospital",
                "territory": None
            }
        }


class DiscoverResponse(BaseModel):
    """Schema for discover users response"""
    users: List[DiscoverUser] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Users per page")
    total_pages: int = Field(..., description="Total number of pages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "users": [
                    {
                        "user_id": "user123",
                        "name": "Dr. Sarah Sharma",
                        "role": "DOCTOR",
                        "specialization": "Cardiology",
                        "hospital": "Apollo Hospital"
                    }
                ],
                "total": 50,
                "page": 1,
                "limit": 20,
                "total_pages": 3
            }
        }


class ConnectionRequestResponse(BaseModel):
    """Schema for connection request response"""
    connection_id: str = Field(..., description="Connection ID")
    receiver_name: str = Field(..., description="Receiver name")
    status: str = Field(..., description="Connection status")
    message: str = Field(..., description="Success message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "connection_id": "conn123",
                "receiver_name": "Dr. Priya Patel",
                "status": "pending",
                "message": "Connection request sent successfully"
            }
        }


class ConnectionRequest(BaseModel):
    """Schema for connection request details"""
    connection_id: str = Field(..., description="Connection ID")
    requester_id: str = Field(..., description="Requester user ID")
    requester_name: str = Field(..., description="Requester name")
    requester_role: str = Field(..., description="Requester role")
    requester_specialization: Optional[str] = Field(None, description="Requester specialization")
    requester_territory: Optional[str] = Field(None, description="Requester territory")
    status: str = Field(..., description="Request status")
    created_at: datetime = Field(..., description="Request creation time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "connection_id": "conn123",
                "requester_id": "user789",
                "requester_name": "Dr. Priya Patel",
                "requester_role": "DOCTOR",
                "requester_specialization": "Neurology",
                "status": "pending",
                "created_at": "2024-04-10T10:00:00"
            }
        }


class ConnectionRequestListResponse(BaseModel):
    """Schema for list of connection requests"""
    requests: List[ConnectionRequest] = Field(..., description="List of requests")
    total: int = Field(..., description="Total number of requests")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Requests per page")
    total_pages: int = Field(..., description="Total number of pages")


class Connection(BaseModel):
    """Schema for connection details"""
    user_id: str = Field(..., description="Connected user ID")
    name: str = Field(..., description="Connected user name")
    role: str = Field(..., description="Connected user role")
    specialization: Optional[str] = Field(None, description="Specialization if doctor")
    territory: Optional[str] = Field(None, description="Territory if MR")
    connected_at: datetime = Field(..., description="Connection established time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user789",
                "name": "Dr. Priya Patel",
                "role": "DOCTOR",
                "specialization": "Neurology",
                "connected_at": "2024-04-10T11:00:00"
            }
        }


class ConnectionListResponse(BaseModel):
    """Schema for list of connections"""
    connections: List[Connection] = Field(..., description="List of connections")
    total: int = Field(..., description="Total number of connections")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Connections per page")
    total_pages: int = Field(..., description="Total number of pages")
