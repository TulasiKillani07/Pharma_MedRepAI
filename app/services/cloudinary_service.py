"""
Cloudinary Service for File Upload and Management
Handles uploading drug brochures (PDFs) to Cloudinary cloud storage.
"""

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile
from typing import Dict, Any
import logging

from app.config import settings

# Configure Cloudinary with credentials from .env
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True  # Use HTTPS URLs
)

logger = logging.getLogger(__name__)


async def upload_drug_brochure(file: UploadFile, drug_id: str) -> Dict[str, Any]:
    """
    Upload drug brochure PDF to Cloudinary.
    
    Args:
        file: UploadFile object containing the PDF
        drug_id: Drug ID to organize files in Cloudinary
        
    Returns:
        dict: Contains secure_url and public_id
        
    Raises:
        HTTPException: If upload fails or file is invalid
    """
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('application/pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed for drug brochures"
        )
    
    # Validate file size (max 10MB)
    file_content = await file.read()
    file_size_mb = len(file_content) / (1024 * 1024)
    
    if file_size_mb > 10:
        raise HTTPException(
            status_code=400,
            detail=f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed size of 10MB"
        )
    
    # Reset file pointer
    await file.seek(0)
    
    try:
        # Upload to Cloudinary
        # Folder structure: drugs/{drug_id}/brochure
        result = cloudinary.uploader.upload(
            file.file,
            folder=f"drugs/{drug_id}",
            resource_type="raw",  # For PDFs and other non-image files
            public_id="brochure",  # Fixed name, will overwrite if exists
            overwrite=True,  # Replace existing brochure
            invalidate=True,  # Clear CDN cache
            use_filename=False,  # Don't use original filename
            unique_filename=False  # Use our public_id
        )
        
        logger.info(f"Successfully uploaded brochure for drug {drug_id}")
        
        return {
            "secure_url": result["secure_url"],
            "public_id": result["public_id"],
            "format": result.get("format", "pdf"),
            "bytes": result.get("bytes", 0),
            "created_at": result.get("created_at")
        }
        
    except Exception as e:
        logger.error(f"Failed to upload brochure for drug {drug_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload brochure to cloud storage: {str(e)}"
        )


async def delete_drug_brochure(public_id: str) -> bool:
    """
    Delete drug brochure from Cloudinary.
    
    Args:
        public_id: Cloudinary public_id of the file (e.g., "drugs/drug123/brochure")
        
    Returns:
        bool: True if deleted successfully
        
    Raises:
        HTTPException: If deletion fails
    """
    
    try:
        result = cloudinary.uploader.destroy(
            public_id,
            resource_type="raw",  # For PDFs
            invalidate=True  # Clear CDN cache
        )
        
        if result.get("result") == "ok":
            logger.info(f"Successfully deleted brochure: {public_id}")
            return True
        else:
            logger.warning(f"Brochure not found or already deleted: {public_id}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to delete brochure {public_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete brochure from cloud storage: {str(e)}"
        )


def get_brochure_url(public_id: str) -> str:
    """
    Generate secure URL for a brochure.
    
    Args:
        public_id: Cloudinary public_id
        
    Returns:
        str: Secure HTTPS URL
    """
    return cloudinary.CloudinaryResource(public_id, resource_type="raw").url


async def validate_cloudinary_connection() -> bool:
    """
    Test Cloudinary connection by checking configuration.
    
    Returns:
        bool: True if connection is valid
    """
    try:
        # Try to get account details
        result = cloudinary.api.ping()
        return result.get("status") == "ok"
    except Exception as e:
        logger.error(f"Cloudinary connection test failed: {str(e)}")
        return False
