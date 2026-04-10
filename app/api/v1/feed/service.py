"""
Feed/Posts Business Logic
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from bson import ObjectId
from app.database import get_database
from fastapi import HTTPException


async def create_post(content: str, current_user: Dict) -> Dict[str, Any]:
    """
    Create a new post.
    
    Args:
        content: Post content
        current_user: Current authenticated user
    
    Returns:
        dict: Created post data
    """
    db = get_database()
    
    # Extract author information
    author_id = current_user["_id"]
    author_name = current_user.get("name", "")
    author_role = current_user.get("role", "")
    
    # Get additional info based on role
    author_specialization = None
    author_territory = None
    
    if author_role == "DOCTOR":
        author_specialization = current_user.get("specialization")
    elif author_role == "MR":
        author_territory = current_user.get("territory")
    
    # Create post document
    post_doc = {
        "author_id": author_id,
        "author_name": author_name,
        "author_role": author_role,
        "author_specialization": author_specialization,
        "author_territory": author_territory,
        "content": content,
        "likes_count": 0,
        "comments_count": 0,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Insert into database
    result = await db["posts"].insert_one(post_doc)
    
    # Return created post
    post_doc["_id"] = result.inserted_id
    
    return {
        "post_id": str(post_doc["_id"]),
        "author_id": post_doc["author_id"],
        "author_name": post_doc["author_name"],
        "author_role": post_doc["author_role"],
        "author_specialization": post_doc["author_specialization"],
        "author_territory": post_doc["author_territory"],
        "content": post_doc["content"],
        "likes_count": post_doc["likes_count"],
        "comments_count": post_doc["comments_count"],
        "created_at": post_doc["created_at"]
    }


async def get_feed(
    page: int = 1,
    limit: int = 20,
    author_role: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get paginated feed of posts.
    
    Args:
        page: Page number (default 1)
        limit: Posts per page (default 20, max 50)
        author_role: Filter by author role (optional)
    
    Returns:
        dict: Paginated posts with metadata
    """
    db = get_database()
    
    # Validate and limit page size
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    # Build query filter
    query_filter = {"is_active": True}
    if author_role:
        query_filter["author_role"] = author_role.upper()
    
    # Get total count
    total = await db["posts"].count_documents(query_filter)
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get posts
    posts_cursor = db["posts"].find(query_filter).sort("created_at", -1).skip(skip).limit(limit)
    posts_list = await posts_cursor.to_list(limit)
    
    # Format posts
    posts = []
    for post in posts_list:
        posts.append({
            "post_id": str(post["_id"]),
            "author_id": post["author_id"],
            "author_name": post["author_name"],
            "author_role": post["author_role"],
            "author_specialization": post.get("author_specialization"),
            "author_territory": post.get("author_territory"),
            "content": post["content"],
            "likes_count": post["likes_count"],
            "comments_count": post["comments_count"],
            "created_at": post["created_at"]
        })
    
    return {
        "posts": posts,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def get_post_by_id(post_id: str) -> Dict[str, Any]:
    """
    Get a single post by ID.
    
    Args:
        post_id: Post ID
    
    Returns:
        dict: Post data
    
    Raises:
        HTTPException: If post not found
    """
    db = get_database()
    
    try:
        post = await db["posts"].find_one({
            "_id": ObjectId(post_id),
            "is_active": True
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return {
        "post_id": str(post["_id"]),
        "author_id": post["author_id"],
        "author_name": post["author_name"],
        "author_role": post["author_role"],
        "author_specialization": post.get("author_specialization"),
        "author_territory": post.get("author_territory"),
        "content": post["content"],
        "likes_count": post["likes_count"],
        "comments_count": post["comments_count"],
        "created_at": post["created_at"]
    }


async def get_user_posts(
    user_id: str,
    page: int = 1,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get posts by a specific user.
    
    Args:
        user_id: User ID
        page: Page number
        limit: Posts per page
    
    Returns:
        dict: Paginated user posts
    """
    db = get_database()
    
    # Validate and limit page size
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    # Build query
    query_filter = {
        "author_id": user_id,
        "is_active": True
    }
    
    # Get total count
    total = await db["posts"].count_documents(query_filter)
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get posts
    posts_cursor = db["posts"].find(query_filter).sort("created_at", -1).skip(skip).limit(limit)
    posts_list = await posts_cursor.to_list(limit)
    
    # Format posts
    posts = []
    for post in posts_list:
        posts.append({
            "post_id": str(post["_id"]),
            "author_id": post["author_id"],
            "author_name": post["author_name"],
            "author_role": post["author_role"],
            "author_specialization": post.get("author_specialization"),
            "author_territory": post.get("author_territory"),
            "content": post["content"],
            "likes_count": post["likes_count"],
            "comments_count": post["comments_count"],
            "created_at": post["created_at"]
        })
    
    return {
        "posts": posts,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def get_my_posts(
    current_user: Dict,
    page: int = 1,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get current user's posts (including deleted ones).
    
    Args:
        current_user: Current authenticated user
        page: Page number
        limit: Posts per page
    
    Returns:
        dict: Paginated user posts
    """
    db = get_database()
    
    # Validate and limit page size
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    user_id = current_user["_id"]
    
    # Build query (show all posts including deleted for owner)
    query_filter = {"author_id": user_id}
    
    # Get total count
    total = await db["posts"].count_documents(query_filter)
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get posts
    posts_cursor = db["posts"].find(query_filter).sort("created_at", -1).skip(skip).limit(limit)
    posts_list = await posts_cursor.to_list(limit)
    
    # Format posts
    posts = []
    for post in posts_list:
        posts.append({
            "post_id": str(post["_id"]),
            "author_id": post["author_id"],
            "author_name": post["author_name"],
            "author_role": post["author_role"],
            "author_specialization": post.get("author_specialization"),
            "author_territory": post.get("author_territory"),
            "content": post["content"],
            "likes_count": post["likes_count"],
            "comments_count": post["comments_count"],
            "created_at": post["created_at"]
        })
    
    return {
        "posts": posts,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def delete_post(post_id: str, current_user: Dict) -> Dict[str, str]:
    """
    Delete own post (soft delete).
    
    Args:
        post_id: Post ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If post not found or unauthorized
    """
    db = get_database()
    
    try:
        post = await db["posts"].find_one({"_id": ObjectId(post_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Check if current user is the author
    if post["author_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only delete your own posts")
    
    # Soft delete
    await db["posts"].update_one(
        {"_id": ObjectId(post_id)},
        {
            "$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": "Post deleted successfully"}


async def admin_delete_post(post_id: str) -> Dict[str, str]:
    """
    Admin delete any post (soft delete for moderation).
    
    Args:
        post_id: Post ID
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If post not found
    """
    db = get_database()
    
    try:
        post = await db["posts"].find_one({"_id": ObjectId(post_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Soft delete
    await db["posts"].update_one(
        {"_id": ObjectId(post_id)},
        {
            "$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": "Post deleted successfully by admin"}
