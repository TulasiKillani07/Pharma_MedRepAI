from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from summarizer import extract_text_from_pdf, summarize_text, summarize_images
 
app = FastAPI(title="MedRep AI Services", version="1.0.0")
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png":  [".png"],
    "image/webp": [".webp"],
}
 
MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5 MB per image
MAX_PDF_SIZE   = 10 * 1024 * 1024  # 10 MB
 
 
@app.get("/health")
def health():
    return {"status": "ok"}
 
 
@app.post("/api/v1/ai/summarize-pdf")
async def summarize_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
 
    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10 MB.")
 
    try:
        text = extract_text_from_pdf(pdf_bytes)
        if not text:
            raise HTTPException(status_code=400, detail="Could not extract text from PDF. The file may be scanned/image-based. Try uploading as an image instead.")
        summary = summarize_text(text)
        return {"filename": file.filename, "char_count": len(text), "summary": summary}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.post("/api/v1/ai/summarize-images")
async def summarize_images_endpoint(files: List[UploadFile] = File(...)):
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
            raise HTTPException(status_code=400, detail=f"{f.filename}: Only JPG, PNG, WEBP images are supported.")
 
        img_bytes = await f.read()
        if len(img_bytes) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=400, detail=f"{f.filename}: File too large. Maximum 5 MB per image.")
 
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