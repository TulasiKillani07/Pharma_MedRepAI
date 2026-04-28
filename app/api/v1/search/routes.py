"""
Search API Endpoints
Intelligent search using NER (Named Entity Recognition)
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict
import logging

from app.core.auth import get_current_user
from app.api.v1.search.schemas import DrugSearchRequest, DrugSearchResponse
from app.api.v1.search import service
from app.api.v1.search.ner_service import extract_medical_entities


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/drugs", response_model=DrugSearchResponse)
async def search_drugs_endpoint(
    search_request: DrugSearchRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Intelligent drug search using natural language query.
    
    **How it works:**
    1. User enters natural language query (e.g., "I have fever and headache")
    2. NER model extracts entities: symptoms, indications, severity, duration
    3. Backend searches drugs matching extracted entities
    4. Results are scored and ranked by relevance
    
    **Scoring Logic:**
    - Indications (diseases) are weighted 2x (more important)
    - Symptoms are weighted 1x
    - Drugs matching more entities rank higher
    
    **Example Query:**
    ```json
    {
        "query": "I have fever, headache and diabetes",
        "skip": 0,
        "limit": 20
    }
    ```
    
    **Example Response:**
    ```json
    {
        "query": "I have fever, headache and diabetes",
        "entities_extracted": {
            "symptoms": ["fever", "headache"],
            "indications": ["diabetes"],
            "severity": [],
            "duration": []
        },
        "results": [
            {
                "_id": "drug123",
                "drug_name": "metformin",
                "brand_name": "glucophage",
                "symptoms": [],
                "indications": ["diabetes", "type 2 diabetes"],
                "match_score": 100.0,
                "matched_entities": {
                    "symptoms": [],
                    "indications": ["diabetes"]
                }
            },
            {
                "_id": "drug456",
                "drug_name": "paracetamol",
                "brand_name": "crocin",
                "symptoms": ["fever", "headache", "pain"],
                "indications": [],
                "match_score": 66.67,
                "matched_entities": {
                    "symptoms": ["fever", "headache"],
                    "indications": []
                }
            }
        ],
        "total_results": 15
    }
    ```
    
    **Use Cases:**
    - Doctor: Quick drug search by symptoms/conditions
    - MR: Find relevant drugs for doctor's patient case
    - Smart drug recommendations based on patient complaints
    
    **Access:** All authenticated users (Admin, Doctor, MR)
    """
    try:
        # Step 1: Extract entities using NER
        entities = await extract_medical_entities(search_request.query)
        
        # Step 2: Search drugs using extracted entities
        search_results = await service.search_drugs_by_entities(
            symptoms=entities.get("symptoms", []),
            indications=entities.get("indications", []),
            skip=search_request.skip,
            limit=search_request.limit
        )
        
        # Step 3: Build response
        return {
            "query": search_request.query,
            "entities_extracted": {
                "symptoms": entities.get("symptoms", []),
                "indications": entities.get("indications", []),
                "severity": entities.get("severity", []),
                "duration": entities.get("duration", [])
            },
            "results": search_results["results"],
            "total_results": search_results["total"]
        }
        
    except Exception as e:
        # Log error and return user-friendly message
        logger.error(f"Drug search error: {str(e)}")
        
        raise HTTPException(
            status_code=500,
            detail=f"Drug search failed: {str(e)}"
        )
