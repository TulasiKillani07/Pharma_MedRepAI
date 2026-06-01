"""
Custom JSON Response - Handles datetime serialization for MongoDB objects.
"""

from fastapi.responses import JSONResponse
from datetime import datetime
from bson import ObjectId
import json


class CustomJSONResponse(JSONResponse):
    """
    Custom JSON response class that handles serialization of:
    - datetime objects (from MongoDB) → ISO format string
    - ObjectId objects (from MongoDB) → string
    """

    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            default=self._json_encoder
        ).encode("utf-8")

    @staticmethod
    def _json_encoder(obj):
        """Handle non-serializable types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
