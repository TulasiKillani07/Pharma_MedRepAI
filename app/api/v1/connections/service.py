"""
Connections Business Logic
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from bson import ObjectId
from app.database import get_database
from fastapi import HTTPException
from app.api.v1.notifications.helpers import notify_connection_request, notify_connection_accepted
from app.models.connection_model import ConnectionInDB, ConnectionStatus


async def discover_users(
    current_user: Dict,
    role: Optional[str] = None,
    search: Optional[str] = None,
    specialization: Optional[str] = None,
    territory: Optional[str] = None,
    page: int = 1,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Discover doctors to connect with.
    ONLY DOCTORS can use network features.
    
    Args:
        current_user: Current authenticated user
        role: Ignored (only doctors shown)
        search: Search by name
        specialization: Filter doctors by specialization
        territory: Ignored (no MRs in network)
        page: Page number
        limit: Users per page
    
    Returns:
        dict: Paginated list of doctors
    """
    # Block MRs from using network features
    if current_user.get("role") == "MR":
        raise HTTPException(
            status_code=403,
            detail="Network features are only available for doctors"
        )
    
    db = get_database()
    
    # Validate and limit page size
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    user_id = current_user["_id"]
    
    # Get all connection IDs (any status) to exclude
    connections_cursor = db["connections"].find({
        "$or": [
            {"requester_id": user_id},
            {"receiver_id": user_id}
        ]
    })
    
    connections_list = await connections_cursor.to_list(None)
    
    # Extract all connected user IDs
    excluded_ids = {user_id}  # Exclude self
    for conn in connections_list:
        if conn["requester_id"] == user_id:
            excluded_ids.add(conn["receiver_id"])
        else:
            excluded_ids.add(conn["requester_id"])
    
    # Build query for doctors only
    base_query = {
        "_id": {"$nin": [ObjectId(uid) if len(uid) == 24 else uid for uid in excluded_ids]},
        "is_active": True
    }
    
    # Apply search filter
    if search:
        base_query["name"] = {"$regex": search, "$options": "i"}
    
    all_users = []
    
    # ONLY show doctors in network (MRs completely removed)
    doctor_query = base_query.copy()
    if specialization:
        doctor_query["specialization"] = {"$regex": specialization, "$options": "i"}
    
    doctors_cursor = db["doctors"].find(doctor_query)
    doctors_list = await doctors_cursor.to_list(None)
    
    for doctor in doctors_list:
        all_users.append({
            "user_id": str(doctor["_id"]),
            "name": doctor.get("name", ""),
            "role": "DOCTOR",
            "specialization": doctor.get("specialization"),
            "hospital": doctor.get("hospital"),
            "territory": None
        })
    
    # Calculate pagination
    total = len(all_users)
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    skip = (page - 1) * limit
    
    # Apply pagination
    paginated_users = all_users[skip:skip + limit]
    
    return {
        "users": paginated_users,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def send_connection_request(
    receiver_id: str,
    current_user: Dict
) -> Dict[str, Any]:
    """
    Send connection request to another user.
    ONLY DOCTORS and ADMINS can send connection requests.
    
    Args:
        receiver_id: User ID to send request to
        current_user: Current authenticated user
    
    Returns:
        dict: Connection request details
    
    Raises:
        HTTPException: If validation fails
    """
    # Block MRs from using network features
    if current_user.get("role") == "MR":
        raise HTTPException(
            status_code=403,
            detail="Network features are only available for doctors"
        )
    
    db = get_database()
    
    requester_id = current_user["_id"]
    
    # Validate receiver_id format first
    if not ObjectId.is_valid(receiver_id):
        raise HTTPException(status_code=400, detail="Invalid receiver ID format")
    
    # Cannot send request to self
    if requester_id == receiver_id:
        raise HTTPException(status_code=400, detail="Cannot send connection request to yourself")
    
    # Get receiver details (ONLY doctors allowed)
    receiver = await db["doctors"].find_one({"_id": ObjectId(receiver_id)})
    
    if not receiver:
        raise HTTPException(status_code=404, detail="User not found or not available for connections")
    
    # Check if connection already exists (any status)
    existing = await db["connections"].find_one({
        "$or": [
            {"requester_id": requester_id, "receiver_id": receiver_id},
            {"requester_id": receiver_id, "receiver_id": requester_id}
        ]
    })
    
    if existing:
        if existing["status"] == "pending":
            raise HTTPException(status_code=400, detail="Connection request already pending")
        elif existing["status"] == "accepted":
            raise HTTPException(status_code=400, detail="Already connected")
        elif existing["status"] == "blocked":
            raise HTTPException(status_code=400, detail="Cannot send request to this user")
    
    # Get requester details (current user - must be doctor or admin)
    requester = await db["doctors"].find_one({"_id": ObjectId(requester_id)})
    if not requester:
        # Check if admin
        requester = await db["admins"].find_one({"_id": ObjectId(requester_id)})
    
    if not requester:
        raise HTTPException(status_code=404, detail="Requester not found")
    
    # Create connection request using model (RULE 1: INSERT with model)
    connection = ConnectionInDB(
        requester_id=requester_id,
        receiver_id=receiver_id,
        requester_name=requester.get("name", ""),
        requester_role=requester.get("role", ""),
        requester_specialization=requester.get("specialization"),
        requester_territory=requester.get("territory"),
        receiver_name=receiver.get("name", ""),
        receiver_role=receiver.get("role", ""),
        receiver_specialization=receiver.get("specialization"),
        receiver_territory=receiver.get("territory"),
        status=ConnectionStatus.PENDING
    )
    
    result = await db["connections"].insert_one(connection.model_dump())
    
    # Notify receiver about connection request
    await notify_connection_request(
        receiver_id=receiver_id,
        requester_name=current_user.get("name", ""),
        requester_id=requester_id,
        requester_role=current_user.get("role", ""),
        connection_id=str(result.inserted_id)
    )
    
    return {
        "connection_id": str(result.inserted_id),
        "receiver_name": receiver.get("name", ""),
        "status": "pending",
        "message": "Connection request sent successfully"
    }


async def get_received_requests(
    current_user: Dict,
    page: int = 1,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get connection requests received by current user.
    ONLY DOCTORS and ADMINS can access network features.
    
    Args:
        current_user: Current authenticated user
        page: Page number
        limit: Requests per page
    
    Returns:
        dict: Paginated list of received requests
    """
    # Block MRs from using network features
    if current_user.get("role") == "MR":
        raise HTTPException(
            status_code=403,
            detail="Network features are only available for doctors"
        )
    
    db = get_database()
    
    # Validate and limit page size
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    user_id = current_user["_id"]
    
    # Get total count
    total = await db["connections"].count_documents({
        "receiver_id": user_id,
        "status": ConnectionStatus.PENDING  # No .value needed
    })
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get requests
    requests_cursor = db["connections"].find({
        "receiver_id": user_id,
        "status": ConnectionStatus.PENDING  # No .value needed
    }).sort("created_at", -1).skip(skip).limit(limit)
    
    requests_list = await requests_cursor.to_list(limit)
    
    # Format requests
    requests = []
    for req in requests_list:
        requests.append({
            "connection_id": str(req["_id"]),
            "requester_id": req["requester_id"],
            "requester_name": req["requester_name"],
            "requester_role": req["requester_role"],
            "requester_specialization": req.get("requester_specialization"),
            "requester_territory": req.get("requester_territory"),
            "status": req["status"],
            "created_at": req["created_at"]
        })
    
    return {
        "requests": requests,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def get_sent_requests(
    current_user: Dict,
    page: int = 1,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get connection requests sent by current user.
    ONLY DOCTORS and ADMINS can access network features.
    
    Args:
        current_user: Current authenticated user
        page: Page number
        limit: Requests per page
    
    Returns:
        dict: Paginated list of sent requests
    """
    # Block MRs from using network features
    if current_user.get("role") == "MR":
        raise HTTPException(
            status_code=403,
            detail="Network features are only available for doctors"
        )
    
    db = get_database()
    
    # Validate and limit page size
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    user_id = current_user["_id"]
    
    # Get total count
    total = await db["connections"].count_documents({
        "requester_id": user_id,
        "status": ConnectionStatus.PENDING  # No .value needed
    })
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get requests
    requests_cursor = db["connections"].find({
        "requester_id": user_id,
        "status": ConnectionStatus.PENDING  # No .value needed
    }).sort("created_at", -1).skip(skip).limit(limit)
    
    requests_list = await requests_cursor.to_list(limit)
    
    # Format requests (show receiver info for sent requests)
    requests = []
    for req in requests_list:
        requests.append({
            "connection_id": str(req["_id"]),
            "requester_id": req["receiver_id"],  # Show receiver as the "other" user
            "requester_name": req["receiver_name"],
            "requester_role": req["receiver_role"],
            "requester_specialization": req.get("receiver_specialization"),
            "requester_territory": req.get("receiver_territory"),
            "status": req["status"],
            "created_at": req["created_at"]
        })
    
    return {
        "requests": requests,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def accept_request(
    connection_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Accept a connection request.
    ONLY DOCTORS and ADMINS can access network features.
    
    Args:
        connection_id: Connection ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    # Block MRs from using network features
    if current_user.get("role") == "MR":
        raise HTTPException(
            status_code=403,
            detail="Network features are only available for doctors"
        )
    
    db = get_database()
    
    # Get connection
    try:
        connection = await db["connections"].find_one({"_id": ObjectId(connection_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid connection ID")
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection request not found")
    
    # Check if current user is the receiver
    if connection["receiver_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only accept requests sent to you")
    
    # Check if status is pending
    if connection["status"] != ConnectionStatus.PENDING:  # No .value needed
        raise HTTPException(status_code=400, detail="Connection request is not pending")
    
    # Update status to accepted (RULE 2: UPDATE with Enum)
    await db["connections"].update_one(
        {"_id": ObjectId(connection_id)},
        {
            "$set": {
                "status": ConnectionStatus.ACCEPTED,  # No .value needed
                "accepted_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Notify requester that connection was accepted
    await notify_connection_accepted(
        requester_id=connection["requester_id"],
        accepter_name=current_user.get("name", ""),
        accepter_id=current_user["_id"],
        accepter_role=current_user.get("role", ""),
        connection_id=connection_id
    )
    
    return {
        "message": "Connection request accepted",
        "connection_id": connection_id
    }


async def reject_request(
    connection_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Reject a connection request.
    ONLY DOCTORS and ADMINS can access network features.
    
    Args:
        connection_id: Connection ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    # Block MRs from using network features
    if current_user.get("role") == "MR":
        raise HTTPException(
            status_code=403,
            detail="Network features are only available for doctors"
        )
    
    db = get_database()
    
    # Get connection
    try:
        connection = await db["connections"].find_one({"_id": ObjectId(connection_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid connection ID")
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection request not found")
    
    # Check if current user is the receiver
    if connection["receiver_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only reject requests sent to you")
    
    # Check if status is pending
    if connection["status"] != ConnectionStatus.PENDING:  # No .value needed
        raise HTTPException(status_code=400, detail="Connection request is not pending")
    
    # Update status to rejected (RULE 2: UPDATE with Enum)
    await db["connections"].update_one(
        {"_id": ObjectId(connection_id)},
        {
            "$set": {
                "status": ConnectionStatus.REJECTED,  # No .value needed
                "rejected_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": "Connection request rejected"}


async def cancel_request(
    connection_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Cancel a sent connection request.
    ONLY DOCTORS and ADMINS can access network features.
    
    Args:
        connection_id: Connection ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    # Block MRs from using network features
    if current_user.get("role") == "MR":
        raise HTTPException(
            status_code=403,
            detail="Network features are only available for doctors"
        )
    
    db = get_database()
    
    # Get connection
    try:
        connection = await db["connections"].find_one({"_id": ObjectId(connection_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid connection ID")
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection request not found")
    
    # Check if current user is the requester
    if connection["requester_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only cancel requests you sent")
    
    # Check if status is pending
    if connection["status"] != ConnectionStatus.PENDING:  # No .value needed
        raise HTTPException(status_code=400, detail="Connection request is not pending")
    
    # Delete the request
    await db["connections"].delete_one({"_id": ObjectId(connection_id)})
    
    return {"message": "Connection request cancelled"}


async def get_my_connections(
    current_user: Dict,
    page: int = 1,
    limit: int = 20,
    status: str = "accepted"
) -> Dict[str, Any]:
    """
    Get current user's connections filtered by status.
    ONLY DOCTORS and ADMINS can access network features.
    
    Args:
        current_user: Current authenticated user
        page: Page number
        limit: Connections per page
        status: Filter by status (accepted, blocked, pending)
    
    Returns:
        dict: Paginated list of connections
    """
    # Block MRs from using network features
    if current_user.get("role") == "MR":
        raise HTTPException(
            status_code=403,
            detail="Network features are only available for doctors"
        )
    
    db = get_database()
    
    # Validate and limit page size
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    user_id = current_user["_id"]
    
    # Convert status string to enum
    if status == "accepted":
        status_enum = ConnectionStatus.ACCEPTED
    elif status == "blocked":
        status_enum = ConnectionStatus.BLOCKED
    elif status == "pending":
        status_enum = ConnectionStatus.PENDING
    else:
        status_enum = ConnectionStatus.ACCEPTED  # Default
    
    # Get total count
    total = await db["connections"].count_documents({
        "$or": [
            {"requester_id": user_id, "status": status_enum},
            {"receiver_id": user_id, "status": status_enum}
        ]
    })
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get connections
    connections_cursor = db["connections"].find({
        "$or": [
            {"requester_id": user_id, "status": status_enum},
            {"receiver_id": user_id, "status": status_enum}
        ]
    }).sort("updated_at", -1).skip(skip).limit(limit)
    
    connections_list = await connections_cursor.to_list(limit)
    
    # Format connections
    connections = []
    for conn in connections_list:
        # Determine which user is the "other" user
        if conn["requester_id"] == user_id:
            other_user = {
                "user_id": conn["receiver_id"],
                "name": conn["receiver_name"],
                "role": conn["receiver_role"],
                "specialization": conn.get("receiver_specialization"),
                "territory": conn.get("receiver_territory")
            }
        else:
            other_user = {
                "user_id": conn["requester_id"],
                "name": conn["requester_name"],
                "role": conn["requester_role"],
                "specialization": conn.get("requester_specialization"),
                "territory": conn.get("requester_territory")
            }
        
        other_user["connected_at"] = conn["updated_at"]
        connections.append(other_user)
    
    return {
        "connections": connections,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def remove_connection(
    connection_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Remove a connection.
    ONLY DOCTORS and ADMINS can access network features.
    
    Args:
        connection_id: Connection ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    # Block MRs from using network features
    if current_user.get("role") == "MR":
        raise HTTPException(
            status_code=403,
            detail="Network features are only available for doctors"
        )
    
    db = get_database()
    
    # Get connection
    try:
        connection = await db["connections"].find_one({"_id": ObjectId(connection_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid connection ID")
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Check if current user is part of this connection
    user_id = current_user["_id"]
    if connection["requester_id"] != user_id and connection["receiver_id"] != user_id:
        raise HTTPException(status_code=403, detail="You can only remove your own connections")
    
    # Check if status is accepted
    if connection["status"] != ConnectionStatus.ACCEPTED:  # No .value needed
        raise HTTPException(status_code=400, detail="Connection is not established")
    
    # Delete the connection
    await db["connections"].delete_one({"_id": ObjectId(connection_id)})
    
    return {"message": "Connection removed successfully"}


async def block_user(
    user_id_to_block: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Block a user.
    ONLY DOCTORS and ADMINS can access network features.
    
    Args:
        user_id_to_block: User ID to block
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    # Block MRs from using network features
    if current_user.get("role") == "MR":
        raise HTTPException(
            status_code=403,
            detail="Network features are only available for doctors"
        )
    
    db = get_database()
    
    requester_id = current_user["_id"]
    
    # Validate user_id_to_block format first
    if not ObjectId.is_valid(user_id_to_block):
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    # Cannot block self
    if requester_id == user_id_to_block:
        raise HTTPException(status_code=400, detail="Cannot block yourself")
    
    # Check if user exists (ONLY doctors can be blocked in network)
    user = await db["doctors"].find_one({"_id": ObjectId(user_id_to_block)})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if connection exists
    existing = await db["connections"].find_one({
        "$or": [
            {"requester_id": requester_id, "receiver_id": user_id_to_block},
            {"requester_id": user_id_to_block, "receiver_id": requester_id}
        ]
    })
    
    if existing:
        # Update existing connection to blocked (RULE 2: UPDATE with Enum)
        await db["connections"].update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "status": ConnectionStatus.BLOCKED,  # No .value needed
                    "updated_at": datetime.utcnow()
                }
            }
        )
    else:
        # Get requester details (current user - must be doctor or admin)
        requester = await db["doctors"].find_one({"_id": ObjectId(requester_id)})
        if not requester:
            requester = await db["admins"].find_one({"_id": ObjectId(requester_id)})
        
        if not requester:
            raise HTTPException(status_code=404, detail="Requester not found")
        
        # Create new blocked connection (RULE 1: INSERT with model)
        connection = ConnectionInDB(
            requester_id=requester_id,
            receiver_id=user_id_to_block,
            requester_name=requester.get("name", ""),
            requester_role=requester.get("role", ""),
            requester_specialization=requester.get("specialization"),
            requester_territory=requester.get("territory"),
            receiver_name=user.get("name", ""),
            receiver_role=user.get("role", ""),
            receiver_specialization=user.get("specialization"),
            receiver_territory=user.get("territory"),
            status=ConnectionStatus.BLOCKED
        )
        await db["connections"].insert_one(connection.model_dump())
    
    return {"message": "User blocked successfully"}


async def unblock_user(
    user_id_to_unblock: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Unblock a user.
    ONLY DOCTORS and ADMINS can access network features.
    
    Args:
        user_id_to_unblock: User ID to unblock
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    # Block MRs from using network features
    if current_user.get("role") == "MR":
        raise HTTPException(
            status_code=403,
            detail="Network features are only available for doctors"
        )
    
    db = get_database()
    
    requester_id = current_user["_id"]
    
    # Validate user_id_to_unblock format first
    if not ObjectId.is_valid(user_id_to_unblock):
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    # Find blocked connection
    connection = await db["connections"].find_one({
        "$or": [
            {"requester_id": requester_id, "receiver_id": user_id_to_unblock, "status": ConnectionStatus.BLOCKED},  # No .value needed
            {"requester_id": user_id_to_unblock, "receiver_id": requester_id, "status": ConnectionStatus.BLOCKED}
        ]
    })
    
    if not connection:
        raise HTTPException(status_code=404, detail="No blocked connection found with this user")
    
    # Check if there was an accepted connection before blocking
    # If accepted_at exists, it means they were connected before
    if connection.get("accepted_at"):
        # Restore the connection to accepted status
        await db["connections"].update_one(
            {"_id": connection["_id"]},
            {
                "$set": {
                    "status": ConnectionStatus.ACCEPTED,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return {"message": "User unblocked and connection restored"}
    else:
        # They were never connected, just blocked - delete the connection
        await db["connections"].delete_one({"_id": connection["_id"]})
        return {"message": "User unblocked successfully"}

