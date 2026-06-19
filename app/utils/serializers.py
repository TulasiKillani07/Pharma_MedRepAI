"""
Serialization utilities for MongoDB documents.
"""
from bson import ObjectId
from typing import Any, Dict, List


def convert_objectids_to_strings(obj: Any) -> Any:
    """
    Recursively convert all ObjectId instances to strings in a dict/list.
    
    This is essential for FastAPI/Pydantic serialization because MongoDB's
    ObjectId type cannot be directly serialized to JSON.
    
    Args:
        obj: Dictionary, list, or any value that might contain ObjectIds
    
    Returns:
        Same structure with ObjectIds converted to strings
    
    Examples:
        >>> doc = {"_id": ObjectId("507f1f77bcf86cd799439011"), "name": "John"}
        >>> convert_objectids_to_strings(doc)
        {"_id": "507f1f77bcf86cd799439011", "name": "John"}
        
        >>> nested = {"user": {"id": ObjectId("...")}, "items": [ObjectId("...")]}
        >>> convert_objectids_to_strings(nested)
        {"user": {"id": "..."}, "items": ["..."]}
    """
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: convert_objectids_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectids_to_strings(item) for item in obj]
    else:
        return obj


def serialize_mongo_document(doc: Dict[str, Any], id_field: str = "id") -> Dict[str, Any]:
    """
    Serialize a MongoDB document for API response.
    
    Converts:
    - _id (ObjectId) to id (string)
    - All nested ObjectIds to strings
    
    Args:
        doc: MongoDB document
        id_field: Name for the converted _id field (default: "id")
    
    Returns:
        Serialized document ready for JSON response
    
    Example:
        >>> doc = await db.users.find_one({"_id": ObjectId("...")})
        >>> serialize_mongo_document(doc)
        {"id": "...", "name": "John", ...}
    """
    if not doc:
        return doc
    
    # Convert _id to id
    if "_id" in doc:
        doc[id_field] = str(doc.pop("_id"))
    
    # Convert all nested ObjectIds
    return convert_objectids_to_strings(doc)


def serialize_mongo_documents(docs: List[Dict[str, Any]], id_field: str = "id") -> List[Dict[str, Any]]:
    """
    Serialize a list of MongoDB documents for API response.
    
    Args:
        docs: List of MongoDB documents
        id_field: Name for the converted _id field (default: "id")
    
    Returns:
        List of serialized documents ready for JSON response
    
    Example:
        >>> docs = await db.users.find({}).to_list(None)
        >>> serialize_mongo_documents(docs)
        [{"id": "...", "name": "John"}, {"id": "...", "name": "Jane"}]
    """
    return [serialize_mongo_document(doc, id_field) for doc in docs]
