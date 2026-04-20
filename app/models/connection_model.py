"""
Connection model - MongoDB document structure for connections collection.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum
from bson import ObjectId


class ConnectionStatus(str, Enum):
    """Valid connection statuses"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class ConnectionInDB(BaseModel):
    """
    Write model for connection document (INSERT operations)
    
    Collection: connections
    Indexes:
    - Compound unique: (requester_id, receiver_id)
    - Compound: (receiver_id, status)
    - Compound: (requester_id, status)
    """
    requester_id: str = Field(..., description="User ID who sent the request")
    receiver_id: str = Field(..., description="User ID who received the request")
    
    # Requester details (denormalized for performance)
    requester_name: str = Field(..., description="Requester's name")
    requester_role: str = Field(..., description="Requester's role (DOCTOR/MR)")
    requester_specialization: Optional[str] = Field(None, description="Requester's specialization (if doctor)")
    requester_territory: Optional[str] = Field(None, description="Requester's territory (if MR)")
    
    # Receiver details (denormalized for performance)
    receiver_name: str = Field(..., description="Receiver's name")
    receiver_role: str = Field(..., description="Receiver's role (DOCTOR/MR)")
    receiver_specialization: Optional[str] = Field(None, description="Receiver's specialization (if doctor)")
    receiver_territory: Optional[str] = Field(None, description="Receiver's territory (if MR)")
    
    status: ConnectionStatus = Field(default=ConnectionStatus.PENDING, description="Connection status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    accepted_at: Optional[datetime] = Field(None, description="When connection was accepted")
    rejected_at: Optional[datetime] = Field(None, description="When connection was rejected")
    
    @field_validator('requester_id', 'receiver_id')
    @classmethod
    def validate_object_id(cls, v: str) -> str:
        """Validate that IDs are valid ObjectId format (external input validation)"""
        try:
            ObjectId(v)
            return v
        except Exception:
            raise ValueError(f'Invalid ObjectId format: {v}')
    
    class Config:
        extra = "forbid"  # Strict - no extra fields allowed for writes


class ConnectionDocument(ConnectionInDB):
    """
    Read model for connection document (if validation needed)
    Inherits all fields from ConnectionInDB
    """
    class Config:
        extra = "allow"  # Flexible - allow extra fields from DB
