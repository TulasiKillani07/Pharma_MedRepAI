"""
MR service - Business logic for MR operations.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status, UploadFile
from bson import ObjectId
import pandas as pd
import re
from io import BytesIO
from app.database import get_database
from app.core.security import hash_password
from app.config import settings
from app.api.v1.activity_logs.helpers import log_activity
from app.models.activity_log_model import ActivityLogAction, ActorRole, TargetType, LogSeverity


def get_company_database():
    """
    Get company database.
    
    TODO: This is temporary. Will be replaced with dynamic database
    selection based on company_slug from JWT token.
    
    For now, uses DATABASE_NAME from .env
    """
    return get_database()


async def create_mr(
    name: str,
    email: str,
    password: Optional[str],
    phone: str,
    territory: str,
    assigned_doctors: List[str],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a new MR account.
    Only company admin can create MRs.
    
    Args:
        name: MR's full name
        email: MR's email
        password: Plain text password (optional, uses default if not provided)
        phone: Phone number
        territory: Sales territory
        assigned_doctors: List of assigned doctor IDs
        current_user: Current authenticated user
    
    Returns:
        dict: Success message and MR ID
    
    Raises:
        HTTPException: If email already exists or doctors already assigned
    """
    # Get company database
    company_db = get_company_database()
    
    # Check if email already exists
    existing_mr = await company_db.mrs.find_one({"email": email})
    if existing_mr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate assigned doctors are not already assigned to another MR
    if assigned_doctors:
        # Find any MR that has any of these doctors assigned
        existing_assignment = await company_db.mrs.find_one({
            "assigned_doctors": {"$in": assigned_doctors}
        })
        
        if existing_assignment:
            # Find which doctor is already assigned
            for doctor_id in assigned_doctors:
                if doctor_id in existing_assignment.get("assigned_doctors", []):
                    # Get doctor name for better error message
                    doctor = await company_db.doctors.find_one(
                        {"_id": ObjectId(doctor_id)},
                        {"name": 1}
                    )
                    doctor_name = doctor["name"] if doctor else "Unknown"
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Doctor {doctor_name} is already assigned to MR {existing_assignment.get('name')}"
                    )
    
    # Use default password if not provided
    if not password:
        password = settings.DEFAULT_USER_PASSWORD
    
    # Hash password
    password_hash = hash_password(password)
    
    # Create MR document
    mr_doc = {
        "name": name,
        "email": email,
        "password_hash": password_hash,
        "phone": phone,
        "territory": territory,
        "assigned_doctors": assigned_doctors or [],
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Insert into database
    result = await company_db.mrs.insert_one(mr_doc)
    
    # Log activity
    await log_activity(
        action_type=ActivityLogAction.USER_CREATED,
        actor=current_user,
        target_type=TargetType.MR,
        target_id=str(result.inserted_id),
        target_name=name,
        details={
            "email": email,
            "territory": territory,
            "assigned_doctors_count": len(assigned_doctors) if assigned_doctors else 0
        },
        severity=LogSeverity.INFO
    )
    
    return {
        "message": "MR added successfully",
        "mr_id": str(result.inserted_id)
    }


async def get_all_mrs(current_user: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get all MRs for a company.
    All roles can view MRs.
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        list: List of MR documents with doctor details
    """
    # Get company database
    company_db = get_company_database()
    
    # Get all MRs
    mrs_cursor = company_db.mrs.find()
    mrs = await mrs_cursor.to_list(length=None)
    
    # Convert ObjectId to string and remove password_hash
    for mr in mrs:
        mr["id"] = str(mr.pop("_id"))
        mr.pop("password_hash", None)
        
        # Fetch doctor details for assigned_doctors
        doctor_details = []
        if mr.get("assigned_doctors"):
            for doctor_id in mr["assigned_doctors"]:
                if ObjectId.is_valid(doctor_id):
                    doctor = await company_db.doctors.find_one(
                        {"_id": ObjectId(doctor_id)},
                        {"name": 1}
                    )
                    if doctor:
                        doctor_details.append({
                            "id": doctor_id,
                            "name": doctor["name"]
                        })
        
        mr["assigned_doctors"] = doctor_details
    
    return mrs


async def get_mr_by_id(mr_id: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a single MR by ID.
    All roles can view MR details.
    
    Args:
        mr_id: MR's ID
        current_user: Current authenticated user
    
    Returns:
        dict: MR document with doctor details
    
    Raises:
        HTTPException: If MR not found
    """
    # Get company database
    company_db = get_company_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(mr_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MR ID"
        )
    
    # Find MR
    mr = await company_db.mrs.find_one({"_id": ObjectId(mr_id)})
    
    if not mr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MR not found"
        )
    
    # Convert ObjectId to string and remove password_hash
    mr["id"] = str(mr.pop("_id"))
    mr.pop("password_hash", None)
    
    # Fetch doctor details for assigned_doctors
    doctor_details = []
    if mr.get("assigned_doctors"):
        for doctor_id in mr["assigned_doctors"]:
            if ObjectId.is_valid(doctor_id):
                doctor = await company_db.doctors.find_one(
                    {"_id": ObjectId(doctor_id)},
                    {"name": 1}
                )
                if doctor:
                    doctor_details.append({
                        "id": doctor_id,
                        "name": doctor["name"]
                    })
    
    mr["assigned_doctors"] = doctor_details
    
    return mr


async def update_mr(
    mr_id: str,
    update_data: Dict[str, Any],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update MR information.
    Only company admin can update MRs.
    
    Args:
        mr_id: MR's ID
        update_data: Fields to update
        current_user: Current authenticated user
    
    Returns:
        dict: Success message and updated fields
    
    Raises:
        HTTPException: If MR not found or doctors already assigned
    """
    # Get company database
    company_db = get_company_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(mr_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MR ID"
        )
    
    # Remove None values from update_data
    update_data = {k: v for k, v in update_data.items() if v is not None}
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    # If updating assigned_doctors, validate they're not already assigned to another MR
    if "assigned_doctors" in update_data:
        new_doctor_ids = update_data["assigned_doctors"]
        
        if new_doctor_ids:
            # Find any OTHER MR that has any of these doctors assigned
            existing_assignment = await company_db.mrs.find_one({
                "_id": {"$ne": ObjectId(mr_id)},  # Exclude current MR
                "assigned_doctors": {"$in": new_doctor_ids}
            })
            
            if existing_assignment:
                # Find which doctor is already assigned
                for doctor_id in new_doctor_ids:
                    if doctor_id in existing_assignment.get("assigned_doctors", []):
                        # Get doctor name for better error message
                        doctor = await company_db.doctors.find_one(
                            {"_id": ObjectId(doctor_id)},
                            {"name": 1}
                        )
                        doctor_name = doctor["name"] if doctor else "Unknown"
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Doctor {doctor_name} is already assigned to MR {existing_assignment.get('name')}"
                        )
    
    # Store the fields that will be updated (before adding updated_at)
    updated_fields = update_data.copy()
    
    # Add updated_at timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update MR
    result = await company_db.mrs.update_one(
        {"_id": ObjectId(mr_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MR not found"
        )
    
    # Get MR details for logging
    mr = await company_db.mrs.find_one({"_id": ObjectId(mr_id)})
    
    # Determine action type and severity based on what was updated
    if "is_active" in updated_fields:
        if updated_fields["is_active"]:
            action_type = ActivityLogAction.USER_ACTIVATED
            severity = LogSeverity.INFO
        else:
            action_type = ActivityLogAction.USER_DEACTIVATED
            severity = LogSeverity.CRITICAL
    else:
        action_type = ActivityLogAction.USER_UPDATED
        severity = LogSeverity.INFO
    
    # Log activity
    await log_activity(
        action_type=action_type,
        actor=current_user,
        target_type=TargetType.MR,
        target_id=mr_id,
        target_name=mr.get("name"),
        details={"updated_fields": list(updated_fields.keys())},
        severity=severity
    )
    
    return {
        "message": "MR updated successfully",
        "updated_fields": updated_fields
    }


async def delete_mr(mr_id: str, current_user: Dict[str, Any]) -> Dict[str, str]:
    """
    Soft delete an MR (set is_active to false).
    Only company admin can delete MRs.
    
    Args:
        mr_id: MR's ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If MR not found
    
    Note: This is a soft delete - MR is marked as inactive but not removed from database.
    """
    # Get company database
    company_db = get_company_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(mr_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MR ID"
        )
    
    # Soft delete: Set is_active to false
    result = await company_db.mrs.update_one(
        {"_id": ObjectId(mr_id)},
        {
            "$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MR not found"
        )
    
    # Get MR details for logging
    mr = await company_db.mrs.find_one({"_id": ObjectId(mr_id)})
    
    # Log activity
    await log_activity(
        action_type=ActivityLogAction.USER_DEACTIVATED,
        actor=current_user,
        target_type=TargetType.MR,
        target_id=mr_id,
        target_name=mr.get("name"),
        details={"reason": "Admin deactivation"},
        severity=LogSeverity.CRITICAL
    )
    
    return {"message": "MR deactivated successfully"}



def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone(phone: str) -> bool:
    """Validate phone number (must be 10 digits)"""
    # Remove any spaces or special characters
    phone_clean = re.sub(r'[^0-9]', '', phone)
    return len(phone_clean) == 10 and phone_clean.isdigit()


async def bulk_upload_mrs(
    file: UploadFile,
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Bulk upload MRs from CSV or Excel file.
    Only admin can perform bulk upload.
    
    Args:
        file: Uploaded CSV or Excel file
        current_user: Current authenticated user (must be admin)
    
    Returns:
        dict: Upload summary with success count, failed count, and error details
    
    Raises:
        HTTPException: If file format is invalid or file is too large
    """
    # Get company database
    company_db = get_company_database()
    
    # Validate file type
    filename = file.filename.lower()
    if not (filename.endswith('.csv') or filename.endswith('.xlsx') or filename.endswith('.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only CSV and Excel (.xlsx, .xls) files are supported."
        )
    
    # Read file content
    try:
        content = await file.read()
        
        # Check file size (max 5MB)
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds 5MB limit"
            )
        
        # Parse file based on type
        if filename.endswith('.csv'):
            df = pd.read_csv(BytesIO(content))
        else:
            df = pd.read_excel(BytesIO(content))
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse file: {str(e)}"
        )
    
    # Validate required columns
    required_columns = ['name', 'email', 'phone', 'territory']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required columns: {', '.join(missing_columns)}. Required columns are: {', '.join(required_columns)}"
        )
    
    # Check max rows limit (100)
    if len(df) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File contains {len(df)} rows. Maximum allowed is 100 rows per upload."
        )
    
    # Initialize counters and error list
    total_rows = len(df)
    successful = 0
    failed = 0
    errors = []
    
    # Get default password
    default_password = settings.DEFAULT_USER_PASSWORD
    password_hash = hash_password(default_password)
    
    # Process each row
    for index, row in df.iterrows():
        row_number = index + 2  # +2 because: +1 for 0-index, +1 for header row
        row_errors = []
        
        # Extract and clean data
        name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
        email = str(row.get('email', '')).strip().lower() if pd.notna(row.get('email')) else ''
        phone = str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else ''
        territory = str(row.get('territory', '')).strip() if pd.notna(row.get('territory')) else ''
        
        # Validate required fields
        if not name:
            row_errors.append("Name is required")
        
        if not email:
            row_errors.append("Email is required")
        elif not validate_email(email):
            row_errors.append("Invalid email format")
        
        if not phone:
            row_errors.append("Phone is required")
        elif not validate_phone(phone):
            row_errors.append("Phone must be 10 digits")
        
        if not territory:
            row_errors.append("Territory is required")
        
        # If basic validation failed, skip to next row
        if row_errors:
            failed += 1
            errors.append({
                "row": row_number,
                "name": name if name else None,
                "email": email if email else None,
                "phone": phone if phone else None,
                "error": "; ".join(row_errors)
            })
            continue
        
        # Check for duplicate email in database
        existing_email = await company_db.mrs.find_one({"email": email})
        if existing_email:
            failed += 1
            errors.append({
                "row": row_number,
                "name": name,
                "email": email,
                "error": "Email already exists in database"
            })
            continue
        
        # Check for duplicate phone in database
        existing_phone = await company_db.mrs.find_one({"phone": phone})
        if existing_phone:
            failed += 1
            errors.append({
                "row": row_number,
                "name": name,
                "phone": phone,
                "error": "Phone number already exists in database"
            })
            continue
        
        # All validations passed, create MR document
        try:
            mr_doc = {
                "name": name,
                "email": email,
                "password_hash": password_hash,
                "phone": phone,
                "territory": territory,
                "assigned_doctors": [],  # Empty on bulk upload
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Insert into database
            await company_db.mrs.insert_one(mr_doc)
            successful += 1
        
        except Exception as e:
            failed += 1
            errors.append({
                "row": row_number,
                "name": name,
                "email": email,
                "error": f"Database error: {str(e)}"
            })
    
    # Prepare response message
    if failed == 0:
        message = f"Bulk upload completed successfully. All {successful} MRs added."
    elif successful == 0:
        message = f"Bulk upload failed. All {failed} rows had errors."
    else:
        message = f"Bulk upload completed. {successful} MRs added successfully, {failed} rows failed."
    
    # Log bulk upload activity
    if successful > 0:
        await log_activity(
            action_type=ActivityLogAction.BULK_UPLOAD_MRS,
            actor=current_user,
            target_type=TargetType.MR,
            target_id=None,
            target_name=None,
            details={
                "total_rows": total_rows,
                "successful": successful,
                "failed": failed,
                "filename": file.filename
            },
            severity=LogSeverity.INFO
        )
    
    return {
        "total_rows": total_rows,
        "successful": successful,
        "failed": failed,
        "errors": errors,
        "message": message
    }
