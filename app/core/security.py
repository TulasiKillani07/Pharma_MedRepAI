"""
Security utilities for password hashing and JWT token management.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings
import hashlib
import secrets
import string


# Password hashing context using bcrypt
# This is used to hash passwords before storing and verify them during login
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _truncate_password(password: str) -> bytes:
    """
    Truncate password to 72 bytes for bcrypt compatibility.
    Uses SHA256 hash for passwords longer than 72 bytes to maintain security.
    
    Args:
        password: Plain text password
    
    Returns:
        bytes: Password truncated/hashed to fit bcrypt's 72 byte limit
    """
    password_bytes = password.encode('utf-8')
    
    # If password is longer than 72 bytes, hash it first with SHA256
    # This maintains security while fitting bcrypt's limit
    if len(password_bytes) > 72:
        # Use SHA256 to create a fixed-length hash
        return hashlib.sha256(password_bytes).hexdigest().encode('utf-8')
    
    return password_bytes


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
    
    Note: Bcrypt has a 72 byte limit. Passwords longer than 72 bytes 
    are first hashed with SHA256 to maintain security.
    """
    # Truncate/hash password to fit bcrypt's 72 byte limit
    truncated = _truncate_password(password)
    return pwd_context.hash(truncated)


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
    # Truncate/hash password to fit bcrypt's 72 byte limit (same as hash_password)
    truncated = _truncate_password(plain_password)
    return pwd_context.verify(truncated, hashed_password)


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


def generate_random_password(length: int = 12) -> str:
    """
    Generate a strong random password.
    
    Args:
        length: Password length (default: 12)
    
    Returns:
        str: Random password with uppercase, lowercase, digits, and special characters
    
    Example:
        >>> password = generate_random_password()
        >>> print(password)
        'Kx9#mP2$qL5@'
    
    Password requirements:
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character
    - Minimum length: 12 characters
    """
    if length < 12:
        length = 12  # Enforce minimum length
    
    # Define character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*"
    
    # Ensure at least one character from each set
    password = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    
    # Fill the rest with random characters from all sets
    all_characters = uppercase + lowercase + digits + special
    password += [secrets.choice(all_characters) for _ in range(length - 4)]
    
    # Shuffle to avoid predictable patterns
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)
