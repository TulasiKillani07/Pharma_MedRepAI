"""
Doctor service - Business logic for doctor operations.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status, UploadFile
from fastapi.responses import StreamingResponse
from bson import ObjectId
import pandas as pd
import re
from io import BytesIO, StringIO
from app.database import get_database
from app.core.security import hash_password, generate_random_password
from app.core.validators import PhoneValidator
from app.config import settings
from app.api.v1.activity_logs.helpers import log_activity
from app.api.v1.email.service import send_invitation_email, send_bulk_upload_summary_email
from app.models.activity_log_model import ActivityLogAction, ActorRole, TargetType, LogSeverity


def get_company_database():
    """
    Get company database.
    
    TODO: This is temporary. Will be replaced with dynamic database
    selection based on company_slug from JWT token.
    
    For now, uses DATABASE_NAME from .env
    """
    return get_database()


async def create_doctor(
    name: str,
    email: str,
    password: Optional[str],
    phone: str,
    specialization: str,
    classification: str,
    hospital: Optional[str],
    license_number: Optional[str],
    address: Optional[str],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a new doctor account.
    Only company admin can create doctors.
    
    Args:
        name: Doctor's full name
        email: Doctor's email
        password: Plain text password (optional, uses default if not provided)
        phone: Phone number
        specialization: Medical specialization
        classification: Doctor classification (A/B/C) for SFE tracking
        hospital: Hospital name (optional)
        license_number: Medical license number (optional)
        address: Address (optional)
        current_user: Current authenticated user
    
    Returns:
        dict: Success message and doctor ID
    
    Raises:
        HTTPException: If email already exists
    """
    # Get company database
    company_db = get_company_database()
    
    # Check if email already exists
    existing_doctor = await company_db.doctors.find_one({"email": email})
    if existing_doctor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Use default password if not provided
    if not password:
        password = generate_random_password()  # Generate strong random password
    
    # Store plain password for email (before hashing)
    plain_password = password
    
    # Hash password
    password_hash = hash_password(password)
    
    # Get admin info from JWT token (no database query needed!)
    admin_name = current_user.get("full_name", "Admin")
    admin_department = current_user.get("department", "general")
    
    # Create doctor document
    doctor_doc = {
        "name": name,
        "email": email,
        "password_hash": password_hash,
        "phone": phone,
        "specialization": specialization,
        "classification": classification,
        "hospital": hospital,
        "license_number": license_number,
        "address": address,
        "is_active": True,
        "is_password_changed": False,  # User must change password on first login
        "password_changed_at": None,
        "first_login_completed": False,  # Track first login
        "first_login_at": None,
        "added_by": {
            "role": "ADMIN",
            "id": current_user["_id"],
            "name": admin_name,
            "department": admin_department
        },
        "approved_by": None,  # Admin added directly, no approval needed
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Insert into database
    result = await company_db.doctors.insert_one(doctor_doc)
    
    # Log activity
    await log_activity(
        action_type=ActivityLogAction.USER_CREATED,
        actor=current_user,
        target_type=TargetType.DOCTOR,
        target_id=str(result.inserted_id),
        target_name=name,
        details={
            "email": email,
            "specialization": specialization,
            "hospital": hospital
        },
        severity=LogSeverity.INFO
    )
    
    # Send invitation email with credentials
    try:
        await send_invitation_email(
            to_email=email,
            name=name,
            role="doctor",
            email=email,
            password=plain_password
        )
    except Exception as e:
        # Log email error but don't fail the creation
        from app.utils.logger import get_medrep_logger
        logger = get_medrep_logger(__name__)
        logger.error(f"Failed to send invitation email to {email}: {str(e)}")
    
    return {
        "message": "Doctor added successfully",
        "doctor_id": str(result.inserted_id)
    }


async def get_all_doctors(current_user: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get all doctors for a company.
    - Admin: Can see all doctors
    - MR: Can see only their assigned doctors
    - Doctor: Can see all doctors
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        list: List of doctor documents
    """
    # Get company database
    company_db = get_company_database()
    
    # Check user role
    user_role = current_user.get("role")
    
    # If MR, filter to show only assigned doctors
    if user_role == "MR":
        # Get MR's assigned doctors
        mr_id = current_user.get("_id")
        mr = await company_db.mrs.find_one({"_id": ObjectId(mr_id)}, {"assigned_doctors": 1})
        
        if not mr or not mr.get("assigned_doctors"):
            # MR has no assigned doctors
            return []
        
        assigned_doctor_ids = mr.get("assigned_doctors", [])
        
        # Get only assigned doctors
        doctors_cursor = company_db.doctors.find({
            "_id": {"$in": [ObjectId(doc_id) for doc_id in assigned_doctor_ids if ObjectId.is_valid(doc_id)]}
        })
    else:
        # Admin and Doctor can see all doctors
        doctors_cursor = company_db.doctors.find()
    
    doctors = await doctors_cursor.to_list(length=None)
    
    # Convert ObjectId to string and remove password_hash
    for doctor in doctors:
        doctor["id"] = str(doctor.pop("_id"))
        doctor.pop("password_hash", None)
        
        # Add default classification if not present (for backward compatibility)
        if "classification" not in doctor:
            doctor["classification"] = "C"
        
        # For MR users: Remove added_by field (they know they added it, only need to see who approved)
        if user_role == "MR":
            doctor.pop("added_by", None)
    
    return doctors


async def get_available_doctors(current_user: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get doctors who are NOT assigned to any MR.
    Only admin can access this.
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        list: List of unassigned doctor documents
    """
    # Get company database
    company_db = get_company_database()
    
    # Get all MRs and collect assigned doctor IDs
    mrs_cursor = company_db.mrs.find({}, {"assigned_doctors": 1})
    mrs = await mrs_cursor.to_list(length=None)
    
    # Collect all assigned doctor IDs
    assigned_doctor_ids = set()
    for mr in mrs:
        if mr.get("assigned_doctors"):
            assigned_doctor_ids.update(mr["assigned_doctors"])
    
    # Get all doctors
    doctors_cursor = company_db.doctors.find()
    doctors = await doctors_cursor.to_list(length=None)
    
    # Filter out assigned doctors
    available_doctors = []
    for doctor in doctors:
        doctor_id = str(doctor["_id"])
        if doctor_id not in assigned_doctor_ids:
            doctor["id"] = doctor_id
            doctor.pop("_id")
            doctor.pop("password_hash", None)
            
            # Add default classification if not present (for backward compatibility)
            if "classification" not in doctor:
                doctor["classification"] = "C"
            
            available_doctors.append(doctor)
    
    return available_doctors


async def get_doctor_by_id(doctor_id: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a single doctor by ID.
    All roles can view doctor details.
    
    Args:
        doctor_id: Doctor's ID
        current_user: Current authenticated user
    
    Returns:
        dict: Doctor document
    
    Raises:
        HTTPException: If doctor not found
    """
    # Get company database
    company_db = get_company_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid doctor ID"
        )
    
    # Find doctor
    doctor = await company_db.doctors.find_one({"_id": ObjectId(doctor_id)})
    
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    # Convert ObjectId to string and remove password_hash
    doctor["id"] = str(doctor.pop("_id"))
    doctor.pop("password_hash", None)
    
    # Add default classification if not present (for backward compatibility)
    if "classification" not in doctor:
        doctor["classification"] = "C"
    
    # For MR users: Remove added_by field (they know they added it, only need to see who approved)
    user_role = current_user.get("role")
    if user_role == "MR":
        doctor.pop("added_by", None)
    
    return doctor


async def update_doctor(
    doctor_id: str,
    update_data: Dict[str, Any],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update doctor information.
    Admin can update any doctor. Doctor can update only their own profile.
    
    Args:
        doctor_id: Doctor's ID
        update_data: Fields to update
        current_user: Current authenticated user
    
    Returns:
        dict: Success message and updated fields
    
    Raises:
        HTTPException: If doctor not found or unauthorized
    """
    # Get company database
    company_db = get_company_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid doctor ID"
        )
    
    # Check authorization
    user_role = current_user.get("role")
    user_id = current_user.get("_id")  # Changed from "sub" to "_id"
    
    # If user is a doctor, they can only update their own profile
    if user_role == "DOCTOR":
        if user_id != doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctors can only update their own profile"
            )
        
        # Doctors cannot update is_active status
        if "is_active" in update_data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctors cannot change their active status"
            )
    
    # Remove None values and email from update_data
    update_data = {k: v for k, v in update_data.items() if v is not None and k != "email"}
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    # Store the fields that will be updated (before adding updated_at)
    updated_fields = update_data.copy()
    
    # Add updated_at timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update doctor
    result = await company_db.doctors.update_one(
        {"_id": ObjectId(doctor_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    # Get doctor details for logging
    doctor = await company_db.doctors.find_one({"_id": ObjectId(doctor_id)})
    
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
        target_type=TargetType.DOCTOR,
        target_id=doctor_id,
        target_name=doctor.get("name"),
        details={"updated_fields": list(updated_fields.keys())},
        severity=severity
    )
    
    return {
        "message": "Doctor updated successfully",
        "updated_fields": updated_fields
    }


async def delete_doctor(doctor_id: str, current_user: Dict[str, Any]) -> Dict[str, str]:
    """
    Soft delete a doctor (set is_active to false).
    Only company admin can delete doctors.
    
    Args:
        doctor_id: Doctor's ID
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If doctor not found
    
    Note: This is a soft delete - doctor is marked as inactive but not removed from database.
    """
    # Get company database
    company_db = get_company_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid doctor ID"
        )
    
    # Soft delete: Set is_active to false
    result = await company_db.doctors.update_one(
        {"_id": ObjectId(doctor_id)},
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
            detail="Doctor not found"
        )
    
    # Get doctor details for logging
    doctor = await company_db.doctors.find_one({"_id": ObjectId(doctor_id)})
    
    # Log activity
    await log_activity(
        action_type=ActivityLogAction.USER_DEACTIVATED,
        actor=current_user,
        target_type=TargetType.DOCTOR,
        target_id=doctor_id,
        target_name=doctor.get("name"),
        details={"reason": "Admin deactivation"},
        severity=LogSeverity.CRITICAL
    )
    
    return {"message": "Doctor deactivated successfully"}



def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

async def download_doctors_template() -> StreamingResponse:
    """Generate and download CSV template for bulk doctor upload"""
    
    # Define template columns
    columns = [
        "name",
        "email",
        "phone",
        "specialization",
        "classification",
        "hospital",
        "license_number",
        "address"
    ]
    
    # Create sample row
    sample_row = {
        "name": "Dr. John Smith",
        "email": "john.smith@example.com",
        "phone": "+919876543210",
        "specialization": "Cardiologist",
        "classification": "A",
        "hospital": "City Hospital",
        "license_number": "MED12345",
        "address": "123 Medical Street, City"
    }
    
    df = pd.DataFrame([sample_row], columns=columns)
    
    # Convert to CSV
    output = StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    # Return as downloadable file
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=doctors_template.csv"}
    )


