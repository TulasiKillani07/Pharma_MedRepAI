"""
Search Request/Response Schemas
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ============ ENTITY SCHEMAS ============

class ExtractedEntities(BaseModel):
    """Schema for extracted entities from NER"""
    symptoms: List[str] = Field(default=[], description="Extracted symptoms")
    indications: List[str] = Field(default=[], description="Extracted indications/diseases")
    severity: List[str] = Field(default=[], description="Extracted severity levels")
    duration: List[str] = Field(default=[], description="Extracted duration")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symptoms": ["fever", "headache", "knee pain"],
                "indications": [],
                "severity": [],
                "duration": ["3 days"]
            }
        }


class MatchedEntities(BaseModel):
    """Schema for matched entities in a drug"""
    symptoms: List[str] = Field(default=[], description="Matched symptoms")
    indications: List[str] = Field(default=[], description="Matched indications")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symptoms": ["fever", "headache"],
                "indications": []
            }
        }


# ============ DRUG SEARCH SCHEMAS ============

class DrugSearchRequest(BaseModel):
    """Schema for intelligent drug search request"""
    query: str = Field(..., min_length=3, max_length=500, description="Natural language query (e.g., 'I have fever and headache')")
    skip: int = Field(default=0, ge=0, description="Number of results to skip (pagination)")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of results to return")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "I have fever, headache and knee pain from 3 days",
                "skip": 0,
                "limit": 20
            }
        }


class DrugSearchResult(BaseModel):
    """Schema for a single drug result in search"""
    id: str = Field(alias="_id", description="Drug ID")
    drug_name: str
    brand_name: Optional[str] = None
    manufacturer: Optional[str] = None
    symptoms: List[str] = Field(default=[], description="Drug's symptoms")
    indications: List[str] = Field(default=[], description="Drug's indications")
    dosage_form: Optional[str] = None
    dosage_strength: Optional[str] = None
    match_score: float = Field(..., description="Match score (0-100)")
    matched_entities: MatchedEntities = Field(..., description="Which entities matched")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "drug_name": "paracetamol",
                "brand_name": "crocin",
                "manufacturer": "GSK",
                "symptoms": ["fever", "headache", "body pain"],
                "indications": ["fever", "pain relief"],
                "dosage_form": "Tablet",
                "dosage_strength": "500mg",
                "match_score": 75.5,
                "matched_entities": {
                    "symptoms": ["fever", "headache"],
                    "indications": []
                }
            }
        }


class DrugSearchResponse(BaseModel):
    """Schema for drug search response"""
    query: str = Field(..., description="Original user query")
    entities_extracted: ExtractedEntities = Field(..., description="Entities extracted by NER")
    results: List[DrugSearchResult] = Field(..., description="Matched drugs sorted by score")
    total_results: int = Field(..., description="Total number of matching drugs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "I have fever, headache and knee pain from 3 days",
                "entities_extracted": {
                    "symptoms": ["fever", "headache", "knee pain"],
                    "indications": [],
                    "severity": [],
                    "duration": ["3 days"]
                },
                "results": [
                    {
                        "_id": "507f1f77bcf86cd799439011",
                        "drug_name": "paracetamol",
                        "brand_name": "crocin",
                        "manufacturer": "GSK",
                        "symptoms": ["fever", "headache", "body pain"],
                        "indications": ["fever", "pain relief"],
                        "dosage_form": "Tablet",
                        "dosage_strength": "500mg",
                        "match_score": 75.5,
                        "matched_entities": {
                            "symptoms": ["fever", "headache"],
                            "indications": []
                        }
                    }
                ],
                "total_results": 15
            }
        }
