"""
Centralized validation utilities for the application.
Contains reusable validators for common fields.
"""

import re
from typing import Optional
from datetime import date, timedelta
from pydantic import field_validator


class ValidationPatterns:
    """Regex patterns for validation"""
    # E.164 international phone format: +[country code][number]
    PHONE = r'^\+[1-9]\d{1,14}$'
    
    # Name: letters, spaces, dots, hyphens, apostrophes
    NAME = r"^[a-zA-Z\s.\-']+$"
    
    # License: alphanumeric, 5-20 characters
    LICENSE = r'^[A-Z0-9]{5,20}$'
    
    # Territory: letters, spaces, commas, hyphens
    TERRITORY = r"^[a-zA-Z\s,\-]+$"
    
    # Time 24-hour format: HH:MM
    TIME_24H = r'^([01]\d|2[0-3]):([0-5]\d)$'
    
    # Time 12-hour format: HH:MM AM/PM
    TIME_12H = r'^(0?[1-9]|1[0-2]):([0-5]\d)\s?(AM|PM|am|pm)$'


class PhoneValidator:
    """Phone number validation"""
    
    @staticmethod
    def validate(v: Optional[str]) -> Optional[str]:
        """
        Validate phone number in E.164 international format.
        User must enter country code with + prefix.
        
        Examples:
            Valid: +919876543210, +14155552671, +442071234567
            Invalid: 9876543210, +91 98765 43210, 123
        """
        if v is None or v == '':
            return None
        
        v = v.strip()
        
        # Check for spaces or dashes in input (not allowed)
        if ' ' in v or '-' in v:
            raise ValueError(
                'Phone number cannot contain spaces or dashes. '
                'Use format: +919876543210'
            )
        
        # Validate E.164 format
        if not re.match(ValidationPatterns.PHONE, v):
            raise ValueError(
                'Phone must be in international format with country code '
                '(e.g., +919876543210, +14155552671). '
                'Include + prefix and country code, 10-15 digits total.'
            )
        
        return v


class NameValidator:
    """Name validation"""
    
    @staticmethod
    def validate(v: Optional[str], min_length: int = 2, max_length: int = 100) -> Optional[str]:
        """
        Validate name fields.
        - Only letters, spaces, dots, hyphens, apostrophes
        - No leading/trailing spaces
        - No multiple consecutive spaces
        """
        if v is None or v == '':
            return None
        
        v = v.strip()
        
        if len(v) < min_length:
            raise ValueError(f'Name must be at least {min_length} characters')
        if len(v) > max_length:
            raise ValueError(f'Name must not exceed {max_length} characters')
        
        # Allow letters, spaces, dots, hyphens, apostrophes
        if not re.match(ValidationPatterns.NAME, v):
            raise ValueError('Name can only contain letters, spaces, dots, hyphens, and apostrophes')
        
        # No multiple consecutive spaces
        if '  ' in v:
            raise ValueError('Name cannot contain multiple consecutive spaces')
        
        return v


class DateValidator:
    """Date validation"""
    
    @staticmethod
    def validate_future_date(v: date, max_years: int = 2) -> date:
        """
        Validate that date is today or in the future.
        Optionally limit how far in the future.
        """
        if v < date.today():
            raise ValueError('Date must be today or in the future')
        
        # Optional: max years in future
        if max_years:
            max_date = date.today() + timedelta(days=365 * max_years)
            if v > max_date:
                raise ValueError(f'Date cannot be more than {max_years} years in the future')
        
        return v
    
    @staticmethod
    def validate_past_date(v: date, min_age: int = 18, max_age: int = 100) -> date:
        """
        Validate that date is in the past.
        Useful for date of birth validation.
        """
        if v >= date.today():
            raise ValueError('Date must be in the past')
        
        age = (date.today() - v).days // 365
        if age < min_age:
            raise ValueError(f'Must be at least {min_age} years old')
        if age > max_age:
            raise ValueError(f'Invalid date (age > {max_age})')
        
        return v


