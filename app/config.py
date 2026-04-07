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
    
    # Application Configuration
    APP_NAME: str = "MedRepAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Default password for doctors/MRs created by admin
    DEFAULT_USER_PASSWORD: str = "Welcome@123"
    
    class Config:
        """
        Pydantic configuration.
        env_file tells Pydantic to read from .env file
        """
        env_file = ".env"
        case_sensitive = True  # Environment variable names are case-sensitive


# Create a single instance of settings to be used throughout the app
settings = Settings()
