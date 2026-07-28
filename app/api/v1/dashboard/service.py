"""
Dashboard Business Logic
"""
from datetime import date
from bson import ObjectId

from datetime import datetime
from typing import Dict, Any, List
from app.database import get_database


async def get_admin_dashboard() -> Dict[str, Any]:
    """
    Get admin dashboard data with statistics and recent activity.
    
    Returns:
        dict: Dashboard data with statistics and recent_activity
    """
    db = get_database()
    
    # ============ STATISTICS ============
    
    # Count active drugs
    total_drugs = await db["drugs"].count_documents({"is_active": True})
    
    # Count MRs
    total_mrs = await db["mrs"].count_documents({})
    active_mrs = await db["mrs"].count_documents({"is_active": True})
    
    # Count doctors
    total_doctors = await db["doctors"].count_documents({})
    active_doctors = await db["doctors"].count_documents({"is_active": True})
    
    # Count CME events
    total_cme_events = await db["cme_events"].count_documents({})
    upcoming_cme_events = await db["cme_events"].count_documents({"status": "upcoming"})
    
    statistics = {
        "total_drugs": total_drugs,
        "total_mrs": total_mrs,
        "total_doctors": total_doctors,
        "total_cme_events": total_cme_events,
        "active_mrs": active_mrs,
        "active_doctors": active_doctors,
        "upcoming_cme_events": upcoming_cme_events
    }
    
    # ============ RECENT ACTIVITY ============
    
    recent_activity = []
    
    # Fetch recent doctors (last 5)
    recent_doctors = await db["doctors"].find().sort("created_at", -1).limit(5).to_list(5)
    for doctor in recent_doctors:
        recent_activity.append({
            "id": f"doctor_{str(doctor['_id'])}",
            "type": "doctor_added",
            "title": "New Doctor Added",
            "description": f"{doctor['name']} joined as {doctor.get('specialization', 'Doctor')}",
            "timestamp": doctor.get("created_at", datetime.utcnow()),
            "user": doctor["name"]
        })
    
    # Fetch recent MRs (last 5)
    recent_mrs = await db["mrs"].find().sort("created_at", -1).limit(5).to_list(5)
    for mr in recent_mrs:
        recent_activity.append({
            "id": f"mr_{str(mr['_id'])}",
            "type": "mr_added",
            "title": "New MR Added",
            "description": f"{mr['name']} joined {mr.get('territory', 'territory')}",
            "timestamp": mr.get("created_at", datetime.utcnow()),
            "user": mr["name"]
        })
    
    # Fetch recent drugs (last 5)
    recent_drugs = await db["drugs"].find({"is_active": True}).sort("created_at", -1).limit(5).to_list(5)
    for drug in recent_drugs:
        # Get drug_name and brand_name from field_values
        drug_name = None
        brand_name = None
        for field in drug.get("field_values", []):
            if field["key"] == "drug_name":
                drug_name = field["value"]
            elif field["key"] == "brand_name":
                brand_name = field["value"]
        
        description = f"{drug_name or 'Drug'}"
        if brand_name:
            description += f" ({brand_name})"
        description += " added to inventory"
        
        recent_activity.append({
            "id": f"drug_{str(drug['_id'])}",
            "type": "drug_added",
            "title": "New Drug Added",
            "description": description,
            "timestamp": drug.get("created_at", datetime.utcnow()),
            "user": "Admin"
        })
    
    # Fetch recent CME events (last 5)
    recent_cme = await db["cme_events"].find().sort("created_at", -1).limit(5).to_list(5)
    for cme in recent_cme:
        recent_activity.append({
            "id": f"cme_{str(cme['_id'])}",
            "type": "cme_created",
            "title": "CME Event Created",
            "description": f"{cme['title']} scheduled",
            "timestamp": cme.get("created_at", datetime.utcnow()),
            "user": "Admin"
        })
    
    # Fetch recent visits (last 5) - if visits collection exists
    try:
        recent_visits = await db["visits"].find().sort("created_at", -1).limit(5).to_list(5)
        
        # Collect all mr_ids and doctor_ids for batch lookup
        mr_ids = set()
        doctor_ids = set()
        for visit in recent_visits:
            if visit.get("mr_id") and ObjectId.is_valid(str(visit["mr_id"])):
                mr_ids.add(str(visit["mr_id"]))
            if visit.get("doctor_id") and ObjectId.is_valid(str(visit["doctor_id"])):
                doctor_ids.add(str(visit["doctor_id"]))
        
        # Batch fetch MRs and Doctors
        mr_map = {}
        if mr_ids:
            mrs_cursor = db["mrs"].find({"_id": {"$in": [ObjectId(i) for i in mr_ids]}}, {"name": 1})
            mrs_list = await mrs_cursor.to_list(length=None)
            mr_map = {str(m["_id"]): m.get("name", "MR") for m in mrs_list}
        
        doctor_map = {}
        if doctor_ids:
            doctors_cursor = db["doctors"].find({"_id": {"$in": [ObjectId(i) for i in doctor_ids]}}, {"name": 1})
            doctors_list = await doctors_cursor.to_list(length=None)
            doctor_map = {str(d["_id"]): d.get("name", "Doctor") for d in doctors_list}
        
        for visit in recent_visits:
            mr_name = mr_map.get(str(visit.get("mr_id", "")), visit.get("mr_name", "MR"))
            doctor_name = doctor_map.get(str(visit.get("doctor_id", "")), visit.get("doctor_name", "Doctor"))
            
            # Use status for better description
            visit_status = visit.get("status", "scheduled")
            if visit_status == "completed":
                action = "completed a visit with"
            elif visit_status == "cancelled":
                action = "cancelled a visit with"
            elif visit_status == "checked_in":
                action = "checked in to visit"
            elif visit_status == "checked_out":
                action = "checked out from visit with"
            else:
                action = "scheduled a visit with"
            
            recent_activity.append({
                "id": f"visit_{str(visit['_id'])}",
                "type": f"visit_{visit_status}",
                "title": f"Visit {visit_status.replace('_', ' ').title()}",
                "description": f"{mr_name} {action} {doctor_name}",
                "timestamp": visit.get("created_at", datetime.utcnow()),
                "user": mr_name
            })
    except Exception:
        # Visits collection might not exist yet
        pass
    
    # Sort all activities by timestamp (most recent first)
    recent_activity.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # Return top 10 most recent activities
    recent_activity = recent_activity[:10]
    
    return {
        "statistics": statistics,
        "recent_activity": recent_activity
    }



