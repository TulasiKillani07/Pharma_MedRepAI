"""
Profile model - MongoDB document structure for profile features.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# Note: Profile data is stored in doctors/mrs/company_admins collections
# This model file is kept minimal as profiles use existing user collections

class CompanyInDB(BaseModel):
    """Database model for company document"""
    company_name: str
    company_logo_url: Optional[str] = None
    company_description: Optional[str] = None
    company_address: Optional[str] = None
    company_city: Optional[str] = None
    company_state: Optional[str] = None
    company_country: Optional[str] = None
    company_pincode: Optional[str] = None
    company_website: Optional[str] = None
    company_industry: Optional[str] = None
    company_founded_year: Optional[int] = None
    company_size: Optional[str] = None
    company_gst_number: Optional[str] = None
    company_pan_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime
