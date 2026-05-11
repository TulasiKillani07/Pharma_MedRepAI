"""
Groups API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict
from app.core.auth import get_current_user, require_doctor
from app.api.v1.groups.schemas import (
    GroupCreate, GroupUpdate, GroupResponse, GroupDetailResponse,
    GroupListResponse, AddMembersRequest, AddMembersResponse,
    GroupMessageCreate, GroupMessageResponse, GroupMessageListResponse
)
from app.api.v1.groups import service


router = APIRouter()


@router.post("", response_model=GroupResponse, status_code=201)
async def create_group_endpoint(
    group_data: GroupCreate,
    current_user: Dict = Depends(require_doctor)
):
    """
    Create a new group.
    
    **Access:** Doctor, MR only
    
    **Purpose:**
    Create a group chat with multiple members.
    
    **Flow:**
    1. User provides group name and optional description
    2. Optionally adds initial members (must be connected)
    3. Creator becomes admin automatically
    4. Group is created and ready for messaging
    
    **Request Body:**
    ```json
    {
        "group_name": "Cardiology Team",
        "group_description": "Discussion for cardiology specialists",
        "member_ids": ["user123", "user456"]
    }
    ```
    
    **Response:**
    ```json
    {
        "group_id": "group123",
        "group_name": "Cardiology Team",
        "group_description": "Discussion for cardiology specialists",
        "created_by": "user789",
        "members_count": 3,
        "admins_count": 1,
        "created_at": "2024-04-13T10:00:00"
    }
    ```
    
    **Rules:**
    - Group name required (3-100 characters)
    - Description optional (max 500 characters)
    - Can only add connected users
    - Max 50 members per group
    - Creator becomes admin automatically
    
    **Use Cases:**
    - Create team discussion groups
    - Form specialty-based groups
    - Create project collaboration groups
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can create groups"
        )
    
    return await service.create_group(
        group_data.group_name,
        group_data.group_description,
        group_data.member_ids or [],
        current_user
    )


@router.get("", response_model=GroupListResponse)
async def get_my_groups_endpoint(
    current_user: Dict = Depends(require_doctor)
):
    """
    Get all groups where user is a member.
    
    **Access:** Doctor, MR only
    
    **Purpose:**
    View all groups you're part of.
    
    **Flow:**
    1. User opens groups section
    2. System retrieves all groups where user is member
    3. Returns list sorted by most recent activity
    
    **Response:**
    ```json
    {
        "groups": [
            {
                "group_id": "group123",
                "group_name": "Cardiology Team",
                "last_message": "Great discussion today!",
                "last_message_at": "2024-04-13T16:45:00",
                "unread_count": 5,
                "members_count": 5
            }
        ],
        "total": 3
    }
    ```
    
    **Sorting:**
    - Most recent activity first (by last_message_at)
    
    **Use Cases:**
    - View all your groups
    - See unread message counts
    - Access group chats
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can access groups"
        )
    
    return await service.get_my_groups(current_user)


@router.get("/{group_id}", response_model=GroupDetailResponse)
async def get_group_details_endpoint(
    group_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    Get detailed group information.
    
    **Access:** Doctor, MR (members only)
    
    **Purpose:**
    View detailed information about a group including all members.
    
    **Flow:**
    1. User clicks on group info
    2. System retrieves group details
    3. Returns complete group information
    
    **Path Parameters:**
    - `group_id`: Group ID
    
    **Response:**
    ```json
    {
        "group_id": "group123",
        "group_name": "Cardiology Team",
        "group_description": "Discussion group",
        "created_by": "user123",
        "admins": ["user123", "user456"],
        "members": [
            {
                "user_id": "user123",
                "name": "Dr. Sarah Sharma",
                "role": "DOCTOR",
                "is_admin": true,
                "joined_at": "2024-04-13T10:00:00"
            }
        ],
        "members_count": 5,
        "created_at": "2024-04-13T10:00:00"
    }
    ```
    
    **Use Cases:**
    - View group members
    - See who are admins
    - Check group details
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can access groups"
        )
    
    return await service.get_group_details(group_id, current_user)


@router.put("/{group_id}")
async def update_group_endpoint(
    group_id: str,
    group_data: GroupUpdate,
    current_user: Dict = Depends(require_doctor)
):
    """
    Update group information (admin only).
    
    **Access:** Group admins only
    
    **Purpose:**
    Update group name and description.
    
    **Flow:**
    1. Admin edits group info
    2. System validates user is admin
    3. Updates group information
    
    **Path Parameters:**
    - `group_id`: Group ID
    
    **Request Body:**
    ```json
    {
        "group_name": "Cardiology Specialists",
        "group_description": "Updated description"
    }
    ```
    
    **Response:**
    ```json
    {
        "message": "Group updated successfully"
    }
    ```
    
    **Rules:**
    - Only admins can update
    - Group name: 3-100 characters
    - Description: max 500 characters
    
    **Use Cases:**
    - Update group name
    - Change group description
    - Rebrand group
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can update groups"
        )
    
    return await service.update_group(
        group_id,
        group_data.group_name,
        group_data.group_description,
        current_user
    )


