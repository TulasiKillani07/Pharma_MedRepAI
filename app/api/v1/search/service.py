"""
Search Business Logic
Handles intelligent search across different entities using NER.
"""

from typing import Dict, List, Any
from app.database import get_database


async def search_drugs_by_entities(
    symptoms: List[str],
    indications: List[str],
    skip: int = 0,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search drugs using extracted entities with weighted scoring.
    
    Scoring Logic:
    - Indications (diseases) are weighted 2x (more important)
    - Symptoms are weighted 1x (surface-level complaints)
    
    Args:
        symptoms: List of symptom terms from NER
        indications: List of indication/disease terms from NER
        skip: Number of results to skip (pagination)
        limit: Maximum number of results to return
        
    Returns:
        Dictionary with results and total count:
        {
            "results": [...],  # List of drugs with match scores
            "total": 15        # Total matching drugs
        }
    """
    db = get_database()
    
    # If no entities provided, return empty
    if not symptoms and not indications:
        return {"results": [], "total": 0}
    
    # Build MongoDB query - find drugs matching ANY entity
    query: Dict[str, Any] = {"is_active": True}
    
    or_conditions = []
    if symptoms:
        or_conditions.append({"symptoms": {"$in": symptoms}})
    if indications:
        or_conditions.append({"indications": {"$in": indications}})
    
    if len(or_conditions) == 1:
        query.update(or_conditions[0])
    else:
        query["$or"] = or_conditions
    
    # Fetch all matching drugs (single DB query)
    drugs = await db["drugs"].find(query).to_list(None)
    
    # Calculate weighted score for each drug
    # Indications are weighted 2x (more important than symptoms)
    indication_weight = 2
    symptom_weight = 1
    total_possible_score = (len(indications) * indication_weight) + (len(symptoms) * symptom_weight)
    
    scored_drugs = []
    for drug in drugs:
        drug_symptoms = set(drug.get("symptoms", []))
        drug_indications = set(drug.get("indications", []))
        
        # Find matches
        matched_symptoms = [s for s in symptoms if s in drug_symptoms]
        matched_indications = [i for i in indications if i in drug_indications]
        
        # Calculate weighted score
        indication_score = len(matched_indications) * indication_weight
        symptom_score = len(matched_symptoms) * symptom_weight
        total_score = indication_score + symptom_score
        
        # Convert to percentage (0-100)
        if total_possible_score > 0:
            match_score = (total_score / total_possible_score) * 100
        else:
            match_score = 0
        
        # Build result object
        scored_drugs.append({
            "_id": str(drug["_id"]),
            "drug_name": drug.get("drug_name", ""),
            "brand_name": drug.get("brand_name"),
            "manufacturer": drug.get("manufacturer"),
            "symptoms": drug.get("symptoms", []),
            "indications": drug.get("indications", []),
            "dosage_form": drug.get("dosage_form"),
            "dosage_strength": drug.get("dosage_strength"),
            "match_score": round(match_score, 2),
            "matched_entities": {
                "symptoms": matched_symptoms,
                "indications": matched_indications
            }
        })
    
    # Sort by match_score (highest first)
    scored_drugs.sort(key=lambda x: x["match_score"], reverse=True)
    
    # Apply pagination
    paginated_results = scored_drugs[skip:skip + limit]
    
    return {
        "results": paginated_results,
        "total": len(scored_drugs)
    }
