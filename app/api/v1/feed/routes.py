"""
Feed/Posts API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Optional
from app.core.auth import get_current_user
from app.api.v1.feed.schemas import PostCreate, PostResponse, PostFeedResponse
from app.api.v1.feed import service


router = APIRouter()


@router.post("", response_model=PostResponse, status_code=201)
async def create_post_endpoint(
    post_data: PostCreate,
    current_user: Dict = Depends(get_current_user)
):
    """
    Create a new post.
    
    **Access:** Doctor, MR only
    
    **Purpose:**
    Allows doctors and MRs to create text posts to share with the community.
    
    **Flow:**
    1. User submits post content
    2. System validates content (1-5000 characters)
    3. System auto-populates author information from current user
    4. Post is created and visible in feed
    
    **Rules:**
    - Content is required (1-5000 characters)
    - Once posted, cannot be edited (only deleted)
    - Author info auto-populated: name, role, specialization/territory
    - Initial likes_count and comments_count set to 0
    
    **Request Body:**
    ```json
    {
        "content": "Excited to share insights from today's cardiology conference!"
    }
    ```
    
    **Response:**
    ```json
    {
        "post_id": "post123",
        "author_id": "user123",
        "author_name": "Dr. Sarah Sharma",
        "author_role": "DOCTOR",
        "author_specialization": "Cardiology",
        "content": "Excited to share insights...",
        "likes_count": 0,
        "comments_count": 0,
        "created_at": "2024-04-09T10:30:00"
    }
    ```
    
    **Use Cases:**
    - Share medical insights and experiences
    - Discuss industry trends
    - Ask questions to the community
    - Share success stories
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can create posts"
        )
    
    return await service.create_post(post_data.content, current_user)


