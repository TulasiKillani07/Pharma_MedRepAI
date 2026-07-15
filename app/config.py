"""
Configuration settings for MedRepAI application.
This file reads environment variables from .env file and validates them.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Pydantic automatically reads from .env file and validates types.
    """
    
    # MongoDB Configuration
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "medrepai_db"
    
    # JWT (JSON Web Token) Configuration
    SECRET_KEY: str  # Must be set in .env - used to sign JWT tokens
    ALGORITHM: str = "HS256"  # Algorithm for JWT encoding
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # Token expires after 60 minutes
    
    # Service-to-Service JWT Secret (isolated from user JWTs)
    SERVICE_JWT_SECRET: str = "mrx-service-jwt-secret-change-in-production-min-32-chars"
    
    # Inbound Service Auth — DRX calling MRX
    # Only one trusted caller (DRX). Verified from env, no DB collection needed.
    # Store bcrypt hash of the secret, not plaintext.
    INBOUND_CLIENT_ID: str = "drx_doctor_platform"
    INBOUND_CLIENT_SECRET_HASH: str = ""  # bcrypt hash of the inbound client secret
    
    # Application Configuration
    APP_NAME: str = "MedRepAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Default password for doctors/MRs created by admin
    DEFAULT_USER_PASSWORD: str = "Welcome@123"
    
    # NER API Configuration
    NER_API_URL: str = "https://ner-medrep.onrender.com/predict"  # NER API endpoint
    NER_API_TIMEOUT: int = 30  # Timeout in seconds (Render can be slow on cold start)
    
    # Email Configuration (Gmail SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None  # Gmail address (optional until configured)
    SMTP_PASSWORD: Optional[str] = None  # Gmail App Password (optional until configured)
    SMTP_FROM_EMAIL: Optional[str] = None  # Email address shown as sender (optional)
    SMTP_FROM_NAME: str = "MedRep Platform"
    
    # Frontend Configuration
    FRONTEND_URL: str = "http://localhost:3000"  # Frontend URL for login links
    
    # Cloudinary Configuration (File Storage)
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str
    
    # AI Configuration (Groq API)
    GROQ_API_KEY: str  # Groq API key for AI report analysis
    
    # Logging Configuration
    LOG_DIR: Optional[str] = None  # Log directory (optional, uses platform default if not set)
    LOG_LEVEL: str = "INFO"  # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    # Location & Geofencing Configuration
    GEOFENCE_RADIUS: int = 100  # Geofence radius in meters
    TEMP_LOCATION_CLUSTER_RADIUS: int = 50  # Clustering radius for temporary locations in meters
    TEMP_LOCATION_MIN_USAGE_COUNT: int = 5  # Minimum visits before suggesting location
    REJECTED_LOCATION_COOLDOWN_DAYS: int = 180  # Days before re-suggesting rejected location
    
    # DRX (Doctor Platform) Integration
    DRX_URL: str = "http://localhost:8002"  # DRX base URL
    DRX_CLIENT_ID: Optional[str] = None  # Generated during org onboarding on DRX
    DRX_CLIENT_SECRET: Optional[str] = None  # Generated during org onboarding on DRX
    
    class Config:
        """
        Pydantic configuration.
        env_file tells Pydantic to read from .env file
        """
        env_file = ".env"
        case_sensitive = True  # Environment variable names are case-sensitive


# Create a single instance of settings to be used throughout the app
settings = Settings()
