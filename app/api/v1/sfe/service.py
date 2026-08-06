"""
SFE (Sales Force Effectiveness) service - Business logic.
"""
from datetime import datetime, date
import calendar
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.models.sfe_models import DoctorClass, DoctorAssignment
from app.utils.logger import get_medrep_logger
from app.utils.serializers import convert_objectids_to_strings

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
    
    # Get SFE settings to determine visit frequency
    settings = await get_sfe_settings()
    classification_targets = settings.get("classification_targets", {"A": 2, "B": 1, "C": 1})
    visit_frequency = classification_targets.get(classification, 1)
    
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



# ============================================================================
# SFE SETTINGS (VISIT TARGETS) - Single source of truth
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
    """
    db = get_company_database()
    user_role = current_user.get("role")
    user_id = current_user["_id"]
    
    # Determine which MR to query
    if mr_id:
        if user_role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can query other MRs' data"
            )
        target_mr_id = mr_id
    else:
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
    
    # Get MR details (assigned_doctors is on the MR document)
    mr = await db.mrs.find_one({"_id": ObjectId(target_mr_id)})
    if not mr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MR not found"
        )
    
    assigned_doctor_ids = mr.get("assigned_doctors", [])
    total_assigned = len(assigned_doctor_ids)
    
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
    
    # Fetch all assigned doctors in one query
    doctor_object_ids = [ObjectId(doc_id) for doc_id in assigned_doctor_ids if ObjectId.is_valid(doc_id)]
    doctors = await db.doctors.find(
        {"_id": {"$in": doctor_object_ids}},
        {"name": 1, "classification": 1}
    ).to_list(length=None)
    doctor_map = {str(doc["_id"]): doc for doc in doctors}
    
    # Create date range for the month
    start_date = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59)
    
    # Get all completed visits for this MR in the given month
    visits = await db.visits.find({
        "mr_id": target_mr_id,
        "status": "completed",
        "completed_at": {
            "$gte": start_date,
            "$lte": end_date
        }
    }).to_list(length=None)
    
    # Collect all product IDs from visits to fetch names in one query
    all_product_ids = set()
    for visit in visits:
        report = visit.get("report")
        if report and report.get("products_discussed"):
            for pid in report["products_discussed"]:
                pid_str = str(pid) if not isinstance(pid, str) else pid
                if ObjectId.is_valid(pid_str):
                    all_product_ids.add(pid_str)
        # Legacy visits
        if visit.get("products_promoted"):
            for pid in visit["products_promoted"]:
                pid_str = str(pid) if not isinstance(pid, str) else pid
                if ObjectId.is_valid(pid_str):
                    all_product_ids.add(pid_str)
    
    # Fetch all products in one batch query
    drug_map = {}
    if all_product_ids:
        product_object_ids = [ObjectId(pid) for pid in all_product_ids]
        products = await db.drugs.find({"_id": {"$in": product_object_ids}}).to_list(length=None)
        for product in products:
            pid = str(product["_id"])
            drug_name = product.get("drug_name", "")
            if not drug_name and product.get("field_values"):
                for field in product["field_values"]:
                    if field.get("key") == "drug_name":
                        drug_name = field.get("value", "Unknown Drug")
                        break
                    elif field.get("key") in ["name", "product_name", "brand_name"]:
                        drug_name = field.get("value", "Unknown Drug")
                        break
            drug_map[pid] = drug_name or "Unknown Drug"
    
    # Count visits per doctor and group visit details
    doctor_visit_count = {}
    doctor_last_visit = {}
    doctor_visits_detail = {}  # Store full visit details per doctor
    
    for visit in visits:
        doc_id = visit["doctor_id"]
        doctor_visit_count[doc_id] = doctor_visit_count.get(doc_id, 0) + 1
        if doc_id not in doctor_last_visit or visit["completed_at"] > doctor_last_visit[doc_id]:
            doctor_last_visit[doc_id] = visit["completed_at"]
        
        # Collect visit details for this doctor
        if doc_id not in doctor_visits_detail:
            doctor_visits_detail[doc_id] = []
        
        visit_info = {
            "visit_id": str(visit["_id"]),
            "scheduled_date": visit.get("scheduled_date"),
            "completed_at": visit.get("completed_at"),
            "duration_minutes": visit.get("duration_minutes"),
            "location": convert_objectids_to_strings(visit.get("location")),
            "purpose": visit.get("purpose"),
        }
        
        # Add report data if available
        report = visit.get("report")
        if report:
            # Resolve product IDs to names
            products_discussed = []
            for pid in report.get("products_discussed", []):
                pid_str = str(pid) if not isinstance(pid, str) else pid
                products_discussed.append({
                    "id": pid_str,
                    "name": drug_map.get(pid_str, "Unknown Drug")
                })
            
            visit_info["doctor_mood"] = report.get("doctor_mood")
            visit_info["products_discussed"] = products_discussed
            visit_info["samples_given"] = report.get("samples_given")
            visit_info["outcome"] = report.get("outcome")
            visit_info["rx_commitment"] = report.get("rx_commitment")
            visit_info["expected_rx_per_month"] = report.get("expected_rx_per_month")
            visit_info["competitor_info"] = report.get("competitor_info")
            visit_info["follow_up_date"] = report.get("follow_up_date")
            visit_info["notes"] = report.get("notes")
        else:
            # Legacy visits (completed via old endpoint)
            products_discussed = []
            for pid in visit.get("products_promoted", []):
                pid_str = str(pid) if not isinstance(pid, str) else pid
                products_discussed.append({
                    "id": pid_str,
                    "name": drug_map.get(pid_str, "Unknown Drug")
                })
            
            visit_info["outcome"] = visit.get("outcome")
            visit_info["feedback"] = visit.get("feedback")
            visit_info["doctor_mood"] = visit.get("doctor_mood")
            visit_info["products_discussed"] = products_discussed
            visit_info["samples_given"] = visit.get("samples_given")
        
        doctor_visits_detail[doc_id].append(visit_info)
    
    # Categorize doctors
    visited_doctors = []
    not_visited_doctors = []
    
    for doc_id in assigned_doctor_ids:
        doctor = doctor_map.get(doc_id)
        if not doctor:
            continue
        
        doctor_name = doctor.get("name", "Unknown")
        classification = doctor.get("classification", "C")
        
        if doc_id in doctor_visit_count:
            visited_doctors.append({
                "doctor_id": doc_id,
                "doctor_name": doctor_name,
                "classification": classification,
                "visits_count": doctor_visit_count[doc_id],
                "last_visit_date": doctor_last_visit[doc_id],
                "visits": doctor_visits_detail.get(doc_id, [])
            })
        else:
            not_visited_doctors.append({
                "doctor_id": doc_id,
                "doctor_name": doctor_name,
                "classification": classification,
                "last_visited": None
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
    """
    db = get_company_database()
    user_role = current_user.get("role")
    user_id = current_user["_id"]
    
    # Determine which MR to query
    if mr_id:
        if user_role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can query other MRs' data"
            )
        target_mr_id = mr_id
    else:
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
    
    # Get MR details (assigned_doctors is on the MR document)
    mr = await db.mrs.find_one({"_id": ObjectId(target_mr_id)})
    if not mr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MR not found"
        )
    
    assigned_doctor_ids = mr.get("assigned_doctors", [])
    total_assigned = len(assigned_doctor_ids)
    
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
    
    # Fetch all assigned doctors in one query
    doctor_object_ids = [ObjectId(doc_id) for doc_id in assigned_doctor_ids if ObjectId.is_valid(doc_id)]
    doctors = await db.doctors.find(
        {"_id": {"$in": doctor_object_ids}},
        {"name": 1, "classification": 1}
    ).to_list(length=None)
    doctor_map = {str(doc["_id"]): doc for doc in doctors}
    
    # Get SFE settings for required visits per classification
    sfe_settings = await get_sfe_settings()
    classification_targets = sfe_settings.get("classification_targets", {"A": 2, "B": 1, "C": 1})
    
    # Create date range for the month
    start_date = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59)
    
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
    
    for doc_id in assigned_doctor_ids:
        doctor = doctor_map.get(doc_id)
        if not doctor:
            continue
        
        doctor_name = doctor.get("name", "Unknown")
        classification = doctor.get("classification", "C")
        required_visits = classification_targets.get(classification, 1)
        actual_visits = doctor_visit_count.get(doc_id, 0)
        
        # Calculate compliance percentage
        compliance_pct = round((actual_visits / required_visits) * 100, 2) if required_visits > 0 else 0.0
        total_compliance += compliance_pct
        
        # Determine status
        if actual_visits >= required_visits:
            doc_status = "covered"
            fully_covered_count += 1
        elif actual_visits > 0:
            doc_status = "under"
            under_covered_count += 1
        else:
            doc_status = "missed"
            not_visited_count += 1
        
        doctors_detail.append({
            "doctor_id": doc_id,
            "doctor_name": doctor_name,
            "classification": classification,
            "required_visits": required_visits,
            "actual_visits": actual_visits,
            "status": doc_status,
            "compliance_percentage": compliance_pct
        })
    
    # Calculate MVC percentage
    total_doctors_counted = len(doctors_detail)
    mvc_percentage = round((fully_covered_count / total_doctors_counted) * 100, 2) if total_doctors_counted > 0 else 0.0
    avg_compliance = round(total_compliance / total_doctors_counted, 2) if total_doctors_counted > 0 else 0.0
    
    # Sort: covered first, then under, then missed
    status_order = {"covered": 0, "under": 1, "missed": 2}
    doctors_detail.sort(key=lambda x: status_order.get(x["status"], 3))
    
    logger.info(f"MVC for MR {target_mr_id} ({month}/{year}): {mvc_percentage}% (covered: {fully_covered_count}/{total_doctors_counted})")
    
    return {
        "mr_id": target_mr_id,
        "mr_name": mr["name"],
        "month": month,
        "year": year,
        "total_assigned": total_doctors_counted,
        "fully_covered": fully_covered_count,
        "under_covered": under_covered_count,
        "not_visited": not_visited_count,
        "mvc_percentage": mvc_percentage,
        "avg_compliance": avg_compliance,
        "doctors": doctors_detail
    }
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




