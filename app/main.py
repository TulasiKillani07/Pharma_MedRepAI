"""
MedRepAI - Main Application Entry Point
This is where the FastAPI application is created and configured.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection
from app.api.v1.router import api_router
from datetime import datetime
import json


# Custom JSON encoder for datetime serialization
class CustomJSONResponse(JSONResponse):
    """Custom JSON response that handles datetime serialization"""
    
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            default=self.json_encoder_default
        ).encode("utf-8")
    
    @staticmethod
    def json_encoder_default(obj):
        """Custom JSON encoder for datetime objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# Create FastAPI application instance
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="MedRep AI",
    docs_url="/docs",  # Swagger UI at http://localhost:8000/docs
    redoc_url="/redoc",  # ReDoc at http://localhost:8000/redoc
    default_response_class=CustomJSONResponse  # Use custom JSON response for datetime serialization
)


# Configure CORS (Cross-Origin Resource Sharing)
# This allows frontend applications to make requests to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins like ["https://yourfrontend.com"]
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)


# Event: Application Startup
@app.on_event("startup")
async def startup_event():
    """
    This function runs when the application starts.
    It connects to MongoDB.
    """
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await connect_to_mongo()
    print("Application started successfully!")


# Event: Application Shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """
    This function runs when the application shuts down.
    It closes the MongoDB connection.
    """
    print("Shutting down application...")
    await close_mongo_connection()
    print("Application shut down successfully!")


# Include API routes
# All API endpoints will be prefixed with /api/v1
app.include_router(api_router, prefix="/api/v1")


# Run the application
# Command: uvicorn app.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Auto-reload on code changes (only for development)
    )