@router.post("/{group_id}/members", response_model=AddMembersResponse)
async def add_members_endpoint(
    group_id: str,
    members_data: AddMembersRequest,
    current_user: Dict = Depends(require_doctor)
):
    """
    Add members to group (admin only).
    
    **Access:** Group admins only
    
    **Purpose:**
    Add new members to the group.
    
    **Flow:**
    1. Admin selects users to add
    2. System validates users are connected
    3. Adds members to group
    4. New members can see group messages
    
    **Path Parameters:**
    - `group_id`: Group ID
    
    **Request Body:**
    ```json
    {
        "user_ids": ["user789", "user012"]
    }
    ```
    
    **Response:**
    ```json
    {
        "message": "Members added successfully",
        "added": 2,
        "failed": []
    }
    ```
    
    **Rules:**
    - Only admins can add members
    - Can only add connected users
    - Max 10 users per request
    - Group limit: 50 members
    - Cannot add existing members
    
    **Use Cases:**
    - Expand group membership
    - Add new team members
    - Invite collaborators
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can add members"
        )
    
    return await service.add_members(
        group_id,
        members_data.user_ids,
        current_user
    )


@router.delete("/{group_id}/members/{member_id}")
async def remove_member_endpoint(
    group_id: str,
    member_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    Remove a member from group (admin only).
    
    **Access:** Group admins only
    
    **Purpose:**
    Remove a member from the group.
    
    **Flow:**
    1. Admin selects member to remove
    2. System validates user is admin
    3. Removes member from group
    4. Member loses access to group
    
    **Path Parameters:**
    - `group_id`: Group ID
    - `member_id`: Member ID to remove
    
    **Response:**
    ```json
    {
        "message": "Member removed successfully"
    }
    ```
    
    **Rules:**
    - Only admins can remove members
    - Cannot remove creator
    - Removed member loses all access
    
    **Use Cases:**
    - Remove inactive members
    - Handle member violations
    - Manage group membership
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can remove members"
        )
    
    return await service.remove_member(group_id, member_id, current_user)


@router.post("/{group_id}/leave")
async def leave_group_endpoint(
    group_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    Leave a group.
    
    **Access:** Group members
    
    **Purpose:**
    Leave a group you're part of.
    
    **Flow:**
    1. User clicks "Leave Group"
    2. System removes user from group
    3. If creator leaves, ownership transfers
    4. User loses access to group
    
    **Path Parameters:**
    - `group_id`: Group ID
    
    **Response:**
    ```json
    {
        "message": "You have left the group"
    }
    ```
    
    **Rules:**
    - Any member can leave
    - If creator leaves, ownership transfers to another admin or oldest member
    - Lose all access after leaving
    
    **Use Cases:**
    - Exit unwanted groups
    - Leave inactive groups
    - Manage group memberships
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can leave groups"
        )
    
    return await service.leave_group(group_id, current_user)


@router.post("/{group_id}/admins/{member_id}")
async def make_admin_endpoint(
    group_id: str,
    member_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    Make a member an admin (admin only).
    
    **Access:** Group admins only
    
    **Purpose:**
    Promote a member to admin role.
    
    **Flow:**
    1. Admin selects member to promote
    2. System validates user is admin
    3. Promotes member to admin
    4. New admin gets admin privileges
    
    **Path Parameters:**
    - `group_id`: Group ID
    - `member_id`: Member ID to promote
    
    **Response:**
    ```json
    {
        "message": "Member promoted to admin"
    }
    ```
    
    **Rules:**
    - Only admins can promote
    - Member must exist in group
    - Cannot promote existing admins
    
    **Use Cases:**
    - Share admin responsibilities
    - Delegate group management
    - Distribute moderation duties
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can manage admins"
        )
    
    return await service.make_admin(group_id, member_id, current_user)


@router.delete("/{group_id}/admins/{admin_id}")
async def remove_admin_endpoint(
    group_id: str,
    admin_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    Remove admin role from a member (admin only).
    
    **Access:** Group admins only
    
    **Purpose:**
    Demote an admin to regular member.
    
    **Flow:**
    1. Admin selects admin to demote
    2. System validates user is admin
    3. Removes admin role
    4. User becomes regular member
    
    **Path Parameters:**
    - `group_id`: Group ID
    - `admin_id`: Admin ID to demote
    
    **Response:**
    ```json
    {
        "message": "Admin role removed"
    }
    ```
    
    **Rules:**
    - Only admins can demote
    - Cannot demote creator
    - Must have at least 1 admin
    
    **Use Cases:**
    - Revoke admin privileges
    - Manage admin team
    - Handle admin violations
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can manage admins"
        )
    
    return await service.remove_admin(group_id, admin_id, current_user)


@router.post("/{group_id}/messages", response_model=GroupMessageResponse, status_code=201)
async def send_group_message_endpoint(
    group_id: str,
    message_data: GroupMessageCreate,
    current_user: Dict = Depends(require_doctor)
):
    """
    Send a message to group.
    
    **Access:** Group members only
    
    **Purpose:**
    Send a text message to all group members.
    
    **Flow:**
    1. User types message and sends
    2. System validates user is member
    3. Creates message in group
    4. All members see the message
    5. Increments unread count for others
    
    **Path Parameters:**
    - `group_id`: Group ID
    
    **Request Body:**
    ```json
    {
        "content": "Hello everyone! Meeting at 3 PM today."
    }
    ```
    
    **Response:**
    ```json
    {
        "message_id": "msg123",
        "group_id": "group123",
        "sender_id": "user123",
        "sender_name": "Dr. Sarah Sharma",
        "sender_role": "DOCTOR",
        "content": "Hello everyone!",
        "message_type": "text",
        "shared_post": null,
        "read_by_count": 1,
        "created_at": "2024-04-13T17:00:00"
    }
    ```
    
    **Rules:**
    - Only members can send
    - Content: 1-2000 characters
    - Message visible to all members
    - Sender marked as read automatically
    
    **Use Cases:**
    - Group discussions
    - Team announcements
    - Collaborative conversations
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can send messages"
        )
    
    return await service.send_group_message(
        group_id,
        message_data.content,
        current_user
    )


