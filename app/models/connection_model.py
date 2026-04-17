"""
Connection model - MongoDB document structure for connections collection.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ConnectionInDB(BaseModel):
    """Database model for connection document"""
    requester_id: str
    receiver_id: str
    status: str  # pending, accepted, rejected
    created_at: datetime
    updated_at: datetime
    accepted_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
