"""
Communications Business Logic
Handles one-way broadcast communication from Admin to MRs.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from bson import ObjectId
from app.database import get_database
from fastapi import HTTPException, status, UploadFile
from app.models.communication_model import CommunicationInDB, CommunicationTargeting
from app.models.communication_read_model import CommunicationReadInDB
import cloudinary
import cloudinary.uploader
from app.config import settings
import os
import json
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET
)


async def create_communication_with_files(
    title: str,
    content: str,
    comm_type: str,
    priority: str,
    targeting_json: str,
    link: Optional[str],
    expires_at_str: Optional[str],
    files: List[UploadFile],
    current_user: Dict
) -> Dict[str, Any]:
    """
    Create communication with file uploads (Admin only).
    Uploads files to Cloudinary and creates communication in one step.
    
    Args:
        title: Communication title
        content: Communication content
        comm_type: Communication type
        priority: Priority level
        targeting_json: Targeting criteria as JSON string
        link: Optional external link (URL)
        expires_at_str: Expiry date as ISO string (optional)
        files: List of uploaded files
        current_user: Current authenticated admin user
    
    Returns:
        dict: Created communication info with attachments
    
    Raises:
        HTTPException: If validation fails or upload fails
    """
    # Validate type
    valid_types = ["announcement", "alert", "target", "training"]
    if comm_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid type. Must be one of: {', '.join(valid_types)}"
        )
    
    # Validate priority
    valid_priorities = ["low", "medium", "high", "urgent"]
    if priority not in valid_priorities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid priority. Must be one of: {', '.join(valid_priorities)}"
        )
    
    # Parse targeting JSON
    try:
        targeting = json.loads(targeting_json)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid targeting JSON: {str(e)}"
        )
    
    # Validate targeting structure
    if not isinstance(targeting, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Targeting must be a JSON object"
        )
    
    required_keys = ["zones", "states", "territories", "specific_mrs"]
    for key in required_keys:
        if key not in targeting:
            targeting[key] = []
    
    # Parse expires_at
    expires_at = None
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid expires_at format. Use ISO format (YYYY-MM-DDTHH:MM:SS): {str(e)}"
            )
    
    # Validate file count
    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 files allowed per communication"
        )
    
    # Upload files to Cloudinary
    attachments = []
    for file in files:
        if file.filename:  # Skip empty file inputs
            try:
                # Upload file to Cloudinary
                file_result = await _upload_file_to_cloudinary(file)
                
                # Add to attachments list
                attachments.append({
                    "file_name": file_result["file_name"],
                    "file_url": file_result["file_url"],
                    "file_type": file_result["file_type"],
                    "file_size": file_result["file_size"]
                })
            except HTTPException as e:
                # If any file upload fails, raise error
                raise HTTPException(
                    status_code=e.status_code,
                    detail=f"Failed to upload {file.filename}: {e.detail}"
                )
    
    # Create communication using existing function
    result = await create_communication(
        title=title,
        content=content,
        comm_type=comm_type,
        priority=priority,
        targeting=targeting,
        attachments=attachments,
        link=link,
        expires_at=expires_at,
        current_user=current_user
    )
    
    # Add attachments to response
    result["attachments"] = attachments
    
    return result


async def _upload_file_to_cloudinary(
    file: UploadFile
) -> Dict[str, Any]:
    """
    Internal function to upload file to Cloudinary.
    Validates file type, size, and uploads to cloud storage.
    
    Args:
        file: Uploaded file
    
    Returns:
        dict: File info with URL
    
    Raises:
        HTTPException: If file validation fails or upload fails
    """
    # Allowed file types
    ALLOWED_EXTENSIONS = {
        # Documents
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt',
        # Images
        'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg',
        # Archives
        'zip', 'rar'
    }
    
    ALLOWED_MIME_TYPES = {
        # Documents
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'text/plain',
        # Images
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp',
        'image/svg+xml',
        # Archives
        'application/zip',
        'application/x-rar-compressed'
    }
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    # Get file extension
    file_ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    
    # Validate extension
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '.{file_ext}' not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Validate MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File MIME type '{file.content_type}' not allowed"
        )
    
    # Read file content
    try:
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file size
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds maximum allowed size (10MB)"
            )
        
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}"
        )
    
    # Upload to Cloudinary
    try:
        # Determine resource type based on file type
        if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg']:
            resource_type = 'image'
        elif file_ext in ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'zip', 'rar']:
            resource_type = 'raw'
        else:
            resource_type = 'auto'
        
        # Upload file
        upload_result = cloudinary.uploader.upload(
            file_content,
            folder="communications/attachments",
            resource_type=resource_type,
            public_id=f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}",
            overwrite=False
        )
        
        file_url = upload_result.get('secure_url') or upload_result.get('url')
        
        logger.info(f"File uploaded to Cloudinary: {file.filename} ({file_size} bytes)")
        
        return {
            "message": "File uploaded successfully",
            "file_name": file.filename,
            "file_url": file_url,
            "file_type": file_ext,
            "file_size": file_size
        }
        
    except Exception as e:
        logger.error(f"Cloudinary upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to cloud storage: {str(e)}"
        )


async def get_targeted_mrs(targeting: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get list of MRs based on targeting criteria.
    
    Targeting Priority:
    1. If specific_mrs is provided → ONLY target those MRs (ignore zones/states/territories)
    2. Otherwise → Use zones/states/territories with OR logic
    
    Args:
        targeting: Targeting criteria dict with zones, states, territories, specific_mrs
    
    Returns:
        List of MR documents that match targeting criteria
    """
    db = get_database()
    
    # Check specific MRs first (highest priority)
    specific_mrs = targeting.get("specific_mrs", [])
    if specific_mrs and len(specific_mrs) > 0:
        # ONLY target specific MRs, ignore all other criteria
        try:
            mr_ids = [ObjectId(mr_id) for mr_id in specific_mrs]
            query = {
                "_id": {"$in": mr_ids},
                "is_active": True
            }
            mrs = await db.mrs.find(query).to_list(None)
            return mrs
        except Exception:
            # Invalid ObjectId format
            return []
    
    # No specific MRs, use zone/state/territory with OR logic
    conditions = []
    
    # Check zones
    zones = targeting.get("zones", [])
    if zones and len(zones) > 0:
        conditions.append({"zone": {"$in": zones}})
    
    # Check states
    states = targeting.get("states", [])
    if states and len(states) > 0:
        conditions.append({"state": {"$in": states}})
    
    # Check territories
    territories = targeting.get("territories", [])
    if territories and len(territories) > 0:
        conditions.append({"territory": {"$in": territories}})
    
    # Build final query
    if not conditions:
        # No targeting specified → target all active MRs
        query = {"is_active": True}
    else:
        # OR logic: match ANY condition
        query = {
            "$or": conditions,
            "is_active": True
        }
    
    # Execute query
    mrs = await db.mrs.find(query).to_list(None)
    return mrs


