"""
Communications Business Logic
Handles one-way broadcast communication from Admin to MRs.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from bson import ObjectId
from app.database import get_database
from fastapi import HTTPException, status
from app.models.communication_model import CommunicationInDB, CommunicationTargeting
from app.models.communication_read_model import CommunicationReadInDB


async def get_targeted_mrs(targeting: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get list of MRs based on targeting criteria.
    Automatically detects targeting type from populated arrays.
    Uses OR logic: MR matches if they match ANY condition.
    
    Args:
        targeting: Targeting criteria dict with zones, states, territories, specific_mrs
    
    Returns:
        List of MR documents that match targeting criteria
    """
    db = get_database()
    
    # Build query conditions (OR logic)
    conditions = []
    
    # Check zones
    zones = targeting.get("zones", [])
    if zones and len(zones) > 0:
        conditions.append({"zone": {"$in": zones}})
    
    # Check states
    states = targeting.get("states", [])
    if states and len(states) > 0:
        conditions.append({"state": {"$in": states}})
    
    # Check territories
    territories = targeting.get("territories", [])
    if territories and len(territories) > 0:
        conditions.append({"territory": {"$in": territories}})
    
    # Check specific MRs
    specific_mrs = targeting.get("specific_mrs", [])
    if specific_mrs and len(specific_mrs) > 0:
        try:
            mr_ids = [ObjectId(mr_id) for mr_id in specific_mrs]
            conditions.append({"_id": {"$in": mr_ids}})
        except Exception:
            # Invalid ObjectId format
            return []
    
    # Build final query
    if not conditions:
        # No targeting specified → target all active MRs
        query = {"is_active": True}
    else:
        # OR logic: match ANY condition
        query = {
            "$or": conditions,
            "is_active": True
        }
    
    # Execute query
    mrs = await db.mrs.find(query).to_list(None)
    return mrs


