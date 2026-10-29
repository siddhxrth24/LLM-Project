import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings


def setup_logging() -> logging.Logger:
    """Configure structured logging with console and file handlers."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if not root_logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler
        log_dir = settings.project_root / "data" / "logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_path = log_dir / "semestrack.log"
            file_handler = RotatingFileHandler(
                filename=str(file_path),
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except OSError as e:
            # Fall back to console only if file creation fails (e.g. read-only env)
            console_handler.setLevel(log_level)

    # SemesTrack app logger
    logger = logging.getLogger("semestrack")
    logger.setLevel(log_level)
    return logger


logger = setup_logging()
