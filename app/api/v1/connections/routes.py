"""
Connections API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Optional
from app.core.auth import get_current_user, require_doctor_or_admin
from app.api.v1.connections.schemas import (
    DiscoverResponse,
    ConnectionRequestResponse,
    ConnectionRequestListResponse,
    ConnectionListResponse
)
from app.api.v1.connections import service


router = APIRouter()


@router.get("/discover", response_model=DiscoverResponse)
async def discover_users_endpoint(
    role: Optional[str] = Query(None, regex="^(DOCTOR|MR)$", description="Filter by role"),
    search: Optional[str] = Query(None, description="Search by name"),
    specialization: Optional[str] = Query(None, description="Filter doctors by specialization"),
    territory: Optional[str] = Query(None, description="Filter MRs by territory"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Users per page (max 50)"),
    current_user: Dict = Depends(require_doctor_or_admin)
):
    """
    Discover users to connect with.
    
    **Access:** Doctor, Admin (MRs blocked)
    
    **Purpose:**
    Find doctors to connect with. Only doctors visible in network.
    
    **Flow:**
    1. User opens "Discover" section
    2. System retrieves all doctors except:
       - Current user
       - Already connected users
       - Users with pending requests (sent or received)
       - Blocked users
    3. Returns paginated list with filters
    
    **Query Parameters:**
    - `role`: Filter by DOCTOR (MR option removed)
    - `search`: Search by name (optional)
    - `specialization`: Filter doctors by specialization (optional)

    - `territory`: Filter MRs by territory (optional)
    - `page`: Page number (default: 1)
    - `limit`: Users per page (default: 20, max: 50)
    
    **Response:**
    ```json
    {
        "users": [
            {
                "user_id": "user123",
                "name": "Dr. Sarah Sharma",
                "role": "DOCTOR",
                "specialization": "Cardiology",
                "hospital": "Apollo Hospital"
            },
            {
                "user_id": "user456",
                "name": "Raj Kumar",
                "role": "MR",
                "territory": "Mumbai"
            }
        ],
        "total": 50,
        "page": 1,
        "limit": 20,
        "total_pages": 3
    }
    ```
    
    **Use Cases:**
    - Find doctors in specific specialization
    - Find MRs in specific territory
    - Search for specific users by name
    - Browse all available users to connect
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can discover users"
        )
    
    return await service.discover_users(
        current_user, role, search, specialization, territory, page, limit
    )


@router.post("/request/{user_id}", response_model=ConnectionRequestResponse)
async def send_connection_request_endpoint(
    user_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Send connection request to another user.
    
    **Access:** Doctor, MR
    
    **Purpose:**
    Send a connection request to another doctor or MR.
    
    **Flow:**
    1. User clicks "Connect" on another user's profile
    2. System validates:
       - Not sending to self
       - User exists and is not admin
       - No existing connection (any status)
    3. Creates pending connection request
    4. Returns success message
    
    **Path Parameters:**
    - `user_id`: User ID to send request to
    
    **Response:**
    ```json
    {
        "connection_id": "conn123",
        "receiver_name": "Dr. Priya Patel",
        "status": "pending",
        "message": "Connection request sent successfully"
    }
    ```
    
    **Rules:**
    - Cannot send request to yourself
    - Cannot send request to admin
    - Cannot send duplicate requests
    - Cannot send if already connected
    - Cannot send if blocked
    
    **Errors:**
    - 400: Invalid request (self, duplicate, blocked)
    - 404: User not found
    
    **Use Cases:**
    - Connect with other doctors
    - Connect with MRs
    - Build professional network
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can send connection requests"
        )
    
    return await service.send_connection_request(user_id, current_user)


@router.get("/requests/received", response_model=ConnectionRequestListResponse)
async def get_received_requests_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Requests per page (max 50)"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get connection requests received by current user.
    
    **Access:** Doctor, MR
    
    **Purpose:**
    View all pending connection requests sent to you.
    
    **Flow:**
    1. User opens "Requests" section
    2. System retrieves all pending requests where user is receiver
    3. Returns paginated list sorted by newest first
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Requests per page (default: 20, max: 50)
    
    **Response:**
    ```json
    {
        "requests": [
            {
                "connection_id": "conn123",
                "requester_id": "user789",
                "requester_name": "Dr. Priya Patel",
                "requester_role": "DOCTOR",
                "requester_specialization": "Neurology",
                "status": "pending",
                "created_at": "2024-04-10T10:00:00"
            }
        ],
        "total": 5,
        "page": 1,
        "limit": 20,
        "total_pages": 1
    }
    ```
    
    **Use Cases:**
    - Review who wants to connect
    - Accept or reject requests
    - Manage incoming connections
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can access this endpoint"
        )
    
    return await service.get_received_requests(current_user, page, limit)


