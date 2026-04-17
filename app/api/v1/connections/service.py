"""
Connections Business Logic
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from bson import ObjectId
from app.database import get_database
from fastapi import HTTPException
from app.api.v1.notifications.helpers import notify_connection_request, notify_connection_accepted


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
    Discover users to connect with.
    
    Args:
        current_user: Current authenticated user
        role: Filter by role (DOCTOR or MR)
        search: Search by name
        specialization: Filter doctors by specialization
        territory: Filter MRs by territory
        page: Page number
        limit: Users per page
    
    Returns:
        dict: Paginated list of users
    """
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
    
    # Build query for both collections
    base_query = {
        "_id": {"$nin": [ObjectId(uid) if len(uid) == 24 else uid for uid in excluded_ids]},
        "is_active": True
    }
    
    # Apply search filter
    if search:
        base_query["name"] = {"$regex": search, "$options": "i"}
    
    all_users = []
    
    # Query doctors if role is None or DOCTOR
    if role is None or role == "DOCTOR":
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
    
    # Query MRs if role is None or MR
    if role is None or role == "MR":
        mr_query = base_query.copy()
        if territory:
            mr_query["territory"] = {"$regex": territory, "$options": "i"}
        
        mrs_cursor = db["mrs"].find(mr_query)
        mrs_list = await mrs_cursor.to_list(None)
        
        for mr in mrs_list:
            all_users.append({
                "user_id": str(mr["_id"]),
                "name": mr.get("name", ""),
                "role": "MR",
                "specialization": None,
                "hospital": None,
                "territory": mr.get("territory")
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
    
    Args:
        receiver_id: User ID to send request to
        current_user: Current authenticated user
    
    Returns:
        dict: Connection request details
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    requester_id = current_user["_id"]
    
    # Cannot send request to self
    if requester_id == receiver_id:
        raise HTTPException(status_code=400, detail="Cannot send connection request to yourself")
    
    # Get receiver details
    receiver = await db["doctors"].find_one({"_id": ObjectId(receiver_id)})
    if not receiver:
        receiver = await db["mrs"].find_one({"_id": ObjectId(receiver_id)})
    
    if not receiver:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if receiver is admin
    if receiver.get("role") == "ADMIN":
        raise HTTPException(status_code=400, detail="Cannot send connection request to admin")
    
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
    
    # Create connection request
    connection_doc = {
        "requester_id": requester_id,
        "requester_name": current_user.get("name", ""),
        "requester_role": current_user.get("role", ""),
        "requester_specialization": current_user.get("specialization"),
        "requester_territory": current_user.get("territory"),
        "receiver_id": receiver_id,
        "receiver_name": receiver.get("name", ""),
        "receiver_role": receiver.get("role", ""),
        "receiver_specialization": receiver.get("specialization"),
        "receiver_territory": receiver.get("territory"),
        "status": "pending",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db["connections"].insert_one(connection_doc)
    
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
    
    Args:
        current_user: Current authenticated user
        page: Page number
        limit: Requests per page
    
    Returns:
        dict: Paginated list of received requests
    """
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
        "status": "pending"
    })
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get requests
    requests_cursor = db["connections"].find({
        "receiver_id": user_id,
        "status": "pending"
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
    
    Args:
        current_user: Current authenticated user
        page: Page number
        limit: Requests per page
    
    Returns:
        dict: Paginated list of sent requests
    """
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
        "status": "pending"
    })
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get requests
    requests_cursor = db["connections"].find({
        "requester_id": user_id,
        "status": "pending"
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
    
    Args:
        connection_id: Connection ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
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
    if connection["status"] != "pending":
        raise HTTPException(status_code=400, detail="Connection request is not pending")
    
    # Update status to accepted
    await db["connections"].update_one(
        {"_id": ObjectId(connection_id)},
        {
            "$set": {
                "status": "accepted",
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
    
    Args:
        connection_id: Connection ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
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
    if connection["status"] != "pending":
        raise HTTPException(status_code=400, detail="Connection request is not pending")
    
    # Update status to rejected
    await db["connections"].update_one(
        {"_id": ObjectId(connection_id)},
        {
            "$set": {
                "status": "rejected",
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
    
    Args:
        connection_id: Connection ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
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
    if connection["status"] != "pending":
        raise HTTPException(status_code=400, detail="Connection request is not pending")
    
    # Delete the request
    await db["connections"].delete_one({"_id": ObjectId(connection_id)})
    
    return {"message": "Connection request cancelled"}


async def get_my_connections(
    current_user: Dict,
    page: int = 1,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get current user's connections.
    
    Args:
        current_user: Current authenticated user
        page: Page number
        limit: Connections per page
    
    Returns:
        dict: Paginated list of connections
    """
    db = get_database()
    
    # Validate and limit page size
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    user_id = current_user["_id"]
    
    # Get total count
    total = await db["connections"].count_documents({
        "$or": [
            {"requester_id": user_id, "status": "accepted"},
            {"receiver_id": user_id, "status": "accepted"}
        ]
    })
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get connections
    connections_cursor = db["connections"].find({
        "$or": [
            {"requester_id": user_id, "status": "accepted"},
            {"receiver_id": user_id, "status": "accepted"}
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
    
    Args:
        connection_id: Connection ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
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
    if connection["status"] != "accepted":
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
    
    Args:
        user_id_to_block: User ID to block
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    requester_id = current_user["_id"]
    
    # Cannot block self
    if requester_id == user_id_to_block:
        raise HTTPException(status_code=400, detail="Cannot block yourself")
    
    # Check if user exists
    user = await db["doctors"].find_one({"_id": ObjectId(user_id_to_block)})
    if not user:
        user = await db["mrs"].find_one({"_id": ObjectId(user_id_to_block)})
    
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
        # Update existing connection to blocked
        await db["connections"].update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "status": "blocked",
                    "updated_at": datetime.utcnow()
                }
            }
        )
    else:
        # Create new blocked connection
        connection_doc = {
            "requester_id": requester_id,
            "requester_name": current_user.get("name", ""),
            "requester_role": current_user.get("role", ""),
            "requester_specialization": current_user.get("specialization"),
            "requester_territory": current_user.get("territory"),
            "receiver_id": user_id_to_block,
            "receiver_name": user.get("name", ""),
            "receiver_role": user.get("role", ""),
            "receiver_specialization": user.get("specialization"),
            "receiver_territory": user.get("territory"),
            "status": "blocked",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        await db["connections"].insert_one(connection_doc)
    
    return {"message": "User blocked successfully"}


async def unblock_user(
    user_id_to_unblock: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Unblock a user.
    
    Args:
        user_id_to_unblock: User ID to unblock
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    requester_id = current_user["_id"]
    
    # Find blocked connection
    connection = await db["connections"].find_one({
        "$or": [
            {"requester_id": requester_id, "receiver_id": user_id_to_unblock, "status": "blocked"},
            {"requester_id": user_id_to_unblock, "receiver_id": requester_id, "status": "blocked"}
        ]
    })
    
    if not connection:
        raise HTTPException(status_code=404, detail="No blocked connection found with this user")
    
    # Delete the blocked connection
    await db["connections"].delete_one({"_id": connection["_id"]})
    
    return {"message": "User unblocked successfully"}