async def get_mr_dashboard(mr_id: str) -> Dict[str, Any]:
    """
    Get MR dashboard data with statistics and visits.
    
    Args:
        mr_id: MR's user ID
    
    Returns:
        dict: Dashboard data with statistics, upcoming_visits, recent_visits
    """
    db = get_database()
    
    
    # Get MR information
    mr = await db["mrs"].find_one({"_id": ObjectId(mr_id)})
    
    if not mr:
        return {
            "statistics": {
                "assigned_doctors": 0,
                "total_visits": 0,
                "completion_rate": "0%"
            },
            "upcoming_visits": [],
            "recent_visits": []
        }
    
    # ============ STATISTICS ============
    
    # Assigned doctors count
    assigned_doctors = len(mr.get("assigned_doctors", []))
    
    # Total visits count
    total_visits = await db["visits"].count_documents({"mr_id": mr_id})
    
    # Completed visits count
    completed_visits = await db["visits"].count_documents({
        "mr_id": mr_id,
        "status": "completed"
    })
    
    # Calculate completion rate
    if total_visits > 0:
        completion_rate = f"{int((completed_visits / total_visits) * 100)}%"
    else:
        completion_rate = "0%"
    
    statistics = {
        "assigned_doctors": assigned_doctors,
        "total_visits": total_visits,
        "completion_rate": completion_rate
    }
    
    # ============ UPCOMING VISITS ============
    # Get visits with status "scheduled" or "rescheduled", sorted by date
    today = date.today()
    
    upcoming_visits_cursor = db["visits"].find({
        "mr_id": mr_id,
        "status": {"$in": ["scheduled", "rescheduled"]},
        "scheduled_date": {"$gte": datetime.combine(today, datetime.min.time())}
    }).sort("scheduled_date", 1).limit(5)
    
    upcoming_visits_list = await upcoming_visits_cursor.to_list(5)
    
    upcoming_visits = []
    for visit in upcoming_visits_list:
        # Get doctor specialization
        doctor_specialization = None
        if visit.get("doctor_id"):
            try:
                doctor = await db["doctors"].find_one(
                    {"_id": ObjectId(visit["doctor_id"])},
                    {"specialization": 1}
                )
                if doctor:
                    doctor_specialization = doctor.get("specialization")
            except:
                pass
        
        upcoming_visits.append({
            "visit_id": str(visit["_id"]),
            "doctor_name": visit.get("doctor_name", ""),
            "doctor_specialization": doctor_specialization,
            "scheduled_date": visit.get("scheduled_date"),
            "scheduled_time": visit.get("scheduled_time", ""),
            "purpose": visit.get("purpose", ""),
            "location": visit.get("location", ""),
            "status": visit.get("status", "")
        })
    
    # ============ RECENT VISITS ============
    # Get visits with status "completed" or "cancelled", sorted by date (most recent first)
    
    recent_visits_cursor = db["visits"].find({
        "mr_id": mr_id,
        "status": {"$in": ["completed", "cancelled"]}
    }).sort("updated_at", -1).limit(5)
    
    recent_visits_list = await recent_visits_cursor.to_list(5)
    
    recent_visits = []
    for visit in recent_visits_list:
        recent_visits.append({
            "visit_id": str(visit["_id"]),
            "doctor_name": visit.get("doctor_name", ""),
            "scheduled_date": visit.get("scheduled_date"),
            "status": visit.get("status", ""),
            "outcome": visit.get("outcome"),
            "completed_at": visit.get("completed_at"),
            "cancelled_at": visit.get("cancelled_at")
        })
    
    return {
        "statistics": statistics,
        "upcoming_visits": upcoming_visits,
        "recent_visits": recent_visits
    }



async def get_doctor_dashboard(doctor_id: str) -> Dict[str, Any]:
    """Doctor dashboard moved to DRX platform."""
    from fastapi import HTTPException
    raise HTTPException(status_code=403, detail="Doctor dashboard is now on DRX platform")
