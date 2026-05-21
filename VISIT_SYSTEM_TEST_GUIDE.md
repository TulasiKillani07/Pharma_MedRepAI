# Visit System - Quick Testing Guide

## 🧪 How to Test the New Endpoints

### Prerequisites:
1. Backend running: `uvicorn app.main:app --reload --port 8000`
2. MR token: Get from login endpoint
3. Visit ID: Create a visit first

---

## Test 1: Complete Happy Path Flow

### Step 1: Schedule a Visit
```bash
curl -X POST http://localhost:8000/api/v1/visits \
  -H "Authorization: Bearer {MR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_id": "{DOCTOR_ID}",
    "scheduled_date": "2026-05-26",
    "scheduled_time": "10:00",
    "purpose": "Drug Promotion Test",
    "location": "Test Hospital"
  }'
```

**Expected:** `{"message": "Visit scheduled successfully", "visit_id": "..."}`

---

### Step 2: Check Active Visit (Should be null)
```bash
curl http://localhost:8000/api/v1/visits/active \
  -H "Authorization: Bearer {MR_TOKEN}"
```

**Expected:** `{"active_visit": null, "pending_reports": 0}`

---

### Step 3: Check In
```bash
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_ID}/check-in \
  -H "Authorization: Bearer {MR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 17.4401,
    "longitude": 78.3489
  }'
```

**Expected:** 
```json
{
  "message": "Checked in successfully",
  "visit_id": "...",
  "check_in_time": "2026-05-25T10:05:32"
}
```

---

### Step 4: Check Active Visit (Should show active)
```bash
curl http://localhost:8000/api/v1/visits/active \
  -H "Authorization: Bearer {MR_TOKEN}"
```

**Expected:**
```json
{
  "active_visit": {
    "id": "...",
    "doctor_id": "...",
    "doctor_name": "Dr. ...",
    "check_in_time": "2026-05-25T10:05:32",
    "location": "Test Hospital",
    "duration_so_far_minutes": 2
  },
  "pending_reports": 0
}
```

---

### Step 5: Check Out
```bash
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_ID}/check-out \
  -H "Authorization: Bearer {MR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 17.4401,
    "longitude": 78.3490
  }'
```

**Expected:**
```json
{
  "message": "Checked out successfully",
  "visit_id": "...",
  "duration_minutes": 5
}
```

---

### Step 6: Check Active Visit (Should be null, pending: 1)
```bash
curl http://localhost:8000/api/v1/visits/active \
  -H "Authorization: Bearer {MR_TOKEN}"
```

**Expected:** `{"active_visit": null, "pending_reports": 1}`

---

### Step 7: Submit Report
```bash
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_ID}/report \
  -H "Authorization: Bearer {MR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_mood": "positive",
    "products_discussed": ["{DRUG_ID}"],
    "samples_given": 3,
    "outcome": "Positive — Doctor interested in the product",
    "rx_commitment": true,
    "expected_rx_per_month": 10,
    "competitor_info": "Cipla — Amlokind 5mg",
    "follow_up_date": "2026-06-01",
    "notes": "Doctor wants clinical trial data"
  }'
```

**Expected:**
```json
{
  "message": "Report submitted successfully",
  "visit_id": "...",
  "status": "completed"
}
```

---

### Step 8: Verify Targets Updated
```bash
curl http://localhost:8000/api/v1/visits \
  -H "Authorization: Bearer {MR_TOKEN}"
```

**Expected:** `targets` array should show `completed: 1` for that doctor

---

## Test 2: Cancel Check-In Flow

### Step 1: Schedule and Check In
```bash
# Schedule
curl -X POST http://localhost:8000/api/v1/visits ...

# Check in
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_ID}/check-in ...
```

---

### Step 2: Cancel Check-In
```bash
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_ID}/cancel-checkin \
  -H "Authorization: Bearer {MR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Doctor was called for emergency surgery"
  }'
```

**Expected:**
```json
{
  "message": "Check-in cancelled successfully",
  "visit_id": "...",
  "status": "scheduled"
}
```

---

### Step 3: Verify Status is Scheduled
```bash
curl http://localhost:8000/api/v1/visits/{VISIT_ID} \
  -H "Authorization: Bearer {MR_TOKEN}"
```

**Expected:** `"status": "scheduled"`

---

## Test 3: Validation Rules

### Test 3.1: Only 1 Active Check-In

```bash
# Check in to visit A
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_A_ID}/check-in ...

# Try to check in to visit B (should fail)
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_B_ID}/check-in ...
```

**Expected Error:**
```json
{
  "detail": "Check out of your current visit first. Only one active check-in allowed at a time."
}
```

---

### Test 3.2: Max 2 Pending Reports

```bash
# Check out from 2 visits without submitting reports
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_A_ID}/check-out ...
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_B_ID}/check-out ...

# Try to check in to visit C (should fail)
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_C_ID}/check-in ...
```

**Expected Error:**
```json
{
  "detail": "Submit pending reports before checking in (max 2 allowed). You have 2 pending reports."
}
```

---

### Test 3.3: Invalid Status Transitions

```bash
# Try to check out without checking in
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_ID}/check-out ...
```

**Expected Error:**
```json
{
  "detail": "Cannot check out from scheduled visit. Only checked-in visits can be checked out."
}
```