async def bulk_upload_doctors(
    file: UploadFile,
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Bulk upload doctors from CSV or Excel file.
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
    required_columns = ['name', 'email', 'phone', 'specialization', 'classification']
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
    created_users = []  # Track created users for email summary
    
    # Process each row
    for index, row in df.iterrows():
        row_number = index + 2  # +2 because: +1 for 0-index, +1 for header row
        row_errors = []
        
        # Extract and clean data
        name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
        email = str(row.get('email', '')).strip().lower() if pd.notna(row.get('email')) else ''
        phone = str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else ''
        specialization = str(row.get('specialization', '')).strip() if pd.notna(row.get('specialization')) else ''
        classification = str(row.get('classification', '')).strip().upper() if pd.notna(row.get('classification')) else ''
        hospital = str(row.get('hospital', '')).strip() if pd.notna(row.get('hospital')) else None
        license_number = str(row.get('license_number', '')).strip() if pd.notna(row.get('license_number')) else None
        address = str(row.get('address', '')).strip() if pd.notna(row.get('address')) else None
        
        # Validate required fields
        if not name:
            row_errors.append("Name is required")
        
        if not email:
            row_errors.append("Email is required")
        elif not validate_email(email):
            row_errors.append("Invalid email format")
        
        if not phone:
            row_errors.append("Phone is required")
        else:
            # Validate phone using PhoneValidator (accepts both formats)
            try:
                phone = PhoneValidator.validate(phone)
            except ValueError as e:
                row_errors.append(str(e))
        
        if not specialization:
            row_errors.append("Specialization is required")
        
        if not classification:
            row_errors.append("Classification is required")
        elif classification not in ['A', 'B', 'C']:
            row_errors.append("Classification must be A, B, or C")
        
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
        existing_email = await company_db.doctors.find_one({"email": email})
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
        existing_phone = await company_db.doctors.find_one({"phone": phone})
        if existing_phone:
            failed += 1
            errors.append({
                "row": row_number,
                "name": name,
                "phone": phone,
                "error": "Phone number already exists in database"
            })
            continue
        
        # All validations passed, create doctor document
        try:
            # Generate random password for this doctor
            random_password = generate_random_password()
            password_hash = hash_password(random_password)
            
            # Get admin info from JWT token (no database query needed!)
            admin_name = current_user.get("full_name", "Admin")
            admin_department = current_user.get("department", "general")
            
            doctor_doc = {
                "name": name,
                "email": email,
                "password_hash": password_hash,
                "phone": phone,
                "specialization": specialization,
                "classification": classification,
                "hospital": hospital if hospital else None,
                "license_number": license_number if license_number else None,
                "address": address if address else None,
                "is_active": True,
                "is_password_changed": False,  # User must change password on first login
                "password_changed_at": None,
                "first_login_completed": False,  # Track first login
                "first_login_at": None,
                "added_by": {
                    "role": "ADMIN",
                    "id": current_user["_id"],
                    "name": admin_name,
                    "department": admin_department
                },
                "approved_by": None,  # Bulk upload by admin, no approval needed
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Insert into database
            result = await company_db.doctors.insert_one(doctor_doc)
            successful += 1
            
            # Send invitation email
            email_sent = False
            try:
                email_sent = await send_invitation_email(
                    to_email=email,
                    name=name,
                    role="doctor",
                    email=email,
                    password=random_password
                )
            except Exception as email_error:
                from app.utils.logger import get_medrep_logger
                logger = get_medrep_logger(__name__)
                logger.error(f"Failed to send email to {email}: {str(email_error)}")
            
            # Track created user for summary
            created_users.append({
                "name": name,
                "email": email,
                "email_sent": email_sent
            })
        
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
        message = f"Bulk upload completed successfully. All {successful} doctors added."
    elif successful == 0:
        message = f"Bulk upload failed. All {failed} rows had errors."
    else:
        message = f"Bulk upload completed. {successful} doctors added successfully, {failed} rows failed."
    
    # Log bulk upload activity
    if successful > 0:
        await log_activity(
            action_type=ActivityLogAction.BULK_UPLOAD_DOCTORS,
            actor=current_user,
            target_type=TargetType.DOCTOR,
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
    
    # Send summary email to admin
    if successful > 0 and created_users:
        try:
            successful_emails = sum(1 for user in created_users if user["email_sent"])
            failed_emails = len(created_users) - successful_emails
            
            await send_bulk_upload_summary_email(
                admin_email=current_user.get("email"),
                admin_name=current_user.get("name", "Admin"),
                role="doctor",
                total_created=successful,
                successful_emails=successful_emails,
                failed_emails=failed_emails,
                created_users=created_users
            )
        except Exception as e:
            from app.utils.logger import get_medrep_logger
            logger = get_medrep_logger(__name__)
            logger.error(f"Failed to send summary email to admin: {str(e)}")
    
    return {
        "total_rows": total_rows,
        "successful": successful,
        "failed": failed,
        "errors": errors,
        "message": message
    }



# ============================================================================
# DOCTOR REQUEST FUNCTIONS (MR Request → Admin Approval Workflow)
# ============================================================================

async def create_doctor_request(
    name: str,
    email: str,
    phone: str,
    specialization: str,
    classification: str,
    hospital: Optional[str],
    license_number: Optional[str],
    address: Optional[str],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a doctor addition request (MR only).
    MR submits doctor details, admin must approve before doctor is created.
    
    Args:
        name: Doctor's full name
        email: Doctor's email
        phone: Phone number
        specialization: Medical specialization
        classification: Doctor classification (A/B/C) for SFE tracking
        hospital: Hospital name (optional)
        license_number: Medical license number (optional)
        address: Address (optional)
        current_user: Current authenticated user (must be MR)
    
    Returns:
        dict: Success message and request ID
    
    Raises:
        HTTPException: If email already exists or request already pending
    """
    from app.api.v1.notifications.service import create_notification
    from app.models.notification_model import NotificationType
    
    # Get company database
    company_db = get_company_database()
    
    # Check if email already exists in doctors collection
    existing_doctor = await company_db.doctors.find_one({"email": email})
    if existing_doctor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctor with this email already exists in the system"
        )
    
    # Check if there's already a pending request for this email
    existing_request = await company_db.doctor_requests.find_one({
        "email": email,
        "status": "pending"
    })
    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pending request for this doctor already exists. Please wait for admin approval."
        )
    
    # Create doctor request document
    request_doc = {
        "requested_by": current_user["_id"],
        "requested_by_name": current_user["name"],
        "requested_by_email": current_user["email"],
        "status": "pending",
        "name": name,
        "email": email,
        "phone": phone,
        "specialization": specialization,
        "classification": classification,
        "hospital": hospital,
        "license_number": license_number,
        "address": address,
        "reviewed_by": None,
        "reviewed_by_name": None,
        "reviewed_at": None,
        "rejection_reason": None,
        "doctor_id": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Insert into database
    result = await company_db.doctor_requests.insert_one(request_doc)
    request_id = str(result.inserted_id)
    
    # Get all admin users to send notifications
    admins_cursor = company_db.admins.find({"is_active": True}, {"_id": 1})
    admins = await admins_cursor.to_list(length=None)
    
    # Send notifications to all admins in parallel
    import asyncio
    notification_tasks = [
        create_notification(
            user_id=str(admin["_id"]),
            notification_type=NotificationType.DOCTOR_REQUEST_PENDING,
            title="New Doctor Addition Request",
            message=f"{current_user['name']} requested to add Dr. {name} ({specialization})",
            data={
                "request_id": request_id,
                "mr_id": current_user["_id"],
                "mr_name": current_user["name"],
                "doctor_name": name,
                "doctor_email": email,
                "specialization": specialization
            }
        )
        for admin in admins
    ]
    await asyncio.gather(*notification_tasks)
    
    # Log activity
    await log_activity(
        action_type=ActivityLogAction.USER_CREATED,  # Using existing action type
        actor=current_user,
        target_type=TargetType.DOCTOR,
        target_id=request_id,
        target_name=f"Doctor Request: {name}",
        details={
            "email": email,
            "specialization": specialization,
            "hospital": hospital,
            "status": "pending_approval"
        },
        severity=LogSeverity.INFO
    )
    
    return {
        "message": "Doctor request submitted successfully. Waiting for admin approval.",
        "request_id": request_id
    }


async def get_doctor_requests(
    current_user: Dict[str, Any],
    status_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get doctor requests.
    - Admin: Can see all requests
    - MR: Can see only their own requests
    
    Args:
        current_user: Current authenticated user
        status_filter: Filter by status (pending, approved, rejected)
    
    Returns:
        list: List of doctor request documents
    """
    from app.utils.logger import get_medrep_logger
    logger = get_medrep_logger(__name__)
    
    try:
        # Get company database
        company_db = get_company_database()
        
        # Build query based on user role
        query = {}
        user_role = current_user.get("role")
        
        if user_role == "MR":
            # MR can only see their own requests
            query["requested_by"] = current_user["_id"]
        # Admin can see all requests (no filter)
        
        # Add status filter if provided
        if status_filter:
            query["status"] = status_filter
        
        # Get requests
        requests_cursor = company_db.doctor_requests.find(query).sort("created_at", -1)
        requests = await requests_cursor.to_list(length=None)
        
        # Note: Approved requests are deleted after doctor creation,
        # so this will only return pending and rejected requests
        
        # Filter out requests for doctors that have been deleted
        # (Only for rejected requests - approved requests are already deleted)
        filtered_requests = []
        for request in requests:
            # Convert ObjectId to string
            request["request_id"] = str(request.pop("_id"))
            
            # Add default classification if not present (backward compatibility)
            if "classification" not in request:
                request["classification"] = "C"
            
            # Note: We no longer need to check if approved doctors exist
            # because approved requests are deleted after doctor creation
            # Only pending and rejected requests remain in the collection
            
            filtered_requests.append(request)
        
        return filtered_requests
        
    except Exception as e:
        logger.error(f"Error in get_doctor_requests: {str(e)}", exc_info=True)
        raise


async def approve_doctor_request(
    request_id: str,
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Approve a doctor request and create the doctor account (Admin only).
    
    Args:
        request_id: Doctor request ID
        current_user: Current authenticated user (must be admin)
    
    Returns:
        dict: Success message and created doctor ID
    
    Raises:
        HTTPException: If request not found, already processed, or email exists
    """
    from app.api.v1.notifications.service import create_notification
    from app.models.notification_model import NotificationType
    from app.utils.logger import get_medrep_logger
    
    logger = get_medrep_logger(__name__)
    
    # Get company database
    company_db = get_company_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(request_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request ID"
        )
    
    # Find request
    request = await company_db.doctor_requests.find_one({"_id": ObjectId(request_id)})
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor request not found"
        )
    
    # Check if already processed
    if request["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request already {request['status']}"
        )
    
    # Check if email already exists (in case it was added after request)
    existing_doctor = await company_db.doctors.find_one({"email": request["email"]})
    if existing_doctor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctor with this email already exists in the system"
        )
    
    # Generate random password for the doctor
    random_password = generate_random_password()
    password_hash = hash_password(random_password)
    
    # Get admin info from JWT token (no database query needed!)
    admin_name = current_user.get("full_name", "Admin")
    admin_department = current_user.get("department", "general")
    
    # Create doctor document
    doctor_doc = {
        "name": request["name"],
        "email": request["email"],
        "password_hash": password_hash,
        "phone": request["phone"],
        "specialization": request["specialization"],
        "classification": request.get("classification", "C"),  # Default to C if not provided (for backward compatibility)
        "hospital": request.get("hospital"),
        "license_number": request.get("license_number"),
        "address": request.get("address"),
        "is_active": True,
        "is_password_changed": False,
        "password_changed_at": None,
        "first_login_completed": False,
        "first_login_at": None,
        "added_by": {
            "role": "MR",
            "id": request["requested_by"],
            "name": request["requested_by_name"]
        },
        "approved_by": {
            "role": "ADMIN",
            "id": current_user["_id"],
            "name": admin_name,
            "department": admin_department
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Insert doctor into database
    doctor_result = await company_db.doctors.insert_one(doctor_doc)
    doctor_id = str(doctor_result.inserted_id)
    
    logger.info(f"Doctor created from approved request - Doctor ID: {doctor_id}, Email: {request['email']}, Requested by: {request['requested_by_name']}")
    
    # Add doctor to MR's assigned_doctors list
    mr_id = request["requested_by"]
    mr_update_result = await company_db.mrs.update_one(
        {"_id": ObjectId(mr_id)},
        {
            "$addToSet": {
                "assigned_doctors": doctor_id
            },
            "$set": {
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if mr_update_result.matched_count > 0:
        logger.info(f"Doctor auto-assigned to MR - Doctor: {doctor_id}, MR: {mr_id}")
    else:
        logger.warning(f"Failed to auto-assign doctor to MR - Doctor: {doctor_id}, MR: {mr_id} not found")
    
    # Get admin name from JWT token (already fetched above, reuse it)
    # admin_name and admin_department are already set from JWT above
    
    # Delete the request from doctor_requests collection (no longer needed)
    await company_db.doctor_requests.delete_one({"_id": ObjectId(request_id)})
    
    # Send notification to MR who requested
    await create_notification(
        user_id=request["requested_by"],
        notification_type=NotificationType.DOCTOR_REQUEST_APPROVED,
        title="Doctor Request Approved",
        message=f"Your request to add Dr. {request['name']} has been approved by {admin_name}",
        data={
            "request_id": request_id,
            "doctor_id": doctor_id,
            "doctor_name": request["name"],
            "doctor_email": request["email"],
            "approved_by": admin_name
        }
    )
    
    # Log activity
    await log_activity(
        action_type=ActivityLogAction.USER_CREATED,
        actor=current_user,
        target_type=TargetType.DOCTOR,
        target_id=doctor_id,
        target_name=request["name"],
        details={
            "email": request["email"],
            "specialization": request["specialization"],
            "hospital": request.get("hospital"),
            "requested_by": request["requested_by_name"],
            "approved_from_request": request_id
        },
        severity=LogSeverity.INFO
    )
    
    # Send invitation email with credentials
    try:
        await send_invitation_email(
            to_email=request["email"],
            name=request["name"],
            role="doctor",
            email=request["email"],
            password=random_password
        )
    except Exception as e:
        # Log email error but don't fail the approval
        from app.utils.logger import get_medrep_logger
        logger = get_medrep_logger(__name__)
        logger.error(f"Failed to send invitation email to {request['email']}: {str(e)}")
    
    return {
        "message": "Doctor request approved and doctor account created successfully",
        "doctor_id": doctor_id
    }


async def reject_doctor_request(
    request_id: str,
    rejection_reason: str,
    current_user: Dict[str, Any]
) -> Dict[str, str]:
    """
    Reject a doctor request (Admin only).
    
    Args:
        request_id: Doctor request ID
        rejection_reason: Reason for rejection
        current_user: Current authenticated user (must be admin)
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If request not found or already processed
    """
    from app.api.v1.notifications.service import create_notification
    from app.models.notification_model import NotificationType
    from app.utils.logger import get_medrep_logger
    
    logger = get_medrep_logger(__name__)
    
    # Get company database
    company_db = get_company_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(request_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request ID"
        )
    
    # Find request
    request = await company_db.doctor_requests.find_one({"_id": ObjectId(request_id)})
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor request not found"
        )
    
    # Check if already processed
    if request["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request already {request['status']}"
        )
    
    # Get admin info from JWT token (no database query needed!)
    admin_name = current_user.get("full_name", "Admin")
    admin_department = current_user.get("department", "general")
    
    # Update request status
    await company_db.doctor_requests.update_one(
        {"_id": ObjectId(request_id)},
        {
            "$set": {
                "status": "rejected",
                "reviewed_by": current_user["_id"],
                "reviewed_by_name": admin_name,
                "reviewed_at": datetime.utcnow(),
                "rejection_reason": rejection_reason,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    logger.info(f"Doctor request rejected - Request ID: {request_id}, Requested by: {request['requested_by_name']}, Reason: {rejection_reason}")
    
    # Send notification to MR who requested
    await create_notification(
        user_id=request["requested_by"],
        notification_type=NotificationType.DOCTOR_REQUEST_REJECTED,
        title="Doctor Request Rejected",
        message=f"Your request to add Dr. {request['name']} was rejected by {admin_name}",
        data={
            "request_id": request_id,
            "doctor_name": request["name"],
            "doctor_email": request["email"],
            "rejected_by": admin_name,
            "rejection_reason": rejection_reason
        }
    )
    
    # Log activity
    await log_activity(
        action_type=ActivityLogAction.USER_UPDATED,  # Using existing action type
        actor=current_user,
        target_type=TargetType.DOCTOR,
        target_id=request_id,
        target_name=f"Doctor Request: {request['name']}",
        details={
            "email": request["email"],
            "requested_by": request["requested_by_name"],
            "rejection_reason": rejection_reason,
            "status": "rejected"
        },
        severity=LogSeverity.WARNING
    )
    
    return {"message": "Doctor request rejected successfully"}