async def create_communication(
    title: str,
    content: str,
    comm_type: str,
    priority: str,
    targeting: Dict[str, Any],
    attachments: List[Dict[str, Any]],
    link: Optional[str],
    expires_at: Optional[datetime],
    current_user: Dict
) -> Dict[str, Any]:
    """
    Create a new communication (Admin only).
    
    Args:
        title: Communication title
        content: Communication content
        comm_type: Communication type (announcement, alert, target, training)
        priority: Priority level (low, medium, high, urgent)
        targeting: Targeting criteria
        attachments: List of file attachments
        link: Optional external link (URL)
        expires_at: Optional expiry date
        current_user: Current authenticated admin user
    
    Returns:
        dict: Created communication info with targeted MR count
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_database()
    
    # Calculate targeted MRs
    targeted_mrs = await get_targeted_mrs(targeting)
    targeted_count = len(targeted_mrs)
    
    # Create communication document
    comm = CommunicationInDB(
        title=title,
        content=content,
        type=comm_type,
        priority=priority,
        targeting=CommunicationTargeting(**targeting),
        attachments=attachments,
        link=link,
        expires_at=expires_at,
        created_by=current_user["_id"],
        created_by_name=current_user.get("full_name", current_user.get("name", "Admin")),
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # Insert into database
    result = await db.communications.insert_one(comm.model_dump())
    
    logger.info(f"Communication created: {title} (ID: {result.inserted_id}, Targeted: {targeted_count} MRs)")
    
    return {
        "message": "Communication sent successfully",
        "communication_id": str(result.inserted_id),
        "targeted_mrs": targeted_count
    }


async def get_communications_for_mr(
    current_user: Dict,
    page: int = 1,
    limit: int = 20,
    comm_type: Optional[str] = None,
    priority: Optional[str] = None,
    is_read: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Get list of communications for current MR.
    Auto-filters based on MR's zone, state, territory.
    
    Args:
        current_user: Current authenticated MR user
        page: Page number
        limit: Communications per page
        comm_type: Filter by type (optional)
        priority: Filter by priority (optional)
        is_read: Filter by read status (optional)
    
    Returns:
        dict: Paginated list of communications
    """
    db = get_database()
    
    # Validate pagination
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    mr_id = current_user["_id"]
    mr_zone = current_user.get("zone", "South")  # Default to South for now
    mr_state = current_user.get("state")
    mr_territory = current_user.get("territory")
    
    # Build base query - find communications that target this MR
    # Priority: specific_mrs > zone/state/territory > all MRs
    base_conditions = [
        # Target all MRs (all targeting arrays empty)
        {
            "targeting.zones": {"$size": 0},
            "targeting.states": {"$size": 0},
            "targeting.territories": {"$size": 0},
            "targeting.specific_mrs": {"$size": 0}
        },
        # Target specific MR (highest priority - if specific_mrs is not empty, only those MRs match)
        {
            "targeting.specific_mrs": {"$ne": []},  # specific_mrs is not empty
            "targeting.specific_mrs": mr_id  # AND this MR is in the list
        },
        # Target by zone/state/territory (only if specific_mrs is empty)
        {
            "targeting.specific_mrs": {"$size": 0},  # specific_mrs is empty
            "$or": [
                {"targeting.zones": mr_zone},
                {"targeting.states": mr_state},
                {"targeting.territories": mr_territory}
            ]
        }
    ]
    
    query = {
        "$and": [
            {"$or": base_conditions},
            {"is_active": True},
            {
                "$or": [
                    {"expires_at": None},
                    {"expires_at": {"$gt": datetime.utcnow()}}
                ]
            }
        ]
    }
    
    # Add optional filters
    if comm_type:
        query["type"] = comm_type
    
    if priority:
        query["priority"] = priority
    
    # Get total count
    total = await db.communications.count_documents(query)
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get communications (sorted by priority then date)
    priority_order = {"urgent": 1, "high": 2, "medium": 3, "low": 4}
    
    comms_cursor = db.communications.find(query).sort([
        ("priority", 1),  # Will be overridden by aggregation
        ("created_at", -1)
    ]).skip(skip).limit(limit)
    
    comms_list = await comms_cursor.to_list(limit)
    
    # Sort by priority (urgent first) then by date
    comms_list.sort(key=lambda x: (priority_order.get(x["priority"], 5), -x["created_at"].timestamp()))
    
    # Check read status for each communication
    communications = []
    for comm in comms_list:
        comm_id = str(comm["_id"])
        
        # Check if MR has read this
        read_record = await db.communication_reads.find_one({
            "communication_id": comm_id,
            "mr_id": mr_id
        })
        
        is_comm_read = read_record is not None
        
        # Apply is_read filter if specified
        if is_read is not None and is_comm_read != is_read:
            continue
        
        # Create preview (first 100 chars)
        preview = comm["content"][:100]
        if len(comm["content"]) > 100:
            preview += "..."
        
        communications.append({
            "id": comm_id,
            "title": comm["title"],
            "type": comm["type"],
            "priority": comm["priority"],
            "preview": preview,
            "is_read": is_comm_read,
            "created_at": comm["created_at"],
            "created_by_name": comm["created_by_name"]
        })
    
    return {
        "total": len(communications),  # Adjusted after is_read filter
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "communications": communications
    }


