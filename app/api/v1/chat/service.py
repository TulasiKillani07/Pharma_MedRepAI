"""
Chat Business Logic
"""

from datetime import datetime
from typing import Dict, Any, List
from bson import ObjectId
from app.database import get_database
from fastapi import HTTPException


async def check_connection(user1_id: str, user2_id: str) -> bool:
    """
    Check if two users are connected.
    
    Args:
        user1_id: First user ID
        user2_id: Second user ID
    
    Returns:
        bool: True if connected, False otherwise
    """
    db = get_database()
    
    connection = await db["connections"].find_one({
        "$or": [
            {"requester_id": user1_id, "receiver_id": user2_id, "status": "accepted"},
            {"requester_id": user2_id, "receiver_id": user1_id, "status": "accepted"}
        ]
    })
    
    return connection is not None


async def get_user_details(user_id: str) -> Dict[str, Any]:
    """
    Get user details from doctors or mrs collection.
    
    Args:
        user_id: User ID
    
    Returns:
        dict: User details
    
    Raises:
        HTTPException: If user not found
    """
    db = get_database()
    
    # Check doctors collection first
    user = await db["doctors"].find_one({"_id": ObjectId(user_id)})
    if user:
        return {
            "user_id": str(user["_id"]),
            "name": user.get("name", ""),
            "role": "DOCTOR"
        }
    
    # Check mrs collection
    user = await db["mrs"].find_one({"_id": ObjectId(user_id)})
    if user:
        return {
            "user_id": str(user["_id"]),
            "name": user.get("name", ""),
            "role": "MR"
        }
    
    # User not found
    raise HTTPException(status_code=404, detail="User not found")


