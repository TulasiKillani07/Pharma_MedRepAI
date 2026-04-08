"""
Dashboard Business Logic
"""

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
        for visit in recent_visits:
            # Get MR and Doctor names
            mr_name = "MR"
            doctor_name = "Doctor"
            
            if visit.get("mr_id"):
                mr = await db["mrs"].find_one({"_id": visit["mr_id"]})
                if mr:
                    mr_name = mr.get("name", "MR")
            
            if visit.get("doctor_id"):
                doctor = await db["doctors"].find_one({"_id": visit["doctor_id"]})
                if doctor:
                    doctor_name = doctor.get("name", "Doctor")
            
            recent_activity.append({
                "id": f"visit_{str(visit['_id'])}",
                "type": "visit_scheduled",
                "title": "Visit Scheduled",
                "description": f"{mr_name} scheduled visit with {doctor_name}",
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
