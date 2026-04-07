"""
Role definitions for MedRepAI.
Defines the three user roles and their corresponding MongoDB collections.
"""

from enum import Enum


class UserRole(str, Enum):
    """
    User roles in the system.
    Each role corresponds to a separate MongoDB collection.
    """
    ADMIN = "ADMIN"      # Company Admin - manages everything
    DOCTOR = "DOCTOR"    # Doctor - views drugs, creates posts, chats
    MR = "MR"            # Medical Representative - promotes drugs, chats with doctors


# Mapping of roles to their MongoDB collection names
ROLE_COLLECTION_MAP = {
    UserRole.ADMIN: "company_admins",
    UserRole.DOCTOR: "doctors",
    UserRole.MR: "mrs"
}


def get_collection_name(role: UserRole) -> str:
    """
    Get the MongoDB collection name for a given role.
    
    Args:
        role: The user role (ADMIN, DOCTOR, or MR)
    
    Returns:
        str: The collection name (company_admins, doctors, or mrs)
    
    Example:
        >>> get_collection_name(UserRole.DOCTOR)
        'doctors'
    """
    return ROLE_COLLECTION_MAP[role]