async def start_conversation(
    other_user_id: str,
    current_user: Dict
) -> Dict[str, Any]:
    """
    Start or get existing conversation with another user.
    
    Args:
        other_user_id: Other user ID
        current_user: Current authenticated user
    
    Returns:
        dict: Conversation details
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    current_user_id = current_user["_id"]
    
    # Cannot chat with self
    if current_user_id == other_user_id:
        raise HTTPException(status_code=400, detail="Cannot start conversation with yourself")
    
    # Check if users are connected
    is_connected = await check_connection(current_user_id, other_user_id)
    if not is_connected:
        raise HTTPException(
            status_code=403,
            detail="You can only message connected users. Send a connection request first."
        )
    
    # Get other user details
    other_user = await get_user_details(other_user_id)
    
    # Create sorted participants array for consistent lookup
    participants = sorted([current_user_id, other_user_id])
    
    # Check if conversation already exists
    existing_conv = await db["conversations"].find_one({"participants": participants})
    
    if existing_conv:
        return {
            "conversation_id": str(existing_conv["_id"]),
            "message": "Conversation already exists"
        }
    
    # Create new conversation
    conversation_doc = {
        "participants": participants,
        "participant_details": [
            {
                "user_id": current_user_id,
                "name": current_user.get("name", ""),
                "role": current_user.get("role", "")
            },
            {
                "user_id": other_user_id,
                "name": other_user["name"],
                "role": other_user["role"]
            }
        ],
        "last_message": None,
        "last_message_at": None,
        "unread_count": {
            current_user_id: 0,
            other_user_id: 0
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db["conversations"].insert_one(conversation_doc)
    
    return {
        "conversation_id": str(result.inserted_id),
        "message": "Conversation started"
    }


async def get_conversations(current_user: Dict) -> Dict[str, Any]:
    """
    Get all conversations for current user.
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        dict: List of conversations
    """
    db = get_database()
    
    user_id = current_user["_id"]
    
    # Get all conversations where user is participant
    conversations_cursor = db["conversations"].find({
        "participants": user_id
    }).sort("last_message_at", -1)
    
    conversations_list = await conversations_cursor.to_list(None)
    
    # Format conversations
    conversations = []
    for conv in conversations_list:
        # Get other user ID
        other_user_id = None
        for participant_id in conv["participants"]:
            if participant_id != user_id:
                other_user_id = participant_id
                break
        
        if not other_user_id:
            continue
        
        # Fetch fresh user details to ensure role is correct
        try:
            other_user = await get_user_details(other_user_id)
        except HTTPException:
            # Skip if user not found
            continue
        
        # Get unread count for current user
        unread_count = conv.get("unread_count", {}).get(user_id, 0)
        
        conversations.append({
            "conversation_id": str(conv["_id"]),
            "other_user": other_user,
            "last_message": conv.get("last_message"),
            "last_message_at": conv.get("last_message_at"),
            "unread_count": unread_count
        })
    
    return {
        "conversations": conversations,
        "total": len(conversations)
    }


async def get_messages(
    conversation_id: str,
    current_user: Dict,
    page: int = 1,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Get messages in a conversation.
    
    Args:
        conversation_id: Conversation ID
        current_user: Current authenticated user
        page: Page number
        limit: Messages per page
    
    Returns:
        dict: Paginated messages
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Validate conversation exists
    try:
        conversation = await db["conversations"].find_one({"_id": ObjectId(conversation_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Check if current user is participant
    user_id = current_user["_id"]
    if user_id not in conversation["participants"]:
        raise HTTPException(status_code=403, detail="You are not part of this conversation")
    
    # Validate and limit page size
    if limit > 100:
        limit = 100
    if page < 1:
        page = 1
    
    # Get total count
    total = await db["messages"].count_documents({"conversation_id": conversation_id})
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get messages (sorted by newest first for pagination, but reverse for display)
    messages_cursor = db["messages"].find({
        "conversation_id": conversation_id
    }).sort("created_at", -1).skip(skip).limit(limit)
    
    messages_list = await messages_cursor.to_list(limit)
    
    # Reverse to show oldest first in the page
    messages_list.reverse()
    
    # Format messages
    messages = []
    for msg in messages_list:
        message_data = {
            "message_id": str(msg["_id"]),
            "conversation_id": msg["conversation_id"],
            "sender_id": msg["sender_id"],
            "sender_name": msg["sender_name"],
            "sender_role": msg["sender_role"],
            "content": msg["content"],
            "message_type": msg.get("message_type", "text"),
            "is_read": msg["is_read"],
            "read_at": msg.get("read_at"),
            "created_at": msg["created_at"]
        }
        
        # Add shared_post data if message type is shared_post
        if msg.get("message_type") == "shared_post" and "shared_post" in msg:
            message_data["shared_post"] = msg["shared_post"]
        else:
            message_data["shared_post"] = None
        
        messages.append(message_data)
    
    return {
        "messages": messages,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def send_message(
    conversation_id: str,
    content: str,
    current_user: Dict
) -> Dict[str, Any]:
    """
    Send a message in a conversation.
    
    Args:
        conversation_id: Conversation ID
        content: Message content
        current_user: Current authenticated user
    
    Returns:
        dict: Created message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Validate conversation exists
    try:
        conversation = await db["conversations"].find_one({"_id": ObjectId(conversation_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Check if current user is participant
    user_id = current_user["_id"]
    if user_id not in conversation["participants"]:
        raise HTTPException(status_code=403, detail="You are not part of this conversation")
    
    # Create message
    message_doc = {
        "conversation_id": conversation_id,
        "sender_id": user_id,
        "sender_name": current_user.get("name", ""),
        "sender_role": current_user.get("role", ""),
        "content": content,
        "is_read": False,
        "read_at": None,
        "created_at": datetime.utcnow()
    }
    
    result = await db["messages"].insert_one(message_doc)
    
    # Update conversation
    # Get other user ID
    other_user_id = None
    for participant_id in conversation["participants"]:
        if participant_id != user_id:
            other_user_id = participant_id
            break
    
    # Update last message and increment unread count for other user
    update_doc = {
        "last_message": content[:100],  # Store first 100 chars as preview
        "last_message_at": message_doc["created_at"],
        "updated_at": datetime.utcnow()
    }
    
    # Increment unread count for other user
    if other_user_id:
        update_doc[f"unread_count.{other_user_id}"] = conversation.get("unread_count", {}).get(other_user_id, 0) + 1
    
    await db["conversations"].update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": update_doc}
    )
    
    return {
        "message_id": str(result.inserted_id),
        "conversation_id": conversation_id,
        "sender_id": user_id,
        "sender_name": current_user.get("name", ""),
        "sender_role": current_user.get("role", ""),
        "content": content,
        "message_type": "text",
        "shared_post": None,
        "is_read": False,
        "read_at": None,
        "created_at": message_doc["created_at"]
    }


async def mark_as_read(
    conversation_id: str,
    current_user: Dict
) -> Dict[str, Any]:
    """
    Mark all messages in conversation as read.
    
    Args:
        conversation_id: Conversation ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message with count
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Validate conversation exists
    try:
        conversation = await db["conversations"].find_one({"_id": ObjectId(conversation_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Check if current user is participant
    user_id = current_user["_id"]
    if user_id not in conversation["participants"]:
        raise HTTPException(status_code=403, detail="You are not part of this conversation")
    
    # Mark all unread messages as read (messages not sent by current user)
    result = await db["messages"].update_many(
        {
            "conversation_id": conversation_id,
            "sender_id": {"$ne": user_id},
            "is_read": False
        },
        {
            "$set": {
                "is_read": True,
                "read_at": datetime.utcnow()
            }
        }
    )
    
    # Reset unread count for current user in conversation
    await db["conversations"].update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {f"unread_count.{user_id}": 0}}
    )
    
    return {
        "message": "Messages marked as read",
        "marked_count": result.modified_count
    }


async def delete_message(
    message_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Delete a message (only sender can delete).
    
    Args:
        message_id: Message ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Get message
    try:
        message = await db["messages"].find_one({"_id": ObjectId(message_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid message ID")
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Check if current user is sender
    if message["sender_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only delete your own messages")
    
    # Delete message
    await db["messages"].delete_one({"_id": ObjectId(message_id)})
    
    return {"message": "Message deleted successfully"}


async def delete_conversation(
    conversation_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Delete a conversation (soft delete - just removes from user's inbox).
    
    Args:
        conversation_id: Conversation ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Validate conversation exists
    try:
        conversation = await db["conversations"].find_one({"_id": ObjectId(conversation_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Check if current user is participant
    user_id = current_user["_id"]
    if user_id not in conversation["participants"]:
        raise HTTPException(status_code=403, detail="You are not part of this conversation")
    
    # For now, we'll actually delete the conversation
    # In production, you might want to implement soft delete per user
    await db["conversations"].delete_one({"_id": ObjectId(conversation_id)})
    
    # Optionally delete all messages in conversation
    await db["messages"].delete_many({"conversation_id": conversation_id})
    
    return {"message": "Conversation deleted successfully"}
