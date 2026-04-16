"""
Feed/Posts API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Optional
from app.core.auth import get_current_user
from app.models.post_model import (
    PostCreate, PostResponse, PostFeedResponse, 
    LikeResponse, LikeListResponse, LikeStatusResponse, 
    CommentCreate, CommentResponse, CommentListResponse,
    SharePostRequest, SharePostResponse
)
from app.api.v1.feed import service


# Router for posts
posts_router = APIRouter()

# Router for likes
likes_router = APIRouter()

# Router for comments
comments_router = APIRouter()


@posts_router.post("", response_model=PostResponse, status_code=201)
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


@posts_router.get("", response_model=PostFeedResponse)
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


@posts_router.get("/me", response_model=PostFeedResponse)
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


@posts_router.get("/user/{user_id}", response_model=PostFeedResponse)
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


@posts_router.get("/{post_id}", response_model=PostResponse)
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


@posts_router.delete("/{post_id}")
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


@posts_router.delete("/{post_id}/admin")
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


@posts_router.post("/{post_id}/share", response_model=SharePostResponse)
async def share_post_endpoint(
    post_id: str,
    share_data: SharePostRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Share a post via direct message to connected users.
    
    **Access:** Doctor, MR only
    
    **Purpose:**
    Share a post by sending it as a direct message to one or more connected users.
    
    **Flow:**
    1. User clicks "Share" on a post
    2. Selects connected users from list (max 10)
    3. Optionally adds personal message
    4. System sends post as special message to each user
    5. Recipients see shared post in their messages
    
    **Path Parameters:**
    - `post_id`: Post ID to share
    
    **Request Body:**
    ```json
    {
        "user_ids": ["user123", "user456"],
        "message": "Thought you'd find this interesting!"
    }
    ```
    
    **Response:**
    ```json
    {
        "message": "Post shared successfully",
        "shared_to": 2,
        "failed": []
    }
    ```
    
    **Partial Success Example:**
    ```json
    {
        "message": "Post shared to 2 user(s)",
        "shared_to": 2,
        "failed": [
            {
                "user_id": "user789",
                "reason": "Not connected"
            }
        ]
    }
    ```
    
    **Rules:**
    - Can only share to connected users (status="accepted")
    - Cannot share to yourself
    - Cannot share to blocked users
    - Max 10 recipients per share
    - Optional personal message (max 500 chars)
    - Creates/uses existing conversation
    - Increments post shares_count
    - Message type: "shared_post"
    
    **Message Format:**
    Recipients see a special message containing:
    - Your optional personal message
    - Post preview (author, content, likes, comments)
    - Link to view full post
    
    **Errors:**
    - 400: Invalid post ID or too many recipients
    - 403: Not authorized (Admin cannot share)
    - 404: Post not found or deleted
    
    **Use Cases:**
    - Share interesting posts with colleagues
    - Send relevant content to connections
    - Recommend posts privately
    - Discuss posts in private conversations
    
    **Frontend Display:**
    In recipient's messages:
    ```
    📤 Shared a post
    "Thought you'd find this interesting!"
    
    [Post Preview]
    Dr. Sarah Sharma
    "New drug insights..."
    ❤️ 10  💬 5  📤 3
    [View Full Post]
    ```
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can share posts"
        )
    
    return await service.share_post(
        post_id,
        share_data.user_ids,
        share_data.message,
        current_user
    )



# ============ LIKES ENDPOINTS ============

@likes_router.post("/{post_id}/like", response_model=LikeResponse)
async def toggle_like_endpoint(
    post_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Toggle like on a post (like if not liked, unlike if already liked).
    
    **Access:** Doctor, MR only
    
    **Purpose:**
    Allow users to like or unlike a post with a single action.
    
    **Flow:**
    1. User clicks "Like" button on a post
    2. System checks if user already liked this post
    3. If not liked → Add like + increment count
    4. If already liked → Remove like + decrement count
    5. Return updated status and count
    
    **Path Parameters:**
    - `post_id`: Post ID to like/unlike
    
    **Response (Liked):**
    ```json
    {
        "liked": true,
        "likes_count": 16,
        "message": "Post liked successfully"
    }
    ```
    
    **Response (Unliked):**
    ```json
    {
        "liked": false,
        "likes_count": 15,
        "message": "Post unliked successfully"
    }
    ```
    
    **Rules:**
    - Toggle behavior: Click once to like, click again to unlike
    - Cannot like same post twice (prevented by database index)
    - Only active posts can be liked
    - Likes_count updated atomically
    
    **Errors:**
    - 400: Invalid post ID format
    - 403: Not authorized (Admin cannot like)
    - 404: Post not found or deleted
    
    **Use Cases:**
    - Show appreciation for a post
    - Bookmark interesting posts
    - Engage with community content
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can like posts"
        )
    
    return await service.toggle_like(post_id, current_user)


@likes_router.get("/{post_id}/likes", response_model=LikeListResponse)
async def get_post_likes_endpoint(
    post_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Likes per page (max 50)"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get list of users who liked a post.
    
    **Access:** Doctor, MR, Admin
    
    **Purpose:**
    View all users who have liked a specific post.
    
    **Flow:**
    1. User clicks "16 likes" on a post
    2. System retrieves list of users who liked
    3. Returns paginated list with user details
    
    **Path Parameters:**
    - `post_id`: Post ID
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Likes per page (default: 20, max: 50)
    
    **Response:**
    ```json
    {
        "likes": [
            {
                "user_id": "user123",
                "user_name": "Dr. Sarah Sharma",
                "user_role": "DOCTOR",
                "created_at": "2024-04-09T10:30:00"
            },
            {
                "user_id": "user456",
                "user_name": "Raj Kumar",
                "user_role": "MR",
                "created_at": "2024-04-09T09:15:00"
            }
        ],
        "total": 16,
        "page": 1,
        "limit": 20,
        "total_pages": 1
    }
    ```
    
    **Sorting:**
    - Most recent likes first (sorted by created_at descending)
    
    **Errors:**
    - 400: Invalid post ID format
    - 404: Post not found
    
    **Use Cases:**
    - See who appreciated your post
    - Discover users with similar interests
    - Check engagement on posts
    """
    return await service.get_post_likes(post_id, page, limit)


