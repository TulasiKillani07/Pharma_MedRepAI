import fitz  # PyMuPDF
import json
import os
import base64
from groq import Groq
from dotenv import load_dotenv
 
load_dotenv()
 
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
 
SYSTEM_PROMPT = """You are a medical assistant. Analyze the medical document and extract information.
 
Return ONLY valid JSON (no markdown, no explanation) with exactly these keys:
{
  "summary": "2-3 sentence plain English overview of the document",
  "key_findings": ["finding 1", "finding 2", ...],
  "diagnosis": ["diagnosis 1", ...],
  "medications": ["medication 1 with dosage", ...],
  "important_notes": ["note 1", "note 2", ...]
}
 
Rules:
- Each array value must be an ARRAY of strings, never a plain string
- Each array item is one clear, complete sentence or fact
- If a section has no information, return an empty array []
- Do NOT hallucinate. Use only information from the given document
- Do NOT include markdown code fences or any text outside the JSON"""
 
 
def _parse_response(raw: str) -> dict:
    raw = raw.strip()
    # Strip markdown code fences if model adds them
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        raw = raw.strip()
    try:
        parsed = json.loads(raw)
        # Normalize all array fields
        for key in ["key_findings", "diagnosis", "medications", "important_notes"]:
            val = parsed.get(key, [])
            if isinstance(val, str):
                parsed[key] = [s.strip() for s in val.replace(";", ",").split(",") if s.strip()]
            elif not isinstance(val, list):
                parsed[key] = [str(val)] if val else []
        if "summary" not in parsed or not parsed["summary"]:
            parsed["summary"] = ""
        return parsed
    except json.JSONDecodeError:
        return {"raw_summary": raw}
 
 
def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()
 
 
def summarize_text(text: str) -> dict:
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this medical document:\n\n{text}"},
        ],
        temperature=0.2,
        max_tokens=1500,
    )
    return _parse_response(response.choices[0].message.content)
 
 
def summarize_images(image_files: list) -> dict:
    """
    image_files: list of (bytes, mime_type) tuples
    e.g. [(b"...", "image/jpeg"), (b"...", "image/png")]
    Max 2 images.
    """
    content = []
 
    for img_bytes, mime_type in image_files[:2]:
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{b64}"},
        })
 
    content.append({
        "type": "text",
        "text": (
            "Analyze this medical document image(s) and extract all information. "
            "Return ONLY valid JSON with keys: summary, key_findings, diagnosis, medications, important_notes. "
            "Each value except summary must be an array of strings. "
            "Do NOT hallucinate. Use only what is visible in the image."
        ),
    })
 
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": content}],
        temperature=0.2,
        max_tokens=1500,
    )
    return _parse_response(response.choices[0].message.content)