# MedRepAI Backend

A B2B SaaS platform for pharmaceutical companies to educate doctors about their drugs and enable digital interaction between Medical Representatives (MRs) and doctors.

## Tech Stack
- **FastAPI** - Modern Python web framework
- **MongoDB** - NoSQL database
- **Motor** - Async MongoDB driver
- **JWT** - Authentication
- **bcrypt** - Password hashing

## Project Structure
```
app/
├── main.py              # Application entry point
├── config.py            # Configuration settings
├── database.py          # MongoDB connection
├── core/                # Framework-level features
├── models/              # Database models
└── api/v1/              # API endpoints
```

## Setup Instructions

1. **Install Python 3.9+**

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   - Copy `.env` file and update values
   - Set your MongoDB connection string
   - Generate a secure SECRET_KEY

5. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

6. **Access API documentation**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## User Roles
- **Company Admin** - Manages doctors, MRs, and drugs
- **Doctor** - Views drugs, creates posts, chats
- **MR** - Views doctors, chats, promotes drugs

## Features
- Authentication (JWT)
- Drug Management
- Social Feed (posts, likes, comments)
- Real-time Chat
- CME Events Management
