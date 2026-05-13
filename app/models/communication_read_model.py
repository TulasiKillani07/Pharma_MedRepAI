"""
Communication Read Tracking model - MongoDB schema for communication_reads collection.
Tracks which MRs have read which communications for analytics.
"""

from pydantic import BaseModel
from datetime import datetime


class CommunicationReadInDB(BaseModel):
    """Schema for communication read tracking"""
    communication_id: str
    mr_id: str
    mr_name: str
    mr_territory: str
    mr_state: str
    read_at: datetime
    created_at: datetime