class URLValidator:
    """URL validation"""
    
    @staticmethod
    def validate(v: Optional[str], max_length: int = 500) -> Optional[str]:
        """
        Validate URL fields.
        Must start with http:// or https://
        """
        if v is None or v == '':
            return None
        
        v = v.strip()
        
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        
        if len(v) > max_length:
            raise ValueError(f'URL must not exceed {max_length} characters')
        
        return v


class TextValidator:
    """Text field validation"""
    
    @staticmethod
    def validate(
        v: Optional[str],
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        strip_html: bool = True
    ) -> Optional[str]:
        """
        Validate text fields.
        - Remove leading/trailing whitespace
        - Optional HTML tag removal for security
        - Optional min/max length
        """
        if v is None or v == '':
            return None
        
        v = v.strip()
        
        # Remove HTML tags for security
        if strip_html:
            v = re.sub(r'<[^>]+>', '', v)
        
        if min_length and len(v) < min_length:
            raise ValueError(f'Must be at least {min_length} characters')
        
        if max_length and len(v) > max_length:
            raise ValueError(f'Must not exceed {max_length} characters')
        
        return v if v else None


class LicenseValidator:
    """License number validation"""
    
    @staticmethod
    def validate(v: Optional[str]) -> Optional[str]:
        """
        Validate license number.
        - Alphanumeric only
        - 5-20 characters
        - Uppercase normalization
        """
        if v is None or v == '':
            return None
        
        v = v.strip().upper()
        
        if not re.match(ValidationPatterns.LICENSE, v):
            raise ValueError('License number must be 5-20 alphanumeric characters')
        
        return v


class TerritoryValidator:
    """Territory validation"""
    
    @staticmethod
    def validate(v: Optional[str]) -> Optional[str]:
        """
        Validate territory field.
        - Letters, spaces, commas, hyphens only
        - 2-100 characters
        """
        if v is None or v == '':
            return None
        
        v = v.strip()
        
        if len(v) < 2:
            raise ValueError('Territory must be at least 2 characters')
        if len(v) > 100:
            raise ValueError('Territory must not exceed 100 characters')
        
        if not re.match(ValidationPatterns.TERRITORY, v):
            raise ValueError('Territory can only contain letters, spaces, commas, and hyphens')
        
        return v


class TimeValidator:
    """Time validation"""
    
    @staticmethod
    def validate(v: Optional[str]) -> Optional[str]:
        """
        Validate time format.
        Accepts: HH:MM (24-hour) or HH:MM AM/PM (12-hour)
        """
        if v is None or v == '':
            return None
        
        v = v.strip()
        
        # Try 24-hour format
        time_24h = re.match(ValidationPatterns.TIME_24H, v)
        # Try 12-hour format
        time_12h = re.match(ValidationPatterns.TIME_12H, v)
        
        if not (time_24h or time_12h):
            raise ValueError('Time must be in HH:MM (24-hour) or HH:MM AM/PM format')
        
        return v


class EmailValidator:
    """Email validation"""
    
    @staticmethod
    def normalize(v: str) -> str:
        """
        Normalize email to lowercase and strip whitespace.
        Use with Pydantic's EmailStr for full validation.
        """
        return v.lower().strip()


class ExperienceValidator:
    """Experience years validation"""
    
    @staticmethod
    def validate(v: Optional[float], min_years: float = 0, max_years: float = 70) -> Optional[float]:
        """
        Validate experience years.
        Allows decimals (e.g., 1.5 years).
        """
        if v is None:
            return None
        
        if v < min_years:
            raise ValueError(f'Experience must be at least {min_years} years')
        if v > max_years:
            raise ValueError(f'Experience cannot exceed {max_years} years')
        
        # Round to 1 decimal place
        return round(v, 1)



class PasswordValidator:
    """Password strength validation"""
    
    @staticmethod
    def validate(v: str) -> str:
        """
        Validate password strength.
        Requirements:
        - Minimum 8 characters
        - Maximum 72 characters (bcrypt limit)
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        - At least one special character
        """
        if not v or len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if len(v) > 72:
            raise ValueError('Password must not exceed 72 characters')
        
        # Check for uppercase
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        # Check for lowercase
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        # Check for digit
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        
        # Check for special character
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', v):
            raise ValueError('Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)')
        
        return v
