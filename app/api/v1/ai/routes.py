"""
AI Report Analyzer Routes
Endpoints for analyzing medical reports (PDFs and images) using AI
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from app.api.v1.ai.service import extract_text_from_pdf, summarize_text, summarize_images
import traceback
from app.utils.logger import get_medrep_logger

logger = get_medrep_logger(__name__)


router = APIRouter()


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png":  [".png"],
    "image/webp": [".webp"],
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5 MB per image
MAX_PDF_SIZE   = 10 * 1024 * 1024  # 10 MB


@router.post("/summarize-pdf")
async def summarize_pdf(file: UploadFile = File(...)):
    """
    Analyze and summarize a medical report PDF.
    
    - **file**: PDF file (max 10 MB)
    
    Returns:
    - filename: Name of the uploaded file
    - char_count: Number of characters extracted
    - summary: AI-generated analysis with key findings, diagnosis, medications, etc.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10 MB.")
    
    try:
        # Extract text from PDF
        text = extract_text_from_pdf(pdf_bytes)
        if not text:
            raise HTTPException(
                status_code=400, 
                detail="Could not extract text from PDF. The file may be scanned/image-based. Try uploading as an image instead."
            )
        
        # Summarize using AI
        summary = summarize_text(text)
        return {
            "filename": file.filename,
            "char_count": len(text),
            "summary": summary
        }
    except HTTPException:
        raise
    except Exception as e:
        # Log the full error for debugging
        error_details = traceback.format_exc()
        logger.error(f"Error in summarize_pdf: {error_details}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing PDF: {str(e)}"
        )


@router.post("/summarize-images")
async def summarize_images_endpoint(files: List[UploadFile] = File(...)):
    """
    Analyze and summarize medical report images.
    
    - **files**: List of image files (max 2 images, 5 MB each)
    - Supported formats: JPG, PNG, WEBP
    
    Returns:
    - filenames: Names of uploaded files
    - image_count: Number of images processed
    - summary: AI-generated analysis with key findings, diagnosis, medications, etc.
    """
    if len(files) > 2:
        raise HTTPException(status_code=400, detail="Maximum 2 images allowed.")
    
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="Please upload at least one image.")
    
    image_data = []
    filenames = []
    
    for f in files:
        ext = "." + f.filename.lower().rsplit(".", 1)[-1] if "." in f.filename else ""
        mime = next((m for m, exts in ALLOWED_IMAGE_TYPES.items() if ext in exts), None)
        
        if not mime:
            raise HTTPException(
                status_code=400, 
                detail=f"{f.filename}: Only JPG, PNG, WEBP images are supported."
            )
        
        img_bytes = await f.read()
        if len(img_bytes) > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"{f.filename}: File too large. Maximum 5 MB per image."
            )
        
        image_data.append((img_bytes, mime))
        filenames.append(f.filename)
    
    try:
        summary = summarize_images(image_data)
        return {
            "filenames": filenames,
            "image_count": len(filenames),
            "summary": summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
