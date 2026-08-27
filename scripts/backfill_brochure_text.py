"""
One-time backfill script: Extract brochure text for existing MRX drugs.

Usage:
    cd backend
    python scripts/backfill_brochure_text.py

Safe to run multiple times — skips drugs that already have brochure_extraction_status == SUCCESS.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path so we can import from app/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

# Load settings
from app.config import settings
from app.api.v1.ai.service import extract_text_from_pdf


async def run_backfill():
    # ── Connect to MongoDB ────────────────────────────────────────────────────
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]

    print(f"\n{'='*60}")
    print(f"MRX Brochure Text Backfill")
    print(f"Database: {settings.DATABASE_NAME}")
    print(f"Started:  {datetime.utcnow().isoformat()}")
    print(f"{'='*60}\n")

    # ── Find all drugs that need extraction ───────────────────────────────────
    # Candidates: has a brochure_url AND (brochure_text is null OR status != SUCCESS)
    query = {
        "is_active": True,
        "brochure_url": {"$exists": True, "$ne": None, "$ne": ""},
        "$or": [
            {"brochure_extraction_status": {"$ne": "SUCCESS"}},
            {"brochure_text": None},
            {"brochure_text": {"$exists": False}}
        ]
    }

    drugs = await db.drugs.find(query, {
        "_id": 1,
        "drug_name": 1,
        "brochure_url": 1,
        "brochure_extraction_status": 1,
        "brochure_text": 1
    }).to_list(length=None)

    total_found = len(drugs)
    total_skipped = 0
    total_success = 0
    total_failed = 0
    failed_drugs = []

    print(f"Found {total_found} drug(s) to process.\n")

    if total_found == 0:
        print("Nothing to do. All drugs with brochures already have extracted text.")
        client.close()
        return

    # ── Process each drug ─────────────────────────────────────────────────────
    for i, drug in enumerate(drugs, 1):
        drug_id = str(drug["_id"])
        drug_name = drug.get("drug_name") or "(no name)"
        brochure_url = drug.get("brochure_url", "")
        current_status = drug.get("brochure_extraction_status")

        print(f"[{i}/{total_found}] {drug_name} (ID: {drug_id})")
        print(f"         Status: {current_status or 'None'}")

        # Skip already successful
        if current_status == "SUCCESS" and drug.get("brochure_text"):
            print(f"         → SKIPPED (already SUCCESS)\n")
            total_skipped += 1
            continue

        # Get brochure_url — from flat field or fallback to field_values
        if not brochure_url:
            # Try field_values
            full_drug = await db.drugs.find_one({"_id": drug["_id"]}, {"field_values": 1})
            for fv in full_drug.get("field_values", []):
                if fv.get("key") == "brochure_url" and fv.get("value"):
                    brochure_url = fv["value"]
                    break

        if not brochure_url:
            print(f"         → SKIPPED (no brochure_url found)\n")
            total_skipped += 1
            continue

        print(f"         URL: {brochure_url[:70]}...")

        try:
            # Download PDF
            async with httpx.AsyncClient(timeout=30.0) as client_http:
                response = await client_http.get(brochure_url)
                response.raise_for_status()
                pdf_bytes = response.content

            # Extract text
            brochure_text = extract_text_from_pdf(pdf_bytes)
            char_count = len(brochure_text) if brochure_text else 0

            # Save to DB
            await db.drugs.update_one(
                {"_id": drug["_id"]},
                {"$set": {
                    "brochure_text": brochure_text or None,
                    "brochure_extraction_status": "SUCCESS" if brochure_text else "FAILED",
                    "brochure_extracted_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }}
            )

            if brochure_text:
                print(f"         → SUCCESS ({char_count} chars extracted)\n")
                total_success += 1
            else:
                print(f"         → FAILED (empty text extracted)\n")
                total_failed += 1
                failed_drugs.append({"id": drug_id, "name": drug_name, "reason": "Empty text extracted"})

        except httpx.HTTPError as e:
            print(f"         → FAILED (download error: {e})\n")
            await db.drugs.update_one(
                {"_id": drug["_id"]},
                {"$set": {
                    "brochure_extraction_status": "FAILED",
                    "updated_at": datetime.utcnow()
                }}
            )
            total_failed += 1
            failed_drugs.append({"id": drug_id, "name": drug_name, "reason": f"Download error: {e}"})

        except Exception as e:
            print(f"         → FAILED (error: {e})\n")
            await db.drugs.update_one(
                {"_id": drug["_id"]},
                {"$set": {
                    "brochure_extraction_status": "FAILED",
                    "updated_at": datetime.utcnow()
                }}
            )
            total_failed += 1
            failed_drugs.append({"id": drug_id, "name": drug_name, "reason": str(e)})

    # ── Summary ───────────────────────────────────────────────────────────────
    client.close()

    print(f"\n{'='*60}")
    print(f"BACKFILL COMPLETE")
    print(f"{'='*60}")
    print(f"  Total found   : {total_found}")
    print(f"  Successful    : {total_success}")
    print(f"  Failed        : {total_failed}")
    print(f"  Skipped       : {total_skipped}")
    print(f"  Finished at   : {datetime.utcnow().isoformat()}")

    if failed_drugs:
        print(f"\nFailed drugs:")
        for d in failed_drugs:
            print(f"  - [{d['id']}] {d['name']}: {d['reason']}")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(run_backfill())
