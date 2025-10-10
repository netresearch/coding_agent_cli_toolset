"""
Centralized logging configuration for CLI Audit.

Provides structured logging with console and file output, replacing
print/vlog patterns with proper logging framework.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


# Global logger instance
_logger: Optional[logging.Logger] = None


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    verbose: bool = False,
    quiet: bool = False,
    propagate: bool = False,
) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        verbose: Enable verbose (DEBUG) output
        quiet: Suppress console output (file only)
        propagate: Allow log propagation (useful for testing)

    Returns:
        Configured logger instance
    """
    global _logger

    # Determine effective log level
    if verbose:
        effective_level = "DEBUG"
    elif quiet:
        effective_level = "WARNING"
    else:
        effective_level = level.upper()

    # Create logger
    logger = logging.getLogger("cli_audit")
    logger.setLevel(getattr(logging, effective_level))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler (unless quiet)
    if not quiet:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, effective_level))

        # Format with colors for console
        console_formatter = ColoredFormatter(
            "%(levelname_colored)s %(message)s",
            use_colors=sys.stdout.isatty()
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file

        # Format without colors for file
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Control propagation to root logger (disable by default for cleaner output)
    logger.propagate = propagate

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """
    Get the configured logger instance.

    If logging hasn't been set up, initializes with defaults.

    Returns:
        Logger instance
    """
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger


class ColoredFormatter(logging.Formatter):
    """
    Formatter with colored output for different log levels.
    """

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[1;31m', # Bold Red
    }
    RESET = '\033[0m'

    # Emoji/symbols for log levels
    SYMBOLS = {
        'DEBUG': '🔍',
        'INFO': '✓',
        'WARNING': '⚠️',
        'ERROR': '✗',
        'CRITICAL': '🚨',
    }

    def __init__(self, fmt: str, use_colors: bool = True):
        super().__init__(fmt)
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        if self.use_colors:
            # Add colored level name
            levelname = record.levelname
            color = self.COLORS.get(levelname, '')
            symbol = self.SYMBOLS.get(levelname, '')

            record.levelname_colored = f"{color}{symbol} {levelname}{self.RESET}"
        else:
            record.levelname_colored = record.levelname

        return super().format(record)


# Convenience functions for backward compatibility with vlog()
def debug(msg: str, verbose: bool = True):
    """Log debug message (only if verbose)."""
    if verbose:
        get_logger().debug(msg)


def info(msg: str, verbose: bool = True):
    """Log info message."""
    if verbose:
        get_logger().info(msg)


def warning(msg: str, verbose: bool = True):
    """Log warning message."""
    if verbose:
        get_logger().warning(msg)


def error(msg: str, verbose: bool = True):
    """Log error message."""
    if verbose:
        get_logger().error(msg)


def critical(msg: str, verbose: bool = True):
    """Log critical message."""
    if verbose:
        get_logger().critical(msg)
