import logging
import os
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler

def setup_logging(
    log_dir="src/logs", 
    log_file_name="microservices_tree.log",
    log_level=logging.INFO,
    max_size_mb=5,
    size_backup_count=5,
    time_backup_days=7,
    console_output=True
):
    """Set up logging with both size and time-based rotation.
    
    Args:
        log_dir: Directory to store log files
        log_file_name: Name of the log file
        log_level: Logging level (default: INFO)
        max_size_mb: Maximum log file size in MB
        size_backup_count: Number of backup files to keep for size rotation
        time_backup_days: Number of days to keep logs for time rotation
        console_output: Whether to output logs to console
        
    Returns:
        Logger: The configured root logger
    """
    # Create logs directory
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, log_file_name)
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers if any
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Size-based rotation handler
    size_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=size_backup_count,
    )
    size_handler.setFormatter(formatter)
    root_logger.addHandler(size_handler)
        
    # Console handler (optional)
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    return root_logger