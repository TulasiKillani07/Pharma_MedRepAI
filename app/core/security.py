"""
Security utilities for password hashing and JWT token management.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings


# Password hashing context using bcrypt
# This is used to hash passwords before storing and verify them during login
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.
    
    Args:
        password: Plain text password (e.g., "SecurePass123")
    
    Returns:
        str: Hashed password (e.g., "$2b$12$KIXxLV8...")
    
    Example:
        >>> hashed = hash_password("mypassword")
        >>> print(hashed)
        '$2b$12$KIXxLV8...'
    
    Why we hash passwords:
    - Never store plain text passwords in database
    - If database is compromised, passwords are still safe
    - Bcrypt is slow by design (prevents brute force attacks)
    
    Note: Bcrypt has a 72 byte limit. Passwords longer than 72 bytes will be truncated.
    """
    # Bcrypt has a 72 byte limit, truncate if necessary
    if len(password.encode('utf-8')) > 72:
        password = password[:72]
    
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.
    
    Args:
        plain_password: Password entered by user during login
        hashed_password: Hashed password stored in database
    
    Returns:
        bool: True if password matches, False otherwise
    
    Example:
        >>> hashed = hash_password("mypassword")
        >>> verify_password("mypassword", hashed)
        True
        >>> verify_password("wrongpassword", hashed)
        False
    """
    # Truncate password to 72 bytes if necessary (same as hash_password)
    if len(plain_password.encode('utf-8')) > 72:
        plain_password = plain_password[:72]
    
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary containing user information to encode in token
              Example: {"sub": "user_id", "email": "user@example.com", "role": "DOCTOR"}
        expires_delta: Optional custom expiration time
    
    Returns:
        str: Encoded JWT token
    
    Example:
        >>> token = create_access_token({"sub": "123", "email": "doctor@example.com", "role": "DOCTOR"})
        >>> print(token)
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
    
    Token structure:
    - Header: {"alg": "HS256", "typ": "JWT"}
    - Payload: {"sub": "user_id", "email": "...", "role": "...", "exp": timestamp}
    - Signature: Created using SECRET_KEY
    """
    # Create a copy of the data to avoid modifying the original
    to_encode = data.copy()
    
    # Set expiration time
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Default: 60 minutes from now (from config)
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Add expiration to token payload
    to_encode.update({"exp": expire})
    
    # Encode the token using SECRET_KEY and algorithm from config
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT access token.
    
    Args:
        token: JWT token string
    
    Returns:
        Dict containing token payload if valid, None if invalid
    
    Example:
        >>> token = create_access_token({"sub": "123", "email": "doctor@example.com"})
        >>> payload = decode_access_token(token)
        >>> print(payload)
        {'sub': '123', 'email': 'doctor@example.com', 'exp': 1704067200}
    
    Verification checks:
    - Signature is valid (using SECRET_KEY)
    - Token is not expired
    - Token format is correct
    """
    try:
        # Decode the token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        # Token is invalid, expired, or tampered with
        return None
