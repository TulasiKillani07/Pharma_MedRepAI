"""
NER (Named Entity Recognition) Service
Integrates with external NER API to extract medical entities from user queries.
"""

import httpx
from typing import Dict, List, Any, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class NERService:
    """Service for extracting medical entities using external NER API"""
    
    def __init__(self):
        self.api_url = settings.NER_API_URL
        self.timeout = settings.NER_API_TIMEOUT
    
    async def extract_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract medical entities from user query.
        
        Args:
            text: User's natural language query
            
        Returns:
            Dictionary with extracted entities grouped by type:
            {
                "symptoms": ["fever", "headache"],
                "indications": ["diabetes"],
                "severity": ["mild"],
                "duration": ["3 days"],
                "raw_response": {...}  # Full NER API response
            }
            
        Raises:
            Exception: If NER API call fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.api_url,
                    json={"text": text}
                )
                response.raise_for_status()
                
                ner_response = response.json()
                
                # Group entities by type
                grouped = self._group_entities(ner_response.get("entities", []))
                
                # Add raw response for debugging
                grouped["raw_response"] = ner_response
                
                return grouped
                
        except httpx.TimeoutException:
            logger.error(f"NER API timeout after {self.timeout}s for query: {text}")
            raise Exception("NER service timeout. Please try again.")
        
        except httpx.HTTPStatusError as e:
            logger.error(f"NER API HTTP error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"NER service error: {e.response.status_code}")
        
        except httpx.RequestError as e:
            logger.error(f"NER API request error: {str(e)}")
            raise Exception("Unable to connect to NER service. Please try again later.")
        
        except Exception as e:
            logger.error(f"Unexpected error in NER service: {str(e)}")
            raise Exception("NER service error. Please try again.")
    
    def _group_entities(self, entities: List[Dict]) -> Dict[str, List[str]]:
        """
        Group entities by their label type.
        Uses canonical_term for database searching.
        Filters out negated entities.
        
        Args:
            entities: List of entity dictionaries from NER API
            
        Returns:
            Dictionary with entities grouped by type:
            {
                "symptoms": ["fever", "headache"],
                "indications": ["diabetes"],
                "severity": ["mild"],
                "duration": ["3 days"]
            }
        """
        grouped = {
            "symptoms": [],
            "indications": [],
            "severity": [],
            "duration": []
        }
        
        for entity in entities:
            # Skip negated entities (e.g., "no fever")
            if entity.get("negated", False):
                continue
            
            label = entity.get("label", "").upper()
            # Use canonical_term for DB search (standardized term)
            term = entity.get("canonical_term") or entity.get("text")
            
            if not term:
                continue
            
            # Normalize term to lowercase for consistent DB matching
            term = term.lower().strip()
            
            # Group by entity type
            if label == "SYMPTOM":
                if term not in grouped["symptoms"]:
                    grouped["symptoms"].append(term)
            
            elif label == "INDICATION":
                if term not in grouped["indications"]:
                    grouped["indications"].append(term)
            
            elif label == "SEVERITY":
                if term not in grouped["severity"]:
                    grouped["severity"].append(term)
            
            elif label == "DURATION":
                if term not in grouped["duration"]:
                    grouped["duration"].append(term)
        
        return grouped


# Singleton instance
ner_service = NERService()


async def extract_medical_entities(text: str) -> Dict[str, Any]:
    """
    Convenience function to extract medical entities.
    
    Args:
        text: User's natural language query
        
    Returns:
        Dictionary with grouped entities
    """
    return await ner_service.extract_entities(text)
