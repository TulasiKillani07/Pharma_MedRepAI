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
# DOCTOR CLASSIFICATION
# ============================================================================

@router.put(
    "/doctors/{doctor_id}/classify",
    response_model=schemas.MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Classify Doctor",
    description="""
    **Purpose:** Set doctor classification (A/B/C) which determines required visit frequency for SFE tracking.
    
    **Classification Guide:**
    - **A-class**: High prescriber, opinion leader (4 visits/month by default)
    - **B-class**: Medium prescriber, growing practice (2 visits/month by default)
    - **C-class**: Low prescriber, new/unknown (1 visit/month by default)
    
    **Required Role:** Admin only
    
    **Use Case:** Admin classifies doctors based on prescription potential to optimize MR visit planning.
    
    **Example Request:**
    ```json
    PUT /api/v1/sfe/doctors/507f1f77bcf86cd799439011/classify
    Headers: Authorization: Bearer <admin_token>
    Body:
    {
      "classification": "A"
    }
    ```
    
    **Example Response:**
    ```json
    {
      "message": "Doctor classified as A-class successfully"
    }
    ```
    
    **What Happens:**
    1. Doctor is assigned to specified class (A/B/C)
    2. Visit frequency is set based on SFE config (e.g., A=4 visits/month)
    3. Record is created/updated in doctor_assignments collection
    4. MVC calculations will use this to track visit compliance
    """
)
async def classify_doctor(
    doctor_id: str,
    request_data: schemas.DoctorClassifyRequest,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    logger.info(f"Admin {current_user['_id']} classifying doctor {doctor_id} as {request_data.classification}")
    
    result = await service.classify_doctor(
        doctor_id=doctor_id,
        classification=request_data.classification,
        current_user=current_user
    )
    
    return {"message": result["message"]}


@router.get(
    "/doctors/{doctor_id}/classification",
    response_model=schemas.DoctorClassificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Doctor Classification",
    description="""
    **Purpose:** Retrieve doctor's classification details including class, required visit frequency, and assignment info.
    
    **Required Role:** MR (own assigned doctors), Admin (all doctors)
    
    **Use Case:** 
    - MR checks how many times they should visit a specific doctor
    - Admin reviews doctor classifications
    
    **Example Request:**
    ```
    GET /api/v1/sfe/doctors/507f1f77bcf86cd799439011/classification
    Headers: Authorization: Bearer <token>
    ```
    
    **Example Response:**
    ```json
    {
      "doctor_id": "507f1f77bcf86cd799439011",
      "doctor_name": "Dr. Arjun Sharma",
      "mr_id": "507f1f77bcf86cd799439012",
      "mr_name": "Rajesh Kumar",
      "classification": "A",
      "visit_frequency": 4,
      "territory": "Visakhapatnam",
      "zone": "South",
      "state": "Andhra Pradesh",
      "assigned_at": "2026-05-01T10:00:00Z",
      "updated_at": "2026-05-19T15:30:00Z"
    }
    ```
    
    **What It Tells You:**
    - Doctor's class (A/B/C)
    - Required visits per month (from SFE config)
    - Which MR is assigned
    - Territory/zone/state information
    """
)
async def get_doctor_classification(
    doctor_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    logger.info(f"User {current_user['_id']} fetching classification for doctor {doctor_id}")
    
    result = await service.get_doctor_classification(
        doctor_id=doctor_id,
        current_user=current_user
    )
    
    return result


# ============================================================================
# SFE CONFIGURATION
# ============================================================================

@router.get(
    "/config",
    response_model=schemas.SFEConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Get SFE Configuration",
    description="""
    **Purpose:** Retrieve system-wide SFE configuration that defines required visit frequency for each doctor class.
    
    **Configuration Meaning:**
    - **A**: Required visits per month for A-class doctors (high prescribers)
    - **B**: Required visits per month for B-class doctors (medium prescribers)
    - **C**: Required visits per month for C-class doctors (low prescribers)
    
    **Required Role:** All authenticated users (MR, Admin, Doctor)
    
    **Use Case:** 
    - MR checks how many times they should visit doctors of each class
    - System uses this for MVC (Monthly Visit Coverage) calculations
    - Admin reviews current visit frequency standards
    
    **Example Request:**
    ```
    GET /api/v1/sfe/config
    Headers: Authorization: Bearer <token>
    ```
    
    **Example Response:**
    ```json
    {
      "A": 4,
      "B": 2,
      "C": 1,
      "updated_at": "2026-05-01T10:00:00Z",
      "updated_by": "Admin Name"
    }
    ```
    
    **What It Tells You:**
    - A-class doctors need 4 visits/month
    - B-class doctors need 2 visits/month
    - C-class doctors need 1 visit/month
    - When config was last updated and by whom
    
    **What Happens:**
    1. System retrieves current SFE configuration from database
    2. Returns visit frequency requirements for all classes
    3. If no config exists, returns default values (A=4, B=2, C=1)
    """
)
async def get_sfe_config(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    logger.info(f"User {current_user['_id']} fetching SFE config")
    
    config = await service.get_sfe_config()
    
    return config


@router.put(
    "/config",
    response_model=schemas.MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Update SFE Configuration",
    description="""
    **Purpose:** Update system-wide visit frequency requirements for each doctor class (A/B/C).
    
    **Required Role:** Admin only
    
    **Use Case:** Admin adjusts visit frequency standards based on company strategy or market conditions.
    
    **Example Request:**
    ```json
    PUT /api/v1/sfe/config
    Headers: Authorization: Bearer <admin_token>
    Body:
    {
      "A": 4,
      "B": 3,
      "C": 1
    }
    ```
    
    **Example Response:**
    ```json
    {
      "message": "SFE configuration updated successfully"
    }
    ```
    
    **What Happens:**
    1. System validates that all three classes (A, B, C) have positive integer values
    2. Configuration is updated in sfe_config collection
    3. Timestamp and admin info are recorded
    4. All future MVC calculations will use new frequency requirements
    5. Existing doctor classifications remain unchanged (only frequency requirements change)
    
    **Impact:**
    - MVC (Monthly Visit Coverage) calculations will use new frequencies
    - MRs will see updated visit targets for each doctor class
    - Does NOT retroactively change past compliance metrics
    
    **Validation:**
    - All values must be positive integers (1-31)
    - Typically: A ≥ B ≥ C (but not enforced)
    """
)
async def update_sfe_config(
    request_data: schemas.SFEConfigUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    logger.info(f"Admin {current_user['_id']} updating SFE config")
    
    config_data = {
        "A": request_data.A,
        "B": request_data.B,
        "C": request_data.C
    }
    
    result = await service.update_sfe_config(
        config_data=config_data,
        current_user=current_user
    )
    
    return {"message": result["message"]}


# ============================================================================
# MCR (MONTHLY CALL REPORT)
# ============================================================================

@router.get(
    "/mcr",
    response_model=schemas.MCRResponse,
    status_code=status.HTTP_200_OK,
    summary="Get MCR (Monthly Call Report)",
    description="""
    **Purpose:** Calculate Monthly Call Report - measures what percentage of assigned doctors were visited at least once in a given month.
    
    **Formula:** MCR % = (Unique doctors with ≥1 completed visit this month / Total assigned doctors) × 100
    
    **Required Role:** 
    - MR: Can view own MCR data (no mr_id parameter needed)
    - Admin: Can view any MR's MCR data (provide mr_id parameter)
    
    **Use Case:**
    - MR checks their monthly doctor coverage performance
    - Admin monitors MR performance and identifies underperformers
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
      "total_assigned": 50,
      "doctors_visited": 42,
      "doctors_not_visited": 8,
      "mcr_percentage": 84.0,
      "visited": [
        {
          "doctor_id": "507f1f77bcf86cd799439011",
          "doctor_name": "Dr. Arjun Sharma",
          "classification": "A",
          "visits_count": 3,
          "last_visit_date": "2026-05-15T14:30:00"
        }
      ],
      "not_visited": [
        {
          "doctor_id": "507f1f77bcf86cd799439012",
          "doctor_name": "Dr. Priya Reddy",
          "classification": "B",
          "last_visited": "2026-04-20T10:15:00"
        }
      ]
    }
    ```
    
    **What It Tells You:**
    - Overall coverage percentage (MCR %)
    - How many doctors were visited vs not visited
    - Detailed list of visited doctors with visit counts
    - List of missed doctors with their last visit date
    - Doctor classifications for prioritization
    
    **What Happens:**
    1. System retrieves all doctors assigned to the MR
    2. Queries all completed visits for the specified month
    3. Counts unique doctors visited
    4. Calculates MCR percentage
    5. Returns detailed breakdown with doctor lists
    
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
    logger.info(f"User {current_user['_id']} requesting MCR for month={month}, year={year}, mr_id={mr_id}")
    
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
    1. System retrieves all doctors assigned to the MR with their classifications
    2. Gets required visit frequency from doctor_assignments (based on SFE config)
    3. Counts actual completed visits per doctor for the month
    4. Calculates compliance percentage for each doctor
    5. Categorizes doctors as covered/under/missed
    6. Calculates overall MVC % and average compliance
    7. Returns sorted list (covered first, then under, then missed)
    
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
    logger.info(f"User {current_user['_id']} requesting MVC for month={month}, year={year}, mr_id={mr_id}")
    
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
    **Purpose:** Manually log a prescription commitment from a doctor (usually done during visit completion).
    
    **Required Role:** MR only
    
    **Use Case:** 
    - MR logs doctor's commitment to prescribe company's product
    - Creates demand forecast for inventory planning
    - Tracks doctor engagement and prescription potential
    
    **Example Request:**
    ```json
    POST /api/v1/sfe/rcpa
    Headers: Authorization: Bearer <mr_token>
    Body:
    {
      "doctor_id": "507f1f77bcf86cd799439011",
      "product_id": "507f1f77bcf86cd799439021",
      "rx_per_week": 15,
      "confidence": "high",
      "visit_id": "507f1f77bcf86cd799439031"
    }
    ```
    
    **Example Response:**
    ```json
    {
      "id": "507f1f77bcf86cd799439041",
      "mr_id": "507f1f77bcf86cd799439013",
      "mr_name": "Rajesh Kumar",
      "doctor_id": "507f1f77bcf86cd799439011",
      "doctor_name": "Dr. Arjun Sharma",
      "product_id": "507f1f77bcf86cd799439021",
      "product_name": "Amlovas 5mg",
      "rx_per_week": 15,
      "confidence": "high",
      "status": "active",
      "visit_id": "507f1f77bcf86cd799439031",
      "territory": "Visakhapatnam",
      "created_at": "2026-05-19T16:20:00"
    }
    ```
    
    **What Happens:**
    1. System validates doctor and product exist
    2. Creates commitment record with MR and territory info
    3. Status is set to "active" by default
    4. Commitment is included in demand forecast calculations
    
    **Note:** Commitments are also auto-created during visit completion when MR logs rx_commitment field.
    """
)
async def create_rcpa_commitment(
    request_data: schemas.RCPACreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    # Only MR can create commitments
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
    - Admin: Can view all commitments or filter by MR
    
    **Use Case:**
    - MR reviews their logged commitments
    - Admin monitors commitments across all MRs
    - Filter by month/year to see recent commitments
    - Filter by product to see demand for specific drug
    
    **Example Request (MR - own commitments):**
    ```
    GET /api/v1/sfe/rcpa?month=5&year=2026
    Headers: Authorization: Bearer <mr_token>
    ```
    
    **Example Request (Admin - specific MR):**
    ```
    GET /api/v1/sfe/rcpa?month=5&year=2026&mr_id=507f1f77bcf86cd799439013
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Example Request (Filter by product):**
    ```
    GET /api/v1/sfe/rcpa?product_id=507f1f77bcf86cd799439021&status=active
    Headers: Authorization: Bearer <token>
    ```
    
    **Example Response:**
    ```json
    {
      "total": 25,
      "commitments": [
        {
          "id": "507f1f77bcf86cd799439041",
          "mr_id": "507f1f77bcf86cd799439013",
          "mr_name": "Rajesh Kumar",
          "doctor_id": "507f1f77bcf86cd799439011",
          "doctor_name": "Dr. Arjun Sharma",
          "product_id": "507f1f77bcf86cd799439021",
          "product_name": "Amlovas 5mg",
          "rx_per_week": 15,
          "confidence": "high",
          "status": "active",
          "territory": "Visakhapatnam",
          "created_at": "2026-05-18T14:30:00"
        }
      ]
    }
    ```
    
    **Query Parameters:**
    - `month`: Filter by month (1-12)
    - `year`: Filter by year
    - `mr_id`: Filter by MR (admin only)
    - `product_id`: Filter by product
    - `status`: Filter by status (active, fulfilled, cancelled)
    
    **What It Tells You:**
    - All commitments matching filters
    - Doctor and product details
    - Expected prescription volume per week
    - Confidence level and status
    """
)
async def get_rcpa_commitments(
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    year: Optional[int] = Query(None, ge=2020, le=2030, description="Year"),
    mr_id: Optional[str] = Query(None, description="MR ID (admin only)"),
    product_id: Optional[str] = Query(None, description="Product ID"),
    status: Optional[str] = Query(None, description="Status filter"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    logger.info(f"User {current_user['_id']} fetching RCPA commitments")
    
    result = await service.get_rcpa_commitments(
        month=month,
        year=year,
        mr_id=mr_id,
        product_id=product_id,
        status_filter=status,
        current_user=current_user
    )
    
    return result


@router.put(
    "/rcpa/{commitment_id}",
    response_model=schemas.MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Update RCPA Commitment",
    description="""
    **Purpose:** Update an existing prescription commitment (e.g., doctor increased/decreased commitment).
    
    **Required Role:**
    - MR: Can update own commitments
    - Admin: Can update any commitment
    
    **Use Case:**
    - Doctor increases prescription commitment
    - Doctor reduces commitment due to stock issues
    - Mark commitment as fulfilled or cancelled
    - Update confidence level based on follow-up
    
    **Example Request:**
    ```json
    PUT /api/v1/sfe/rcpa/507f1f77bcf86cd799439041
    Headers: Authorization: Bearer <mr_token>
    Body:
    {
      "rx_per_week": 20,
      "confidence": "high"
    }
    ```
    
    **Example Response:**
    ```json
    {
      "message": "Commitment updated successfully"
    }
    ```
    
    **Updatable Fields:**
    - `rx_per_week`: New prescription volume
    - `confidence`: Updated confidence level (high/medium/low)
    - `status`: Change status (active/fulfilled/cancelled)
    
    **What Happens:**
    1. System validates commitment exists
    2. Checks authorization (MR owns it or user is admin)
    3. Updates specified fields
    4. Records update timestamp
    5. New values are reflected in demand forecast
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
    
    **Use Case:**
    - Company forecasts product demand
    - Inventory planning based on prescription commitments
    - Territory-wise demand analysis
    - Product-wise prescription potential
    
    **Example Request:**
    ```
    GET /api/v1/sfe/rcpa/summary?month=5&year=2026
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Example Response:**
    ```json
    {
      "total_rx_per_week": 1200,
      "total_commitments": 85,
      "total_doctors": 65,
      "total_products": 8,
      "by_product": [
        {
          "product_id": "507f1f77bcf86cd799439021",
          "product_name": "Amlovas 5mg",
          "rx_per_week": 450,
          "doctors_count": 25
        },
        {
          "product_id": "507f1f77bcf86cd799439022",
          "product_name": "Metformin 500mg",
          "rx_per_week": 350,
          "doctors_count": 20
        }
      ],
      "by_territory": [
        {
          "territory": "Visakhapatnam",
          "rx_per_week": 350,
          "doctors_count": 20,
          "products_count": 6
        },
        {
          "territory": "Hyderabad",
          "rx_per_week": 500,
          "doctors_count": 30,
          "products_count": 7
        }
      ]
    }
    ```
    
    **What It Tells You:**
    - **Total Demand**: Expected prescriptions per week across all products
    - **By Product**: Which products have highest demand
    - **By Territory**: Which territories need more inventory
    - **Doctor Engagement**: How many doctors are committing to prescribe
    
    **What Happens:**
    1. System aggregates all active commitments
    2. Groups by product (sorted by demand)
    3. Groups by territory (sorted by demand)
    4. Calculates totals and unique counts
    5. Returns demand forecast for inventory planning
    
    **Business Value:**
    - Prevents stockouts in high-demand territories
    - Optimizes inventory distribution
    - Identifies top-performing products
    - Validates MR effectiveness (commitments vs actual prescriptions)
    """
)
async def get_rcpa_summary(
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    year: Optional[int] = Query(None, ge=2020, le=2030, description="Year"),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    logger.info(f"Admin {current_user['_id']} fetching RCPA summary")
    
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
      "total_rx_per_week": 3500,
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
          "rx_per_week": 250
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
          "rx_per_week": 50
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
          "rx_per_week": 1200
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
    1. System fetches all MRs in the company
    2. Calculates MCR, MVC, and RCPA for each MR
    3. Aggregates company-wide metrics
    4. Generates leaderboard (top 10 by avg performance)
    5. Identifies underperformers (below thresholds)
    6. Groups by territory with averages
    7. Creates alerts for critical issues
    8. Returns comprehensive dashboard
    
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
    logger.info(f"Admin {current_user['_id']} fetching SFE dashboard for {month}/{year}")
    
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
        "rx_per_week": 180
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
    1. System validates MR exists
    2. Fetches current month MCR, MVC, RCPA data
    3. Retrieves historical data for last 6 months
    4. Calculates trend (improving/declining)
    5. Returns comprehensive drill-down
    
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
    logger.info(f"Admin {current_user['_id']} fetching drill-down for MR {mr_id} ({month}/{year})")
    
    result = await service.get_mr_drilldown(
        mr_id=mr_id,
        month=month,
        year=year,
        current_user=current_user
    )
    
    return result



# ============================================================================
# CHEMIST CHECK
# ============================================================================

@router.post(
    "/chemist-check",
    response_model=schemas.ChemistCheckResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Chemist Check",
    description="""
    **Purpose:** Log chemist/pharmacy stock observation to validate RCPA commitments and identify supply chain issues.
    
    **Required Role:** MR only
    
    **Use Case:**
    - MR visits chemist near doctor's clinic
    - Checks if company's products are in stock
    - Records stock levels and sales
    - Validates that doctor prescriptions are being filled
    - Identifies stockout risks
    
    **Example Request:**
    ```json
    POST /api/v1/sfe/chemist-check
    Headers: Authorization: Bearer <mr_token>
    Body:
    {
      "chemist_name": "Apollo Pharmacy",
      "chemist_location": "Near Dr. Arjun's clinic, MG Road",
      "product_id": "507f1f77bcf86cd799439021",
      "stock_available": 30,
      "sold_this_week": 20,
      "notes": "High demand, restock needed soon",
      "gps_lat": 17.3850,
      "gps_lng": 78.4867
    }
    ```
    
    **Example Response:**
    ```json
    {
      "id": "507f1f77bcf86cd799439051",
      "mr_id": "507f1f77bcf86cd799439013",
      "mr_name": "Rajesh Kumar",
      "chemist_name": "Apollo Pharmacy",
      "chemist_location": "Near Dr. Arjun's clinic, MG Road",
      "product_id": "507f1f77bcf86cd799439021",
      "product_name": "Amlovas 5mg",
      "stock_available": 30,
      "sold_this_week": 20,
      "notes": "High demand, restock needed soon",
      "territory": "Visakhapatnam",
      "date": "2026-05-19T00:00:00",
      "created_at": "2026-05-19T16:30:00"
    }
    ```
    
    **What Happens:**
    1. System validates product exists
    2. Creates chemist check record with MR and territory info
    3. Records stock and sales data
    4. Data is used for supply chain analysis
    
    **Business Value:**
    - Validates RCPA commitments (are doctors actually prescribing?)
    - Identifies stockout risks before they happen
    - Optimizes inventory distribution
    - Measures product availability at point of sale
    """
)
async def create_chemist_check(
    request_data: schemas.ChemistCheckCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    # Only MR can create checks
    if current_user.get("role") != "MR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MRs can create chemist checks"
        )
    
    logger.info(f"MR {current_user['_id']} creating chemist check")
    
    result = await service.create_chemist_check(
        check_data=request_data.model_dump(),
        current_user=current_user
    )
    
    return result


@router.get(
    "/chemist-check",
    response_model=schemas.ChemistCheckListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Chemist Checks",
    description="""
    **Purpose:** Retrieve chemist check observations with optional filters.
    
    **Required Role:**
    - MR: Can view own checks
    - Admin: Can view all checks or filter by MR
    
    **Use Case:**
    - MR reviews their chemist observations
    - Admin monitors product availability across territories
    - Filter by month/year to see recent checks
    - Filter by product to see specific drug availability
    - Filter by territory for regional analysis
    
    **Example Request (MR - own checks):**
    ```
    GET /api/v1/sfe/chemist-check?month=5&year=2026
    Headers: Authorization: Bearer <mr_token>
    ```
    
    **Example Request (Admin - specific MR):**
    ```
    GET /api/v1/sfe/chemist-check?month=5&year=2026&mr_id=507f1f77bcf86cd799439013
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Example Request (Filter by product and territory):**
    ```
    GET /api/v1/sfe/chemist-check?product_id=507f1f77bcf86cd799439021&territory=Visakhapatnam
    Headers: Authorization: Bearer <token>
    ```
    
    **Example Response:**
    ```json
    {
      "total": 15,
      "checks": [
        {
          "id": "507f1f77bcf86cd799439051",
          "mr_id": "507f1f77bcf86cd799439013",
          "mr_name": "Rajesh Kumar",
          "chemist_name": "Apollo Pharmacy",
          "chemist_location": "Near Dr. Arjun's clinic",
          "product_id": "507f1f77bcf86cd799439021",
          "product_name": "Amlovas 5mg",
          "stock_available": 30,
          "sold_this_week": 20,
          "territory": "Visakhapatnam",
          "date": "2026-05-19T00:00:00",
          "created_at": "2026-05-19T16:30:00"
        }
      ]
    }
    ```
    
    **Query Parameters:**
    - `month`: Filter by month (1-12)
    - `year`: Filter by year
    - `mr_id`: Filter by MR (admin only)
    - `product_id`: Filter by product
    - `territory`: Filter by territory
    
    **What It Tells You:**
    - All chemist observations matching filters
    - Stock levels at each chemist
    - Sales velocity (sold this week)
    - Geographic distribution
    """
)
async def get_chemist_checks(
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    year: Optional[int] = Query(None, ge=2020, le=2030, description="Year"),
    mr_id: Optional[str] = Query(None, description="MR ID (admin only)"),
    product_id: Optional[str] = Query(None, description="Product ID"),
    territory: Optional[str] = Query(None, description="Territory"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    logger.info(f"User {current_user['_id']} fetching chemist checks")
    
    result = await service.get_chemist_checks(
        month=month,
        year=year,
        mr_id=mr_id,
        product_id=product_id,
        territory=territory,
        current_user=current_user
    )
    
    return result


@router.get(
    "/chemist-check/summary",
    response_model=schemas.ChemistCheckSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Chemist Check Summary (Admin Only)",
    description="""
    **Purpose:** Get aggregated chemist check data for supply chain analysis and inventory planning.
    
    **Required Role:** Admin only
    
    **Use Case:**
    - Company monitors product availability at retail level
    - Identifies stockout risks before they impact sales
    - Validates RCPA commitments (prescriptions → sales)
    - Optimizes inventory distribution by territory
    - Measures product velocity (sales rate)
    
    **Example Request:**
    ```
    GET /api/v1/sfe/chemist-check/summary?month=5&year=2026
    Headers: Authorization: Bearer <admin_token>
    ```
    
    **Example Response:**
    ```json
    {
      "total_checks": 85,
      "total_chemists": 45,
      "total_stock": 2500,
      "total_sold_this_week": 1800,
      "by_product": [
        {
          "product_id": "507f1f77bcf86cd799439021",
          "product_name": "Amlovas 5mg",
          "total_stock": 450,
          "total_sold_this_week": 280,
          "chemists_count": 15,
          "avg_stock_per_chemist": 30.0
        }
      ],
      "by_territory": [
        {
          "territory": "Visakhapatnam",
          "total_stock": 600,
          "total_sold": 350,
          "chemists_count": 20,
          "products_count": 8
        }
      ],
      "low_stock_alerts": [
        {
          "chemist_name": "Apollo Pharmacy",
          "product_name": "Amlovas 5mg",
          "stock_available": 5,
          "territory": "Visakhapatnam",
          "mr_name": "Rajesh Kumar"
        }
      ]
    }
    ```
    
    **What It Tells You:**
    - **Total Metrics**: Checks, chemists, stock, sales
    - **By Product**: Which products are selling fast, stock levels
    - **By Territory**: Regional stock distribution and sales
    - **Low Stock Alerts**: Chemists with stock < 10 units (urgent restock)
    
    **What Happens:**
    1. System aggregates all chemist checks
    2. Groups by product (sorted by sales)
    3. Groups by territory (sorted by sales)
    4. Identifies low stock situations (< 10 units)
    5. Returns supply chain intelligence
    
    **Business Value:**
    - **Prevent Stockouts**: Proactive alerts for low stock
    - **Validate RCPA**: Compare commitments vs actual sales
    - **Optimize Distribution**: Send stock where it's selling
    - **Measure Velocity**: Identify fast-moving products
    - **Territory Planning**: Understand regional demand patterns
    
    **RCPA Validation Example:**
    - RCPA: Dr. Arjun committed to 15 rx/week of Amlovas
    - Chemist Check: Nearby chemist sold 20 units this week
    - Insight: ✓ Commitment is being fulfilled (or exceeded)
    """
)
async def get_chemist_check_summary(
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    year: Optional[int] = Query(None, ge=2020, le=2030, description="Year"),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    logger.info(f"Admin {current_user['_id']} fetching chemist check summary")
    
    result = await service.get_chemist_check_summary(
        month=month,
        year=year,
        current_user=current_user
    )
    
    return result