async def get_communication_detail_for_mr(
    communication_id: str,
    current_user: Dict
) -> Dict[str, Any]:
    """
    Get full communication details for MR.
    Auto-marks as read if not already read.
    
    Args:
        communication_id: Communication ID
        current_user: Current authenticated MR user
    
    Returns:
        dict: Full communication details
    
    Raises:
        HTTPException: If communication not found or not accessible
    """
    db = get_database()
    
    # Get communication
    try:
        comm = await db.communications.find_one({
            "_id": ObjectId(communication_id),
            "is_active": True
        })
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid communication ID"
        )
    
    if not comm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication not found"
        )
    
    # Check if expired
    if comm.get("expires_at") and comm["expires_at"] < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication has expired"
        )
    
    # Check if MR has access to this communication
    mr_id = current_user["_id"]
    mr_zone = current_user.get("zone", "South")
    mr_state = current_user.get("state")
    mr_territory = current_user.get("territory")
    
    targeting = comm["targeting"]
    has_access = False
    
    # Priority: specific_mrs > zone/state/territory > all MRs
    specific_mrs = targeting.get("specific_mrs", [])
    
    if specific_mrs and len(specific_mrs) > 0:
        # If specific_mrs is provided, ONLY those MRs have access
        has_access = mr_id in specific_mrs
    elif (not targeting.get("zones") and not targeting.get("states") and 
          not targeting.get("territories")):
        # No targeting specified → all MRs have access
        has_access = True
    else:
        # Check zone/state/territory (OR logic)
        if mr_zone in targeting.get("zones", []):
            has_access = True
        elif mr_state in targeting.get("states", []):
            has_access = True
        elif mr_territory in targeting.get("territories", []):
            has_access = True
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this communication"
        )
    
    # Check if already read
    read_record = await db.communication_reads.find_one({
        "communication_id": communication_id,
        "mr_id": mr_id
    })
    
    is_read = read_record is not None
    
    # Mark as read if not already
    if not is_read:
        read_doc = CommunicationReadInDB(
            communication_id=communication_id,
            mr_id=mr_id,
            mr_name=current_user.get("name", ""),
            mr_territory=mr_territory or "",
            mr_state=mr_state or "",
            read_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        
        await db.communication_reads.insert_one(read_doc.model_dump())
        is_read = True
        
        logger.info(f"MR {mr_id} read communication {communication_id}")
    
    # Return full details
    return {
        "id": str(comm["_id"]),
        "title": comm["title"],
        "content": comm["content"],
        "type": comm["type"],
        "priority": comm["priority"],
        "targeting": targeting,
        "attachments": comm.get("attachments", []),
        "link": comm.get("link"),
        "expires_at": comm.get("expires_at"),
        "created_at": comm["created_at"],
        "created_by_name": comm["created_by_name"],
        "is_read": is_read
    }


async def get_unread_count(current_user: Dict) -> Dict[str, int]:
    """
    Get count of unread communications for current MR.
    
    Args:
        current_user: Current authenticated MR user
    
    Returns:
        dict: Unread count
    """
    db = get_database()
    
    mr_id = current_user["_id"]
    mr_zone = current_user.get("zone", "South")
    mr_state = current_user.get("state")
    mr_territory = current_user.get("territory")
    
    # Find all communications targeted to this MR
    # Priority: specific_mrs > zone/state/territory > all MRs
    base_conditions = [
        # Target all MRs (all targeting arrays empty)
        {
            "targeting.zones": {"$size": 0},
            "targeting.states": {"$size": 0},
            "targeting.territories": {"$size": 0},
            "targeting.specific_mrs": {"$size": 0}
        },
        # Target specific MR (highest priority - if specific_mrs is not empty, only those MRs match)
        {
            "targeting.specific_mrs": {"$ne": []},  # specific_mrs is not empty
            "targeting.specific_mrs": mr_id  # AND this MR is in the list
        },
        # Target by zone/state/territory (only if specific_mrs is empty)
        {
            "targeting.specific_mrs": {"$size": 0},  # specific_mrs is empty
            "$or": [
                {"targeting.zones": mr_zone},
                {"targeting.states": mr_state},
                {"targeting.territories": mr_territory}
            ]
        }
    ]
    
    query = {
        "$and": [
            {"$or": base_conditions},
            {"is_active": True},
            {
                "$or": [
                    {"expires_at": None},
                    {"expires_at": {"$gt": datetime.utcnow()}}
                ]
            }
        ]
    }
    
    # Get all targeted communications
    comms = await db.communications.find(query, {"_id": 1}).to_list(None)
    comm_ids = [str(c["_id"]) for c in comms]
    
    # Get read communications
    read_comms = await db.communication_reads.find({
        "mr_id": mr_id,
        "communication_id": {"$in": comm_ids}
    }, {"communication_id": 1}).to_list(None)
    
    read_comm_ids = [r["communication_id"] for r in read_comms]
    
    # Calculate unread
    unread_count = len(comm_ids) - len(read_comm_ids)
    
    return {"unread_count": unread_count}



# ============ ADMIN FUNCTIONS ============

async def get_all_communications_admin(
    page: int = 1,
    limit: int = 20,
    comm_type: Optional[str] = None,
    priority: Optional[str] = None,
    is_active: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Get all communications (Admin view).
    
    Args:
        page: Page number
        limit: Communications per page
        comm_type: Filter by type (optional)
        priority: Filter by priority (optional)
        is_active: Filter by active status (optional)
    
    Returns:
        dict: Paginated list of communications
    """
    db = get_database()
    
    # Validate pagination
    if limit > 50:
        limit = 50
    if page < 1:
        page = 1
    
    # Build query
    query = {}
    
    if comm_type:
        query["type"] = comm_type
    
    if priority:
        query["priority"] = priority
    
    if is_active is not None:
        query["is_active"] = is_active
    
    # Get total count
    total = await db.communications.count_documents(query)
    
    # Calculate pagination
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Get communications
    comms_cursor = db.communications.find(query).sort("created_at", -1).skip(skip).limit(limit)
    comms_list = await comms_cursor.to_list(limit)
    
    # Format response
    communications = []
    for comm in comms_list:
        # Create preview (first 100 chars)
        preview = comm["content"][:100]
        if len(comm["content"]) > 100:
            preview += "..."
        
        communications.append({
            "id": str(comm["_id"]),
            "title": comm["title"],
            "content": comm["content"],  # Full content for admin
            "preview": preview,  # Preview for quick view
            "type": comm["type"],
            "priority": comm["priority"],
            "targeting": comm["targeting"],
            "is_active": comm["is_active"],
            "expires_at": comm.get("expires_at"),
            "created_at": comm["created_at"],
            "created_by_name": comm["created_by_name"]
        })
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "communications": communications
    }


async def get_communication_detail_admin(communication_id: str) -> Dict[str, Any]:
    """
    Get full communication details (Admin view).
    
    Args:
        communication_id: Communication ID
    
    Returns:
        dict: Full communication details
    
    Raises:
        HTTPException: If communication not found
    """
    db = get_database()
    
    try:
        comm = await db.communications.find_one({"_id": ObjectId(communication_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid communication ID"
        )
    
    if not comm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication not found"
        )
    
    return {
        "id": str(comm["_id"]),
        "title": comm["title"],
        "content": comm["content"],
        "type": comm["type"],
        "priority": comm["priority"],
        "targeting": comm["targeting"],
        "attachments": comm.get("attachments", []),
        "link": comm.get("link"),
        "expires_at": comm.get("expires_at"),
        "is_active": comm["is_active"],
        "created_at": comm["created_at"],
        "updated_at": comm["updated_at"],
        "created_by_name": comm["created_by_name"]
    }


async def update_communication(
    communication_id: str,
    update_data: Dict[str, Any],
    current_user: Dict
) -> Dict[str, str]:
    """
    Update communication (Admin only).
    
    Args:
        communication_id: Communication ID
        update_data: Fields to update
        current_user: Current authenticated admin user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If communication not found
    """
    db = get_database()
    
    try:
        comm = await db.communications.find_one({"_id": ObjectId(communication_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid communication ID"
        )
    
    if not comm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication not found"
        )
    
    # Add updated_at timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update communication
    await db.communications.update_one(
        {"_id": ObjectId(communication_id)},
        {"$set": update_data}
    )
    
    logger.info(f"Communication updated: {communication_id}")
    
    return {"message": "Communication updated successfully"}


async def delete_communication(
    communication_id: str,
    current_user: Dict
) -> Dict[str, str]:
    """
    Deactivate communication (soft delete, Admin only).
    
    Args:
        communication_id: Communication ID
        current_user: Current authenticated admin user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If communication not found
    """
    db = get_database()
    
    try:
        comm = await db.communications.find_one({"_id": ObjectId(communication_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid communication ID"
        )
    
    if not comm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication not found"
        )
    
    # Soft delete
    await db.communications.update_one(
        {"_id": ObjectId(communication_id)},
        {
            "$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    logger.info(f"Communication deactivated: {communication_id}")
    
    return {"message": "Communication deactivated successfully"}


async def get_communication_analytics(communication_id: str) -> Dict[str, Any]:
    """
    Get read analytics for a communication (Admin only).
    
    Args:
        communication_id: Communication ID
    
    Returns:
        dict: Analytics data with read/unread MRs
    
    Raises:
        HTTPException: If communication not found
    """
    db = get_database()
    
    try:
        comm = await db.communications.find_one({"_id": ObjectId(communication_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid communication ID"
        )
    
    if not comm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication not found"
        )
    
    # Get targeted MRs
    targeted_mrs = await get_targeted_mrs(comm["targeting"])
    total_targeted = len(targeted_mrs)
    
    # Get read records
    reads = await db.communication_reads.find({
        "communication_id": communication_id
    }).to_list(None)
    
    total_read = len(reads)
    read_percentage = (total_read / total_targeted * 100) if total_targeted > 0 else 0
    
    # Format read_by list
    read_by = []
    for read in reads:
        read_by.append({
            "mr_id": read["mr_id"],
            "mr_name": read["mr_name"],
            "territory": read["mr_territory"],
            "state": read["mr_state"],
            "read_at": read["read_at"]
        })
    
    # Get MRs who didn't read
    read_mr_ids = [r["mr_id"] for r in reads]
    not_read_by = []
    
    for mr in targeted_mrs:
        mr_id = str(mr["_id"])
        if mr_id not in read_mr_ids:
            not_read_by.append({
                "mr_id": mr_id,
                "mr_name": mr.get("name", ""),
                "territory": mr.get("territory", ""),
                "state": mr.get("state", ""),
                "read_at": None
            })
    
    return {
        "communication_id": communication_id,
        "title": comm["title"],
        "total_targeted": total_targeted,
        "total_read": total_read,
        "read_percentage": round(read_percentage, 2),
        "read_by": read_by,
        "not_read_by": not_read_by
    }