@router.get("/{group_id}/messages", response_model=GroupMessageListResponse)
async def get_group_messages_endpoint(
    group_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Messages per page (max 100)"),
    current_user: Dict = Depends(require_doctor)
):
    """
    Get messages in a group.
    
    **Access:** Group members only
    
    **Purpose:**
    View message history in a group.
    
    **Flow:**
    1. User opens group chat
    2. System retrieves messages with pagination
    3. Returns messages sorted oldest first
    
    **Path Parameters:**
    - `group_id`: Group ID
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Messages per page (default: 50, max: 100)
    
    **Response:**
    ```json
    {
        "messages": [
            {
                "message_id": "msg123",
                "group_id": "group123",
                "sender_name": "Dr. Sarah Sharma",
                "sender_role": "DOCTOR",
                "content": "Hello everyone!",
                "message_type": "text",
                "read_by_count": 5,
                "created_at": "2024-04-13T16:00:00"
            }
        ],
        "total": 50,
        "page": 1,
        "limit": 50,
        "total_pages": 1
    }
    ```
    
    **Sorting:**
    - Oldest messages first (natural chat order)
    
    **Use Cases:**
    - View group chat history
    - Load more messages
    - Display conversation
    
    **Frontend Polling:**
    ```javascript
    // Poll every 3 seconds for new messages
    setInterval(async () => {
        const messages = await getGroupMessages(groupId, 1, 50);
        // Update UI with new messages
    }, 3000);
    ```
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can access messages"
        )
    
    return await service.get_group_messages(group_id, current_user, page, limit)


@router.post("/{group_id}/read")
async def mark_group_as_read_endpoint(
    group_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    Mark all group messages as read.
    
    **Access:** Group members only
    
    **Purpose:**
    Mark all unread messages as read when viewing group.
    
    **Flow:**
    1. User opens group chat
    2. System marks all messages as read
    3. Resets unread count to 0
    
    **Path Parameters:**
    - `group_id`: Group ID
    
    **Response:**
    ```json
    {
        "message": "Messages marked as read",
        "marked_count": 5
    }
    ```
    
    **Rules:**
    - Adds user to read_by array
    - Resets unread_count for user
    - Only affects unread messages
    
    **Use Cases:**
    - Clear unread badge
    - Mark messages as seen
    - Update read status
    
    **Frontend Usage:**
    ```javascript
    // When user opens group
    await markGroupAsRead(groupId);
    ```
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can mark messages as read"
        )
    
    return await service.mark_group_as_read(group_id, current_user)



@router.delete("/{group_id}/clear-chat")
async def clear_left_group_endpoint(
    group_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    Clear/delete a left group from your view.
    
    **Access:** Users who have left the group
    
    **Purpose:**
    Remove a left group from your groups list (like WhatsApp's "Delete Chat").
    
    **Flow:**
    1. User leaves a group
    2. Group appears in list with status="left"
    3. User decides they don't want to see it anymore
    4. User clicks "Delete Chat" or "Clear Chat"
    5. Group is removed from their view only
    6. Other members are not affected
    
    **Path Parameters:**
    - `group_id`: Group ID to clear
    
    **Response:**
    ```json
    {
        "message": "Group chat cleared from your view"
    }
    ```
    
    **Rules:**
    - Can only clear groups you have left
    - Must leave the group first before clearing
    - Doesn't affect other members
    - Cannot undo (group won't appear in your list anymore)
    - Old messages are not deleted from database
    
    **Errors:**
    - 400: You haven't left this group yet
    - 403: Not authorized
    - 404: Group not found
    
    **Use Cases:**
    - Clean up left groups from your list
    - Remove old group chats you don't need
    - Declutter your groups list
    
    **Difference from Delete Group:**
    - **Delete Group** (creator only): Deletes entire group for everyone
    - **Clear Chat** (left members): Removes from your view only
    
    **Example:**
    ```
    User leaves "Old Project Group"
    → Group shows in list with status="left"
    → User calls DELETE /groups/{id}/clear-chat
    → Group disappears from user's list
    → Other members still see the group
    ```
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can clear groups"
        )
    
    return await service.clear_left_group(group_id, current_user)