async def create_communication(
    title: str,
    content: str,
    comm_type: str,
    priority: str,
    targeting: Dict[str, Any],
    attachments: List[Dict[str, Any]],
    expires_at: Optional[datetime],
    current_user: Dict
) -> Dict[str, Any]:
    """
    Create a new communication (Admin only).
    
    Args:
        title: Communication title
        content: Communication content
        comm_type: Communication type (announcement, alert, target, training)
        priority: Priority level (low, medium, high, urgent)
        targeting: Targeting criteria
        attachments: List of file attachments
        expires_at: Optional expiry date
        current_user: Current authenticated admin user
    
    Returns:
        dict: Created communication info with targeted MR count
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Calculate targeted MRs
    targeted_mrs = await get_targeted_mrs(targeting)
    targeted_count = len(targeted_mrs)
    
    # Create communication document
    comm = CommunicationInDB(
        title=title,
        content=content,
        type=comm_type,
        priority=priority,
        targeting=CommunicationTargeting(**targeting),
        attachments=attachments,
        expires_at=expires_at,
        created_by=current_user["_id"],
        created_by_name=current_user.get("full_name", current_user.get("name", "Admin")),
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # Insert into database
    result = await db.communications.insert_one(comm.model_dump())
    
    print(f"[SUCCESS] Communication created: {title} (ID: {result.inserted_id}, Targeted: {targeted_count} MRs)")
    
    return {
        "message": "Communication sent successfully",
        "communication_id": str(result.inserted_id),
        "targeted_mrs": targeted_count
    }


async def get_communications_for_mr(
    current_user: Dict,
    page: int = 1,
    limit: int = 20,
    comm_type: Optional[str] = None,
    priority: Optional[str] = None,
    is_read: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Get list of communications for current MR.
    Auto-filters based on MR's zone, state, territory.
    
    Args:
        current_user: Current authenticated MR user
        page: Page number
        limit: Communications per page
        comm_type: Filter by type (optional)
        priority: Filter by priority (optional)
        is_read: Filter by read status (optional)
    
    Returns:
        dict: Paginated list of communications
    """
    db = get_database()
    
    # Validate pagination
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    mr_id = current_user["_id"]
    mr_zone = current_user.get("zone", "South")  # Default to South for now
    mr_state = current_user.get("state")
    mr_territory = current_user.get("territory")
    
    # Build base query - find communications that target this MR
    base_conditions = [
        # Target all MRs (all targeting arrays empty)
        {
            "targeting.zones": {"$size": 0},
            "targeting.states": {"$size": 0},
            "targeting.territories": {"$size": 0},
            "targeting.specific_mrs": {"$size": 0}
        },
        # Target by zone
        {"targeting.zones": mr_zone},
        # Target by state
        {"targeting.states": mr_state},
        # Target by territory
        {"targeting.territories": mr_territory},
        # Target specific MR
        {"targeting.specific_mrs": mr_id}
    ]
    
    query = {
        "$and": [
            {"$or": base_conditions},
            {"is_active": True},
            {
                "$or": [
                    {"expires_at": None},
                    {"expires_at": {"$gt": datetime.utcnow()}}
                ]
            }
        ]
    }
    
    # Add optional filters
    if comm_type:
        query["type"] = comm_type
    
    if priority:
        query["priority"] = priority
    
    # Get total count
    total = await db.communications.count_documents(query)
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get communications (sorted by priority then date)
    priority_order = {"urgent": 1, "high": 2, "medium": 3, "low": 4}
    
    comms_cursor = db.communications.find(query).sort([
        ("priority", 1),  # Will be overridden by aggregation
        ("created_at", -1)
    ]).skip(skip).limit(limit)
    
    comms_list = await comms_cursor.to_list(limit)
    
    # Sort by priority (urgent first) then by date
    comms_list.sort(key=lambda x: (priority_order.get(x["priority"], 5), -x["created_at"].timestamp()))
    
    # Check read status for each communication
    communications = []
    for comm in comms_list:
        comm_id = str(comm["_id"])
        
        # Check if MR has read this
        read_record = await db.communication_reads.find_one({
            "communication_id": comm_id,
            "mr_id": mr_id
        })
        
        is_comm_read = read_record is not None
        
        # Apply is_read filter if specified
        if is_read is not None and is_comm_read != is_read:
            continue
        
        # Create preview (first 100 chars)
        preview = comm["content"][:100]
        if len(comm["content"]) > 100:
            preview += "..."
        
        communications.append({
            "id": comm_id,
            "title": comm["title"],
            "type": comm["type"],
            "priority": comm["priority"],
            "preview": preview,
            "is_read": is_comm_read,
            "created_at": comm["created_at"],
            "created_by_name": comm["created_by_name"]
        })
    
    return {
        "total": len(communications),  # Adjusted after is_read filter
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "communications": communications
    }