@router.get("", response_model=PostFeedResponse)
async def get_feed_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Posts per page (max 50)"),
    author_role: Optional[str] = Query(None, description="Filter by author role: DOCTOR or MR"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get paginated feed of all posts.
    
    **Access:** Doctor, MR, Admin
    
    **Purpose:**
    Retrieve a paginated list of all active posts from the community.
    
    **Flow:**
    1. User requests feed with optional filters
    2. System retrieves active posts sorted by newest first
    3. Returns paginated results with metadata
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Posts per page (default: 20, max: 50)
    - `author_role`: Filter by DOCTOR or MR (optional)
    
    **Response:**
    ```json
    {
        "posts": [
            {
                "post_id": "post123",
                "author_id": "user123",
                "author_name": "Dr. Sarah Sharma",
                "author_role": "DOCTOR",
                "author_specialization": "Cardiology",
                "content": "Excited to share insights!",
                "likes_count": 15,
                "comments_count": 3,
                "created_at": "2024-04-09T10:30:00"
            }
        ],
        "total": 150,
        "page": 1,
        "limit": 20,
        "total_pages": 8
    }
    ```
    
    **Sorting:**
    - Posts sorted by created_at (newest first)
    
    **Filtering:**
    - Only active posts (is_active=true) are shown
    - Optional filter by author_role
    
    **Use Cases:**
    - Browse community posts
    - Discover insights from doctors and MRs
    - Stay updated with industry discussions
    """
    return await service.get_feed(page, limit, author_role)


@router.get("/me", response_model=PostFeedResponse)
async def get_my_posts_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Posts per page (max 50)"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get current user's posts.
    
    **Access:** Doctor, MR
    
    **Purpose:**
    Retrieve all posts created by the current user (including deleted ones).
    
    **Flow:**
    1. User requests their own posts
    2. System retrieves all posts by user (including deleted)
    3. Returns paginated results
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Posts per page (default: 20, max: 50)
    
    **Response:**
    Same format as feed endpoint
    
    **Note:**
    - Shows all posts including deleted ones (is_active=false)
    - Only accessible by post owner
    
    **Use Cases:**
    - View your posting history
    - Manage your posts
    - Track engagement on your posts
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can access this endpoint"
        )
    
    return await service.get_my_posts(current_user, page, limit)


@router.get("/user/{user_id}", response_model=PostFeedResponse)
async def get_user_posts_endpoint(
    user_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Posts per page (max 50)"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get posts by a specific user.
    
    **Access:** Doctor, MR, Admin
    
    **Purpose:**
    Retrieve all active posts created by a specific user.
    
    **Flow:**
    1. User requests posts by specific user ID
    2. System retrieves active posts by that user
    3. Returns paginated results
    
    **Path Parameters:**
    - `user_id`: User ID to get posts from
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Posts per page (default: 20, max: 50)
    
    **Response:**
    Same format as feed endpoint
    
    **Note:**
    - Only shows active posts (is_active=true)
    - Sorted by newest first
    
    **Use Cases:**
    - View another user's posts
    - Browse posts from specific doctor or MR
    - Check user's posting activity
    """
    return await service.get_user_posts(user_id, page, limit)


@router.get("/{post_id}", response_model=PostResponse)
async def get_post_endpoint(
    post_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get a single post by ID.
    
    **Access:** Doctor, MR, Admin
    
    **Purpose:**
    Retrieve details of a specific post.
    
    **Flow:**
    1. User requests post by ID
    2. System validates post exists and is active
    3. Returns post details
    
    **Path Parameters:**
    - `post_id`: Post ID
    
    **Response:**
    ```json
    {
        "post_id": "post123",
        "author_id": "user123",
        "author_name": "Dr. Sarah Sharma",
        "author_role": "DOCTOR",
        "author_specialization": "Cardiology",
        "content": "Excited to share insights!",
        "likes_count": 15,
        "comments_count": 3,
        "created_at": "2024-04-09T10:30:00"
    }
    ```
    
    **Errors:**
    - 400: Invalid post ID format
    - 404: Post not found or deleted
    
    **Use Cases:**
    - View post details
    - Share post link
    - View post with comments (future)
    """
    return await service.get_post_by_id(post_id)


@router.delete("/{post_id}")
async def delete_post_endpoint(
    post_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Delete own post (soft delete).
    
    **Access:** Doctor, MR (only own posts)
    
    **Purpose:**
    Allow users to delete their own posts.
    
    **Flow:**
    1. User requests to delete post
    2. System validates post exists and belongs to user
    3. Post is soft deleted (is_active=false)
    4. Post no longer appears in feed
    
    **Path Parameters:**
    - `post_id`: Post ID to delete
    
    **Response:**
    ```json
    {
        "message": "Post deleted successfully"
    }
    ```
    
    **Rules:**
    - Can only delete your own posts
    - Soft delete: Post remains in database but hidden
    - Likes and comments are preserved
    - Cannot be undone
    
    **Errors:**
    - 400: Invalid post ID format
    - 403: Not authorized (not post owner)
    - 404: Post not found
    
    **Use Cases:**
    - Remove unwanted posts
    - Delete posts with errors
    - Manage your content
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can delete posts"
        )
    
    return await service.delete_post(post_id, current_user)


@router.delete("/{post_id}/admin")
async def admin_delete_post_endpoint(
    post_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Admin delete any post (moderation).
    
    **Access:** Admin only
    
    **Purpose:**
    Allow admins to delete any post for moderation purposes.
    
    **Flow:**
    1. Admin requests to delete post
    2. System validates post exists
    3. Post is soft deleted (is_active=false)
    4. Post no longer appears in feed
    
    **Path Parameters:**
    - `post_id`: Post ID to delete
    
    **Response:**
    ```json
    {
        "message": "Post deleted successfully by admin"
    }
    ```
    
    **Rules:**
    - Admin can delete any post
    - Soft delete: Post remains in database but hidden
    - Used for content moderation
    - Cannot be undone
    
    **Errors:**
    - 400: Invalid post ID format
    - 403: Not authorized (not admin)
    - 404: Post not found
    
    **Use Cases:**
    - Remove inappropriate content
    - Moderate community posts
    - Handle reported posts
    """
    # Check role
    role = current_user.get("role")
    if role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Only admins can use this endpoint"
        )
    
    return await service.admin_delete_post(post_id)
