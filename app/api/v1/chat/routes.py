"""
Chat API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict
from app.core.auth import get_current_user
from app.api.v1.chat.schemas import (
    MessageCreate,
    MessageResponse,
    MessageListResponse,
    ConversationResponse,
    ConversationListResponse,
    ConversationStartResponse
)
from app.api.v1.chat import service


router = APIRouter()


@router.post("/conversations/{user_id}", response_model=ConversationStartResponse)
async def start_conversation_endpoint(
    user_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Start or get existing conversation with another user.
    
    **Access:** Doctor, MR
    
    **Purpose:**
    Start a new conversation or get existing conversation with a connected user.
    
    **Flow:**
    1. User clicks "Message" on another user's profile
    2. System checks if users are connected
    3. System checks if conversation already exists
    4. If exists → Returns existing conversation ID
    5. If not → Creates new conversation
    
    **Path Parameters:**
    - `user_id`: User ID to start conversation with
    
    **Response:**
    ```json
    {
        "conversation_id": "conv123",
        "message": "Conversation started"
    }
    ```
    
    **Rules:**
    - Can only message connected users (status="accepted")
    - Cannot message yourself
    - Cannot message if blocked
    - Returns existing conversation if already exists
    
    **Errors:**
    - 400: Cannot message self
    - 403: Not connected (send connection request first)
    - 404: User not found
    
    **Use Cases:**
    - Start chatting with connected user
    - Get conversation ID for messaging
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can start conversations"
        )
    
    return await service.start_conversation(user_id, current_user)


@router.get("/conversations", response_model=ConversationListResponse)
async def get_conversations_endpoint(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get all conversations (inbox).
    
    **Access:** Doctor, MR
    
    **Purpose:**
    View all your conversations sorted by most recent activity.
    
    **Flow:**
    1. User opens "Messages" section
    2. System retrieves all conversations where user is participant
    3. Returns list sorted by last message time
    
    **Response:**
    ```json
    {
        "conversations": [
            {
                "conversation_id": "conv123",
                "other_user": {
                    "user_id": "user456",
                    "name": "Raj Kumar",
                    "role": "MR"
                },
                "last_message": "Thanks for the information!",
                "last_message_at": "2024-04-10T15:30:00",
                "unread_count": 2
            }
        ],
        "total": 10
    }
    ```
    
    **Sorting:**
    - Most recent conversations first (by last_message_at)
    
    **Unread Count:**
    - Shows number of unread messages per conversation
    - Reset when user marks as read
    
    **Use Cases:**
    - View message inbox
    - See unread messages
    - Access conversations
    
    **Frontend Polling:**
    ```javascript
    // Poll every 3 seconds for new messages
    setInterval(async () => {
        const inbox = await getConversations();
        // Update UI with new messages/unread counts
    }, 3000);
    ```
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can access conversations"
        )
    
    return await service.get_conversations(current_user)


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def get_messages_endpoint(
    conversation_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Messages per page (max 100)"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get messages in a conversation.
    
    **Access:** Doctor, MR (only participants)
    
    **Purpose:**
    View message history in a conversation.
    
    **Flow:**
    1. User opens a conversation
    2. System retrieves messages with pagination
    3. Returns messages sorted oldest first (natural chat order)
    
    **Path Parameters:**
    - `conversation_id`: Conversation ID
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Messages per page (default: 50, max: 100)
    
    **Response:**
    ```json
    {
        "messages": [
            {
                "message_id": "msg123",
                "conversation_id": "conv123",
                "sender_id": "user123",
                "sender_name": "Dr. Sarah Sharma",
                "sender_role": "DOCTOR",
                "content": "Hello!",
                "is_read": true,
                "read_at": "2024-04-10T15:35:00",
                "created_at": "2024-04-10T15:30:00"
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
    - Pagination from newest to oldest
    
    **Errors:**
    - 400: Invalid conversation ID
    - 403: Not a participant
    - 404: Conversation not found
    
    **Use Cases:**
    - View chat history
    - Load more messages (pagination)
    - Display conversation
    
    **Frontend Polling:**
    ```javascript
    // Poll every 3 seconds for new messages
    setInterval(async () => {
        const messages = await getMessages(conversationId, 1, 50);
        // Update UI with new messages
    }, 3000);
    ```
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can access messages"
        )
    
    return await service.get_messages(conversation_id, current_user, page, limit)


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
async def send_message_endpoint(
    conversation_id: str,
    message_data: MessageCreate,
    current_user: Dict = Depends(get_current_user)
):
    """
    Send a message in a conversation.
    
    **Access:** Doctor, MR (only participants)
    
    **Purpose:**
    Send a text message to another user in a conversation.
    
    **Flow:**
    1. User types message and clicks send
    2. System validates user is participant
    3. Creates message document
    4. Updates conversation (last message, unread count)
    5. Returns created message
    
    **Path Parameters:**
    - `conversation_id`: Conversation ID
    
    **Request Body:**
    ```json
    {
        "content": "Hello! How are you doing today?"
    }
    ```
    
    **Response:**
    ```json
    {
        "message_id": "msg123",
        "conversation_id": "conv123",
        "sender_id": "user123",
        "sender_name": "Dr. Sarah Sharma",
        "sender_role": "DOCTOR",
        "content": "Hello!",
        "is_read": false,
        "read_at": null,
        "created_at": "2024-04-10T15:30:00"
    }
    ```
    
    **Rules:**
    - Content required (1-2000 characters)
    - Only participants can send messages
    - Message marked as unread initially
    - Increments unread count for other user
    
    **Errors:**
    - 400: Invalid conversation ID or content
    - 403: Not a participant
    - 404: Conversation not found
    
    **Use Cases:**
    - Send text messages
    - Reply to messages
    - Chat with connected users
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can send messages"
        )
    
    return await service.send_message(conversation_id, message_data.content, current_user)


