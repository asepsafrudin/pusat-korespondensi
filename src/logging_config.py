import logging
import sys
import os
from logging.handlers import RotatingFileHandler

def setup_logging(name="korespondensi-server"):
    """Setup centralized logging with rotation and console output."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Standard formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (Rotating: 5MB per file, max 5 files)
    file_path = os.path.join(log_dir, f"{name}.log")
    file_handler = RotatingFileHandler(
        file_path, maxBytes=5*1024*1024, backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