async def get_communication_detail_for_mr(
    communication_id: str,
    current_user: Dict
) -> Dict[str, Any]:
    """
    Get full communication details for MR.
    Auto-marks as read if not already read.
    
    Args:
        communication_id: Communication ID
        current_user: Current authenticated MR user
    
    Returns:
        dict: Full communication details
    
    Raises:
        HTTPException: If communication not found or not accessible
    """
    db = get_database()
    
    # Get communication
    try:
        comm = await db.communications.find_one({
            "_id": ObjectId(communication_id),
            "is_active": True
        })
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid communication ID"
        )
    
    if not comm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication not found"
        )
    
    # Check if expired
    if comm.get("expires_at") and comm["expires_at"] < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication has expired"
        )
    
    # Check if MR has access to this communication
    mr_id = current_user["_id"]
    mr_zone = current_user.get("zone", "South")
    mr_state = current_user.get("state")
    mr_territory = current_user.get("territory")
    
    targeting = comm["targeting"]
    has_access = False
    
    # Check if targeting matches MR
    if (not targeting["zones"] and not targeting["states"] and 
        not targeting["territories"] and not targeting["specific_mrs"]):
        # Target all MRs
        has_access = True
    elif mr_zone in targeting.get("zones", []):
        has_access = True
    elif mr_state in targeting.get("states", []):
        has_access = True
    elif mr_territory in targeting.get("territories", []):
        has_access = True
    elif mr_id in targeting.get("specific_mrs", []):
        has_access = True
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this communication"
        )
    
    # Check if already read
    read_record = await db.communication_reads.find_one({
        "communication_id": communication_id,
        "mr_id": mr_id
    })
    
    is_read = read_record is not None
    
    # Mark as read if not already
    if not is_read:
        read_doc = CommunicationReadInDB(
            communication_id=communication_id,
            mr_id=mr_id,
            mr_name=current_user.get("name", ""),
            mr_territory=mr_territory or "",
            mr_state=mr_state or "",
            read_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        
        await db.communication_reads.insert_one(read_doc.model_dump())
        is_read = True
        
        print(f"[INFO] MR {mr_id} read communication {communication_id}")
    
    # Return full details
    return {
        "id": str(comm["_id"]),
        "title": comm["title"],
        "content": comm["content"],
        "type": comm["type"],
        "priority": comm["priority"],
        "targeting": targeting,
        "attachments": comm.get("attachments", []),
        "expires_at": comm.get("expires_at"),
        "created_at": comm["created_at"],
        "created_by_name": comm["created_by_name"],
        "is_read": is_read
    }


async def get_unread_count(current_user: Dict) -> Dict[str, int]:
    """
    Get count of unread communications for current MR.
    
    Args:
        current_user: Current authenticated MR user
    
    Returns:
        dict: Unread count
    """
    db = get_database()
    
    mr_id = current_user["_id"]
    mr_zone = current_user.get("zone", "South")
    mr_state = current_user.get("state")
    mr_territory = current_user.get("territory")
    
    # Find all communications targeted to this MR
    base_conditions = [
        {
            "targeting.zones": {"$size": 0},
            "targeting.states": {"$size": 0},
            "targeting.territories": {"$size": 0},
            "targeting.specific_mrs": {"$size": 0}
        },
        {"targeting.zones": mr_zone},
        {"targeting.states": mr_state},
        {"targeting.territories": mr_territory},
        {"targeting.specific_mrs": mr_id}
    ]
    
    query = {
        "$and": [
            {"$or": base_conditions},
            {"is_active": True},
            {
                "$or": [
                    {"expires_at": None},
                    {"expires_at": {"$gt": datetime.utcnow()}}
                ]
            }
        ]
    }
    
    # Get all targeted communications
    comms = await db.communications.find(query, {"_id": 1}).to_list(None)
    comm_ids = [str(c["_id"]) for c in comms]
    
    # Get read communications
    read_comms = await db.communication_reads.find({
        "mr_id": mr_id,
        "communication_id": {"$in": comm_ids}
    }, {"communication_id": 1}).to_list(None)
    
    read_comm_ids = [r["communication_id"] for r in read_comms]
    
    # Calculate unread
    unread_count = len(comm_ids) - len(read_comm_ids)
    
    return {"unread_count": unread_count}



# ============ ADMIN FUNCTIONS ============

async def get_all_communications_admin(
    page: int = 1,
    limit: int = 20,
    comm_type: Optional[str] = None,
    priority: Optional[str] = None,
    is_active: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Get all communications (Admin view).
    
    Args:
        page: Page number
        limit: Communications per page
        comm_type: Filter by type (optional)
        priority: Filter by priority (optional)
        is_active: Filter by active status (optional)
    
    Returns:
        dict: Paginated list of communications
    """
    db = get_database()
    
    # Validate pagination
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    # Build query
    query = {}
    
    if comm_type:
        query["type"] = comm_type
    
    if priority:
        query["priority"] = priority
    
    if is_active is not None:
        query["is_active"] = is_active
    
    # Get total count
    total = await db.communications.count_documents(query)
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get communications
    comms_cursor = db.communications.find(query).sort("created_at", -1).skip(skip).limit(limit)
    comms_list = await comms_cursor.to_list(limit)
    
    # Format response
    communications = []
    for comm in comms_list:
        communications.append({
            "id": str(comm["_id"]),
            "title": comm["title"],
            "type": comm["type"],
            "priority": comm["priority"],
            "targeting": comm["targeting"],
            "is_active": comm["is_active"],
            "expires_at": comm.get("expires_at"),
            "created_at": comm["created_at"],
            "created_by_name": comm["created_by_name"]
        })
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "communications": communications
    }


async def get_communication_detail_admin(communication_id: str) -> Dict[str, Any]:
    """
    Get full communication details (Admin view).
    
    Args:
        communication_id: Communication ID
    
    Returns:
        dict: Full communication details
    
    Raises:
        HTTPException: If communication not found
    """
    db = get_database()
    
    try:
        comm = await db.communications.find_one({"_id": ObjectId(communication_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid communication ID"
        )
    
    if not comm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication not found"
        )
    
    return {
        "id": str(comm["_id"]),
        "title": comm["title"],
        "content": comm["content"],
        "type": comm["type"],
        "priority": comm["priority"],
        "targeting": comm["targeting"],
        "attachments": comm.get("attachments", []),
        "expires_at": comm.get("expires_at"),
        "is_active": comm["is_active"],
        "created_at": comm["created_at"],
        "updated_at": comm["updated_at"],
        "created_by_name": comm["created_by_name"]
    }


async def update_communication(
    communication_id: str,
    update_data: Dict[str, Any],
    current_user: Dict
) -> Dict[str, str]:
    """
    Update communication (Admin only).
    
    Args:
        communication_id: Communication ID
        update_data: Fields to update
        current_user: Current authenticated admin user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If communication not found
    """
    db = get_database()
    
    try:
        comm = await db.communications.find_one({"_id": ObjectId(communication_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid communication ID"
        )
    
    if not comm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication not found"
        )
    
    # Add updated_at timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update communication
    await db.communications.update_one(
        {"_id": ObjectId(communication_id)},
        {"$set": update_data}
    )
    
    print(f"[SUCCESS] Communication updated: {communication_id}")
    
    return {"message": "Communication updated successfully"}


async def delete_communication(
    communication_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Deactivate communication (soft delete, Admin only).
    
    Args:
        communication_id: Communication ID
        current_user: Current authenticated admin user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If communication not found
    """
    db = get_database()
    
    try:
        comm = await db.communications.find_one({"_id": ObjectId(communication_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid communication ID"
        )
    
    if not comm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication not found"
        )
    
    # Soft delete
    await db.communications.update_one(
        {"_id": ObjectId(communication_id)},
        {
            "$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    print(f"[SUCCESS] Communication deactivated: {communication_id}")
    
    return {"message": "Communication deactivated successfully"}


async def get_communication_analytics(communication_id: str) -> Dict[str, Any]:
    """
    Get read analytics for a communication (Admin only).
    
    Args:
        communication_id: Communication ID
    
    Returns:
        dict: Analytics data with read/unread MRs
    
    Raises:
        HTTPException: If communication not found
    """
    db = get_database()
    
    try:
        comm = await db.communications.find_one({"_id": ObjectId(communication_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid communication ID"
        )
    
    if not comm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication not found"
        )
    
    # Get targeted MRs
    targeted_mrs = await get_targeted_mrs(comm["targeting"])
    total_targeted = len(targeted_mrs)
    
    # Get read records
    reads = await db.communication_reads.find({
        "communication_id": communication_id
    }).to_list(None)
    
    total_read = len(reads)
    read_percentage = (total_read / total_targeted * 100) if total_targeted > 0 else 0
    
    # Format read_by list
    read_by = []
    for read in reads:
        read_by.append({
            "mr_id": read["mr_id"],
            "mr_name": read["mr_name"],
            "territory": read["mr_territory"],
            "state": read["mr_state"],
            "read_at": read["read_at"]
        })
    
    # Get MRs who didn't read
    read_mr_ids = [r["mr_id"] for r in reads]
    not_read_by = []
    
    for mr in targeted_mrs:
        mr_id = str(mr["_id"])
        if mr_id not in read_mr_ids:
            not_read_by.append({
                "mr_id": mr_id,
                "mr_name": mr.get("name", ""),
                "territory": mr.get("territory", ""),
                "state": mr.get("state", ""),
                "read_at": None
            })
    
    return {
        "communication_id": communication_id,
        "title": comm["title"],
        "total_targeted": total_targeted,
        "total_read": total_read,
        "read_percentage": round(read_percentage, 2),
        "read_by": read_by,
        "not_read_by": not_read_by
    }
