"""
Logger utility for the Remote MCP Control System.
Provides structured logging with file and console output.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Optional


# Global logger instance
_logger: Optional[logging.Logger] = None


def setup_logger(
    name: str = "RemoteAgent",
    level: str = "INFO",
    log_file: str = "logs/agent.log",
    max_size_mb: int = 10,
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up and configure the logger.
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file
        max_size_mb: Max size of log file before rotation
        backup_count: Number of backup files to keep
        
    Returns:
        Configured logger instance
    """
    global _logger
    
    if _logger is not None:
        return _logger
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(levelname)-8s | %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    _logger = logger
    logger.info(f"Logger initialized: {name}")
    
    return logger


def get_logger() -> logging.Logger:
    """Get the global logger instance."""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


class AuditLogger:
    """
    Audit logger for tracking command executions.
    Maintains a separate audit trail for security purposes.
    """
    
    def __init__(self, audit_file: str = "logs/audit.log"):
        self.audit_file = Path(audit_file)
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.audit_logger = logging.getLogger("Audit")
        self.audit_logger.setLevel(logging.INFO)
        
        # Audit file handler
        handler = RotatingFileHandler(
            str(self.audit_file),
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=10,
            encoding='utf-8'
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.audit_logger.addHandler(handler)
    
    def log_command(
        self,
        user_id: int,
        username: str,
        command: str,
        tool: str,
        result: str,
        success: bool
    ):
        """Log a command execution to the audit trail."""
        status = "SUCCESS" if success else "FAILED"
        self.audit_logger.info(
            f"USER:{user_id} ({username}) | TOOL:{tool} | CMD:{command} | STATUS:{status} | RESULT:{result[:200]}"
        )
    
    def log_auth_attempt(
        self,
        user_id: int,
        username: str,
        success: bool,
        reason: str = ""
    ):
        """Log an authentication attempt."""
        status = "GRANTED" if success else "DENIED"
        self.audit_logger.info(
            f"AUTH:{status} | USER:{user_id} ({username}) | REASON:{reason}"
        )