@router.get("/requests/sent", response_model=ConnectionRequestListResponse)
async def get_sent_requests_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Requests per page (max 50)"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get connection requests sent by current user.
    
    **Access:** Doctor, MR
    
    **Purpose:**
    View all pending connection requests you've sent.
    
    **Flow:**
    1. User opens "Sent Requests" section
    2. System retrieves all pending requests where user is requester
    3. Returns paginated list sorted by newest first
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Requests per page (default: 20, max: 50)
    
    **Response:**
    ```json
    {
        "requests": [
            {
                "connection_id": "conn123",
                "requester_id": "user789",
                "requester_name": "Dr. Priya Patel",
                "requester_role": "DOCTOR",
                "requester_specialization": "Neurology",
                "status": "pending",
                "created_at": "2024-04-10T10:00:00"
            }
        ],
        "total": 3,
        "page": 1,
        "limit": 20,
        "total_pages": 1
    }
    ```
    
    **Use Cases:**
    - Track sent requests
    - Cancel pending requests
    - See who hasn't responded yet
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can access this endpoint"
        )
    
    return await service.get_sent_requests(current_user, page, limit)



@router.post("/requests/{connection_id}/accept")
async def accept_request_endpoint(
    connection_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Accept a connection request.
    
    **Access:** Doctor, MR (only receiver)
    
    **Purpose:**
    Accept a pending connection request sent to you.
    
    **Flow:**
    1. User clicks "Accept" on a request
    2. System validates:
       - Request exists and is pending
       - Current user is the receiver
    3. Updates status to "accepted"
    4. Connection is established
    
    **Path Parameters:**
    - `connection_id`: Connection request ID
    
    **Response:**
    ```json
    {
        "message": "Connection request accepted",
        "connection_id": "conn123"
    }
    ```
    
    **Rules:**
    - Only receiver can accept
    - Request must be pending
    
    **Errors:**
    - 400: Invalid ID or not pending
    - 403: Not authorized (not receiver)
    - 404: Request not found
    
    **Use Cases:**
    - Accept connection from another user
    - Build your network
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can accept requests"
        )
    
    return await service.accept_request(connection_id, current_user)


@router.post("/requests/{connection_id}/reject")
async def reject_request_endpoint(
    connection_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Reject a connection request.
    
    **Access:** Doctor, MR (only receiver)
    
    **Purpose:**
    Reject a pending connection request sent to you.
    
    **Flow:**
    1. User clicks "Reject" on a request
    2. System validates:
       - Request exists and is pending
       - Current user is the receiver
    3. Updates status to "rejected"
    4. Request is declined
    
    **Path Parameters:**
    - `connection_id`: Connection request ID
    
    **Response:**
    ```json
    {
        "message": "Connection request rejected"
    }
    ```
    
    **Rules:**
    - Only receiver can reject
    - Request must be pending
    - Requester can send again later
    
    **Errors:**
    - 400: Invalid ID or not pending
    - 403: Not authorized (not receiver)
    - 404: Request not found
    
    **Use Cases:**
    - Decline unwanted connections
    - Manage incoming requests
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can reject requests"
        )
    
    return await service.reject_request(connection_id, current_user)


@router.delete("/requests/{connection_id}/cancel")
async def cancel_request_endpoint(
    connection_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Cancel a sent connection request.
    
    **Access:** Doctor, MR (only requester)
    
    **Purpose:**
    Cancel a pending connection request you sent.
    
    **Flow:**
    1. User clicks "Cancel" on a sent request
    2. System validates:
       - Request exists and is pending
       - Current user is the requester
    3. Deletes the request
    
    **Path Parameters:**
    - `connection_id`: Connection request ID
    
    **Response:**
    ```json
    {
        "message": "Connection request cancelled"
    }
    ```
    
    **Rules:**
    - Only requester can cancel
    - Request must be pending
    - Request is permanently deleted
    
    **Errors:**
    - 400: Invalid ID or not pending
    - 403: Not authorized (not requester)
    - 404: Request not found
    
    **Use Cases:**
    - Cancel accidental requests
    - Change your mind
    - Manage sent requests
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can cancel requests"
        )
    
    return await service.cancel_request(connection_id, current_user)


