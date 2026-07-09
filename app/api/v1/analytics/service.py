"""
RCPA Analytics Service
All analytics sourced from prescription_commitments collection.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.database import get_database
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)


def _get_db():
    return get_database()


def _month_query(month: Optional[int], year: Optional[int]) -> Dict:
    """Build month/year filter"""
    q = {}
    if month and year:
        q["month"] = month
        q["year"] = year
    elif year:
        q["year"] = year
    return q


async def get_dashboard(month: Optional[int], year: Optional[int]) -> Dict[str, Any]:
    """
    Layer 1 — Dashboard KPI cards.
    """
    db = _get_db()
    query = _month_query(month, year)

    # All commitments for the period
    commitments = await db.prescription_commitments.find(query).to_list(length=None)

    committed_revenue = sum(c.get("committed_revenue", 0) for c in commitments)
    net_revenue = sum(c.get("net_revenue", 0) for c in commitments if c.get("net_revenue"))
    pending_revenue = sum(c.get("committed_revenue", 0) for c in commitments if c.get("approval_status") == "PENDING")
    discount_given = committed_revenue - net_revenue if net_revenue else 0

    total = len(commitments)
    pending = sum(1 for c in commitments if c.get("approval_status") == "PENDING")
    approved = sum(1 for c in commitments if c.get("approval_status") == "APPROVED")
    rejected = sum(1 for c in commitments if c.get("approval_status") == "REJECTED")

    # Today's approvals/rejections
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    approved_today = sum(1 for c in commitments if c.get("approved_at") and c["approved_at"] >= today_start and c.get("approval_status") == "APPROVED")
    rejected_today = sum(1 for c in commitments if c.get("approved_at") and c["approved_at"] >= today_start and c.get("approval_status") == "REJECTED")

    active_mrs = len(set(c["mr_id"] for c in commitments))
    active_doctors = len(set(c["doctor_id"] for c in commitments))
    active_drugs = len(set(c.get("drug_id", "") for c in commitments))

    # MoM growth
    mom_growth = 0.0
    if month and year:
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        prev_commitments = await db.prescription_commitments.find({"month": prev_month, "year": prev_year}).to_list(length=None)
        prev_revenue = sum(c.get("committed_revenue", 0) for c in prev_commitments)
        if prev_revenue > 0:
            mom_growth = round(((committed_revenue - prev_revenue) / prev_revenue) * 100, 1)

    return {
        "committed_revenue": committed_revenue,
        "net_revenue": net_revenue,
        "discount_given": discount_given,
        "pending_revenue": pending_revenue,
        "mom_growth": mom_growth,
        "total_commitments": total,
        "pending_approvals": pending,
        "approved": approved,
        "rejected": rejected,
        "approved_today": approved_today,
        "rejected_today": rejected_today,
        "active_mrs": active_mrs,
        "active_doctors": active_doctors,
        "active_drugs": active_drugs
    }


async def get_drug_analytics(month: Optional[int], year: Optional[int]) -> List[Dict]:
    """Layer 2 — Drug-wise analytics"""
    db = _get_db()
    query = _month_query(month, year)
    commitments = await db.prescription_commitments.find(query).to_list(length=None)

    drug_map = {}
    for c in commitments:
        did = c.get("drug_id", "unknown")
        if did not in drug_map:
            drug_map[did] = {
                "drug_id": did,
                "drug_name": c.get("drug_name", "Unknown"),
                "commitments": 0,
                "committed_quantity": 0,
                "rx_per_month": 0,
                "committed_revenue": 0,
                "net_revenue": 0,
                "total_discount": 0,
                "approved_count": 0
            }
        d = drug_map[did]
        d["commitments"] += 1
        d["committed_quantity"] += c.get("committed_quantity", 0)
        d["rx_per_month"] += c.get("rx_per_month", 0)
        d["committed_revenue"] += c.get("committed_revenue", 0)
        if c.get("net_revenue"):
            d["net_revenue"] += c["net_revenue"]
        if c.get("approved_discount"):
            d["total_discount"] += c["approved_discount"]
            d["approved_count"] += 1

    result = []
    for d in drug_map.values():
        d["avg_discount"] = round(d["total_discount"] / d["approved_count"], 1) if d["approved_count"] > 0 else 0
        d["approval_rate"] = round((d["approved_count"] / d["commitments"]) * 100, 1) if d["commitments"] > 0 else 0
        del d["total_discount"]
        del d["approved_count"]
        result.append(d)

    result.sort(key=lambda x: x["committed_revenue"], reverse=True)
    return result


async def get_mr_analytics(month: Optional[int], year: Optional[int]) -> List[Dict]:
    """Layer 2 — MR-wise analytics"""
    db = _get_db()
    query = _month_query(month, year)
    commitments = await db.prescription_commitments.find(query).to_list(length=None)

    # Get visit counts per MR
    mr_visits = {}
    visit_query = {}
    if month and year:
        import calendar
        start = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = datetime(year, month, last_day, 23, 59, 59)
        visit_query = {"status": "completed", "completed_at": {"$gte": start, "$lte": end}}
    else:
        visit_query = {"status": "completed"}

    visits = await db.visits.find(visit_query, {"mr_id": 1}).to_list(length=None)
    for v in visits:
        mid = v.get("mr_id", "")
        mr_visits[mid] = mr_visits.get(mid, 0) + 1

    mr_map = {}
    for c in commitments:
        mid = c.get("mr_id", "unknown")
        if mid not in mr_map:
            mr_map[mid] = {
                "mr_id": mid,
                "mr_name": c.get("mr_name", "Unknown"),
                "commitments": 0,
                "committed_revenue": 0,
                "net_revenue": 0,
                "total_discount": 0,
                "discount_count": 0,
                "doctors": set()
            }
        m = mr_map[mid]
        m["commitments"] += 1
        m["committed_revenue"] += c.get("committed_revenue", 0)
        if c.get("net_revenue"):
            m["net_revenue"] += c["net_revenue"]
        if c.get("approved_discount"):
            m["total_discount"] += c["approved_discount"]
            m["discount_count"] += 1
        m["doctors"].add(c.get("doctor_id", ""))

    result = []
    for m in mr_map.values():
        visits_count = mr_visits.get(m["mr_id"], 0)
        m["visits"] = visits_count
        m["conversion_rate"] = round((m["commitments"] / visits_count) * 100, 1) if visits_count > 0 else 0
        m["avg_revenue_per_visit"] = round(m["committed_revenue"] / visits_count) if visits_count > 0 else 0
        m["avg_discount"] = round(m["total_discount"] / m["discount_count"], 1) if m["discount_count"] > 0 else 0
        m["active_doctors"] = len(m["doctors"])
        del m["total_discount"]
        del m["discount_count"]
        del m["doctors"]
        result.append(m)

    result.sort(key=lambda x: x["committed_revenue"], reverse=True)
    return result


async def get_doctor_analytics(month: Optional[int], year: Optional[int]) -> List[Dict]:
    """Layer 2 — Doctor-wise analytics"""
    db = _get_db()
    query = _month_query(month, year)
    commitments = await db.prescription_commitments.find(query).to_list(length=None)

    doc_map = {}
    for c in commitments:
        did = c.get("doctor_id", "unknown")
        if did not in doc_map:
            doc_map[did] = {
                "doctor_id": did,
                "doctor_name": c.get("doctor_name", "Unknown"),
                "commitments": 0,
                "committed_revenue": 0,
                "net_revenue": 0,
                "total_discount": 0,
                "discount_count": 0,
                "drugs": {},
                "last_visit": None,
                "mr_name": c.get("mr_name")
            }
        d = doc_map[did]
        d["commitments"] += 1
        d["committed_revenue"] += c.get("committed_revenue", 0)
        if c.get("net_revenue"):
            d["net_revenue"] += c["net_revenue"]
        if c.get("approved_discount"):
            d["total_discount"] += c["approved_discount"]
            d["discount_count"] += 1
        drug_name = c.get("drug_name", "")
        d["drugs"][drug_name] = d["drugs"].get(drug_name, 0) + c.get("committed_revenue", 0)

    result = []
    for d in doc_map.values():
        d["avg_discount"] = round(d["total_discount"] / d["discount_count"], 1) if d["discount_count"] > 0 else 0
        d["most_prescribed_drug"] = max(d["drugs"], key=d["drugs"].get) if d["drugs"] else None
        del d["total_discount"]
        del d["discount_count"]
        del d["drugs"]
        result.append(d)

    result.sort(key=lambda x: x["committed_revenue"], reverse=True)
    return result


async def get_region_analytics(level: str, month: Optional[int], year: Optional[int],
                                state: Optional[str] = None, district: Optional[str] = None,
                                location_type: Optional[str] = None) -> List[Dict]:
    """Layer 2 — Region drill-down (state → district → area → hospital)"""
    db = _get_db()
    query = _month_query(month, year)

    if state:
        query["doctor_location.state"] = state
    if district:
        query["doctor_location.district"] = district
    if location_type:
        query["doctor_location.type"] = location_type

    commitments = await db.prescription_commitments.find(query).to_list(length=None)

    region_map = {}
    for c in commitments:
        loc = c.get("doctor_location") or {}
        if level == "state":
            key = loc.get("state", "Unknown")
        elif level == "district":
            key = loc.get("district", "Unknown")
        elif level == "area":
            key = loc.get("area", "Unknown")
        else:
            key = loc.get("name", "Unknown")

        if key not in region_map:
            region_map[key] = {
                "name": key,
                "commitments": 0,
                "committed_revenue": 0,
                "net_revenue": 0,
                "doctors": set(),
                "mrs": set()
            }
        r = region_map[key]
        r["commitments"] += 1
        r["committed_revenue"] += c.get("committed_revenue", 0)
        if c.get("net_revenue"):
            r["net_revenue"] += c["net_revenue"]
        r["doctors"].add(c.get("doctor_id", ""))
        r["mrs"].add(c.get("mr_id", ""))

    result = []
    for r in region_map.values():
        r["doctors"] = len(r["doctors"])
        r["mrs"] = len(r["mrs"])
        result.append(r)

    result.sort(key=lambda x: x["committed_revenue"], reverse=True)
    return result


async def get_trends(months: int = 6) -> Dict[str, List]:
    """Layer 2 — Monthly trends for last N months"""
    db = _get_db()
    now = datetime.utcnow()

    revenue_trend = []
    commitment_trend = []
    approval_trend = []

    for i in range(months - 1, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1

        commitments = await db.prescription_commitments.find({"month": m, "year": y}).to_list(length=None)

        committed = sum(c.get("committed_revenue", 0) for c in commitments)
        net = sum(c.get("net_revenue", 0) for c in commitments if c.get("net_revenue"))
        approved = sum(1 for c in commitments if c.get("approval_status") == "APPROVED")
        rejected = sum(1 for c in commitments if c.get("approval_status") == "REJECTED")

        label = f"{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1]} {y}"

        revenue_trend.append({"month": label, "committed": committed, "net": net})
        commitment_trend.append({"month": label, "count": len(commitments)})
        approval_trend.append({"month": label, "approved": approved, "rejected": rejected})

    return {
        "revenue_trend": revenue_trend,
        "commitment_trend": commitment_trend,
        "approval_trend": approval_trend
    }


async def get_doctors_by_location(location_name: str, month: Optional[int], year: Optional[int]) -> List[Dict]:
    """Which doctors generated most revenue at a specific location"""
    db = _get_db()
    query = _month_query(month, year)
    query["doctor_location.name"] = location_name

    commitments = await db.prescription_commitments.find(query).to_list(length=None)

    doc_map = {}
    for c in commitments:
        did = c.get("doctor_id", "unknown")
        if did not in doc_map:
            doc_map[did] = {
                "doctor_id": did,
                "doctor_name": c.get("doctor_name", "Unknown"),
                "commitments": 0,
                "committed_revenue": 0,
                "net_revenue": 0
            }
        d = doc_map[did]
        d["commitments"] += 1
        d["committed_revenue"] += c.get("committed_revenue", 0)
        if c.get("net_revenue"):
            d["net_revenue"] += c["net_revenue"]

    result = list(doc_map.values())
    result.sort(key=lambda x: x["committed_revenue"], reverse=True)
    return result
