"""
Feed/Posts Business Logic
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from bson import ObjectId
from app.database import get_database
from fastapi import HTTPException
from app.api.v1.notifications.helpers import (
    notify_post_liked,
    notify_post_commented,
    notify_post_shared
)
from app.models.post_model import PostInDB, LikeInDB, CommentInDB


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
    
    # RULE 1: INSERT with model
    post = PostInDB(
        author_id=author_id,
        content=content
    )
    
    # Add author details (DB-specific fields not in model)
    post_doc = post.model_dump()
    post_doc.update({
        "author_name": author_name,
        "author_role": author_role,
        "author_specialization": author_specialization,
        "author_territory": author_territory
    })
    
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
        "shares_count": post_doc["shares_count"],
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
            "shares_count": post.get("shares_count", 0),
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
        "shares_count": post.get("shares_count", 0),
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
            "shares_count": post.get("shares_count", 0),
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
            "shares_count": post.get("shares_count", 0),
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



# ============ LIKES FUNCTIONS ============

async def toggle_like(post_id: str, current_user: Dict) -> Dict[str, Any]:
    """
    Toggle like on a post (like if not liked, unlike if already liked).
    
    Args:
        post_id: Post ID
        current_user: Current authenticated user
    
    Returns:
        dict: Like status and updated count
    
    Raises:
        HTTPException: If post not found
    """
    db = get_database()
    
    # Validate post exists and is active
    try:
        post = await db["posts"].find_one({
            "_id": ObjectId(post_id),
            "is_active": True
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    user_id = current_user["_id"]
    
    # Check if user already liked this post
    existing_like = await db["post_likes"].find_one({
        "post_id": post_id,
        "user_id": user_id
    })
    
    if existing_like:
        # User already liked → UNLIKE
        await db["post_likes"].delete_one({
            "post_id": post_id,
            "user_id": user_id
        })
        
        # Decrement likes_count
        await db["posts"].update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"likes_count": -1}}
        )
        
        # Get updated count
        updated_post = await db["posts"].find_one({"_id": ObjectId(post_id)})
        
        return {
            "liked": False,
            "likes_count": updated_post["likes_count"],
            "message": "Post unliked successfully"
        }
    else:
        # User hasn't liked → LIKE
        # RULE 1: INSERT with model
        like = LikeInDB(
            post_id=str(post["_id"]),
            user_id=user_id
        )
        
        # Add user details (DB-specific fields)
        like_doc = like.model_dump()
        like_doc.update({
            "user_name": current_user.get("name", ""),
            "user_role": current_user.get("role", "")
        })
        
        await db["post_likes"].insert_one(like_doc)
        
        # Increment likes_count
        await db["posts"].update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"likes_count": 1}}
        )
        
        # Get updated count
        updated_post = await db["posts"].find_one({"_id": ObjectId(post_id)})
        
        # Notify post author (don't notify if user likes their own post)
        if post["author_id"] != user_id:
            await notify_post_liked(
                post_id=post_id,
                post_author_id=post["author_id"],
                liker_name=current_user.get("name", ""),
                liker_id=user_id
            )
        
        return {
            "liked": True,
            "likes_count": updated_post["likes_count"],
            "message": "Post liked successfully"
        }


async def get_post_likes(
    post_id: str,
    page: int = 1,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get list of users who liked a post.
    
    Args:
        post_id: Post ID
        page: Page number
        limit: Likes per page
    
    Returns:
        dict: Paginated list of users who liked
    
    Raises:
        HTTPException: If post not found
    """
    db = get_database()
    
    # Validate post exists
    try:
        post = await db["posts"].find_one({"_id": ObjectId(post_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Validate and limit page size
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    # Get total count
    total = await db["post_likes"].count_documents({"post_id": post_id})
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get likes
    likes_cursor = db["post_likes"].find(
        {"post_id": post_id}
    ).sort("created_at", -1).skip(skip).limit(limit)
    
    likes_list = await likes_cursor.to_list(limit)
    
    # Format likes
    likes = []
    for like in likes_list:
        likes.append({
            "user_id": like["user_id"],
            "user_name": like["user_name"],
            "user_role": like["user_role"],
            "created_at": like["created_at"]
        })
    
    return {
        "likes": likes,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def check_like_status(post_id: str, current_user: Dict) -> Dict[str, Any]:
    """
    Check if current user has liked a post.
    
    Args:
        post_id: Post ID
        current_user: Current authenticated user
    
    Returns:
        dict: Like status and total count
    
    Raises:
        HTTPException: If post not found
    """
    db = get_database()
    
    # Validate post exists
    try:
        post = await db["posts"].find_one({"_id": ObjectId(post_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    user_id = current_user["_id"]
    
    # Check if user liked this post
    like = await db["post_likes"].find_one({
        "post_id": post_id,
        "user_id": user_id
    })
    
    return {
        "liked": like is not None,
        "likes_count": post.get("likes_count", 0)
    }


async def get_my_liked_posts(
    current_user: Dict,
    page: int = 1,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get posts that current user has liked.
    
    Args:
        current_user: Current authenticated user
        page: Page number
        limit: Posts per page
    
    Returns:
        dict: Paginated list of liked posts
    """
    db = get_database()
    
    # Validate and limit page size
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    user_id = current_user["_id"]
    
    # Get total count of liked posts
    total = await db["post_likes"].count_documents({"user_id": user_id})
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get liked post IDs
    likes_cursor = db["post_likes"].find(
        {"user_id": user_id}
    ).sort("created_at", -1).skip(skip).limit(limit)
    
    likes_list = await likes_cursor.to_list(limit)
    
    # Get post IDs - handle conversion errors gracefully
    post_ids = []
    valid_likes = []
    
    for like in likes_list:
        try:
            pid = like["post_id"]
            if isinstance(pid, ObjectId):
                post_ids.append(pid)
                valid_likes.append(like)
            elif isinstance(pid, str):
                # Try to convert string to ObjectId
                post_ids.append(ObjectId(pid))
                valid_likes.append(like)
        except Exception as e:
            # Skip invalid post IDs - don't fail the entire request
            print(f"Skipping invalid post_id in like: {like.get('post_id')} - Error: {e}")
            continue
    
    if not post_ids:
        return {
            "posts": [],
            "total": 0,
            "page": page,
            "limit": limit,
            "total_pages": 0
        }
    
    # Get posts
    posts_cursor = db["posts"].find({
        "_id": {"$in": post_ids},
        "is_active": True
    })
    
    posts_list = await posts_cursor.to_list(len(post_ids))
    
    # Create a map of post_id to liked_at timestamp using valid_likes
    liked_at_map = {like["post_id"]: like["created_at"] for like in valid_likes}
    
    # Format posts with liked_at timestamp
    posts = []
    for post in posts_list:
        post_id_str = str(post["_id"])
        posts.append({
            "post_id": post_id_str,
            "author_id": post["author_id"],
            "author_name": post["author_name"],
            "author_role": post["author_role"],
            "author_specialization": post.get("author_specialization"),
            "author_territory": post.get("author_territory"),
            "content": post["content"],
            "likes_count": post["likes_count"],
            "comments_count": post["comments_count"],
            "shares_count": post.get("shares_count", 0),
            "created_at": post["created_at"],
            "liked_at": liked_at_map.get(post_id_str)
        })
    
    # Sort by liked_at (most recently liked first)
    posts.sort(key=lambda x: x.get("liked_at") or datetime.min, reverse=True)
    
    return {
        "posts": posts,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }



# ============ COMMENTS FUNCTIONS ============

async def add_comment(post_id: str, content: str, current_user: Dict) -> Dict[str, Any]:
    """
    Add a comment to a post.
    
    Args:
        post_id: Post ID
        content: Comment content
        current_user: Current authenticated user
    
    Returns:
        dict: Created comment data
    
    Raises:
        HTTPException: If post not found
    """
    db = get_database()
    
    # Validate post exists and is active
    try:
        post = await db["posts"].find_one({
            "_id": ObjectId(post_id),
            "is_active": True
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # RULE 1: INSERT with model
    comment = CommentInDB(
        post_id=str(post["_id"]),
        author_id=current_user["_id"],
        content=content
    )
    
    # Add author details (DB-specific fields)
    comment_doc = comment.model_dump()
    comment_doc.update({
        "author_name": current_user.get("name", ""),
        "author_role": current_user.get("role", ""),
        "updated_at": datetime.utcnow()
    })
    
    # Insert comment
    result = await db["post_comments"].insert_one(comment_doc)
    
    # Increment comments_count on post
    await db["posts"].update_one(
        {"_id": ObjectId(post_id)},
        {"$inc": {"comments_count": 1}}
    )
    
    # Notify post author (don't notify if user comments on their own post)
    if post["author_id"] != current_user["_id"]:
        await notify_post_commented(
            post_id=post_id,
            post_author_id=post["author_id"],
            commenter_name=current_user.get("name", ""),
            commenter_id=current_user["_id"],
            comment_id=str(result.inserted_id)
        )
    
    return {
        "comment_id": str(result.inserted_id),
        "post_id": comment_doc["post_id"],
        "author_id": comment_doc["author_id"],
        "author_name": comment_doc["author_name"],
        "author_role": comment_doc["author_role"],
        "content": comment_doc["content"],
        "created_at": comment_doc["created_at"]
    }


async def get_post_comments(
    post_id: str,
    page: int = 1,
    limit: int = 20,
    sort: str = "asc"
) -> Dict[str, Any]:
    """
    Get comments for a post.
    
    Args:
        post_id: Post ID
        page: Page number
        limit: Comments per page
        sort: Sort order (asc=oldest first, desc=newest first)
    
    Returns:
        dict: Paginated list of comments
    
    Raises:
        HTTPException: If post not found
    """
    db = get_database()
    
    # Validate post exists
    try:
        post = await db["posts"].find_one({"_id": ObjectId(post_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Validate and limit page size
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    # Determine sort order
    sort_order = 1 if sort == "asc" else -1
    
    # Get total count
    total = await db["post_comments"].count_documents({
        "post_id": str(post["_id"]),
        "is_active": True
    })
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get comments
    comments_cursor = db["post_comments"].find({
        "post_id": str(post["_id"]),
        "is_active": True
    }).sort("created_at", sort_order).skip(skip).limit(limit)
    
    comments_list = await comments_cursor.to_list(limit)
    
    # Format comments
    comments = []
    for comment in comments_list:
        comments.append({
            "comment_id": str(comment["_id"]),
            "post_id": comment["post_id"],
            "author_id": comment["author_id"],
            "author_name": comment["author_name"],
            "author_role": comment["author_role"],
            "content": comment["content"],
            "created_at": comment["created_at"]
        })
    
    return {
        "comments": comments,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def get_my_comments(
    current_user: Dict,
    page: int = 1,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get comments made by current user.
    
    Args:
        current_user: Current authenticated user
        page: Page number
        limit: Comments per page
    
    Returns:
        dict: Paginated list of user's comments
    """
    db = get_database()
    
    # Validate and limit page size
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    user_id = current_user["_id"]
    
    # Get total count
    total = await db["post_comments"].count_documents({
        "author_id": user_id,
        "is_active": True
    })
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get comments
    comments_cursor = db["post_comments"].find({
        "author_id": user_id,
        "is_active": True
    }).sort("created_at", -1).skip(skip).limit(limit)
    
    comments_list = await comments_cursor.to_list(limit)
    
    # Format comments
    comments = []
    for comment in comments_list:
        comments.append({
            "comment_id": str(comment["_id"]),
            "post_id": comment["post_id"],
            "author_id": comment["author_id"],
            "author_name": comment["author_name"],
            "author_role": comment["author_role"],
            "content": comment["content"],
            "created_at": comment["created_at"]
        })
    
    return {
        "comments": comments,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


async def delete_comment(
    post_id: str,
    comment_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Delete own comment (soft delete).
    
    Args:
        post_id: Post ID
        comment_id: Comment ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If comment not found or unauthorized
    """
    db = get_database()
    
    # Validate comment exists
    try:
        comment = await db["post_comments"].find_one({"_id": ObjectId(comment_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid comment ID")
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Check if comment belongs to this post
    if comment["post_id"] != post_id:
        raise HTTPException(status_code=400, detail="Comment does not belong to this post")
    
    # Check if current user is the author
    if comment["author_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only delete your own comments")
    
    # Soft delete
    await db["post_comments"].update_one(
        {"_id": ObjectId(comment_id)},
        {
            "$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Decrement comments_count on post
    try:
        await db["posts"].update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"comments_count": -1}}
        )
    except Exception:
        pass  # Post might be deleted, but comment deletion should still succeed
    
    return {"message": "Comment deleted successfully"}


async def admin_delete_comment(
    post_id: str,
    comment_id: str
) -> Dict[str, str]:
    """
    Admin delete any comment (soft delete for moderation).
    
    Args:
        post_id: Post ID
        comment_id: Comment ID
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If comment not found
    """
    db = get_database()
    
    # Validate comment exists
    try:
        comment = await db["post_comments"].find_one({"_id": ObjectId(comment_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid comment ID")
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Check if comment belongs to this post
    if comment["post_id"] != post_id:
        raise HTTPException(status_code=400, detail="Comment does not belong to this post")
    
    # Soft delete
    await db["post_comments"].update_one(
        {"_id": ObjectId(comment_id)},
        {
            "$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Decrement comments_count on post
    try:
        await db["posts"].update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"comments_count": -1}}
        )
    except Exception:
        pass  # Post might be deleted, but comment deletion should still succeed
    
    return {"message": "Comment deleted successfully by admin"}



async def share_post(
    post_id: str,
    user_ids: List[str],
    message: Optional[str],
    current_user: Dict
) -> Dict[str, Any]:
    """
    Share a post via DM to one or more connected users.
    
    Args:
        post_id: Post ID to share
        user_ids: List of user IDs to share with
        message: Optional personal message
        current_user: Current authenticated user
    
    Returns:
        dict: Share result with success count and failures
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Validate post exists and is active
    try:
        post = await db["posts"].find_one({"_id": ObjectId(post_id), "is_active": True})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found or has been deleted")
    
    current_user_id = current_user["_id"]
    
    # Cannot share to yourself
    if current_user_id in user_ids:
        raise HTTPException(status_code=400, detail="Cannot share post to yourself")
    
    # Validate max recipients
    if len(user_ids) > 10:
        raise HTTPException(status_code=400, detail="Cannot share to more than 10 users at once")
    
    # Track results
    shared_count = 0
    failed_shares = []
    
    # Process each recipient
    for user_id in user_ids:
        try:
            # Check if users are connected
            connection = await db["connections"].find_one({
                "$or": [
                    {"requester_id": current_user_id, "receiver_id": user_id, "status": "accepted"},
                    {"requester_id": user_id, "receiver_id": current_user_id, "status": "accepted"}
                ]
            })
            
            if not connection:
                failed_shares.append({
                    "user_id": user_id,
                    "reason": "Not connected"
                })
                continue
            
            # Check if blocked
            blocked = await db["connections"].find_one({
                "$or": [
                    {"requester_id": current_user_id, "receiver_id": user_id, "status": "blocked"},
                    {"requester_id": user_id, "receiver_id": current_user_id, "status": "blocked"}
                ]
            })
            
            if blocked:
                failed_shares.append({
                    "user_id": user_id,
                    "reason": "User blocked"
                })
                continue
            
            # Get or create conversation
            participants = sorted([current_user_id, user_id])
            conversation = await db["conversations"].find_one({"participants": participants})
            
            if not conversation:
                # Get recipient details
                recipient = await db["doctors"].find_one({"_id": ObjectId(user_id)})
                if not recipient:
                    recipient = await db["mrs"].find_one({"_id": ObjectId(user_id)})
                
                if not recipient:
                    failed_shares.append({
                        "user_id": user_id,
                        "reason": "User not found"
                    })
                    continue
                
                recipient_role = "DOCTOR" if await db["doctors"].find_one({"_id": ObjectId(user_id)}) else "MR"
                
                # Create conversation
                conversation_doc = {
                    "participants": participants,
                    "participant_details": [
                        {
                            "user_id": current_user_id,
                            "name": current_user.get("name", ""),
                            "role": current_user.get("role", "")
                        },
                        {
                            "user_id": user_id,
                            "name": recipient.get("name", ""),
                            "role": recipient_role
                        }
                    ],
                    "last_message": None,
                    "last_message_at": None,
                    "unread_count": {
                        current_user_id: 0,
                        user_id: 0
                    },
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                
                result = await db["conversations"].insert_one(conversation_doc)
                conversation = await db["conversations"].find_one({"_id": result.inserted_id})
            
            conversation_id = str(conversation["_id"])
            
            # Create shared post message
            message_content = message if message else ""
            
            message_doc = {
                "conversation_id": conversation_id,
                "sender_id": current_user_id,
                "sender_name": current_user.get("name", ""),
                "sender_role": current_user.get("role", ""),
                "content": message_content,
                "message_type": "shared_post",
                "shared_post": {
                    "post_id": post_id,
                    "author_name": post.get("author_name", ""),
                    "author_role": post.get("author_role", ""),
                    "content": post.get("content", ""),
                    "likes_count": post.get("likes_count", 0),
                    "comments_count": post.get("comments_count", 0),
                    "shares_count": post.get("shares_count", 0),
                    "created_at": post.get("created_at")
                },
                "is_read": False,
                "read_at": None,
                "created_at": datetime.utcnow()
            }
            
            await db["messages"].insert_one(message_doc)
            
            # Notify recipient about shared post
            await notify_post_shared(
                receiver_id=user_id,
                post_id=post_id,
                sharer_name=current_user.get("name", ""),
                sharer_id=current_user_id,
                personal_message=message
            )
            
            # Update conversation
            preview = f"📤 Shared a post"
            if message_content:
                preview = f"{message_content[:50]}..."
            
            await db["conversations"].update_one(
                {"_id": ObjectId(conversation_id)},
                {
                    "$set": {
                        "last_message": preview,
                        "last_message_at": message_doc["created_at"],
                        "updated_at": datetime.utcnow(),
                        f"unread_count.{user_id}": conversation.get("unread_count", {}).get(user_id, 0) + 1
                    }
                }
            )
            
            shared_count += 1
            
        except Exception as e:
            failed_shares.append({
                "user_id": user_id,
                "reason": str(e)
            })
    
    # Increment shares_count on post
    if shared_count > 0:
        await db["posts"].update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"shares_count": shared_count}}
        )
    
    # Build response message
    if shared_count == len(user_ids):
        response_message = "Post shared successfully"
    elif shared_count > 0:
        response_message = f"Post shared to {shared_count} user(s)"
    else:
        response_message = "Failed to share post"
    
    return {
        "message": response_message,
        "shared_to": shared_count,
        "failed": failed_shares
    }
