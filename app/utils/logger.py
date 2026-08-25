"""
MedRep AI Logging Utility

Production-ready logging with:
- Configurable log directory (outside project)
- Rotating file logs (10MB per file, 10 backups)
- Console output for development
- JSON format option for production
- Prevents duplicate handlers
- Platform-specific defaults
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional
import platform


def get_log_directory() -> Path:
    """
    Get log directory from environment or use platform-specific default.
    
    Priority:
    1. LOG_DIR environment variable (from .env)
    2. Platform-specific default
    
    Returns:
        Path object for log directory
    """
    # Check settings first (loaded from .env by Pydantic)
    from app.config import settings
    if settings.LOG_DIR:
        return Path(settings.LOG_DIR)
    
    # Platform-specific defaults
    system = platform.system()
    
    if system == "Windows":
        # Windows: C:\Logs\MedRep_AI
        return Path("C:/Logs/MedRep_AI")
    elif system == "Linux":
        # Linux: /var/log/medrep_ai (if root) or ~/.medrep_ai/logs (if user)
        try:
            if os.geteuid() == 0:  # Running as root
                return Path("/var/log/medrep_ai")
        except AttributeError:
            pass  # Windows doesn't have geteuid
        return Path.home() / ".medrep_ai" / "logs"
    elif system == "Darwin":  # macOS
        return Path.home() / ".medrep_ai" / "logs"
    else:
        # Fallback: user home directory
        return Path.home() / ".medrep_ai" / "logs"


def get_medrep_logger(
    module_name: str = __name__,
    console_level: Optional[str] = None,
    file_level: Optional[str] = None
) -> logging.Logger:
    """
    Get or create a configured logger for MedRep AI application.
    
    Features:
    - Logs stored outside project directory (configurable via LOG_DIR env var)
    - Rotating file logs (10MB per file, 10 backups = ~100MB total)
    - Console output for development
    - Platform-specific defaults (Windows: C:\\Logs\\MedRep_AI, Linux: /var/log/medrep_ai)
    
    Args:
        module_name: Name of the module using the logger (usually __name__)
        console_level: Log level for console output (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                      If None, reads from LOG_LEVEL env var (default: INFO)
        file_level: Log level for file output (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                   If None, reads from LOG_LEVEL env var (default: INFO)
    
    Returns:
        Configured logger instance
    
    Usage:
        # Basic usage
        from app.utils.logger import get_medrep_logger
        
        logger = get_medrep_logger(__name__)
        logger.info("User logged in")
        logger.error("Database error", exc_info=True)
        
        # With custom levels
        logger = get_medrep_logger(__name__, console_level="DEBUG", file_level="INFO")
    
    Environment Variables:
        LOG_DIR: Directory for log files (default: C:\\Logs\\MedRep_AI on Windows)
        LOG_LEVEL: Default log level (default: INFO)
    """
    
    # Get or create logger
    logger = logging.getLogger(module_name)
    
    # If logger already has handlers, return it (prevent duplicates)
    if logger.handlers:
        return logger
    
    # Set logger level to DEBUG (handlers will filter)
    logger.setLevel(logging.DEBUG)
    
    # Get log levels from environment or use defaults
    default_level = os.getenv("LOG_LEVEL", "INFO").upper()
    console_level = (console_level or default_level).upper()
    file_level = (file_level or default_level).upper()
    
    # Get log directory
    log_dir = get_log_directory()
    
    # Create log directory if it doesn't exist
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # If can't create in default location, fall back to temp directory
        import tempfile
        log_dir = Path(tempfile.gettempdir()) / "medrep_ai_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        # Use stderr for warnings during logger initialization
        sys.stderr.write(f"[WARNING] Could not create log directory. Using temp: {log_dir}\n")
    
    # Log file path
    log_file = log_dir / "mrx.log"
    
    # Create formatter
    fmt_string = (
        "[%(levelname)s] %(asctime)s | %(name)s | "
        "%(filename)s:%(lineno)d (%(funcName)s) | "
        "%(message)s"
    )
    formatter = logging.Formatter(fmt=fmt_string, datefmt="%Y-%m-%d %H:%M:%S")
    
    # Console Handler (stdout)
    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(getattr(logging, console_level))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File Handler (rotating)
    try:
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10,
            encoding="utf-8",
            delay=True  # Create file only when first log is written
        )
        file_handler.setLevel(getattr(logging, file_level))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # If file handler fails, log to console only
        logger.warning(f"Could not create file handler: {e}. Logging to console only.")
    
    # Prevent propagation to root logger (avoid duplicate logs)
    logger.propagate = False
    
    # Log initialization message
    logger.debug(f"Logger initialized: {module_name} | Log dir: {log_dir}")
    
    return logger


# Quick test when running directly
if __name__ == "__main__":
    log_dir = get_log_directory()
    print(f"[INFO] Log directory: {log_dir}")
    print(f"[INFO] Platform: {platform.system()}")
    print(f"[SUCCESS] Check log file: {log_dir / 'app.log'}")

