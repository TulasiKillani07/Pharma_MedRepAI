"""
AI Report Analyzer Service
Handles PDF text extraction and AI-powered medical report analysis using Groq
"""

import os
import base64
import fitz  # PyMuPDF
from groq import Groq
from typing import List, Tuple
from app.config import settings


# Initialize Groq client
client = Groq(api_key=settings.GROQ_API_KEY)


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract text from PDF bytes using PyMuPDF.
    
    Args:
        pdf_bytes: PDF file content as bytes
        
    Returns:
        Extracted text as string
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()


def summarize_text(text: str) -> dict:
    """
    Summarize medical report text using Groq AI.
    
    Args:
        text: Medical report text content
        
    Returns:
        Dictionary with summary, key_findings, diagnosis, medications, important_notes
    """
    prompt = f"""
You are a medical assistant. Analyze the following medical report and provide:
1. A brief summary
2. Key findings
3. Diagnosis (if mentioned)
4. Medications prescribed (if any)
5. Important notes or recommendations

Medical Report:
{text}

Respond in JSON format:
{{
  "summary": "...",
  "key_findings": ["...", "..."],
  "diagnosis": "...",
  "medications": ["...", "..."],
  "important_notes": "..."
}}
"""
    
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        max_tokens=1500,
    )
    
    response_text = chat_completion.choices[0].message.content
    
    # Try to parse JSON response
    import json
    try:
        # Extract JSON from markdown code blocks if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        return json.loads(response_text)
    except json.JSONDecodeError:
        # If JSON parsing fails, return raw response
        return {
            "summary": response_text,
            "key_findings": [],
            "diagnosis": "Unable to parse",
            "medications": [],
            "important_notes": ""
        }


def summarize_images(image_data: List[Tuple[bytes, str]]) -> dict:
    """
    Summarize medical report images using Groq Vision AI.
    
    Args:
        image_data: List of tuples containing (image_bytes, mime_type)
        
    Returns:
        Dictionary with summary, key_findings, diagnosis, medications, important_notes
    """
    content = [
        {
            "type": "text",
            "text": """
You are a medical assistant. Analyze the medical report image(s) and provide:
1. A brief summary
2. Key findings
3. Diagnosis (if mentioned)
4. Medications prescribed (if any)
5. Important notes or recommendations

Respond in JSON format:
{
  "summary": "...",
  "key_findings": ["...", "..."],
  "diagnosis": "...",
  "medications": ["...", "..."],
  "important_notes": "..."
}
"""
        }
    ]
    
    # Add all images to the content
    for img_bytes, mime_type in image_data:
        b64_image = base64.b64encode(img_bytes).decode("utf-8")
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{b64_image}"
            }
        })
    
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": content}],
        model="meta-llama/llama-4-scout-17b-16e-instruct",  # Vision model that works
        temperature=0.3,
        max_tokens=1500,
    )
    
    response_text = chat_completion.choices[0].message.content
    
    # Try to parse JSON response
    import json
    try:
        # Extract JSON from markdown code blocks if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        return json.loads(response_text)
    except json.JSONDecodeError:
        # If JSON parsing fails, return raw response
        return {
            "summary": response_text,
            "key_findings": [],
            "diagnosis": "Unable to parse",
            "medications": [],
            "important_notes": ""
        }
