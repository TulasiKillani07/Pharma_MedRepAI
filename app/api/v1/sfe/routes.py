"""
SFE (Sales Force Effectiveness) API routes.
"""

from fastapi import APIRouter, Depends, status, Request, Query, HTTPException
from typing import Dict, Any, Optional
from app.core.auth import get_current_user, require_admin
from app.api.v1.sfe import schemas, service
from app.utils.logger import get_medrep_logger

# Initialize logger
logger = get_medrep_logger(__name__)
router = APIRouter(prefix="/sfe", tags=["SFE - Sales Force Effectiveness"])


# ============================================================================
# MCR (MONTHLY CALL REPORT)
# ============================================================================

@router.get(
    "/mcr",
    response_model=schemas.MCRResponse,
    status_code=status.HTTP_200_OK,
    summary="Get MCR (Monthly Call Report)",
    description="""
    **Purpose:** Calculate Monthly Call Report - measures what percentage of assigned doctors were visited at least once in a given month. Includes full visit details with report data (products discussed, doctor mood, outcome, etc.).
    
    **Formula:** MCR % = (Unique doctors with ≥1 completed visit this month / Total assigned doctors) × 100
    
    **Required Role:** 
    - MR: Can view own MCR data (no mr_id parameter needed)
    - Admin: Can view any MR's MCR data (provide mr_id parameter)
    
    **Use Case:**
    - MR checks their monthly doctor coverage performance
    - Admin monitors MR performance and identifies underperformers
    - View full visit details: products discussed, doctor feedback, outcomes
    - Company tracks overall field force effectiveness
    
    **Example Request (MR):**
    ```
    GET /api/v1/sfe/mcr?month=5&year=2026
    Headers: Authorization: Bearer <mr_token>
    ```
    
    **Example Request (Admin):**
    ```
    GET /api/v1/sfe/mcr?month=5&year=2026&mr_id=507f1f77bcf86cd799439013
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Example Response:**
    ```json
    {
      "mr_id": "507f1f77bcf86cd799439013",
      "mr_name": "Rajesh Kumar",
      "month": 5,
      "year": 2026,
      "total_assigned": 10,
      "doctors_visited": 7,
      "doctors_not_visited": 3,
      "mcr_percentage": 70.0,
      "visited": [
        {
          "doctor_id": "6a0d9fa2...",
          "doctor_name": "Dr. Sneha Sharma",
          "classification": "A",
          "visits_count": 3,
          "last_visit_date": "2026-05-20T14:30:00",
          "visits": [
            {
              "visit_id": "6a0edec2...",
              "scheduled_date": "2026-05-20",
              "completed_at": "2026-05-20T14:30:00",
              "duration_minutes": 28,
              "location": "Apollo Hospital",
              "purpose": "Drug Promotion",
              "doctor_mood": "positive",
              "products_discussed": [{"id": "drug_id_1", "name": "Amlodipine 5mg"}, {"id": "drug_id_2", "name": "Metformin 500mg"}],
              "samples_given": 3,
              "outcome": "Positive — Doctor interested in Amlodipine 5mg",
              "rx_commitment": true,
              "expected_rx_per_month": 10,
              "competitor_info": "Cipla — Amlokind 5mg",
              "follow_up_date": "2026-06-01",
              "notes": "Doctor wants clinical trial data"
            },
            {
              "visit_id": "6a0edf12...",
              "scheduled_date": "2026-05-10",
              "completed_at": "2026-05-10T11:00:00",
              "duration_minutes": 22,
              "location": "Apollo Hospital",
              "purpose": "Follow-up",
              "doctor_mood": "neutral",
              "products_discussed": [{"id": "drug_id_1", "name": "Amlodipine 5mg"}],
              "samples_given": 2,
              "outcome": "Doctor asked for more data before committing",
              "rx_commitment": false,
              "expected_rx_per_month": null,
              "competitor_info": null,
              "follow_up_date": "2026-05-20",
              "notes": null
            }
          ]
        }
      ],
      "not_visited": [
        {
          "doctor_id": "6a0da18e...",
          "doctor_name": "Dr. Priya Reddy",
          "classification": "B",
          "last_visited": null
        }
      ]
    }
    ```
    
    **What It Tells You:**
    - **MCR %**: Overall coverage percentage
    - **visited[]**: Doctors who were visited with full visit details:
      - How many times visited
      - Each visit's duration, location, purpose
      - Doctor's mood during each visit
      - Products discussed and samples given
      - Outcome and feedback
      - Prescription commitments
      - Competitor information
      - Follow-up dates
    - **not_visited[]**: Doctors who were NOT visited this month
    
    **Visit Details Fields:**
    - `doctor_mood`: positive / neutral / negative
    - `products_discussed`: Array of objects with drug id and name (e.g., `[{"id": "...", "name": "Amlodipine 5mg"}]`)
    - `samples_given`: Number of samples distributed
    - `outcome`: Visit outcome summary
    - `rx_commitment`: Did doctor commit to prescribing? (true/false)
    - `expected_rx_per_month`: Expected prescriptions per month
    - `competitor_info`: Competitor information observed
    - `follow_up_date`: Next follow-up date
    - `notes`: Additional notes
    - `duration_minutes`: How long the visit lasted
    
    **What Happens:**
    1. System retrieves all doctors assigned to the MR (from `mrs.assigned_doctors`)
    2. Fetches doctor details (name, classification) from `doctors` collection
    3. Reads required visits per classification from `sfe_settings` collection
    4. Queries all completed visits for the specified month from `visits` collection
    5. Groups visits by doctor with full report data
    6. Calculates MCR percentage
    7. Returns detailed breakdown with visit reports
    
    **Not stored in DB** — calculated on-the-fly from existing visit data every time.
    
    **Performance Benchmarks:**
    - Excellent: MCR ≥ 90%
    - Good: MCR 75-89%
    - Needs Improvement: MCR 60-74%
    - Critical: MCR < 60%
    """
)
async def get_mcr_report(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2030, description="Year (e.g., 2026)"),
    mr_id: Optional[str] = Query(None, description="MR ID (admin only, optional for MR)"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    
    result = await service.get_mcr_report(
        month=month,
        year=year,
        mr_id=mr_id,
        current_user=current_user
    )
    
    return result


# ============================================================================
# MVC (MONTHLY VISIT COVERAGE)
# ============================================================================

@router.get(
    "/mvc",
    response_model=schemas.MVCResponse,
    status_code=status.HTTP_200_OK,
    summary="Get MVC (Monthly Visit Coverage)",
    description="""
    **Purpose:** Calculate Monthly Visit Coverage - measures whether each doctor received their required number of visits based on their classification.
    
    **Formula:** MVC % = (Doctors who received ≥ required visits / Total assigned doctors) × 100
    
    **Required Role:** 
    - MR: Can view own MVC data (no mr_id parameter needed)
    - Admin: Can view any MR's MVC data (provide mr_id parameter)
    
    **Use Case:**
    - MR checks visit frequency compliance for each doctor
    - Identifies which doctors need more attention
    - Admin monitors MR adherence to visit frequency standards
    - Company tracks quality of field force execution
    
    **Example Request (MR):**
    ```
    GET /api/v1/sfe/mvc?month=5&year=2026
    Headers: Authorization: Bearer <mr_token>
    ```
    
    **Example Request (Admin):**
    ```
    GET /api/v1/sfe/mvc?month=5&year=2026&mr_id=507f1f77bcf86cd799439013
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Example Response:**
    ```json
    {
      "mr_id": "507f1f77bcf86cd799439013",
      "mr_name": "Rajesh Kumar",
      "month": 5,
      "year": 2026,
      "total_assigned": 50,
      "fully_covered": 36,
      "under_covered": 10,
      "not_visited": 4,
      "mvc_percentage": 72.0,
      "avg_compliance": 85.5,
      "doctors": [
        {
          "doctor_id": "507f1f77bcf86cd799439011",
          "doctor_name": "Dr. Arjun Sharma",
          "classification": "A",
          "required_visits": 4,
          "actual_visits": 4,
          "status": "covered",
          "compliance_percentage": 100.0
        },
        {
          "doctor_id": "507f1f77bcf86cd799439012",
          "doctor_name": "Dr. Sneha Patel",
          "classification": "A",
          "required_visits": 4,
          "actual_visits": 2,
          "status": "under",
          "compliance_percentage": 50.0
        },
        {
          "doctor_id": "507f1f77bcf86cd799439013",
          "doctor_name": "Dr. Priya Reddy",
          "classification": "C",
          "required_visits": 1,
          "actual_visits": 0,
          "status": "missed",
          "compliance_percentage": 0.0
        }
      ]
    }
    ```
    
    **What It Tells You:**
    - **MVC %**: Percentage of doctors who received required visits
    - **Avg Compliance**: Average compliance across all doctors (useful for partial compliance)
    - **Fully Covered**: Doctors who met their visit requirement
    - **Under Covered**: Doctors visited but not enough times
    - **Not Visited**: Doctors with zero visits
    - **Per-Doctor Details**: Required vs actual visits with compliance %
    
    **Status Definitions:**
    - **covered**: Actual visits ≥ Required visits (100%+ compliance)
    - **under**: 0 < Actual visits < Required visits (partial compliance)
    - **missed**: Actual visits = 0 (no visits)
    
    **What Happens:**
    1. System retrieves all doctors assigned to the MR (from `mrs.assigned_doctors`)
    2. Fetches doctor details (name, classification) from `doctors` collection
    3. Gets required visit frequency from `sfe_settings` based on doctor classification (A/B/C)
    4. Counts actual completed visits per doctor from `visits` collection for the month
    5. Calculates compliance percentage for each doctor
    6. Categorizes doctors as covered/under/missed
    7. Calculates overall MVC % and average compliance
    8. Returns sorted list (covered first, then under, then missed)
    
    **Not stored in DB** — calculated on-the-fly from existing visit and settings data every time.
    
    **Performance Benchmarks:**
    - Excellent: MVC ≥ 85%
    - Good: MVC 70-84%
    - Needs Improvement: MVC 55-69%
    - Critical: MVC < 55%
    
    **Difference from MCR:**
    - **MCR**: Did you visit the doctor at least once? (Yes/No)
    - **MVC**: Did you visit the doctor enough times? (Frequency compliance)
    - Example: Doctor needs 4 visits, got 2 → MCR counts as "visited" (✓), MVC counts as "under-covered" (✗)
    """
)
async def get_mvc_report(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2030, description="Year (e.g., 2026)"),
    mr_id: Optional[str] = Query(None, description="MR ID (admin only, optional for MR)"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    
    result = await service.get_mvc_report(
        month=month,
        year=year,
        mr_id=mr_id,
        current_user=current_user
    )
    
    return result


# ============================================================================
# RCPA (PRESCRIPTION COMMITMENTS)
# ============================================================================

@router.post(
    "/rcpa",
    response_model=schemas.RCPACommitmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create RCPA Commitment",
    description="""
    **Purpose:** Log a prescription commitment from a doctor (usually done during or after a visit).
    
    **Required Role:** MR only
    
    **Example Request:**
    ```json
    {
      "doctor_id": "507f1f77bcf86cd799439011",
      "drug_id": "507f1f77bcf86cd799439021",
      "rx_per_month": 15,
      "visit_id": "507f1f77bcf86cd799439031"
    }
    ```
    
    **What Happens:**
    1. System validates doctor and drug exist
    2. Creates commitment record
    3. Included in demand forecast calculations
    
    **Note:** Commitments are also auto-created during visit completion when MR logs rx_commitment.
    """
)
async def create_rcpa_commitment(
    request_data: schemas.RCPACreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if current_user.get("role") != "MR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MRs can create RCPA commitments"
        )
    
    logger.info(f"MR {current_user['_id']} creating RCPA commitment")
    
    result = await service.create_rcpa_commitment(
        commitment_data=request_data.model_dump(),
        current_user=current_user
    )
    
    return result


@router.get(
    "/rcpa",
    response_model=schemas.RCPAListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get RCPA Commitments",
    description="""
    **Purpose:** Retrieve prescription commitments with optional filters.
    
    **Required Role:**
    - MR: Can view own commitments
    - Admin: Can view all or filter by MR
    
    **Query Parameters:**
    - `month`: Filter by month (1-12)
    - `year`: Filter by year
    - `mr_id`: Filter by MR (admin only)
    - `drug_id`: Filter by drug
    """
)
async def get_rcpa_commitments(
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    year: Optional[int] = Query(None, ge=2020, le=2030, description="Year"),
    mr_id: Optional[str] = Query(None, description="MR ID (admin only)"),
    drug_id: Optional[str] = Query(None, description="Drug ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    result = await service.get_rcpa_commitments(
        month=month,
        year=year,
        mr_id=mr_id,
        drug_id=drug_id,
        current_user=current_user
    )
    
    return result


@router.put(
    "/rcpa/{commitment_id}",
    response_model=schemas.MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Update RCPA Commitment",
    description="""
    **Purpose:** Update an existing prescription commitment.
    
    **Required Role:** MR (own) or Admin (any)
    
    **Updatable Fields:**
    - `rx_per_month`: New prescription volume
    - `notes`: Additional notes
    
    **Example Request:**
    ```json
    {
      "rx_per_month": 20,
      "notes": "Doctor confirmed after follow-up"
    }
    ```
    """
)
async def update_rcpa_commitment(
    commitment_id: str,
    request_data: schemas.RCPAUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    logger.info(f"User {current_user['_id']} updating RCPA commitment {commitment_id}")
    
    result = await service.update_rcpa_commitment(
        commitment_id=commitment_id,
        update_data=request_data.model_dump(exclude_none=True),
        current_user=current_user
    )
    
    return result


@router.get(
    "/rcpa/summary",
    response_model=schemas.RCPASummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get RCPA Summary (Admin Only)",
    description="""
    **Purpose:** Get aggregated RCPA data for demand forecasting and inventory planning.
    
    **Required Role:** Admin only
    
    **Example Request:**
    ```
    GET /api/v1/sfe/rcpa/summary?month=5&year=2026
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Example Response:**
    ```json
    {
      "total_rx_per_month": 1200,
      "total_commitments": 85,
      "total_doctors": 65,
      "total_drugs": 8,
      "by_drug": [
        {
          "drug_id": "507f1f77bcf86cd799439021",
          "drug_name": "Amlovas 5mg",
          "rx_per_month": 450,
          "doctors_count": 25
        },
        {
          "drug_id": "507f1f77bcf86cd799439022",
          "drug_name": "Metformin 500mg",
          "rx_per_month": 350,
          "doctors_count": 20
        }
      ]
    }
    ```
    
    **What It Tells You:**
    - Total expected prescriptions per month
    - Which drugs have highest demand
    - How many doctors are committing to prescribe each drug
    """
)
async def get_rcpa_summary(
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    year: Optional[int] = Query(None, ge=2020, le=2030, description="Year"),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    result = await service.get_rcpa_summary(
        month=month,
        year=year,
        current_user=current_user
    )
    
    return result



# ============================================================================
# SFE DASHBOARD
# ============================================================================

@router.get(
    "/dashboard",
    response_model=schemas.SFEDashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get SFE Dashboard (Admin Only)",
    description="""
    **Purpose:** Get company-wide SFE overview with all metrics, leaderboards, territory performance, and alerts.
    
    **Required Role:** Admin only
    
    **Use Case:**
    - Company leadership monitors overall field force effectiveness
    - Identify top performers and underperformers
    - Territory-wise performance comparison
    - Proactive alerts for critical issues
    - Strategic decision-making based on aggregated data
    
    **Example Request:**
    ```
    GET /api/v1/sfe/dashboard?month=5&year=2026
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Example Response:**
    ```json
    {
      "month": 5,
      "year": 2026,
      "total_mrs": 15,
      "avg_mcr_pct": 82.0,
      "avg_mvc_pct": 76.0,
      "total_doctors": 750,
      "total_visits": 2500,
      "total_commitments": 450,
      "total_rx_per_month": 3500,
      "leaderboard": [
        {
          "mr_id": "507f1f77bcf86cd799439013",
          "mr_name": "Rajesh Kumar",
          "territory": "Visakhapatnam",
          "mcr_percentage": 95.0,
          "mvc_percentage": 88.0,
          "avg_compliance": 92.0,
          "total_assigned": 50,
          "doctors_visited": 48,
          "rcpa_commitments": 30,
          "rx_per_month": 250
        }
      ],
      "underperformers": [
        {
          "mr_id": "507f1f77bcf86cd799439014",
          "mr_name": "Suresh Patel",
          "territory": "Mumbai",
          "mcr_percentage": 45.0,
          "mvc_percentage": 30.0,
          "avg_compliance": 40.0,
          "total_assigned": 60,
          "doctors_visited": 27,
          "rcpa_commitments": 5,
          "rx_per_month": 50
        }
      ],
      "by_territory": [
        {
          "territory": "Visakhapatnam",
          "mrs_count": 5,
          "avg_mcr": 88.0,
          "avg_mvc": 80.0,
          "total_doctors": 250,
          "total_visits": 900,
          "total_commitments": 150,
          "rx_per_month": 1200
        }
      ],
      "alerts": [
        {
          "mr_id": "507f1f77bcf86cd799439014",
          "mr_name": "Suresh Patel",
          "territory": "Mumbai",
          "alert_type": "critical_mcr",
          "severity": "critical",
          "message": "MCR below 60% (45.0%)",
          "metric_value": 45.0
        }
      ]
    }
    ```
    
    **What It Tells You:**
    - **Company Metrics**: Average MCR/MVC, total doctors, visits, commitments
    - **Leaderboard**: Top 10 MRs by combined MCR+MVC performance
    - **Underperformers**: MRs with MCR < 60% or MVC < 55%
    - **Territory Performance**: Aggregated metrics by territory
    - **Alerts**: Critical issues requiring immediate attention
    
    **Alert Types:**
    - `critical_mcr`: MCR below 60%
    - `critical_mvc`: MVC below 55%
    - `no_commitments`: No RCPA commitments logged
    - `declining_trend`: Performance declining over 3+ months (future)
    
    **What Happens:**
    1. Fetches all active MRs from `mrs` collection
    2. For each MR, calculates MCR and MVC for the given month
    3. Fetches RCPA commitments from `prescription_commitments` collection
    4. Aggregates company-wide totals (visits, doctors, commitments, rx/month)
    5. Generates leaderboard (top 10 by avg MCR+MVC score)
    6. Identifies underperformers (MCR < 60% or MVC < 55%)
    7. Groups metrics by territory
    8. Creates alerts for critical issues
    9. Returns comprehensive dashboard
    
    **Not stored in DB** — aggregated on-the-fly every time.
    
    **Business Value:**
    - Identify coaching opportunities (underperformers)
    - Recognize and reward top performers
    - Optimize territory assignments
    - Proactive intervention for critical issues
    - Data-driven strategic planning
    """
)
async def get_sfe_dashboard(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2030, description="Year (e.g., 2026)"),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    
    result = await service.get_sfe_dashboard(
        month=month,
        year=year,
        current_user=current_user
    )
    
    return result


@router.get(
    "/dashboard/mr/{mr_id}",
    response_model=schemas.MRDrillDownResponse,
    status_code=status.HTTP_200_OK,
    summary="Get MR Drill-Down (Admin Only)",
    description="""
    **Purpose:** Get detailed performance analysis for a specific MR including historical trends.
    
    **Required Role:** Admin only
    
    **Use Case:**
    - Deep-dive into individual MR performance
    - Analyze performance trends over time
    - Identify specific areas for improvement
    - Prepare for coaching sessions
    - Performance reviews
    
    **Example Request:**
    ```
    GET /api/v1/sfe/dashboard/mr/507f1f77bcf86cd799439013?month=5&year=2026
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Example Response:**
    ```json
    {
      "mr_id": "507f1f77bcf86cd799439013",
      "mr_name": "Rajesh Kumar",
      "territory": "Visakhapatnam",
      "zone": "South",
      "state": "Andhra Pradesh",
      "month": 5,
      "year": 2026,
      "mcr_data": {
        "mcr_percentage": 84.0,
        "total_assigned": 50,
        "doctors_visited": 42,
        "doctors_not_visited": 8
      },
      "mvc_data": {
        "mvc_percentage": 72.0,
        "avg_compliance": 85.5,
        "fully_covered": 36,
        "under_covered": 10,
        "not_visited": 4
      },
      "rcpa_summary": {
        "total_commitments": 25,
        "rx_per_month": 180
      },
      "performance_trend": [
        {"month": 12, "year": 2025, "mcr": 80.0, "mvc": 70.0, "avg_compliance": 82.0},
        {"month": 1, "year": 2026, "mcr": 82.0, "mvc": 71.0, "avg_compliance": 83.0},
        {"month": 2, "year": 2026, "mcr": 83.0, "mvc": 72.0, "avg_compliance": 84.0},
        {"month": 3, "year": 2026, "mcr": 84.0, "mvc": 72.0, "avg_compliance": 85.0},
        {"month": 4, "year": 2026, "mcr": 83.0, "mvc": 71.0, "avg_compliance": 84.5},
        {"month": 5, "year": 2026, "mcr": 84.0, "mvc": 72.0, "avg_compliance": 85.5}
      ]
    }
    ```
    
    **What It Tells You:**
    - **Current Month Performance**: Detailed MCR, MVC, RCPA metrics
    - **Performance Trend**: Last 6 months of MCR/MVC data
    - **Trend Analysis**: Identify improving, stable, or declining performance
    - **Territory Context**: Zone, state, territory information
    
    **What Happens:**
    1. Validates MR exists in `mrs` collection
    2. Calculates current month MCR from `visits` + `mrs` + `doctors`
    3. Calculates current month MVC from `visits` + `mrs` + `doctors` + `sfe_settings`
    4. Fetches RCPA commitments count from `prescription_commitments`
    5. Loops back 6 months and calculates MCR/MVC for each month (trend)
    6. Returns comprehensive drill-down
    
    **Not stored in DB** — all metrics calculated on-the-fly every time.
    
    **Use Cases:**
    - **Improving Trend**: Recognize and reward
    - **Stable High Performance**: Maintain and replicate
    - **Declining Trend**: Investigate and intervene
    - **Stable Low Performance**: Coaching or reassignment
    
    **Business Value:**
    - Data-driven coaching conversations
    - Identify root causes of performance issues
    - Recognize improvement efforts
    - Make informed territory/assignment decisions
    """
)
async def get_mr_drilldown(
    mr_id: str,
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2030, description="Year (e.g., 2026)"),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    
    result = await service.get_mr_drilldown(
        mr_id=mr_id,
        month=month,
        year=year,
        current_user=current_user
    )
    
    return result



# ============================================================================
# SFE SETTINGS (VISIT TARGETS)
# ============================================================================

@router.get(
    "/settings",
    response_model=schemas.ClassificationTargetsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get SFE Settings (Visit Targets)",
    description="""
    **Purpose:** Retrieve SFE visit target settings for doctor classifications.
    
    **Access:** All authenticated users (Admin, MR, Doctor)
    
    **Use Case:**
    - MR checks required visit frequency for each doctor class
    - System uses these targets for MVC (Monthly Visit Coverage) calculations
    - Admin reviews current visit standards
    - Frontend displays visit targets in UI
    
    **Example Request:**
    ```
    GET /api/v1/sfe/settings
    Headers: Authorization: Bearer <token>
    ```
    
    **Example Response:**
    ```json
    {
      "classification_targets": {
        "A": 4,
        "B": 3,
        "C": 2
      },
      "updated_at": "2026-05-20T12:00:00",
      "updated_by": {
        "name": "vamsi vakada"
      }
    }
    ```
    
    **Default Values:**
    If no settings exist in database, returns:
    ```json
    {
      "classification_targets": {
        "A": 2,
        "B": 1,
        "C": 1
      }
    }
    ```
    
    **What It Tells You:**
    - A-class doctors need X visits/month
    - B-class doctors need Y visits/month
    - C-class doctors need Z visits/month
    - When settings were last updated and by whom
    
    **What Happens:**
    1. Reads single document from `sfe_settings` collection (`company_id: "default"`)
    2. If no document exists, returns defaults (A=2, B=1, C=1)
    3. Returns visit targets with metadata (updated_at, updated_by)
    
    **Stored in DB:** `sfe_settings` collection (single document per company).
    **Note:** This is a single company-wide setting, not per-user or per-doctor.
    """
)
async def get_sfe_settings(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    result = await service.get_sfe_settings()
    return result


@router.put(
    "/settings",
    response_model=schemas.MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Update SFE Settings (Visit Targets)",
    description="""
    **Purpose:** Update SFE visit target requirements for each doctor classification.
    
    **Access:** Admin only
    
    **Use Case:**
    - Admin adjusts visit frequency standards based on company strategy
    - Change targets when market conditions change
    - Align visit frequency with business goals
    
    **Example Request:**
    ```json
    PUT /api/v1/sfe/settings
    Headers: Authorization: Bearer <admin_token>
    Body:
    {
      "classification_targets": {
        "A": 4,
        "B": 3,
        "C": 2
      }
    }
    ```
    
    **Example Response:**
    ```json
    {
      "message": "Settings updated successfully",
      "classification_targets": {
        "A": 4,
        "B": 3,
        "C": 2
      }
    }
    ```
    
    **Validation:**
    - All three keys (A, B, C) must be present
    - Values must be integers between 1 and 30
    - Typically A ≥ B ≥ C (but not enforced)
    
    **What Happens:**
    1. Validates all three classifications (A, B, C) are present and valid
    2. Upserts single document in `sfe_settings` collection (`company_id: "default"`)
    3. Records timestamp and admin name for audit trail
    4. All future MVC calculations immediately use new targets
    5. Existing doctor classifications remain unchanged (only frequency changes)
    
    **Stored in DB:** `sfe_settings` collection.
    
    **Impact:**
    - **MVC Calculations**: Immediately use new targets
    - **MR Targets**: MRs see updated visit requirements
    - **Historical Data**: Past compliance metrics unchanged
    - **Doctor Assignments**: Classifications stay same, only frequency changes
    
    **Example Scenario:**
    - Current: A=2, B=1, C=1
    - Admin changes to: A=4, B=3, C=2
    - Result: All A-class doctors now need 4 visits/month instead of 2
    - MVC % will likely drop initially as MRs adjust to new targets
    
    **Business Value:**
    - Flexible visit frequency without code changes
    - Align field force activity with business priorities
    - Respond quickly to market changes
    - No deployment needed to change targets
    """
)
async def update_sfe_settings(
    request_data: schemas.ClassificationTargetsUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    logger.info(f"Admin {current_user['_id']} updating SFE settings")
    
    result = await service.update_sfe_settings(
        classification_targets=request_data.classification_targets,
        current_user=current_user
    )
    
    return result