@router.post("/conversations/{conversation_id}/read")
async def mark_as_read_endpoint(
    conversation_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Mark all messages in conversation as read.
    
    **Access:** Doctor, MR (only participants)
    
    **Purpose:**
    Mark all unread messages as read when user views conversation.
    
    **Flow:**
    1. User opens conversation
    2. System marks all unread messages as read
    3. Resets unread count to 0
    4. Returns count of marked messages
    
    **Path Parameters:**
    - `conversation_id`: Conversation ID
    
    **Response:**
    ```json
    {
        "message": "Messages marked as read",
        "marked_count": 5
    }
    ```
    
    **Rules:**
    - Only marks messages sent by other user
    - Sets is_read=true and read_at timestamp
    - Resets unread_count in conversation
    
    **Errors:**
    - 400: Invalid conversation ID
    - 403: Not a participant
    - 404: Conversation not found
    
    **Use Cases:**
    - Mark messages as read when viewing
    - Clear unread badge
    - Update read status
    
    **Frontend Usage:**
    ```javascript
    // When user opens conversation
    await markAsRead(conversationId);
    ```
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can mark messages as read"
        )
    
    return await service.mark_as_read(conversation_id, current_user)


@router.delete("/messages/{message_id}")
async def delete_message_endpoint(
    message_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Delete a message (only sender can delete).
    
    **Access:** Doctor, MR (only sender)
    
    **Purpose:**
    Delete your own message from conversation.
    
    **Flow:**
    1. User clicks "Delete" on their message
    2. System validates user is sender
    3. Deletes message from database
    4. Message removed from conversation
    
    **Path Parameters:**
    - `message_id`: Message ID to delete
    
    **Response:**
    ```json
    {
        "message": "Message deleted successfully"
    }
    ```
    
    **Rules:**
    - Can only delete your own messages
    - Permanently deleted (not soft delete)
    - Other user won't see deleted message
    
    **Errors:**
    - 400: Invalid message ID
    - 403: Not authorized (not sender)
    - 404: Message not found
    
    **Use Cases:**
    - Delete sent messages
    - Remove mistakes
    - Manage message history
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can delete messages"
        )
    
    return await service.delete_message(message_id, current_user)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation_endpoint(
    conversation_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Delete a conversation.
    
    **Access:** Doctor, MR (only participants)
    
    **Purpose:**
    Delete entire conversation and all its messages.
    
    **Flow:**
    1. User clicks "Delete Conversation"
    2. System validates user is participant
    3. Deletes conversation and all messages
    4. Conversation removed from inbox
    
    **Path Parameters:**
    - `conversation_id`: Conversation ID to delete
    
    **Response:**
    ```json
    {
        "message": "Conversation deleted successfully"
    }
    ```
    
    **Rules:**
    - Can only delete conversations you're part of
    - Permanently deletes conversation and all messages
    - Cannot be undone
    
    **Errors:**
    - 400: Invalid conversation ID
    - 403: Not a participant
    - 404: Conversation not found
    
    **Use Cases:**
    - Clean up inbox
    - Remove old conversations
    - Delete unwanted chats
    """
    # Check role
    user_role = current_user.get("role")
    if user_role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can delete conversations"
        )
    
    return await service.delete_conversation(conversation_id, current_user)
