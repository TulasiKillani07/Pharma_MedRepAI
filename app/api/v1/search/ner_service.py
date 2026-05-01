"""
NER (Named Entity Recognition) Service
Integrates with external NER API to extract medical entities from user queries.
Includes post-processing filters to clean up model errors.
"""

import httpx
from typing import Dict, List, Any, Optional
from app.config import settings
import logging
import re

logger = logging.getLogger(__name__)


# Blacklist of common non-medical words that model incorrectly labels
NOISE_WORDS = {
    # Question words
    "what", "when", "where", "why", "how", "who", "which",
    # Common verbs
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "can", "could", "should", "would", "will",
    # Pronouns
    "i", "you", "he", "she", "it", "we", "they", "this", "that", "these", "those",
    # Prepositions
    "in", "on", "at", "to", "for", "with", "from", "about", "by",
    # Conjunctions
    "and", "or", "but", "so", "yet",
    # Articles
    "a", "an", "the",
    # Common phrases
    "there", "even", "just", "only", "also", "very", "much", "many",
    # Question fragments
    "causing", "related", "worried", "noticed", "sudden",
    # Punctuation
    ",", ".", "?", "!", ";", ":", "-"
}

# Known symptoms (whitelist for validation)
KNOWN_SYMPTOMS = {
    "fever", "headache", "cough", "pain", "nausea", "vomiting", "diarrhea",
    "fatigue", "weakness", "dizziness", "chills", "sweating", "itching",
    "rash", "swelling", "bleeding", "bruising", "numbness", "tingling",
    "shortness of breath", "chest pain", "abdominal pain", "back pain",
    "joint pain", "muscle pain", "sore throat", "runny nose", "sneezing",
    "watery eyes", "blurred vision", "ear pain", "toothache", "heartburn",
    "constipation", "bloating", "cramps", "frequent urination", "thirst",
    "dry mouth", "loss of appetite", "weight loss", "weight gain",
    "insomnia", "anxiety", "depression", "confusion", "memory loss"
}

# Known diseases/indications (whitelist for validation)
KNOWN_INDICATIONS = {
    "diabetes", "hypertension", "asthma", "copd", "arthritis", "migraine",
    "epilepsy", "parkinson", "alzheimer", "cancer", "tuberculosis",
    "pneumonia", "bronchitis", "sinusitis", "gastritis", "ulcer",
    "gerd", "ibs", "crohn", "colitis", "hepatitis", "cirrhosis",
    "kidney disease", "heart disease", "stroke", "angina", "arrhythmia",
    "anemia", "leukemia", "lymphoma", "thyroid disorder", "hypothyroidism",
    "hyperthyroidism", "osteoporosis", "gout", "psoriasis", "eczema",
    "acne", "rosacea", "dermatitis", "allergy", "hay fever"
}


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
    
    def _is_valid_entity(self, text: str, label: str) -> bool:
        """
        Validate if extracted entity is actually medical.
        Filters out noise words and invalid entities.
        
        Args:
            text: Entity text
            label: Entity label (SYMPTOM, INDICATION, etc.)
            
        Returns:
            bool: True if valid medical entity
        """
        text_lower = text.lower().strip()
        
        # Filter 1: Remove noise words
        if text_lower in NOISE_WORDS:
            return False
        
        # Filter 2: Remove single characters (except valid ones)
        if len(text_lower) == 1 and text_lower not in ["a", "b", "c"]:  # vitamin names
            return False
        
        # Filter 3: Remove pure punctuation
        if re.match(r'^[^\w\s]+$', text_lower):
            return False
        
        # Filter 4: Remove question fragments
        question_patterns = [
            r'\bcausing\b', r'\brelated\b', r'\bworried\b', r'\bnoticed\b',
            r'\bcould this\b', r'\bwhat could\b', r'\bshould i\b'
        ]
        for pattern in question_patterns:
            if re.search(pattern, text_lower):
                return False
        
        # Filter 5: Validate against known medical terms
        if label == "SYMPTOM":
            # Check if it's a known symptom or contains symptom keywords
            if text_lower in KNOWN_SYMPTOMS:
                return True
            # Allow compound symptoms (e.g., "severe headache")
            for known in KNOWN_SYMPTOMS:
                if known in text_lower or text_lower in known:
                    return True
            # Reject if it's clearly not a symptom
            if len(text_lower.split()) > 5:  # Too long to be a symptom
                return False
        
        elif label == "INDICATION":
            # Check if it's a known disease
            if text_lower in KNOWN_INDICATIONS:
                return True
            # Allow compound diseases (e.g., "type 2 diabetes")
            for known in KNOWN_INDICATIONS:
                if known in text_lower or text_lower in known:
                    return True
            # Reject if it's clearly not a disease
            if len(text_lower.split()) > 6:  # Too long to be a disease name
                return False
        
        # Filter 6: Minimum length check
        if len(text_lower) < 3:  # Too short to be meaningful
            return False
        
        # If we reach here, it's probably valid (or we're not sure, so keep it)
        return True
    
    def _clean_entity_text(self, text: str) -> str:
        """
        Clean entity text by removing extra words and normalizing.
        
        Args:
            text: Raw entity text
            
        Returns:
            str: Cleaned entity text
        """
        # Remove leading/trailing articles
        text = re.sub(r'^\s*(a|an|the)\s+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+(a|an|the)\s*$', '', text, flags=re.IGNORECASE)
        
        # Remove question marks and exclamation points
        text = text.replace('?', '').replace('!', '')
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def _group_entities(self, entities: List[Dict]) -> Dict[str, List[str]]:
        """
        Group entities by their label type with filtering and validation.
        Uses canonical_term for database searching.
        Filters out negated entities and noise.
        
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
            
            # Clean the entity text
            term = self._clean_entity_text(term)
            
            # Validate entity before adding
            if not self._is_valid_entity(term, label):
                logger.debug(f"Filtered out invalid entity: '{term}' (label: {label})")
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
