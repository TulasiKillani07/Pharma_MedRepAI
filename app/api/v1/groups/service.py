"""
Groups Business Logic
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from bson import ObjectId
from app.database import get_database
from fastapi import HTTPException
from app.api.v1.notifications.helpers import notify_group_message, notify_group_added


async def get_user_details(user_id: str) -> Dict[str, Any]:
    """Get user details from doctors or mrs collection."""
    db = get_database()
    
    user = await db["doctors"].find_one({"_id": ObjectId(user_id)})
    if user:
        return {
            "user_id": str(user["_id"]),
            "name": user.get("name", ""),
            "role": "DOCTOR"
        }
    
    user = await db["mrs"].find_one({"_id": ObjectId(user_id)})
    if user:
        return {
            "user_id": str(user["_id"]),
            "name": user.get("name", ""),
            "role": "MR"
        }
    
    raise HTTPException(status_code=404, detail=f"User {user_id} not found")


async def check_connection(user1_id: str, user2_id: str) -> bool:
    """Check if two users are connected."""
    db = get_database()
    
    connection = await db["connections"].find_one({
        "$or": [
            {"requester_id": user1_id, "receiver_id": user2_id, "status": "accepted"},
            {"requester_id": user2_id, "receiver_id": user1_id, "status": "accepted"}
        ]
    })
    
    return connection is not None


async def create_group(
    group_name: str,
    group_description: Optional[str],
    member_ids: List[str],
    current_user: Dict
) -> Dict[str, Any]:
    """
    Create a new group.
    
    Args:
        group_name: Group name
        group_description: Group description
        member_ids: Initial member IDs
        current_user: Current authenticated user
    
    Returns:
        dict: Created group data
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    creator_id = current_user["_id"]
    
    # Validate member limit
    total_members = len(member_ids) + 1  # +1 for creator
    if total_members > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 members allowed per group")
    
    # Validate all members are connected to creator
    failed_members = []
    valid_member_ids = []
    
    for member_id in member_ids:
        if member_id == creator_id:
            continue  # Skip creator
        
        if not await check_connection(creator_id, member_id):
            failed_members.append({
                "user_id": member_id,
                "reason": "Not connected"
            })
        else:
            valid_member_ids.append(member_id)
    
    # Get member details
    all_members = [creator_id] + valid_member_ids
    member_details = []
    
    for member_id in all_members:
        try:
            user = await get_user_details(member_id)
            member_details.append({
                "user_id": member_id,
                "name": user["name"],
                "role": user["role"],
                "is_admin": (member_id == creator_id),
                "joined_at": datetime.utcnow()
            })
        except HTTPException:
            continue
    
    # Create group document
    group_doc = {
        "group_name": group_name,
        "group_description": group_description,
        "created_by": creator_id,
        "admins": [creator_id],
        "members": all_members,
        "member_details": member_details,
        "last_message": None,
        "last_message_at": None,
        "unread_count": {m: 0 for m in all_members},
        "settings": {
            "only_admins_can_send": False,
            "allow_members_to_add": False,
            "max_members": 50
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db["groups"].insert_one(group_doc)
    
    response = {
        "group_id": str(result.inserted_id),
        "group_name": group_name,
        "group_description": group_description,
        "created_by": creator_id,
        "members_count": len(all_members),
        "admins_count": 1,
        "created_at": group_doc["created_at"]
    }
    
    # Add failed members info if any
    if failed_members:
        response["failed_members"] = failed_members
        response["message"] = f"Group created with {len(valid_member_ids)} of {len(member_ids)} requested members"
    
    return response


async def get_my_groups(current_user: Dict) -> Dict[str, Any]:
    """
    Get all groups where user is a member or has left.
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        dict: List of groups (active and left)
    """
    db = get_database()
    
    user_id = current_user["_id"]
    
    # Get all groups where user is current member OR in left_members
    # Exclude soft-deleted groups
    groups_cursor = db["groups"].find({
        "$and": [
            {
                "$or": [
                    {"members": user_id},
                    {f"left_members.{user_id}": {"$exists": True}}
                ]
            },
            {"is_active": {"$ne": False}}  # Exclude soft-deleted groups
        ]
    }).sort("last_message_at", -1)
    
    groups_list = await groups_cursor.to_list(None)
    
    # Format groups
    groups = []
    for group in groups_list:
        is_current_member = user_id in group.get("members", [])
        left_members = group.get("left_members", {})
        is_left_member = user_id in left_members
        
        group_item = {
            "group_id": str(group["_id"]),
            "group_name": group["group_name"],
            "last_message": group.get("last_message"),
            "last_message_at": group.get("last_message_at"),
            "members_count": len(group["members"])
        }
        
        if is_current_member:
            # Active member - show unread count
            group_item["unread_count"] = group.get("unread_count", {}).get(user_id, 0)
            group_item["status"] = "active"
        elif is_left_member:
            # Left member - no unread count, show left status
            group_item["unread_count"] = 0
            group_item["status"] = "left"
            group_item["you_left_at"] = left_members[user_id]["left_at"]
        
        groups.append(group_item)
    
    return {
        "groups": groups,
        "total": len(groups)
    }


async def get_group_details(group_id: str, current_user: Dict) -> Dict[str, Any]:
    """
    Get detailed group information.
    
    Args:
        group_id: Group ID
        current_user: Current authenticated user
    
    Returns:
        dict: Group details
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Get group
    try:
        group = await db["groups"].find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid group ID")
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if user is current member or left member
    user_id = current_user["_id"]
    is_current_member = user_id in group["members"]
    left_members = group.get("left_members", {})
    is_left_member = user_id in left_members
    
    if not is_current_member and not is_left_member:
        raise HTTPException(status_code=403, detail="You are not a member of this group")
    
    # Format response
    response = {
        "group_id": str(group["_id"]),
        "group_name": group["group_name"],
        "group_description": group.get("group_description"),
        "created_by": group["created_by"],
        "admins": group["admins"],
        "members": group["member_details"],
        "members_count": len(group["members"]),
        "created_at": group["created_at"]
    }
    
    # Add left status if user has left
    if is_left_member:
        response["you_left_at"] = left_members[user_id]["left_at"]
        response["status"] = "left"
    
    return response


async def update_group(
    group_id: str,
    group_name: Optional[str],
    group_description: Optional[str],
    current_user: Dict
) -> Dict[str, str]:
    """
    Update group information (admin only).
    
    Args:
        group_id: Group ID
        group_name: New group name
        group_description: New group description
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Get group
    try:
        group = await db["groups"].find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid group ID")
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if user is admin
    user_id = current_user["_id"]
    if user_id not in group["admins"]:
        raise HTTPException(status_code=403, detail="Only admins can update group info")
    
    # Build update document
    update_doc = {"updated_at": datetime.utcnow()}
    
    if group_name is not None:
        update_doc["group_name"] = group_name
    
    if group_description is not None:
        update_doc["group_description"] = group_description
    
    # Update group
    await db["groups"].update_one(
        {"_id": ObjectId(group_id)},
        {"$set": update_doc}
    )
    
    return {"message": "Group updated successfully"}


async def add_members(
    group_id: str,
    user_ids: List[str],
    current_user: Dict
) -> Dict[str, Any]:
    """
    Add members to group (admin only).
    
    Args:
        group_id: Group ID
        user_ids: User IDs to add
        current_user: Current authenticated user
    
    Returns:
        dict: Add members result
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Get group
    try:
        group = await db["groups"].find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid group ID")
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if user is admin
    user_id = current_user["_id"]
    if user_id not in group["admins"]:
        raise HTTPException(status_code=403, detail="Only admins can add members")
    
    # Check member limit
    current_count = len(group["members"])
    max_members = group.get("settings", {}).get("max_members", 50)
    
    if current_count + len(user_ids) > max_members:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot add members. Group limit is {max_members}"
        )
    
    # Validate and add members
    added_count = 0
    failed = []
    
    for new_member_id in user_ids:
        # Skip if already member
        if new_member_id in group["members"]:
            failed.append({
                "user_id": new_member_id,
                "reason": "Already a member"
            })
            continue
        
        # Check connection
        if not await check_connection(user_id, new_member_id):
            failed.append({
                "user_id": new_member_id,
                "reason": "Not connected"
            })
            continue
        
        # Get user details
        try:
            user = await get_user_details(new_member_id)
        except HTTPException:
            failed.append({
                "user_id": new_member_id,
                "reason": "User not found"
            })
            continue
        
        # Add member
        member_detail = {
            "user_id": new_member_id,
            "name": user["name"],
            "role": user["role"],
            "is_admin": False,
            "joined_at": datetime.utcnow()
        }
        
        await db["groups"].update_one(
            {"_id": ObjectId(group_id)},
            {
                "$push": {
                    "members": new_member_id,
                    "member_details": member_detail
                },
                "$set": {
                    f"unread_count.{new_member_id}": 0,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Send notification to new member
        await notify_group_added(
            user_id=new_member_id,
            group_id=group_id,
            group_name=group["group_name"],
            added_by_name=current_user.get("name", ""),
            added_by_id=user_id
        )
        
        added_count += 1
    
    return {
        "message": f"Added {added_count} member(s)" if added_count > 0 else "No members added",
        "added": added_count,
        "failed": failed
    }


async def remove_member(
    group_id: str,
    member_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Remove a member from group (admin only).
    
    Args:
        group_id: Group ID
        member_id: Member ID to remove
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Get group
    try:
        group = await db["groups"].find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid group ID")
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if user is admin
    user_id = current_user["_id"]
    if user_id not in group["admins"]:
        raise HTTPException(status_code=403, detail="Only admins can remove members")
    
    # Cannot remove creator
    if member_id == group["created_by"]:
        raise HTTPException(status_code=400, detail="Cannot remove group creator")
    
    # Check if member exists
    if member_id not in group["members"]:
        raise HTTPException(status_code=404, detail="User is not a member of this group")
    
    # Remove member
    await db["groups"].update_one(
        {"_id": ObjectId(group_id)},
        {
            "$pull": {
                "members": member_id,
                "member_details": {"user_id": member_id},
                "admins": member_id
            },
            "$unset": {
                f"unread_count.{member_id}": ""
            },
            "$set": {
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": "Member removed successfully"}


async def leave_group(group_id: str, current_user: Dict) -> Dict[str, str]:
    """
    Leave a group.
    
    Args:
        group_id: Group ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Get group
    try:
        group = await db["groups"].find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid group ID")
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    user_id = current_user["_id"]
    
    # Check if user is member
    if user_id not in group["members"]:
        raise HTTPException(status_code=400, detail="You are not a member of this group")
    
    # If creator is leaving, transfer ownership
    if user_id == group["created_by"]:
        # Find another admin or oldest member
        new_creator = None
        
        # Try to find another admin
        for admin_id in group["admins"]:
            if admin_id != user_id:
                new_creator = admin_id
                break
        
        # If no other admin, make oldest member the creator
        if not new_creator and len(group["members"]) > 1:
            for member_id in group["members"]:
                if member_id != user_id:
                    new_creator = member_id
                    break
        
        if new_creator:
            # Transfer ownership
            await db["groups"].update_one(
                {"_id": ObjectId(group_id)},
                {
                    "$set": {
                        "created_by": new_creator
                    },
                    "$addToSet": {
                        "admins": new_creator
                    }
                }
            )
    
    # Store left_at timestamp and user info for read-only access
    left_member_info = {
        "user_id": user_id,
        "name": current_user.get("name", ""),
        "role": current_user.get("role", ""),
        "left_at": datetime.utcnow()
    }
    
    # Remove user from group but keep left_at timestamp
    await db["groups"].update_one(
        {"_id": ObjectId(group_id)},
        {
            "$pull": {
                "members": user_id,
                "member_details": {"user_id": user_id},
                "admins": user_id
            },
            "$unset": {
                f"unread_count.{user_id}": ""
            },
            "$set": {
                f"left_members.{user_id}": left_member_info,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": "You have left the group"}


async def make_admin(
    group_id: str,
    member_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Make a member an admin (admin only).
    
    Args:
        group_id: Group ID
        member_id: Member ID to promote
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Get group
    try:
        group = await db["groups"].find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid group ID")
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if user is admin
    user_id = current_user["_id"]
    if user_id not in group["admins"]:
        raise HTTPException(status_code=403, detail="Only admins can promote members")
    
    # Check if member exists
    if member_id not in group["members"]:
        raise HTTPException(status_code=404, detail="User is not a member of this group")
    
    # Check if already admin
    if member_id in group["admins"]:
        raise HTTPException(status_code=400, detail="User is already an admin")
    
    # Make admin
    await db["groups"].update_one(
        {"_id": ObjectId(group_id)},
        {
            "$addToSet": {"admins": member_id},
            "$set": {
                "member_details.$[elem].is_admin": True,
                "updated_at": datetime.utcnow()
            }
        },
        array_filters=[{"elem.user_id": member_id}]
    )
    
    return {"message": "Member promoted to admin"}


async def remove_admin(
    group_id: str,
    admin_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Remove admin role from a member (admin only).
    
    Args:
        group_id: Group ID
        admin_id: Admin ID to demote
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Get group
    try:
        group = await db["groups"].find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid group ID")
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if user is admin
    user_id = current_user["_id"]
    if user_id not in group["admins"]:
        raise HTTPException(status_code=403, detail="Only admins can demote admins")
    
    # Cannot demote creator
    if admin_id == group["created_by"]:
        raise HTTPException(status_code=400, detail="Cannot demote group creator")
    
    # Check if user is admin
    if admin_id not in group["admins"]:
        raise HTTPException(status_code=400, detail="User is not an admin")
    
    # Must have at least one admin
    if len(group["admins"]) <= 1:
        raise HTTPException(status_code=400, detail="Group must have at least one admin")
    
    # Remove admin
    await db["groups"].update_one(
        {"_id": ObjectId(group_id)},
        {
            "$pull": {"admins": admin_id},
            "$set": {
                "member_details.$[elem].is_admin": False,
                "updated_at": datetime.utcnow()
            }
        },
        array_filters=[{"elem.user_id": admin_id}]
    )
    
    return {"message": "Admin role removed"}


async def send_group_message(
    group_id: str,
    content: str,
    current_user: Dict
) -> Dict[str, Any]:
    """
    Send a message to group.
    
    Args:
        group_id: Group ID
        content: Message content
        current_user: Current authenticated user
    
    Returns:
        dict: Created message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Get group
    try:
        group = await db["groups"].find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid group ID")
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if user is member
    user_id = current_user["_id"]
    if user_id not in group["members"]:
        raise HTTPException(status_code=403, detail="You are not a member of this group")
    
    # Create message
    message_doc = {
        "conversation_id": group_id,
        "conversation_type": "group",
        "sender_id": user_id,
        "sender_name": current_user.get("name", ""),
        "sender_role": current_user.get("role", ""),
        "content": content,
        "message_type": "text",
        "read_by": [user_id],
        "created_at": datetime.utcnow()
    }
    
    result = await db["messages"].insert_one(message_doc)
    
    # Update group
    unread_updates = {}
    for member_id in group["members"]:
        if member_id != user_id:
            current_unread = group["unread_count"].get(member_id, 0)
            unread_updates[f"unread_count.{member_id}"] = current_unread + 1
    
    await db["groups"].update_one(
        {"_id": ObjectId(group_id)},
        {
            "$set": {
                "last_message": content[:100],
                "last_message_at": message_doc["created_at"],
                "updated_at": datetime.utcnow(),
                **unread_updates
            }
        }
    )
    
    # Send notification to all group members except sender
    await notify_group_message(
        group_id=group_id,
        group_name=group["group_name"],
        sender_name=current_user.get("name", ""),
        sender_id=user_id,
        message_preview=content,
        member_ids=group["members"],
        exclude_sender=True
    )
    
    return {
        "message_id": str(result.inserted_id),
        "group_id": group_id,
        "sender_id": user_id,
        "sender_name": current_user.get("name", ""),
        "sender_role": current_user.get("role", ""),
        "content": content,
        "message_type": "text",
        "shared_post": None,
        "read_by_count": 1,
        "created_at": message_doc["created_at"]
    }


async def get_group_messages(
    group_id: str,
    current_user: Dict,
    page: int = 1,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Get messages in a group.
    
    Args:
        group_id: Group ID
        current_user: Current authenticated user
        page: Page number
        limit: Messages per page
    
    Returns:
        dict: Paginated messages
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Get group
    try:
        group = await db["groups"].find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid group ID")
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if user is member or left member
    user_id = current_user["_id"]
    is_current_member = user_id in group["members"]
    left_members = group.get("left_members", {})
    is_left_member = user_id in left_members
    
    if not is_current_member and not is_left_member:
        raise HTTPException(status_code=403, detail="You are not a member of this group")
    
    # If user left, only show messages before they left
    message_filter = {
        "conversation_id": group_id,
        "conversation_type": "group"
    }
    
    if is_left_member:
        left_at = left_members[user_id]["left_at"]
        message_filter["created_at"] = {"$lte": left_at}
    
    # Validate pagination
    if limit > 100:
        limit = 100
    if page < 1:
        page = 1
    
    # Get total count
    total = await db["messages"].count_documents(message_filter)
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get messages
    messages_cursor = db["messages"].find(message_filter).sort("created_at", -1).skip(skip).limit(limit)
    
    messages_list = await messages_cursor.to_list(limit)
    messages_list.reverse()  # Oldest first
    
    # Format messages
    messages = []
    for msg in messages_list:
        messages.append({
            "message_id": str(msg["_id"]),
            "group_id": group_id,
            "sender_id": msg["sender_id"],
            "sender_name": msg["sender_name"],
            "sender_role": msg["sender_role"],
            "content": msg["content"],
            "message_type": msg.get("message_type", "text"),
            "shared_post": msg.get("shared_post"),
            "read_by_count": len(msg.get("read_by", [])),
            "created_at": msg["created_at"]
        })
    
    return {
        "messages": messages,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def mark_group_as_read(
    group_id: str,
    current_user: Dict
) -> Dict[str, Any]:
    """
    Mark all group messages as read.
    
    Args:
        group_id: Group ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Get group
    try:
        group = await db["groups"].find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid group ID")
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if user is current member or left member
    user_id = current_user["_id"]
    is_current_member = user_id in group["members"]
    left_members = group.get("left_members", {})
    is_left_member = user_id in left_members
    
    if not is_current_member and not is_left_member:
        raise HTTPException(status_code=403, detail="You are not a member of this group")
    
    # Left members can mark old messages as read but don't have unread_count
    message_filter = {
        "conversation_id": group_id,
        "conversation_type": "group",
        "read_by": {"$ne": user_id}
    }
    
    # If user left, only mark messages before they left
    if is_left_member:
        left_at = left_members[user_id]["left_at"]
        message_filter["created_at"] = {"$lte": left_at}
    
    # Add user to read_by array for all unread messages
    result = await db["messages"].update_many(
        message_filter,
        {
            "$addToSet": {"read_by": user_id}
        }
    )
    
    # Reset unread count (only for current members)
    if is_current_member:
        await db["groups"].update_one(
            {"_id": ObjectId(group_id)},
            {"$set": {f"unread_count.{user_id}": 0}}
        )
    
    return {
        "message": "Messages marked as read",
        "marked_count": result.modified_count
    }



async def clear_left_group(group_id: str, current_user: Dict) -> Dict[str, str]:
    """
    Clear/delete a left group from user's view.
    If last user, soft delete the group.
    
    Args:
        group_id: Group ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Get group
    try:
        group = await db["groups"].find_one({"_id": ObjectId(group_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid group ID")
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    user_id = current_user["_id"]
    
    # Check if user has left this group
    left_members = group.get("left_members", {})
    if user_id not in left_members:
        raise HTTPException(
            status_code=400,
            detail="You can only clear groups you have left. Use leave endpoint first."
        )
    
    # Remove user from left_members
    await db["groups"].update_one(
        {"_id": ObjectId(group_id)},
        {
            "$unset": {
                f"left_members.{user_id}": ""
            }
        }
    )
    
    # Check if this was the last user
    # Get updated group
    updated_group = await db["groups"].find_one({"_id": ObjectId(group_id)})
    current_members = updated_group.get("members", [])
    remaining_left_members = updated_group.get("left_members", {})
    
    # If no current members AND no left members → soft delete
    if len(current_members) == 0 and len(remaining_left_members) == 0:
        await db["groups"].update_one(
            {"_id": ObjectId(group_id)},
            {
                "$set": {
                    "is_active": False,
                    "deleted_at": datetime.utcnow()
                }
            }
        )
        return {"message": "Group chat cleared. Group archived as you were the last user."}
    
    return {"message": "Group chat cleared from your view"}