@router.get("", response_model=ConnectionListResponse)
async def get_my_connections_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Connections per page (max 50)"),
    status: Optional[str] = Query("accepted", regex="^(accepted|blocked|pending)$", description="Filter by connection status"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get current user's connections filtered by status.
    
    **Access:** Doctor, MR
    
    **Purpose:**
    View your connections, blocked users, or pending requests.
    
    **Flow:**
    1. User opens "My Connections" or "Blocked Users" section
    2. System retrieves connections filtered by status
    3. Returns paginated list sorted by most recent
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Connections per page (default: 20, max: 50)
    - `status`: Filter by status (default: "accepted")
      - `accepted`: Your established connections
      - `blocked`: Users you have blocked
      - `pending`: Pending connection requests (sent or received)
    
    **Response:**
    ```json
    {
        "connections": [
            {
                "user_id": "user789",
                "name": "Dr. Priya Patel",
                "role": "DOCTOR",
                "specialization": "Neurology",
                "connected_at": "2024-04-10T11:00:00"
            }
        ],
        "total": 25,
        "page": 1,
        "limit": 20,
        "total_pages": 2
    }
    ```
    
    **Examples:**
    - `GET /connections` - Get accepted connections (default)
    - `GET /connections?status=blocked` - Get blocked users
    - `GET /connections?status=pending` - Get pending requests
    
    **Use Cases:**
    - View your network
    - Manage blocked users
    - Check pending requests
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can access this endpoint"
        )
    
    return await service.get_my_connections(current_user, page, limit, status)


@router.delete("/{connection_id}")
async def remove_connection_endpoint(
    connection_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Remove a connection.
    
    **Access:** Doctor, MR
    
    **Purpose:**
    Remove/unfriend an established connection.
    
    **Flow:**
    1. User clicks "Remove Connection"
    2. System validates:
       - Connection exists and is accepted
       - Current user is part of connection
    3. Deletes the connection
    4. Users are no longer connected
    
    **Path Parameters:**
    - `connection_id`: Connection ID
    
    **Response:**
    ```json
    {
        "message": "Connection removed successfully"
    }
    ```
    
    **Rules:**
    - Can only remove your own connections
    - Connection must be accepted
    - Permanently deleted
    
    **Errors:**
    - 400: Invalid ID or not accepted
    - 403: Not authorized
    - 404: Connection not found
    
    **Use Cases:**
    - Unfriend users
    - Clean up connections
    - Manage your network
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can remove connections"
        )
    
    return await service.remove_connection(connection_id, current_user)


@router.post("/{user_id}/block")
async def block_user_endpoint(
    user_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Block a user.
    
    **Access:** Doctor, MR
    
    **Purpose:**
    Block a user to prevent them from sending connection requests.
    
    **Flow:**
    1. User clicks "Block User"
    2. System validates user exists
    3. Creates or updates connection with status "blocked"
    4. User cannot send requests anymore
    
    **Path Parameters:**
    - `user_id`: User ID to block
    
    **Response:**
    ```json
    {
        "message": "User blocked successfully"
    }
    ```
    
    **Rules:**
    - Cannot block yourself
    - Blocks existing connection if any
    - Prevents future requests
    
    **Errors:**
    - 400: Cannot block self
    - 404: User not found
    
    **Use Cases:**
    - Block unwanted users
    - Prevent spam requests
    - Manage privacy
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can block users"
        )
    
    return await service.block_user(user_id, current_user)


@router.delete("/{user_id}/unblock")
async def unblock_user_endpoint(
    user_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Unblock a user.
    
    **Access:** Doctor, MR
    
    **Purpose:**
    Unblock a previously blocked user.
    
    **Flow:**
    1. User clicks "Unblock User"
    2. System finds blocked connection
    3. Deletes the blocked connection
    4. User can send requests again
    
    **Path Parameters:**
    - `user_id`: User ID to unblock
    
    **Response:**
    ```json
    {
        "message": "User unblocked successfully"
    }
    ```
    
    **Rules:**
    - Must have blocked connection
    - Permanently removes block
    
    **Errors:**
    - 404: No blocked connection found
    
    **Use Cases:**
    - Unblock users
    - Allow requests again
    - Manage blocked list
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can unblock users"
        )
    
    return await service.unblock_user(user_id, current_user)