@likes_router.get("/{post_id}/like/status", response_model=LikeStatusResponse)
async def check_like_status_endpoint(
    post_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Check if current user has liked a post.
    
    **Access:** Doctor, MR
    
    **Purpose:**
    Determine if current user has already liked a post (for UI state).
    
    **Flow:**
    1. Frontend loads a post
    2. Calls this endpoint to check like status
    3. Shows "Liked" or "Like" button based on response
    
    **Path Parameters:**
    - `post_id`: Post ID
    
    **Response:**
    ```json
    {
        "liked": true,
        "likes_count": 16
    }
    ```
    
    **Fields:**
    - `liked`: true if user has liked, false if not
    - `likes_count`: Total likes on the post
    
    **Errors:**
    - 400: Invalid post ID format
    - 404: Post not found
    
    **Use Cases:**
    - Set initial button state when loading post
    - Check like status before toggling
    - Display correct UI state
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can check like status"
        )
    
    return await service.check_like_status(post_id, current_user)


@likes_router.get("/liked", response_model=PostFeedResponse)
async def get_my_liked_posts_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Posts per page (max 50)"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get posts that current user has liked.
    
    **Access:** Doctor, MR
    
    **Purpose:**
    View all posts that the current user has liked (like a "Saved" or "Favorites" list).
    
    **Flow:**
    1. User navigates to "My Liked Posts" section
    2. System retrieves all posts user has liked
    3. Returns paginated list sorted by most recently liked
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Posts per page (default: 20, max: 50)
    
    **Response:**
    ```json
    {
        "posts": [
            {
                "post_id": "post123",
                "author_name": "Dr. John Smith",
                "content": "Great insights...",
                "likes_count": 16,
                "comments_count": 3,
                "created_at": "2024-04-08T14:00:00",
                "liked_at": "2024-04-09T10:30:00"
            }
        ],
        "total": 25,
        "page": 1,
        "limit": 20,
        "total_pages": 2
    }
    ```
    
    **Sorting:**
    - Most recently liked first (sorted by liked_at descending)
    
    **Note:**
    - Only shows active posts (deleted posts are excluded)
    - Includes `liked_at` timestamp showing when user liked it
    
    **Use Cases:**
    - Review posts you found interesting
    - Revisit saved content
    - Track your engagement history
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can access this endpoint"
        )
    
    return await service.get_my_liked_posts(current_user, page, limit)