```bash
# Try to submit report without checking out
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_ID}/report ...
```

**Expected Error:**
```json
{
  "detail": "Cannot submit report for scheduled visit. Only checked-out visits can have reports submitted."
}
```

---

## Test 4: GPS Validation

### Test 4.1: Invalid Latitude
```bash
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_ID}/check-in \
  -H "Authorization: Bearer {MR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 100,
    "longitude": 78.3489
  }'
```

**Expected Error:** Validation error (latitude must be -90 to 90)

---

### Test 4.2: Invalid Longitude
```bash
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_ID}/check-in \
  -H "Authorization: Bearer {MR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 17.4401,
    "longitude": 200
  }'
```

**Expected Error:** Validation error (longitude must be -180 to 180)

---

## Test 5: Report Validation

### Test 5.1: Invalid Doctor Mood
```bash
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_ID}/report \
  -H "Authorization: Bearer {MR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_mood": "happy",
    "products_discussed": ["{DRUG_ID}"],
    "samples_given": 3,
    "outcome": "Test outcome"
  }'
```

**Expected Error:** `"Doctor mood must be: positive, neutral, or negative"`

---

### Test 5.2: Outcome Too Short
```bash
curl -X PUT http://localhost:8000/api/v1/visits/{VISIT_ID}/report \
  -H "Authorization: Bearer {MR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_mood": "positive",
    "products_discussed": ["{DRUG_ID}"],
    "samples_given": 3,
    "outcome": "Good"
  }'
```

**Expected Error:** Validation error (outcome must be at least 10 characters)

---

## Quick Test Script (Python)

```python
import requests
import time

BASE_URL = "http://localhost:8000/api/v1"
MR_TOKEN = "your_mr_token_here"
DOCTOR_ID = "your_doctor_id_here"
DRUG_ID = "your_drug_id_here"

headers = {
    "Authorization": f"Bearer {MR_TOKEN}",
    "Content-Type": "application/json"
}

# 1. Schedule visit
response = requests.post(f"{BASE_URL}/visits", headers=headers, json={
    "doctor_id": DOCTOR_ID,
    "scheduled_date": "2026-05-26",
    "scheduled_time": "10:00",
    "purpose": "Test Visit",
    "location": "Test Hospital"
})
visit_id = response.json()["visit_id"]
print(f"✅ Visit scheduled: {visit_id}")

# 2. Check active (should be null)
response = requests.get(f"{BASE_URL}/visits/active", headers=headers)
print(f"✅ Active visit: {response.json()}")

# 3. Check in
response = requests.put(f"{BASE_URL}/visits/{visit_id}/check-in", headers=headers, json={
    "latitude": 17.4401,
    "longitude": 78.3489
})
print(f"✅ Checked in: {response.json()}")

# 4. Wait 5 seconds
time.sleep(5)

# 5. Check out
response = requests.put(f"{BASE_URL}/visits/{visit_id}/check-out", headers=headers, json={
    "latitude": 17.4401,
    "longitude": 78.3490
})
print(f"✅ Checked out: {response.json()}")

# 6. Submit report
response = requests.put(f"{BASE_URL}/visits/{visit_id}/report", headers=headers, json={
    "doctor_mood": "positive",
    "products_discussed": [DRUG_ID],
    "samples_given": 3,
    "outcome": "Positive — Doctor interested in the product"
})
print(f"✅ Report submitted: {response.json()}")

# 7. Check targets
response = requests.get(f"{BASE_URL}/visits", headers=headers)
targets = response.json()["targets"]
print(f"✅ Targets: {targets}")
```

---

## Swagger UI Testing

**Easiest way to test:**

1. Open: `http://localhost:8000/docs`
2. Click "Authorize" button
3. Enter MR token
4. Test each endpoint in order:
   - POST /visits (schedule)
   - GET /visits/active (check active)
   - PUT /visits/{id}/check-in (check in)
   - GET /visits/active (verify active)
   - PUT /visits/{id}/check-out (check out)
   - PUT /visits/{id}/report (submit report)
   - GET /visits (verify targets)

---

## Expected Results Summary

| Test | Expected Result |
|------|----------------|
| Schedule visit | Status: scheduled |
| Check in | Status: checked_in, GPS saved |
| Active visit | Shows active visit details |
| Check out | Status: checked_out, duration calculated |
| Submit report | Status: completed, counts toward target |
| Cancel check-in | Status: back to scheduled |
| 2nd check-in attempt | Error: "Check out first" |
| 3rd pending report | Error: "Submit reports first" |
| Invalid GPS | Validation error |
| Invalid mood | Validation error |

---

## Troubleshooting

### Issue: "Invalid visit ID"
- **Solution:** Make sure visit_id is a valid ObjectId format

### Issue: "Visit not found"
- **Solution:** Check that the visit exists and belongs to this MR

### Issue: "Only MRs can check in"
- **Solution:** Make sure you're using an MR token, not admin token

### Issue: "Product not in assigned drugs"
- **Solution:** Use drug IDs from the MR's assigned_drugs list

### Issue: GPS validation error
- **Solution:** Latitude: -90 to 90, Longitude: -180 to 180

---

**Happy Testing!** 🎉
