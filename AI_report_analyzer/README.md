# AI Report Analyzer

Medical document analysis service using Groq AI.

## Features

- **PDF Analysis**: Extract and summarize text from PDF medical reports
- **Image Analysis**: Analyze medical report images (JPG, PNG, WEBP)
- **Structured Output**: Returns JSON with summary, findings, diagnosis, medications, and notes

## Setup

1. **Install dependencies:**
```bash
pip install -r ../requirements.txt
```

2. **Set up environment variables:**
```bash
# Copy .env.example to .env
cp .env.example .env

# Add your Groq API key
GROQ_API_KEY=your_groq_api_key_here
```

3. **Get Groq API Key:**
   - Visit https://console.groq.com/
   - Sign up/Login
   - Create an API key
   - Add it to your `.env` file

## Running the Service

```bash
# From AI_report_analyzer directory
uvicorn main:app --reload --port 8001

# Or specify host
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

## API Endpoints

### Health Check
```bash
GET /health
```

### Summarize PDF
```bash
POST /api/v1/ai/summarize-pdf
Content-Type: multipart/form-data

file: <pdf_file>
```

**Response:**
```json
{
  "filename": "report.pdf",
  "char_count": 1234,
  "summary": {
    "summary": "Patient report overview...",
    "key_findings": ["Finding 1", "Finding 2"],
    "diagnosis": ["Diagnosis 1"],
    "medications": ["Medicine 1 - 500mg"],
    "important_notes": ["Note 1", "Note 2"]
  }
}
```

### Summarize Images
```bash
POST /api/v1/ai/summarize-images
Content-Type: multipart/form-data

files: <image_file_1>
files: <image_file_2>  # Optional, max 2 images
```

**Response:**
```json
{
  "filenames": ["report1.jpg", "report2.jpg"],
  "image_count": 2,
  "summary": {
    "summary": "Medical report overview...",
    "key_findings": ["Finding 1"],
    "diagnosis": ["Diagnosis 1"],
    "medications": ["Medicine 1"],
    "important_notes": ["Note 1"]
  }
}
```

## File Limits

- **PDF**: Max 10 MB
- **Images**: Max 5 MB per image, max 2 images
- **Supported formats**: JPG, JPEG, PNG, WEBP

## Testing

### Test PDF Upload
```bash
curl -X POST "http://localhost:8001/api/v1/ai/summarize-pdf" \
  -F "file=@test_report.pdf"
```

### Test Image Upload
```bash
curl -X POST "http://localhost:8001/api/v1/ai/summarize-images" \
  -F "files=@report1.jpg" \
  -F "files=@report2.jpg"
```

## Integration with Main Backend

To integrate with the main MedRep backend, you can:

1. **Proxy through main backend** - Add routes in main backend that forward to this service
2. **Direct frontend calls** - Frontend calls this service directly on port 8001
3. **Merge into main app** - Import these routes into the main FastAPI app

## Models Used

- **Text Analysis**: `llama-3.1-8b-instant` (Groq)
- **Image Analysis**: `meta-llama/llama-4-scout-17b-16e-instruct` (Groq)

## Error Handling

- Returns 400 for invalid file types or sizes
- Returns 500 for processing errors
- All errors include descriptive messages

## Notes

- Service runs independently on port 8001
- CORS enabled for all origins (configure for production)
- Uses Groq AI for fast inference
- Structured JSON output for easy frontend integration
