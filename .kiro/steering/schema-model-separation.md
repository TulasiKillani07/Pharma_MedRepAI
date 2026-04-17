---
inclusion: auto
---

# Schema/Model Separation Rule - ALWAYS FOLLOW

## Critical Rule for AI Assistant

When writing ANY code for this project, you MUST follow this separation:

### Schemas (API Validation)
- **Location**: `backend/app/api/v1/{feature}/schemas.py`
- **Used by**: `routes.py` files
- **Purpose**: API request/response validation
- **Contains**: Pydantic models with Field validators, examples

### Models (Database Structure)
- **Location**: `backend/app/models/{feature}_model.py`
- **Used by**: `service.py` files
- **Purpose**: MongoDB document structure
- **Contains**: Minimal Pydantic models, constants

## Import Rules

```python
# routes.py - ALWAYS import from schemas
from app.api.v1.{feature}.schemas import RequestSchema, ResponseSchema

# service.py - ONLY import from models if needed
from app.models.{feature}_model import DocumentInDB
```

## Never Do This

❌ Import models in routes.py
❌ Import schemas in service.py
❌ Put API validation schemas in models folder
❌ Put DB document models in schemas.py

## When Creating New Features

1. Create `api/v1/{feature}/schemas.py` for API validation
2. Create `models/{feature}_model.py` for DB structure (if new collection)
3. Routes import from schemas
4. Service imports from models (if needed)

## Remember

**"Schemas for API, Models for DB"**

This separation is critical for maintainability. Breaking this rule causes confusion for developers and makes debugging difficult.