# ============ COMMENTS ENDPOINTS ============

@comments_router.post("/{post_id}/comments", response_model=CommentResponse, status_code=201)
async def add_comment_endpoint(
    post_id: str,
    comment_data: CommentCreate,
    current_user: Dict = Depends(get_current_user)
):
    """
    Add a comment to a post.
    
    **Access:** Doctor, MR only
    
    **Purpose:**
    Allow users to comment on posts to engage in discussions.
    
    **Flow:**
    1. User writes a comment on a post
    2. System validates post exists and is active
    3. Comment is created and linked to post
    4. Post's comments_count is incremented
    5. Returns created comment
    
    **Path Parameters:**
    - `post_id`: Post ID to comment on
    
    **Request Body:**
    ```json
    {
        "content": "Great insights! Thanks for sharing this information."
    }
    ```
    
    **Response:**
    ```json
    {
        "comment_id": "comment123",
        "post_id": "post123",
        "author_id": "user456",
        "author_name": "Dr. Sarah Sharma",
        "author_role": "DOCTOR",
        "content": "Great insights!",
        "created_at": "2024-04-10T10:30:00"
    }
    ```
    
    **Rules:**
    - Content required (1-1000 characters)
    - Can only comment on active posts
    - Comments cannot be edited (only deleted)
    - Author info auto-populated
    
    **Errors:**
    - 400: Invalid post ID format
    - 403: Not authorized (Admin cannot comment)
    - 404: Post not found or deleted
    
    **Use Cases:**
    - Share thoughts on a post
    - Ask questions
    - Provide feedback
    - Start discussions
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can comment on posts"
        )
    
    return await service.add_comment(post_id, comment_data.content, current_user)


@comments_router.get("/{post_id}/comments", response_model=CommentListResponse)
async def get_post_comments_endpoint(
    post_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Comments per page (max 50)"),
    sort: str = Query("asc", regex="^(asc|desc)$", description="Sort order: asc (oldest first) or desc (newest first)"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get comments for a post.
    
    **Access:** Doctor, MR, Admin
    
    **Purpose:**
    View all comments on a specific post.
    
    **Flow:**
    1. User views a post
    2. System retrieves all active comments
    3. Returns paginated list sorted by time
    
    **Path Parameters:**
    - `post_id`: Post ID
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Comments per page (default: 20, max: 50)
    - `sort`: Sort order - "asc" (oldest first) or "desc" (newest first)
    
    **Response:**
    ```json
    {
        "comments": [
            {
                "comment_id": "comment123",
                "post_id": "post123",
                "author_id": "user456",
                "author_name": "Dr. Sarah Sharma",
                "author_role": "DOCTOR",
                "content": "Great insights!",
                "created_at": "2024-04-10T10:30:00"
            }
        ],
        "total": 15,
        "page": 1,
        "limit": 20,
        "total_pages": 1
    }
    ```
    
    **Sorting:**
    - `asc` (default): Oldest first - natural conversation flow
    - `desc`: Newest first - see latest comments
    
    **Note:**
    - Only shows active comments (deleted comments hidden)
    
    **Errors:**
    - 400: Invalid post ID format
    - 404: Post not found
    
    **Use Cases:**
    - Read discussions on a post
    - Follow conversation threads
    - See community feedback
    """
    return await service.get_post_comments(post_id, page, limit, sort)


