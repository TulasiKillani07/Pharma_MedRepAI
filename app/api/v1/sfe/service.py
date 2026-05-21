"""
SFE (Sales Force Effectiveness) service - Business logic.
"""

from datetime import datetime, date
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.models.sfe_models import DoctorClass, DoctorAssignment, SFEConfig
from app.utils.logger import get_medrep_logger

# Initialize logger
logger = get_medrep_logger(__name__)


def get_company_database():
    """Get company database."""
    return get_database()


async def classify_doctor(
    doctor_id: str,
    classification: str,
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Classify a doctor (Admin only).
    Updates the doctor assignment with classification and visit frequency.
    
    Args:
        doctor_id: Doctor's ID
        classification: Doctor class (A/B/C)
        current_user: Current authenticated admin
    
    Returns:
        dict: Success message and classification details
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_company_database()
    admin_id = current_user["_id"]
    
    # Validate doctor ID
    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid doctor ID"
        )
    
    # Get doctor details
    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    # Get SFE config to determine visit frequency
    config = await get_sfe_config()
    visit_frequency = config["visit_frequency_config"].get(classification, 1)
    
    # Find which MR this doctor is assigned to
    # Check in MRs' assigned_doctors array
    mr = await db.mrs.find_one({"assigned_doctors": doctor_id})
    
    if not mr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor is not assigned to any MR. Please assign doctor to MR first."
        )
    
    # Check if assignment already exists
    existing_assignment = await db.doctor_assignments.find_one({
        "mr_id": str(mr["_id"]),
        "doctor_id": doctor_id
    })
    
    if existing_assignment:
        # Update existing assignment
        await db.doctor_assignments.update_one(
            {"_id": existing_assignment["_id"]},
            {
                "$set": {
                    "classification": classification,
                    "visit_frequency": visit_frequency,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        logger.info(f"Updated doctor classification: {doctor_id} -> {classification}")
    else:
        # Create new assignment
        assignment = DoctorAssignment(
            mr_id=str(mr["_id"]),
            mr_name=mr["name"],
            doctor_id=doctor_id,
            doctor_name=doctor["name"],
            classification=DoctorClass(classification),
            visit_frequency=visit_frequency,
            territory=mr.get("territory"),
            zone=mr.get("zone"),
            state=mr.get("state"),
            assigned_by=admin_id
        )
        
        await db.doctor_assignments.insert_one(assignment.model_dump())
        logger.info(f"Created doctor classification: {doctor_id} -> {classification}")
    
    return {
        "message": f"Doctor classified as {classification}-class successfully",
        "doctor_id": doctor_id,
        "doctor_name": doctor["name"],
        "classification": classification,
        "visit_frequency": visit_frequency,
        "mr_id": str(mr["_id"]),
        "mr_name": mr["name"]
    }


async def get_doctor_classification(
    doctor_id: str,
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get doctor classification details.
    
    Args:
        doctor_id: Doctor's ID
        current_user: Current authenticated user
    
    Returns:
        dict: Classification details
    
    Raises:
        HTTPException: If not found
    """
    db = get_company_database()
    
    # Validate doctor ID
    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid doctor ID"
        )
    
    # Find assignment
    assignment = await db.doctor_assignments.find_one({"doctor_id": doctor_id})
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor classification not found. Doctor may not be assigned to any MR."
        )
    
    # Convert ObjectId to string
    assignment["id"] = str(assignment.pop("_id"))
    
    return assignment


async def get_sfe_config() -> Dict[str, Any]:
    """
    Get SFE configuration.
    
    Returns:
        dict: SFE config
    """
    db = get_company_database()
    
    # Get config (single document)
    config = await db.sfe_config.find_one({"company_id": "default"})
    
    if not config:
        # Create default config if not exists
        default_config = SFEConfig()
        await db.sfe_config.insert_one(default_config.model_dump())
        logger.info("Created default SFE config")
        return default_config.model_dump()
    
    return config


async def update_sfe_config(
    config_data: Dict[str, int],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update SFE configuration (Admin only).
    
    Args:
        config_data: New visit frequency config (A, B, C)
        current_user: Current authenticated admin
    
    Returns:
        dict: Success message and updated config
    """
    db = get_company_database()
    admin_id = current_user["_id"]
    
    # Prepare update data
    visit_frequency_config = {
        "A": config_data["A"],
        "B": config_data["B"],
        "C": config_data["C"]
    }
    
    # Update or create config
    result = await db.sfe_config.update_one(
        {"company_id": "default"},
        {
            "$set": {
                "visit_frequency_config": visit_frequency_config,
                "updated_by": admin_id,
                "updated_at": datetime.utcnow()
            }
        },
        upsert=True
    )
    
    logger.info(f"Updated SFE config: {visit_frequency_config}")
    
    return {
        "message": "SFE configuration updated successfully",
        "visit_frequency_config": visit_frequency_config
    }


# ============================================================================
# SFE SETTINGS (VISIT TARGETS)
# ============================================================================

async def get_sfe_settings() -> Dict[str, Any]:
    """
    Get SFE settings (visit targets).
    Returns defaults if no settings exist.
    
    Returns:
        dict: SFE settings with classification targets
    """
    db = get_company_database()
    
    # Get settings (single document)
    settings = await db.sfe_settings.find_one({"company_id": "default"})
    
    if not settings:
        # Return defaults if no settings exist
        return {
            "classification_targets": {
                "A": 2,
                "B": 1,
                "C": 1
            }
        }
    
    # Format response
    response = {
        "classification_targets": settings.get("classification_targets", {"A": 2, "B": 1, "C": 1})
    }
    
    if "updated_at" in settings:
        response["updated_at"] = settings["updated_at"]
    
    if "updated_by" in settings:
        response["updated_by"] = {
            "name": settings["updated_by"].get("name", "Unknown")
        }
    
    return response


async def update_sfe_settings(
    classification_targets: Dict[str, int],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update SFE settings (Admin only).
    
    Args:
        classification_targets: New visit targets for A, B, C
        current_user: Current authenticated admin
    
    Returns:
        dict: Success message and updated targets
    """
    db = get_company_database()
    admin_id = current_user["_id"]
    admin_name = current_user.get("full_name", current_user.get("name", "Unknown"))
    
    # Prepare update data
    update_data = {
        "company_id": "default",
        "classification_targets": classification_targets,
        "updated_at": datetime.utcnow(),
        "updated_by": {
            "id": admin_id,
            "name": admin_name
        }
    }
    
    # Upsert settings
    await db.sfe_settings.update_one(
        {"company_id": "default"},
        {"$set": update_data},
        upsert=True
    )
    
    logger.info(f"Admin {admin_id} updated SFE settings: {classification_targets}")
    
    return {
        "message": "Settings updated successfully",
        "classification_targets": classification_targets
    }


async def get_mcr_report(
    month: int,
    year: int,
    mr_id: Optional[str],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get MCR (Monthly Call Report) - Doctor coverage percentage.
    
    Formula: MCR % = (Unique doctors with ≥1 completed visit this month / Total assigned doctors) × 100
    
    Args:
        month: Month (1-12)
        year: Year (e.g., 2026)
        mr_id: MR ID (optional, admin can query any MR)
        current_user: Current authenticated user
    
    Returns:
        dict: MCR report with visited/not-visited doctors
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_company_database()
    user_role = current_user.get("role")
    user_id = current_user["_id"]
    
    # Determine which MR to query
    if mr_id:
        # Admin querying specific MR
        if user_role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can query other MRs' data"
            )
        target_mr_id = mr_id
    else:
        # MR querying own data
        if user_role != "MR":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MR ID is required for admin queries"
            )
        target_mr_id = user_id
    
    # Validate MR ID
    if not ObjectId.is_valid(target_mr_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MR ID"
        )
    
    # Get MR details
    mr = await db.mrs.find_one({"_id": ObjectId(target_mr_id)})
    if not mr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MR not found"
        )
    
    # Get all assigned doctors for this MR
    assigned_doctors = await db.doctor_assignments.find({
        "mr_id": target_mr_id
    }).to_list(length=None)
    
    total_assigned = len(assigned_doctors)
    
    if total_assigned == 0:
        logger.info(f"MR {target_mr_id} has no assigned doctors")
        return {
            "mr_id": target_mr_id,
            "mr_name": mr["name"],
            "month": month,
            "year": year,
            "total_assigned": 0,
            "doctors_visited": 0,
            "doctors_not_visited": 0,
            "mcr_percentage": 0.0,
            "visited": [],
            "not_visited": []
        }
    
    # Create date range for the month
    from datetime import datetime as dt
    import calendar
    
    start_date = dt(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = dt(year, month, last_day, 23, 59, 59)
    
    # Get all completed visits for this MR in the given month
    visits = await db.visits.find({
        "mr_id": target_mr_id,
        "status": "completed",
        "completed_at": {
            "$gte": start_date,
            "$lte": end_date
        }
    }).to_list(length=None)
    
    # Count visits per doctor
    doctor_visit_count = {}
    doctor_last_visit = {}
    
    for visit in visits:
        doc_id = visit["doctor_id"]
        doctor_visit_count[doc_id] = doctor_visit_count.get(doc_id, 0) + 1
        
        # Track last visit date
        if doc_id not in doctor_last_visit or visit["completed_at"] > doctor_last_visit[doc_id]:
            doctor_last_visit[doc_id] = visit["completed_at"]
    
    # Categorize doctors
    visited_doctors = []
    not_visited_doctors = []
    
    for assignment in assigned_doctors:
        doc_id = assignment["doctor_id"]
        
        if doc_id in doctor_visit_count:
            # Doctor was visited
            visited_doctors.append({
                "doctor_id": doc_id,
                "doctor_name": assignment["doctor_name"],
                "classification": assignment.get("classification"),
                "visits_count": doctor_visit_count[doc_id],
                "last_visit_date": doctor_last_visit[doc_id]
            })
        else:
            # Doctor was not visited this month
            # Check if doctor was ever visited (get last visit from all time)
            last_visit_ever = await db.visits.find_one(
                {
                    "mr_id": target_mr_id,
                    "doctor_id": doc_id,
                    "status": "completed"
                },
                sort=[("completed_at", -1)]
            )
            
            not_visited_doctors.append({
                "doctor_id": doc_id,
                "doctor_name": assignment["doctor_name"],
                "classification": assignment.get("classification"),
                "last_visited": last_visit_ever["completed_at"] if last_visit_ever else None
            })
    
    # Calculate MCR percentage
    doctors_visited_count = len(visited_doctors)
    doctors_not_visited_count = len(not_visited_doctors)
    mcr_percentage = round((doctors_visited_count / total_assigned) * 100, 2) if total_assigned > 0 else 0.0
    
    logger.info(f"MCR for MR {target_mr_id} ({month}/{year}): {mcr_percentage}% ({doctors_visited_count}/{total_assigned})")
    
    return {
        "mr_id": target_mr_id,
        "mr_name": mr["name"],
        "month": month,
        "year": year,
        "total_assigned": total_assigned,
        "doctors_visited": doctors_visited_count,
        "doctors_not_visited": doctors_not_visited_count,
        "mcr_percentage": mcr_percentage,
        "visited": visited_doctors,
        "not_visited": not_visited_doctors
    }


async def get_mvc_report(
    month: int,
    year: int,
    mr_id: Optional[str],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get MVC (Monthly Visit Coverage) - Visit frequency compliance.
    
    Formula: MVC % = (Doctors who received ≥ required visits / Total assigned doctors) × 100
    
    Args:
        month: Month (1-12)
        year: Year (e.g., 2026)
        mr_id: MR ID (optional, admin can query any MR)
        current_user: Current authenticated user
    
    Returns:
        dict: MVC report with per-doctor compliance
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_company_database()
    user_role = current_user.get("role")
    user_id = current_user["_id"]
    
    # Determine which MR to query
    if mr_id:
        # Admin querying specific MR
        if user_role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can query other MRs' data"
            )
        target_mr_id = mr_id
    else:
        # MR querying own data
        if user_role != "MR":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MR ID is required for admin queries"
            )
        target_mr_id = user_id
    
    # Validate MR ID
    if not ObjectId.is_valid(target_mr_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MR ID"
        )
    
    # Get MR details
    mr = await db.mrs.find_one({"_id": ObjectId(target_mr_id)})
    if not mr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MR not found"
        )
    
    # Get all assigned doctors for this MR
    assigned_doctors = await db.doctor_assignments.find({
        "mr_id": target_mr_id
    }).to_list(length=None)
    
    total_assigned = len(assigned_doctors)
    
    if total_assigned == 0:
        logger.info(f"MR {target_mr_id} has no assigned doctors")
        return {
            "mr_id": target_mr_id,
            "mr_name": mr["name"],
            "month": month,
            "year": year,
            "total_assigned": 0,
            "fully_covered": 0,
            "under_covered": 0,
            "not_visited": 0,
            "mvc_percentage": 0.0,
            "avg_compliance": 0.0,
            "doctors": []
        }
    
    # Create date range for the month
    from datetime import datetime as dt
    import calendar
    
    start_date = dt(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = dt(year, month, last_day, 23, 59, 59)
    
    # Get all completed visits for this MR in the given month
    visits = await db.visits.find({
        "mr_id": target_mr_id,
        "status": "completed",
        "completed_at": {
            "$gte": start_date,
            "$lte": end_date
        }
    }).to_list(length=None)
    
    # Count visits per doctor
    doctor_visit_count = {}
    for visit in visits:
        doc_id = visit["doctor_id"]
        doctor_visit_count[doc_id] = doctor_visit_count.get(doc_id, 0) + 1
    
    # Analyze each doctor's compliance
    doctors_detail = []
    fully_covered_count = 0
    under_covered_count = 0
    not_visited_count = 0
    total_compliance = 0.0
    
    for assignment in assigned_doctors:
        doc_id = assignment["doctor_id"]
        classification = assignment.get("classification", "C")
        required_visits = assignment.get("visit_frequency", 1)
        actual_visits = doctor_visit_count.get(doc_id, 0)
        
        # Calculate compliance percentage
        compliance_pct = round((actual_visits / required_visits) * 100, 2) if required_visits > 0 else 0.0
        total_compliance += compliance_pct
        
        # Determine status
        if actual_visits >= required_visits:
            status = "covered"
            fully_covered_count += 1
        elif actual_visits > 0:
            status = "under"
            under_covered_count += 1
        else:
            status = "missed"
            not_visited_count += 1
        
        doctors_detail.append({
            "doctor_id": doc_id,
            "doctor_name": assignment["doctor_name"],
            "classification": classification,
            "required_visits": required_visits,
            "actual_visits": actual_visits,
            "status": status,
            "compliance_percentage": compliance_pct
        })
    
    # Calculate MVC percentage (doctors who met their requirement)
    mvc_percentage = round((fully_covered_count / total_assigned) * 100, 2) if total_assigned > 0 else 0.0
    
    # Calculate average compliance across all doctors
    avg_compliance = round(total_compliance / total_assigned, 2) if total_assigned > 0 else 0.0
    
    # Sort doctors by status (covered first, then under, then missed)
    status_order = {"covered": 0, "under": 1, "missed": 2}
    doctors_detail.sort(key=lambda x: (status_order[x["status"]], -x["compliance_percentage"]))
    
    logger.info(f"MVC for MR {target_mr_id} ({month}/{year}): {mvc_percentage}% ({fully_covered_count}/{total_assigned}), Avg Compliance: {avg_compliance}%")
    
    return {
        "mr_id": target_mr_id,
        "mr_name": mr["name"],
        "month": month,
        "year": year,
        "total_assigned": total_assigned,
        "fully_covered": fully_covered_count,
        "under_covered": under_covered_count,
        "not_visited": not_visited_count,
        "mvc_percentage": mvc_percentage,
        "avg_compliance": avg_compliance,
        "doctors": doctors_detail
    }




async def create_rcpa_commitment(
    commitment_data: Dict[str, Any],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create RCPA commitment manually (MR only).
    
    Args:
        commitment_data: Commitment details
        current_user: Current authenticated MR
    
    Returns:
        dict: Created commitment
    
    Raises:
        HTTPException: If validation fails
    """
    from app.models.sfe_models import PrescriptionCommitment
    
    db = get_company_database()
    mr_id = current_user["_id"]
    
    # Validate doctor ID
    doctor_id = commitment_data["doctor_id"]
    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid doctor ID"
        )
    
    # Get doctor details
    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    # Validate product ID
    product_id = commitment_data["product_id"]
    if not ObjectId.is_valid(product_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid product ID"
        )
    
    # Get product details
    product = await db.drugs.find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Get MR details
    mr = await db.mrs.find_one({"_id": ObjectId(mr_id)})
    
    # Create commitment
    commitment = PrescriptionCommitment(
        mr_id=mr_id,
        mr_name=mr["name"],
        doctor_id=doctor_id,
        doctor_name=doctor["name"],
        product_id=product_id,
        product_name=product["name"],
        rx_per_week=commitment_data["rx_per_week"],
        confidence=commitment_data.get("confidence", "medium"),
        visit_id=commitment_data.get("visit_id"),
        territory=mr.get("territory"),
        zone=mr.get("zone"),
        state=mr.get("state")
    )
    
    result = await db.prescription_commitments.insert_one(commitment.model_dump())
    
    logger.info(f"MR {mr_id} created RCPA commitment: {doctor_id} -> {product_id} ({commitment_data['rx_per_week']}/week)")
    
    commitment_dict = commitment.model_dump()
    commitment_dict["id"] = str(result.inserted_id)
    
    return commitment_dict


async def get_rcpa_commitments(
    month: Optional[int],
    year: Optional[int],
    mr_id: Optional[str],
    product_id: Optional[str],
    status_filter: Optional[str],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get RCPA commitments with filters.
    
    Args:
        month: Filter by month (optional)
        year: Filter by year (optional)
        mr_id: Filter by MR (admin only, optional)
        product_id: Filter by product (optional)
        status_filter: Filter by status (optional)
        current_user: Current authenticated user
    
    Returns:
        dict: List of commitments
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_company_database()
    user_role = current_user.get("role")
    user_id = current_user["_id"]
    
    # Build query
    query = {}
    
    # Determine which MR to query
    if mr_id:
        # Admin querying specific MR
        if user_role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can query other MRs' data"
            )
        query["mr_id"] = mr_id
    else:
        # MR querying own data
        if user_role == "MR":
            query["mr_id"] = user_id
        # Admin without mr_id gets all
    
    # Date filter
    if month and year:
        from datetime import datetime as dt
        import calendar
        
        start_date = dt(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = dt(year, month, last_day, 23, 59, 59)
        
        query["created_at"] = {
            "$gte": start_date,
            "$lte": end_date
        }
    
    # Product filter
    if product_id:
        if not ObjectId.is_valid(product_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid product ID"
            )
        query["product_id"] = product_id
    
    # Status filter
    if status_filter:
        query["status"] = status_filter
    
    # Get commitments
    commitments = await db.prescription_commitments.find(query).sort("created_at", -1).to_list(length=None)
    
    # Convert ObjectId to string
    for commitment in commitments:
        commitment["id"] = str(commitment.pop("_id"))
    
    logger.info(f"User {user_id} fetched {len(commitments)} RCPA commitments")
    
    return {
        "total": len(commitments),
        "commitments": commitments
    }


async def update_rcpa_commitment(
    commitment_id: str,
    update_data: Dict[str, Any],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update RCPA commitment (MR who created it, or Admin).
    
    Args:
        commitment_id: Commitment ID
        update_data: Fields to update
        current_user: Current authenticated user
    
    Returns:
        dict: Success message
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_company_database()
    user_role = current_user.get("role")
    user_id = current_user["_id"]
    
    # Validate commitment ID
    if not ObjectId.is_valid(commitment_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid commitment ID"
        )
    
    # Get commitment
    commitment = await db.prescription_commitments.find_one({"_id": ObjectId(commitment_id)})
    if not commitment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commitment not found"
        )
    
    # Check authorization
    if user_role != "ADMIN" and commitment["mr_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own commitments"
        )
    
    # Prepare update
    update_fields = {}
    if "rx_per_week" in update_data and update_data["rx_per_week"] is not None:
        update_fields["rx_per_week"] = update_data["rx_per_week"]
    if "confidence" in update_data and update_data["confidence"] is not None:
        update_fields["confidence"] = update_data["confidence"]
    if "status" in update_data and update_data["status"] is not None:
        update_fields["status"] = update_data["status"]
    
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    update_fields["updated_at"] = datetime.utcnow()
    
    # Update commitment
    await db.prescription_commitments.update_one(
        {"_id": ObjectId(commitment_id)},
        {"$set": update_fields}
    )
    
    logger.info(f"User {user_id} updated RCPA commitment {commitment_id}")
    
    return {
        "message": "Commitment updated successfully"
    }


async def get_rcpa_summary(
    month: Optional[int],
    year: Optional[int],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get RCPA summary for admin (demand forecast).
    
    Args:
        month: Filter by month (optional)
        year: Filter by year (optional)
        current_user: Current authenticated admin
    
    Returns:
        dict: RCPA summary by product and territory
    
    Raises:
        HTTPException: If not admin
    """
    db = get_company_database()
    user_role = current_user.get("role")
    
    if user_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access RCPA summary"
        )
    
    # Build query
    query = {"status": "active"}
    
    # Date filter
    if month and year:
        from datetime import datetime as dt
        import calendar
        
        start_date = dt(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = dt(year, month, last_day, 23, 59, 59)
        
        query["created_at"] = {
            "$gte": start_date,
            "$lte": end_date
        }
    
    # Get all active commitments
    commitments = await db.prescription_commitments.find(query).to_list(length=None)
    
    # Calculate totals
    total_rx_per_week = sum(c["rx_per_week"] for c in commitments)
    total_commitments = len(commitments)
    unique_doctors = len(set(c["doctor_id"] for c in commitments))
    unique_products = len(set(c["product_id"] for c in commitments))
    
    # Group by product
    product_summary = {}
    for c in commitments:
        prod_id = c["product_id"]
        if prod_id not in product_summary:
            product_summary[prod_id] = {
                "product_id": prod_id,
                "product_name": c["product_name"],
                "rx_per_week": 0,
                "doctors_count": set()
            }
        product_summary[prod_id]["rx_per_week"] += c["rx_per_week"]
        product_summary[prod_id]["doctors_count"].add(c["doctor_id"])
    
    # Convert to list
    by_product = [
        {
            "product_id": v["product_id"],
            "product_name": v["product_name"],
            "rx_per_week": v["rx_per_week"],
            "doctors_count": len(v["doctors_count"])
        }
        for v in product_summary.values()
    ]
    by_product.sort(key=lambda x: x["rx_per_week"], reverse=True)
    
    # Group by territory
    territory_summary = {}
    for c in commitments:
        terr = c.get("territory", "Unknown")
        if terr not in territory_summary:
            territory_summary[terr] = {
                "territory": terr,
                "rx_per_week": 0,
                "doctors_count": set(),
                "products_count": set()
            }
        territory_summary[terr]["rx_per_week"] += c["rx_per_week"]
        territory_summary[terr]["doctors_count"].add(c["doctor_id"])
        territory_summary[terr]["products_count"].add(c["product_id"])
    
    # Convert to list
    by_territory = [
        {
            "territory": v["territory"],
            "rx_per_week": v["rx_per_week"],
            "doctors_count": len(v["doctors_count"]),
            "products_count": len(v["products_count"])
        }
        for v in territory_summary.values()
    ]
    by_territory.sort(key=lambda x: x["rx_per_week"], reverse=True)
    
    logger.info(f"Admin fetched RCPA summary: {total_rx_per_week} rx/week from {total_commitments} commitments")
    
    return {
        "total_rx_per_week": total_rx_per_week,
        "total_commitments": total_commitments,
        "total_doctors": unique_doctors,
        "total_products": unique_products,
        "by_product": by_product,
        "by_territory": by_territory
    }


async def get_sfe_dashboard(
    month: int,
    year: int,
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get company-wide SFE dashboard (Admin only).
    
    Args:
        month: Month (1-12)
        year: Year (e.g., 2026)
        current_user: Current authenticated admin
    
    Returns:
        dict: Complete SFE dashboard with metrics, leaderboard, alerts
    
    Raises:
        HTTPException: If not admin
    """
    db = get_company_database()
    user_role = current_user.get("role")
    
    if user_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access SFE dashboard"
        )
    
    # Get all MRs
    mrs = await db.mrs.find({"role": "MR"}).to_list(length=None)
    total_mrs = len(mrs)
    
    if total_mrs == 0:
        logger.info("No MRs found in system")
        return {
            "month": month,
            "year": year,
            "total_mrs": 0,
            "avg_mcr_pct": 0.0,
            "avg_mvc_pct": 0.0,
            "total_doctors": 0,
            "total_visits": 0,
            "total_commitments": 0,
            "total_rx_per_week": 0,
            "leaderboard": [],
            "underperformers": [],
            "by_territory": {},
            "alerts": []
        }
    
    # Collect performance data for each MR
    mr_performances = []
    total_mcr = 0.0
    total_mvc = 0.0
    total_doctors_count = 0
    total_visits_count = 0
    
    for mr in mrs:
        mr_id = str(mr["_id"])
        
        # Get MCR
        try:
            mcr_data = await get_mcr_report(month, year, mr_id, {"_id": current_user["_id"], "role": "ADMIN"})
        except:
            mcr_data = {
                "mcr_percentage": 0.0,
                "total_assigned": 0,
                "doctors_visited": 0
            }
        
        # Get MVC
        try:
            mvc_data = await get_mvc_report(month, year, mr_id, {"_id": current_user["_id"], "role": "ADMIN"})
        except:
            mvc_data = {
                "mvc_percentage": 0.0,
                "avg_compliance": 0.0
            }
        
        # Get RCPA commitments count
        rcpa_query = {
            "mr_id": mr_id,
            "status": "active"
        }
        
        # Date filter for RCPA
        from datetime import datetime as dt
        import calendar
        
        start_date = dt(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = dt(year, month, last_day, 23, 59, 59)
        
        rcpa_query["created_at"] = {"$gte": start_date, "$lte": end_date}
        
        rcpa_commitments = await db.prescription_commitments.find(rcpa_query).to_list(length=None)
        rcpa_count = len(rcpa_commitments)
        rx_per_week = sum(c["rx_per_week"] for c in rcpa_commitments)
        
        # Aggregate
        total_mcr += mcr_data["mcr_percentage"]
        total_mvc += mvc_data["mvc_percentage"]
        total_doctors_count += mcr_data["total_assigned"]
        total_visits_count += mcr_data["doctors_visited"]
        
        mr_performances.append({
            "mr_id": mr_id,
            "mr_name": mr["name"],
            "territory": mr.get("territory"),
            "zone": mr.get("zone"),
            "state": mr.get("state"),
            "mcr_percentage": mcr_data["mcr_percentage"],
            "mvc_percentage": mvc_data["mvc_percentage"],
            "avg_compliance": mvc_data["avg_compliance"],
            "total_assigned": mcr_data["total_assigned"],
            "doctors_visited": mcr_data["doctors_visited"],
            "rcpa_commitments": rcpa_count,
            "rx_per_week": rx_per_week
        })
    
    # Calculate averages
    avg_mcr_pct = round(total_mcr / total_mrs, 2) if total_mrs > 0 else 0.0
    avg_mvc_pct = round(total_mvc / total_mrs, 2) if total_mrs > 0 else 0.0
    
    # Get total commitments and rx
    total_commitments_query = {
        "status": "active",
        "created_at": {"$gte": start_date, "$lte": end_date}
    }
    all_commitments = await db.prescription_commitments.find(total_commitments_query).to_list(length=None)
    total_commitments = len(all_commitments)
    total_rx_per_week = sum(c["rx_per_week"] for c in all_commitments)
    
    # Sort for leaderboard (top 10)
    leaderboard = sorted(mr_performances, key=lambda x: (x["mcr_percentage"] + x["mvc_percentage"]) / 2, reverse=True)[:10]
    
    # Underperformers (MCR < 60% or MVC < 55%)
    underperformers = [
        mr for mr in mr_performances
        if mr["mcr_percentage"] < 60 or mr["mvc_percentage"] < 55
    ]
    underperformers.sort(key=lambda x: (x["mcr_percentage"] + x["mvc_percentage"]) / 2)
    
    # Group by territory
    territory_data = {}
    for mr_perf in mr_performances:
        terr = mr_perf.get("territory", "Unknown")
        if terr not in territory_data:
            territory_data[terr] = {
                "territory": terr,
                "mrs_count": 0,
                "mcr_sum": 0.0,
                "mvc_sum": 0.0,
                "total_doctors": 0,
                "total_visits": 0,
                "total_commitments": 0,
                "rx_per_week": 0
            }
        
        territory_data[terr]["mrs_count"] += 1
        territory_data[terr]["mcr_sum"] += mr_perf["mcr_percentage"]
        territory_data[terr]["mvc_sum"] += mr_perf["mvc_percentage"]
        territory_data[terr]["total_doctors"] += mr_perf["total_assigned"]
        territory_data[terr]["total_visits"] += mr_perf["doctors_visited"]
        territory_data[terr]["total_commitments"] += mr_perf["rcpa_commitments"]
        territory_data[terr]["rx_per_week"] += mr_perf["rx_per_week"]
    
    # Convert to list with averages
    by_territory = []
    for terr_data in territory_data.values():
        mrs_count = terr_data["mrs_count"]
        by_territory.append({
            "territory": terr_data["territory"],
            "mrs_count": mrs_count,
            "avg_mcr": round(terr_data["mcr_sum"] / mrs_count, 2) if mrs_count > 0 else 0.0,
            "avg_mvc": round(terr_data["mvc_sum"] / mrs_count, 2) if mrs_count > 0 else 0.0,
            "total_doctors": terr_data["total_doctors"],
            "total_visits": terr_data["total_visits"],
            "total_commitments": terr_data["total_commitments"],
            "rx_per_week": terr_data["rx_per_week"]
        })
    
    by_territory.sort(key=lambda x: x["rx_per_week"], reverse=True)
    
    # Generate alerts
    alerts = []
    for mr_perf in mr_performances:
        # Critical MCR
        if mr_perf["mcr_percentage"] < 60:
            alerts.append({
                "mr_id": mr_perf["mr_id"],
                "mr_name": mr_perf["mr_name"],
                "territory": mr_perf.get("territory"),
                "alert_type": "critical_mcr",
                "severity": "critical",
                "message": f"MCR below 60% ({mr_perf['mcr_percentage']}%)",
                "metric_value": mr_perf["mcr_percentage"]
            })
        
        # Critical MVC
        if mr_perf["mvc_percentage"] < 55:
            alerts.append({
                "mr_id": mr_perf["mr_id"],
                "mr_name": mr_perf["mr_name"],
                "territory": mr_perf.get("territory"),
                "alert_type": "critical_mvc",
                "severity": "critical",
                "message": f"MVC below 55% ({mr_perf['mvc_percentage']}%)",
                "metric_value": mr_perf["mvc_percentage"]
            })
        
        # No commitments
        if mr_perf["rcpa_commitments"] == 0:
            alerts.append({
                "mr_id": mr_perf["mr_id"],
                "mr_name": mr_perf["mr_name"],
                "territory": mr_perf.get("territory"),
                "alert_type": "no_commitments",
                "severity": "warning",
                "message": "No RCPA commitments logged this month",
                "metric_value": 0.0
            })
    
    logger.info(f"Admin fetched SFE dashboard for {month}/{year}: {total_mrs} MRs, Avg MCR: {avg_mcr_pct}%, Avg MVC: {avg_mvc_pct}%")
    
    return {
        "month": month,
        "year": year,
        "total_mrs": total_mrs,
        "avg_mcr_pct": avg_mcr_pct,
        "avg_mvc_pct": avg_mvc_pct,
        "total_doctors": total_doctors_count,
        "total_visits": total_visits_count,
        "total_commitments": total_commitments,
        "total_rx_per_week": total_rx_per_week,
        "leaderboard": leaderboard,
        "underperformers": underperformers,
        "by_territory": by_territory,
        "alerts": alerts
    }


async def get_mr_drilldown(
    mr_id: str,
    month: int,
    year: int,
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get detailed drill-down for individual MR (Admin only).
    
    Args:
        mr_id: MR ID
        month: Month (1-12)
        year: Year (e.g., 2026)
        current_user: Current authenticated admin
    
    Returns:
        dict: Detailed MR performance with trend
    
    Raises:
        HTTPException: If not admin or MR not found
    """
    db = get_company_database()
    user_role = current_user.get("role")
    
    if user_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access MR drill-down"
        )
    
    # Validate MR ID
    if not ObjectId.is_valid(mr_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MR ID"
        )
    
    # Get MR details
    mr = await db.mrs.find_one({"_id": ObjectId(mr_id)})
    if not mr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MR not found"
        )
    
    # Get MCR data
    mcr_data = await get_mcr_report(month, year, mr_id, {"_id": current_user["_id"], "role": "ADMIN"})
    
    # Get MVC data
    mvc_data = await get_mvc_report(month, year, mr_id, {"_id": current_user["_id"], "role": "ADMIN"})
    
    # Get RCPA summary
    from datetime import datetime as dt
    import calendar
    
    start_date = dt(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = dt(year, month, last_day, 23, 59, 59)
    
    rcpa_query = {
        "mr_id": mr_id,
        "status": "active",
        "created_at": {"$gte": start_date, "$lte": end_date}
    }
    
    rcpa_commitments = await db.prescription_commitments.find(rcpa_query).to_list(length=None)
    rcpa_summary = {
        "total_commitments": len(rcpa_commitments),
        "rx_per_week": sum(c["rx_per_week"] for c in rcpa_commitments)
    }
    
    # Get performance trend (last 6 months)
    performance_trend = []
    for i in range(5, -1, -1):
        trend_month = month - i
        trend_year = year
        
        if trend_month <= 0:
            trend_month += 12
            trend_year -= 1
        
        try:
            trend_mcr = await get_mcr_report(trend_month, trend_year, mr_id, {"_id": current_user["_id"], "role": "ADMIN"})
            trend_mvc = await get_mvc_report(trend_month, trend_year, mr_id, {"_id": current_user["_id"], "role": "ADMIN"})
            
            performance_trend.append({
                "month": trend_month,
                "year": trend_year,
                "mcr": trend_mcr["mcr_percentage"],
                "mvc": trend_mvc["mvc_percentage"],
                "avg_compliance": trend_mvc["avg_compliance"]
            })
        except:
            performance_trend.append({
                "month": trend_month,
                "year": trend_year,
                "mcr": 0.0,
                "mvc": 0.0,
                "avg_compliance": 0.0
            })
    
    logger.info(f"Admin fetched drill-down for MR {mr_id} ({month}/{year})")
    
    return {
        "mr_id": mr_id,
        "mr_name": mr["name"],
        "territory": mr.get("territory"),
        "zone": mr.get("zone"),
        "state": mr.get("state"),
        "month": month,
        "year": year,
        "mcr_data": {
            "mcr_percentage": mcr_data["mcr_percentage"],
            "total_assigned": mcr_data["total_assigned"],
            "doctors_visited": mcr_data["doctors_visited"],
            "doctors_not_visited": mcr_data["doctors_not_visited"]
        },
        "mvc_data": {
            "mvc_percentage": mvc_data["mvc_percentage"],
            "avg_compliance": mvc_data["avg_compliance"],
            "fully_covered": mvc_data["fully_covered"],
            "under_covered": mvc_data["under_covered"],
            "not_visited": mvc_data["not_visited"]
        },
        "rcpa_summary": rcpa_summary,
        "performance_trend": performance_trend
    }


async def create_chemist_check(
    check_data: Dict[str, Any],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create chemist check observation (MR only).
    
    Args:
        check_data: Check details
        current_user: Current authenticated MR
    
    Returns:
        dict: Created check
    
    Raises:
        HTTPException: If validation fails
    """
    from app.models.sfe_models import ChemistCheck
    
    db = get_company_database()
    mr_id = current_user["_id"]
    
    # Validate product ID
    product_id = check_data["product_id"]
    if not ObjectId.is_valid(product_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid product ID"
        )
    
    # Get product details
    product = await db.drugs.find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Get MR details
    mr = await db.mrs.find_one({"_id": ObjectId(mr_id)})
    
    # Create check
    check = ChemistCheck(
        mr_id=mr_id,
        mr_name=mr["name"],
        chemist_name=check_data["chemist_name"],
        chemist_location=check_data["chemist_location"],
        product_id=product_id,
        product_name=product["name"],
        stock_available=check_data["stock_available"],
        sold_this_week=check_data["sold_this_week"],
        notes=check_data.get("notes"),
        territory=mr.get("territory"),
        zone=mr.get("zone"),
        state=mr.get("state"),
        gps_lat=check_data.get("gps_lat"),
        gps_lng=check_data.get("gps_lng"),
        date=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    )
    
    result = await db.chemist_checks.insert_one(check.model_dump())
    
    logger.info(f"MR {mr_id} created chemist check: {check_data['chemist_name']} - {product_id}")
    
    check_dict = check.model_dump()
    check_dict["id"] = str(result.inserted_id)
    
    return check_dict


async def get_chemist_checks(
    month: Optional[int],
    year: Optional[int],
    mr_id: Optional[str],
    product_id: Optional[str],
    territory: Optional[str],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get chemist checks with filters.
    
    Args:
        month: Filter by month (optional)
        year: Filter by year (optional)
        mr_id: Filter by MR (admin only, optional)
        product_id: Filter by product (optional)
        territory: Filter by territory (optional)
        current_user: Current authenticated user
    
    Returns:
        dict: List of checks
    
    Raises:
        HTTPException: If validation fails
    """
    db = get_company_database()
    user_role = current_user.get("role")
    user_id = current_user["_id"]
    
    # Build query
    query = {}
    
    # Determine which MR to query
    if mr_id:
        # Admin querying specific MR
        if user_role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can query other MRs' data"
            )
        query["mr_id"] = mr_id
    else:
        # MR querying own data
        if user_role == "MR":
            query["mr_id"] = user_id
        # Admin without mr_id gets all
    
    # Date filter
    if month and year:
        from datetime import datetime as dt
        import calendar
        
        start_date = dt(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = dt(year, month, last_day, 23, 59, 59)
        
        query["date"] = {
            "$gte": start_date,
            "$lte": end_date
        }
    
    # Product filter
    if product_id:
        if not ObjectId.is_valid(product_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid product ID"
            )
        query["product_id"] = product_id
    
    # Territory filter
    if territory:
        query["territory"] = territory
    
    # Get checks
    checks = await db.chemist_checks.find(query).sort("date", -1).to_list(length=None)
    
    # Convert ObjectId to string
    for check in checks:
        check["id"] = str(check.pop("_id"))
    
    logger.info(f"User {user_id} fetched {len(checks)} chemist checks")
    
    return {
        "total": len(checks),
        "checks": checks
    }


async def get_chemist_check_summary(
    month: Optional[int],
    year: Optional[int],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get chemist check summary for admin.
    
    Args:
        month: Filter by month (optional)
        year: Filter by year (optional)
        current_user: Current authenticated admin
    
    Returns:
        dict: Chemist check summary
    
    Raises:
        HTTPException: If not admin
    """
    db = get_company_database()
    user_role = current_user.get("role")
    
    if user_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access chemist check summary"
        )
    
    # Build query
    query = {}
    
    # Date filter
    if month and year:
        from datetime import datetime as dt
        import calendar
        
        start_date = dt(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = dt(year, month, last_day, 23, 59, 59)
        
        query["date"] = {
            "$gte": start_date,
            "$lte": end_date
        }
    
    # Get all checks
    checks = await db.chemist_checks.find(query).to_list(length=None)
    
    total_checks = len(checks)
    unique_chemists = len(set(c["chemist_name"] for c in checks))
    total_stock = sum(c["stock_available"] for c in checks)
    total_sold = sum(c["sold_this_week"] for c in checks)
    
    # Group by product
    product_summary = {}
    for c in checks:
        prod_id = c["product_id"]
        if prod_id not in product_summary:
            product_summary[prod_id] = {
                "product_id": prod_id,
                "product_name": c["product_name"],
                "total_stock": 0,
                "total_sold_this_week": 0,
                "chemists": set()
            }
        product_summary[prod_id]["total_stock"] += c["stock_available"]
        product_summary[prod_id]["total_sold_this_week"] += c["sold_this_week"]
        product_summary[prod_id]["chemists"].add(c["chemist_name"])
    
    # Convert to list
    by_product = [
        {
            "product_id": v["product_id"],
            "product_name": v["product_name"],
            "total_stock": v["total_stock"],
            "total_sold_this_week": v["total_sold_this_week"],
            "chemists_count": len(v["chemists"]),
            "avg_stock_per_chemist": round(v["total_stock"] / len(v["chemists"]), 2) if len(v["chemists"]) > 0 else 0.0
        }
        for v in product_summary.values()
    ]
    by_product.sort(key=lambda x: x["total_sold_this_week"], reverse=True)
    
    # Group by territory
    territory_summary = {}
    for c in checks:
        terr = c.get("territory", "Unknown")
        if terr not in territory_summary:
            territory_summary[terr] = {
                "territory": terr,
                "total_stock": 0,
                "total_sold": 0,
                "chemists": set(),
                "products": set()
            }
        territory_summary[terr]["total_stock"] += c["stock_available"]
        territory_summary[terr]["total_sold"] += c["sold_this_week"]
        territory_summary[terr]["chemists"].add(c["chemist_name"])
        territory_summary[terr]["products"].add(c["product_id"])
    
    # Convert to list
    by_territory = [
        {
            "territory": v["territory"],
            "total_stock": v["total_stock"],
            "total_sold": v["total_sold"],
            "chemists_count": len(v["chemists"]),
            "products_count": len(v["products"])
        }
        for v in territory_summary.values()
    ]
    by_territory.sort(key=lambda x: x["total_sold"], reverse=True)
    
    # Low stock alerts (stock < 10)
    low_stock_alerts = [
        {
            "chemist_name": c["chemist_name"],
            "product_name": c["product_name"],
            "stock_available": c["stock_available"],
            "territory": c.get("territory", "Unknown"),
            "mr_name": c["mr_name"]
        }
        for c in checks
        if c["stock_available"] < 10
    ]
    low_stock_alerts.sort(key=lambda x: x["stock_available"])
    
    logger.info(f"Admin fetched chemist check summary: {total_checks} checks, {unique_chemists} chemists")
    
    return {
        "total_checks": total_checks,
        "total_chemists": unique_chemists,
        "total_stock": total_stock,
        "total_sold_this_week": total_sold,
        "by_product": by_product,
        "by_territory": by_territory,
        "low_stock_alerts": low_stock_alerts
    }