async def get_eligible_visits(current_user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get completed visits for the logged-in MR (eligible for RCPA commitment).
    Only COMPLETED visits qualify.
    """
    db = get_company_database()
    mr_id = current_user["_id"]
    
    visits = await db.visits.find({
        "mr_id": mr_id,
        "status": "completed"
    }).sort("created_at", -1).to_list(length=None)
    
    result = []
    for v in visits:
        # Build location snapshot from visit location
        loc_snapshot = None
        location = v.get("location")
        if isinstance(location, dict):
            if location.get("type") == "permanent":
                loc_snapshot = {"name": location.get("location_name", "")}
                # Try to get full details from doctor locations
                doctor = await db.doctors.find_one({"_id": ObjectId(v["doctor_id"])})
                if doctor:
                    for dl in doctor.get("locations", []):
                        if dl.get("id") == location.get("location_id"):
                            loc_snapshot = {
                                "name": dl.get("name", ""),
                                "area": dl.get("area"),
                                "district": dl.get("district"),
                                "state": dl.get("state")
                            }
                            break
            elif location.get("type") == "temporary":
                temp = location.get("temporary_location", {})
                loc_snapshot = {"name": temp.get("name", ""), "area": None, "district": None, "state": None}
        
        scheduled_date = v.get("scheduled_date")
        visit_date = scheduled_date.strftime("%Y-%m-%d") if scheduled_date else None
        
        result.append({
            "visit_id": str(v["_id"]),
            "visit_title": v.get("title"),
            "doctor_id": v.get("doctor_id"),
            "doctor_name": v.get("doctor_name"),
            "doctor_location": loc_snapshot,
            "visit_date": visit_date
        })
    
    return {"total": len(result), "visits": result}


async def create_rcpa_commitment(
    commitment_data: Dict[str, Any],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create RCPA commitment from a completed visit.
    Backend auto-populates mr, doctor, location from visit.
    MR only provides: visit_id, drug_id, committed_quantity, rx_per_month, requested_discount.
    """
    from app.models.sfe_models import PrescriptionCommitment, ApprovalStatus
    
    db = get_company_database()
    mr_id = current_user["_id"]
    
    visit_id = commitment_data["visit_id"]
    drug_id = commitment_data["drug_id"]
    
    # 1. Validate visit
    if not ObjectId.is_valid(visit_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid visit ID")
    
    visit = await db.visits.find_one({"_id": ObjectId(visit_id)})
    if not visit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")
    
    if visit.get("status") != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Visit not completed")
    
    if visit.get("mr_id") != mr_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your visit")
    
    # 2. Check duplicate (one RCPA per drug per visit)
    if not ObjectId.is_valid(drug_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid drug ID")
    
    existing = await db.prescription_commitments.find_one({"visit_id": visit_id, "drug_id": drug_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Commitment already exists for this drug on this visit"
        )
    
    # 3. Validate drug and get pricing
    drug = await db.drugs.find_one({"_id": ObjectId(drug_id), "is_active": True})
    if not drug:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drug not found or inactive")
    
    packaging = drug.get("packaging")
    if not packaging or not isinstance(packaging, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drug has no pricing configured. Please set packaging info first.")
    
    if not packaging.get("selling_price"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drug packaging is missing selling_price. Please update the drug's pricing.")

    selling_price = packaging["selling_price"]
    max_discount = packaging.get("max_discount_percent", 0)
    quantity_unit = packaging.get("sales_unit", "")
    
    # Extract drug name
    drug_name = drug.get("drug_name", "")
    if not drug_name and drug.get("field_values"):
        for fv in drug["field_values"]:
            if fv.get("key") == "drug_name":
                drug_name = fv.get("value", "Unknown Drug")
                break
    if not drug_name:
        drug_name = "Unknown Drug"
    
    # 4. Validate discount
    requested_discount = commitment_data.get("requested_discount", 0.0)
    if requested_discount > max_discount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Discount exceeds allowed maximum of {max_discount}%"
        )
    
    # 5. Build location snapshot from visit
    doctor_location = None
    doctor_location_id = None
    location = visit.get("location")
    if isinstance(location, dict):
        if location.get("type") == "permanent":
            doctor_location_id = location.get("location_id")
            doctor_location = {"name": location.get("location_name", ""), "type": None}
            # Get full details from doctor
            doctor_doc = await db.doctors.find_one({"_id": ObjectId(visit["doctor_id"])})
            if doctor_doc:
                for dl in doctor_doc.get("locations", []):
                    if dl.get("id") == doctor_location_id:
                        doctor_location = {
                            "name": dl.get("name", ""),
                            "type": dl.get("type"),
                            "area": dl.get("area"),
                            "district": dl.get("district"),
                            "state": dl.get("state")
                        }
                        break
        elif location.get("type") == "temporary":
            temp = location.get("temporary_location", {})
            doctor_location = {"name": temp.get("name", ""), "type": "temporary"}
    
    # 6. Calculate
    committed_quantity = commitment_data["committed_quantity"]
    committed_revenue = committed_quantity * selling_price
    
    # All commitments start as PENDING — admin must approve every one
    approval_status = ApprovalStatus.PENDING
    net_revenue = None
    
    now = datetime.utcnow()
    
    # 7. Create commitment
    commitment = PrescriptionCommitment(
        visit_id=visit_id,
        visit_title=visit.get("title"),
        mr_id=mr_id,
        mr_name=visit.get("mr_name", current_user.get("name", "")),
        doctor_id=visit.get("doctor_id"),
        doctor_name=visit.get("doctor_name"),
        doctor_location_id=doctor_location_id,
        doctor_location=doctor_location,
        drug_id=drug_id,
        drug_name=drug_name,
        committed_quantity=committed_quantity,
        quantity_unit=quantity_unit,
        rx_per_month=commitment_data["rx_per_month"],
        selling_price=selling_price,
        max_discount_percent=max_discount,
        committed_revenue=committed_revenue,
        requested_discount=requested_discount,
        net_revenue=net_revenue,
        approval_status=approval_status,
        month=now.month,
        year=now.year,
        created_at=now,
        updated_at=now
    )
    
    result = await db.prescription_commitments.insert_one(commitment.model_dump())
    
    logger.info(f"MR {mr_id} created RCPA: visit={visit_id} drug={drug_id} qty={committed_quantity} revenue={committed_revenue}")
    
    commitment_dict = commitment.model_dump()
    commitment_dict["id"] = str(result.inserted_id)
    
    return commitment_dict


async def get_rcpa_commitments(
    month: Optional[int],
    year: Optional[int],
    mr_id: Optional[str],
    drug_id: Optional[str],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get RCPA commitments with filters.
    
    Args:
        month: Filter by month (optional)
        year: Filter by year (optional)
        mr_id: Filter by MR (admin only, optional)
        drug_id: Filter by drug (optional)
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
        start_date = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day, 23, 59, 59)
        
        query["created_at"] = {
            "$gte": start_date,
            "$lte": end_date
        }
    
    # Drug filter (supports both old product_id and new drug_id)
    if drug_id:
        if not ObjectId.is_valid(drug_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid drug ID"
            )
        query["$or"] = [{"drug_id": drug_id}, {"product_id": drug_id}]
    
    # Get commitments
    commitments = await db.prescription_commitments.find(query).sort("created_at", -1).to_list(length=None)
    
    # Convert ObjectId to string and normalize old field names
    for commitment in commitments:
        commitment["id"] = str(commitment.pop("_id"))
        # Normalize old product_id/product_name to drug_id/drug_name
        if "product_id" in commitment and "drug_id" not in commitment:
            commitment["drug_id"] = commitment.pop("product_id")
        if "product_name" in commitment and "drug_name" not in commitment:
            commitment["drug_name"] = commitment.pop("product_name")
    
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
    Update RCPA commitment — supports changing drug, quantity, rx_per_month, discount.
    Recalculates revenue and resets approval if discount changed.
    """
    from app.models.sfe_models import ApprovalStatus
    
    db = get_company_database()
    user_role = current_user.get("role")
    user_id = current_user["_id"]
    
    if not ObjectId.is_valid(commitment_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid commitment ID")
    
    commitment = await db.prescription_commitments.find_one({"_id": ObjectId(commitment_id)})
    if not commitment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commitment not found")
    
    # Authorization
    if user_role != "ADMIN" and commitment["mr_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own commitments")
    
    update_fields = {"updated_at": datetime.utcnow()}
    
    # If drug_id is changing, re-fetch drug pricing
    new_drug_id = update_data.get("drug_id")
    selling_price = commitment.get("selling_price", 0)
    max_discount = commitment.get("max_discount_percent", 0)
    quantity_unit = commitment.get("quantity_unit", "")
    
    if new_drug_id and new_drug_id != commitment.get("drug_id"):
        if not ObjectId.is_valid(new_drug_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid drug ID")
        
        # Check duplicate: same visit + new drug
        existing = await db.prescription_commitments.find_one({
            "visit_id": commitment["visit_id"],
            "drug_id": new_drug_id,
            "_id": {"$ne": ObjectId(commitment_id)}
        })
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Commitment already exists for this drug on this visit")
        
        drug = await db.drugs.find_one({"_id": ObjectId(new_drug_id), "is_active": True})
        if not drug:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drug not found or inactive")
        
        packaging = drug.get("packaging")
        if not packaging or not isinstance(packaging, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drug has no pricing configured. Please set packaging info first.")
        
        if not packaging.get("selling_price"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drug packaging is missing selling_price.")

        selling_price = packaging["selling_price"]
        max_discount = packaging.get("max_discount_percent", 0)
        quantity_unit = packaging.get("sales_unit", "")
        
        # Get drug name
        drug_name = drug.get("drug_name", "")
        if not drug_name and drug.get("field_values"):
            for fv in drug["field_values"]:
                if fv.get("key") == "drug_name":
                    drug_name = fv.get("value", "Unknown Drug")
                    break
        
        update_fields["drug_id"] = new_drug_id
        update_fields["drug_name"] = drug_name or "Unknown Drug"
        update_fields["selling_price"] = selling_price
        update_fields["max_discount_percent"] = max_discount
        update_fields["quantity_unit"] = quantity_unit
    
    # Update quantity
    committed_quantity = update_data.get("committed_quantity") or commitment.get("committed_quantity", 1)
    if "committed_quantity" in update_data and update_data["committed_quantity"] is not None:
        update_fields["committed_quantity"] = committed_quantity
    
    # Update rx_per_month
    if "rx_per_month" in update_data and update_data["rx_per_month"] is not None:
        update_fields["rx_per_month"] = update_data["rx_per_month"]
    
    # Recalculate revenue
    committed_revenue = committed_quantity * selling_price
    update_fields["committed_revenue"] = committed_revenue
    
    # Update discount
    requested_discount = update_data.get("requested_discount")
    if requested_discount is not None:
        if requested_discount > max_discount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Discount exceeds allowed maximum of {max_discount}%"
            )
        update_fields["requested_discount"] = requested_discount
        
        # Reset approval — all changes require admin re-approval
        update_fields["approval_status"] = ApprovalStatus.PENDING.value
        update_fields["net_revenue"] = None
        update_fields["approved_discount"] = None
        update_fields["approved_by"] = None
        update_fields["approved_at"] = None
    
    if len(update_fields) <= 1:  # only updated_at
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    
    await db.prescription_commitments.update_one(
        {"_id": ObjectId(commitment_id)},
        {"$set": update_fields}
    )
    
    logger.info(f"User {user_id} updated RCPA commitment {commitment_id}")
    
    return {"message": "Commitment updated successfully"}


async def approve_rcpa_discount(
    commitment_id: str,
    approved_discount: float,
    admin_user: Dict[str, Any],
    approved_quantity: Optional[int] = None
) -> Dict[str, str]:
    """
    Admin approves a discount request on a commitment.
    Optionally adjusts quantity. Calculates net_revenue.
    net_revenue = approved_quantity × selling_price × (1 - approved_discount/100)
    """
    db = get_company_database()
    
    if not ObjectId.is_valid(commitment_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid commitment ID")
    
    commitment = await db.prescription_commitments.find_one({"_id": ObjectId(commitment_id)})
    if not commitment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commitment not found")
    
    if commitment.get("approval_status") != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Commitment already {commitment.get('approval_status')}"
        )
    
    # Use approved_quantity if provided, otherwise use committed_quantity
    final_quantity = approved_quantity if approved_quantity else commitment["committed_quantity"]
    selling_price = commitment.get("selling_price", 0)
    
    # net_revenue = approved_quantity × selling_price × (1 - discount/100)
    net_revenue = round(final_quantity * selling_price * (1 - approved_discount / 100), 2)
    
    await db.prescription_commitments.update_one(
        {"_id": ObjectId(commitment_id)},
        {"$set": {
            "approval_status": "APPROVED",
            "approved_discount": approved_discount,
            "approved_quantity": final_quantity,
            "net_revenue": net_revenue,
            "approved_by": admin_user["_id"],
            "approved_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }}
    )
    
    logger.info(f"Admin {admin_user['_id']} approved commitment {commitment_id}: discount={approved_discount}%, qty={final_quantity}, net_revenue={net_revenue}")
    
    return {"message": f"Approved: {approved_discount}% discount, qty={final_quantity}, net_revenue=₹{net_revenue}"}


async def reject_rcpa_discount(
    commitment_id: str,
    admin_user: Dict[str, Any]
) -> Dict[str, str]:
    """
    Admin rejects a discount request on a commitment.
    """
    db = get_company_database()
    
    if not ObjectId.is_valid(commitment_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid commitment ID")
    
    commitment = await db.prescription_commitments.find_one({"_id": ObjectId(commitment_id)})
    if not commitment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commitment not found")
    
    if commitment.get("approval_status") != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Commitment already {commitment.get('approval_status')}"
        )
    
    await db.prescription_commitments.update_one(
        {"_id": ObjectId(commitment_id)},
        {"$set": {
            "approval_status": "REJECTED",
            "approved_discount": None,
            "approved_by": admin_user["_id"],
            "approved_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }}
    )
    
    logger.info(f"Admin {admin_user['_id']} rejected discount for commitment {commitment_id}")
    
    return {"message": "Discount request rejected"}


async def get_pending_discount_approvals(
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get all commitments with pending discount approval (Admin only).
    """
    db = get_company_database()
    
    commitments = await db.prescription_commitments.find(
        {"approval_status": "PENDING"}
    ).sort("created_at", -1).to_list(length=None)
    
    for c in commitments:
        c["id"] = str(c.pop("_id"))
    
    logger.info(f"Admin fetched {len(commitments)} pending discount approvals")
    
    return {
        "total": len(commitments),
        "commitments": commitments
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
        start_date = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day, 23, 59, 59)
        
        query["created_at"] = {
            "$gte": start_date,
            "$lte": end_date
        }
    
    # Get all active commitments
    commitments = await db.prescription_commitments.find(query).to_list(length=None)
    
    # Calculate totals
    total_rx_per_month = sum(c.get("rx_per_month", 0) for c in commitments)
    total_commitments = len(commitments)
    unique_doctors = len(set(c["doctor_id"] for c in commitments))
    unique_drugs = len(set(c.get("drug_id") or c.get("product_id", "") for c in commitments))
    
    # Group by drug
    drug_summary = {}
    for c in commitments:
        d_id = c.get("drug_id") or c.get("product_id", "unknown")
        d_name = c.get("drug_name") or c.get("product_name", "Unknown Drug")
        if d_id not in drug_summary:
            drug_summary[d_id] = {
                "drug_id": d_id,
                "drug_name": d_name,
                "rx_per_month": 0,
                "doctors_count": set()
            }
        drug_summary[d_id]["rx_per_month"] += c.get("rx_per_month", 0)
        drug_summary[d_id]["doctors_count"].add(c["doctor_id"])
    
    # Convert to list
    by_drug = [
        {
            "drug_id": v["drug_id"],
            "drug_name": v["drug_name"],
            "rx_per_month": v["rx_per_month"],
            "doctors_count": len(v["doctors_count"])
        }
        for v in drug_summary.values()
    ]
    by_drug.sort(key=lambda x: x["rx_per_month"], reverse=True)
    
    logger.info(f"Admin fetched RCPA summary: {total_rx_per_month} rx/month from {total_commitments} commitments")
    
    return {
        "total_rx_per_month": total_rx_per_month,
        "total_commitments": total_commitments,
        "total_doctors": unique_doctors,
        "total_drugs": unique_drugs,
        "by_drug": by_drug
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
    
    # Get all MRs (MRs are in the mrs collection, no role field needed)
    mrs = await db.mrs.find({"is_active": True}).to_list(length=None)
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
            "total_rx_per_month": 0,
            "leaderboard": [],
            "underperformers": [],
            "by_territory": [],
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
        start_date = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day, 23, 59, 59)
        
        rcpa_query["created_at"] = {"$gte": start_date, "$lte": end_date}
        
        rcpa_commitments = await db.prescription_commitments.find(rcpa_query).to_list(length=None)
        rcpa_count = len(rcpa_commitments)
        rx_per_month = sum(c.get("rx_per_month", 0) for c in rcpa_commitments)
        
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
            "rx_per_month": rx_per_month
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
    total_rx_per_month = sum(c.get("rx_per_month", 0) for c in all_commitments)
    
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
                "rx_per_month": 0
            }
        
        territory_data[terr]["mrs_count"] += 1
        territory_data[terr]["mcr_sum"] += mr_perf["mcr_percentage"]
        territory_data[terr]["mvc_sum"] += mr_perf["mvc_percentage"]
        territory_data[terr]["total_doctors"] += mr_perf["total_assigned"]
        territory_data[terr]["total_visits"] += mr_perf["doctors_visited"]
        territory_data[terr]["total_commitments"] += mr_perf["rcpa_commitments"]
        territory_data[terr]["rx_per_month"] += mr_perf["rx_per_month"]
    
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
            "rx_per_month": terr_data["rx_per_month"]
        })
    
    by_territory.sort(key=lambda x: x["rx_per_month"], reverse=True)
    
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
        "total_rx_per_month": total_rx_per_month,
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
    start_date = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59)
    
    rcpa_query = {
        "mr_id": mr_id,
        "status": "active",
        "created_at": {"$gte": start_date, "$lte": end_date}
    }
    
    rcpa_commitments = await db.prescription_commitments.find(rcpa_query).to_list(length=None)
    rcpa_summary = {
        "total_commitments": len(rcpa_commitments),
        "rx_per_month": sum(c.get("rx_per_month", 0) for c in rcpa_commitments)
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