@comments_router.get("/comments/me", response_model=CommentListResponse)
async def get_my_comments_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Comments per page (max 50)"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get comments made by current user.
    
    **Access:** Doctor, MR
    
    **Purpose:**
    View all comments you've made across all posts.
    
    **Flow:**
    1. User navigates to "My Comments" section
    2. System retrieves all active comments by user
    3. Returns paginated list sorted by newest first
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Comments per page (default: 20, max: 50)
    
    **Response:**
    ```json
    {
        "comments": [
            {
                "comment_id": "comment123",
                "post_id": "post123",
                "author_id": "user456",
                "author_name": "Dr. Sarah Sharma",
                "author_role": "DOCTOR",
                "content": "Great insights!",
                "created_at": "2024-04-10T10:30:00"
            }
        ],
        "total": 25,
        "page": 1,
        "limit": 20,
        "total_pages": 2
    }
    ```
    
    **Sorting:**
    - Most recent comments first (sorted by created_at descending)
    
    **Note:**
    - Only shows active comments (deleted comments excluded)
    
    **Use Cases:**
    - Review your comment history
    - Track your engagement
    - Find posts you commented on
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can access this endpoint"
        )
    
    return await service.get_my_comments(current_user, page, limit)


@comments_router.delete("/{post_id}/comments/{comment_id}")
async def delete_comment_endpoint(
    post_id: str,
    comment_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Delete own comment (soft delete).
    
    **Access:** Doctor, MR (only own comments)
    
    **Purpose:**
    Allow users to delete their own comments.
    
    **Flow:**
    1. User requests to delete comment
    2. System validates comment exists and belongs to user
    3. Comment is soft deleted (is_active=false)
    4. Post's comments_count is decremented
    5. Comment no longer appears in list
    
    **Path Parameters:**
    - `post_id`: Post ID
    - `comment_id`: Comment ID to delete
    
    **Response:**
    ```json
    {
        "message": "Comment deleted successfully"
    }
    ```
    
    **Rules:**
    - Can only delete your own comments
    - Soft delete: Comment remains in database but hidden
    - Cannot be undone
    
    **Errors:**
    - 400: Invalid comment ID format or comment doesn't belong to post
    - 403: Not authorized (not comment author)
    - 404: Comment not found
    
    **Use Cases:**
    - Remove unwanted comments
    - Delete comments with errors
    - Manage your content
    """
    # Check role
    role = current_user.get("role")
    if role not in ["DOCTOR", "MR"]:
        raise HTTPException(
            status_code=403,
            detail="Only doctors and MRs can delete comments"
        )
    
    return await service.delete_comment(post_id, comment_id, current_user)


@comments_router.delete("/{post_id}/comments/{comment_id}/admin")
async def admin_delete_comment_endpoint(
    post_id: str,
    comment_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Admin delete any comment (moderation).
    
    **Access:** Admin only
    
    **Purpose:**
    Allow admins to delete any comment for moderation purposes.
    
    **Flow:**
    1. Admin requests to delete comment
    2. System validates comment exists
    3. Comment is soft deleted (is_active=false)
    4. Post's comments_count is decremented
    5. Comment no longer appears in list
    
    **Path Parameters:**
    - `post_id`: Post ID
    - `comment_id`: Comment ID to delete
    
    **Response:**
    ```json
    {
        "message": "Comment deleted successfully by admin"
    }
    ```
    
    **Rules:**
    - Admin can delete any comment
    - Soft delete: Comment remains in database but hidden
    - Used for content moderation
    - Cannot be undone
    
    **Errors:**
    - 400: Invalid comment ID format or comment doesn't belong to post
    - 403: Not authorized (not admin)
    - 404: Comment not found
    
    **Use Cases:**
    - Remove inappropriate comments
    - Moderate community discussions
    - Handle reported comments
    """
    # Check role
    role = current_user.get("role")
    if role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Only admins can use this endpoint"
        )
    
    return await service.admin_delete_comment(post_id, comment_id)
