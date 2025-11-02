"""Utilities"""

import structlog
import logging
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure structured logging"""
    
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if log_format == "json":
        # Render JSON without escaping non-ASCII characters so logs contain
        # readable Unicode (e.g. Cyrillic) instead of \uXXXX escapes.
        processors.append(structlog.processors.JSONRenderer(ensure_ascii=False))
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def sanitize_text(text: str, max_length: int = 4096) -> str:
    """Sanitize text input"""
    # Remove control characters except newline and tab
    text = ''.join(char for char in text if char.isprintable() or char in '\n\t')
    # Limit length
    return text[:max_length]


def sanitize_file_path(path: str) -> str:
    """Sanitize file path"""
    # Prevent directory traversal
    path = path.replace('../', '').replace('..\\', '')
    return Path(path).name
