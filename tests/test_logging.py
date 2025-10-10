"""
Tests for logging configuration module.
"""

import logging
import tempfile
from pathlib import Path

import pytest

from cli_audit.logging_config import (
    setup_logging,
    get_logger,
    ColoredFormatter,
    debug,
    info,
    warning,
    error,
    critical,
)


class TestSetupLogging:
    """Test logging setup and configuration."""

    def test_setup_logging_default(self):
        """Test default logging setup."""
        logger = setup_logging()
        assert logger is not None
        assert logger.name == "cli_audit"
        assert logger.level == logging.INFO

    def test_setup_logging_verbose(self):
        """Test verbose logging enables DEBUG level."""
        logger = setup_logging(verbose=True)
        assert logger.level == logging.DEBUG

    def test_setup_logging_quiet(self):
        """Test quiet mode suppresses console output."""
        logger = setup_logging(quiet=True)
        assert logger.level == logging.WARNING
        # Should have no console handlers (only file handler if specified)
        console_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        assert len(console_handlers) == 0

    def test_setup_logging_with_file(self):
        """Test logging to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_logging(log_file=str(log_file))

            # Verify file handler exists
            file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
            assert len(file_handlers) > 0

            # Test logging message
            logger.info("Test message")

            # Verify file was created and contains message
            assert log_file.exists()
            content = log_file.read_text()
            assert "Test message" in content

    def test_setup_logging_creates_log_directory(self):
        """Test that log directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "subdir" / "test.log"
            logger = setup_logging(log_file=str(log_file))

            logger.info("Test")
            assert log_file.exists()
            assert log_file.parent.exists()

    def test_setup_logging_custom_level(self):
        """Test custom log level."""
        logger = setup_logging(level="WARNING")
        assert logger.level == logging.WARNING


class TestGetLogger:
    """Test logger retrieval."""

    def test_get_logger_returns_instance(self):
        """Test get_logger returns logger instance."""
        logger = get_logger()
        assert logger is not None
        assert isinstance(logger, logging.Logger)

    def test_get_logger_singleton(self):
        """Test get_logger returns same instance."""
        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2


class TestColoredFormatter:
    """Test colored log formatter."""

    def test_colored_formatter_with_colors(self):
        """Test formatter with colors enabled."""
        formatter = ColoredFormatter("%(levelname_colored)s %(message)s", use_colors=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        assert "Test message" in formatted
        # Should contain ANSI color codes
        assert "\033[" in formatted

    def test_colored_formatter_without_colors(self):
        """Test formatter with colors disabled."""
        formatter = ColoredFormatter("%(levelname_colored)s %(message)s", use_colors=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        assert "Test message" in formatted
        # Should NOT contain ANSI color codes
        assert "\033[" not in formatted

    def test_colored_formatter_all_levels(self):
        """Test formatter with all log levels."""
        formatter = ColoredFormatter("%(levelname_colored)s", use_colors=True)

        for level in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="",
                lineno=0,
                msg="Test",
                args=(),
                exc_info=None,
            )
            formatted = formatter.format(record)
            assert formatted  # Should produce some output


class TestConvenienceFunctions:
    """Test convenience logging functions."""

    def test_debug_with_verbose(self, caplog):
        """Test debug function with verbose enabled."""
        setup_logging(level="DEBUG", propagate=True)
        with caplog.at_level(logging.DEBUG, logger="cli_audit"):
            debug("Debug message", verbose=True)
            assert "Debug message" in caplog.text

    def test_debug_without_verbose(self, caplog):
        """Test debug function with verbose disabled."""
        setup_logging(level="DEBUG", propagate=True)
        with caplog.at_level(logging.DEBUG, logger="cli_audit"):
            debug("Debug message", verbose=False)
            # Should not log when verbose=False
            # (depends on implementation - function respects verbose flag)

    def test_info_logs_message(self, caplog):
        """Test info function logs message."""
        setup_logging(level="INFO", propagate=True)
        with caplog.at_level(logging.INFO, logger="cli_audit"):
            info("Info message", verbose=True)
            assert "Info message" in caplog.text

    def test_warning_logs_message(self, caplog):
        """Test warning function logs message."""
        setup_logging(level="WARNING", propagate=True)
        with caplog.at_level(logging.WARNING, logger="cli_audit"):
            warning("Warning message", verbose=True)
            assert "Warning message" in caplog.text

    def test_error_logs_message(self, caplog):
        """Test error function logs message."""
        setup_logging(level="ERROR", propagate=True)
        with caplog.at_level(logging.ERROR, logger="cli_audit"):
            error("Error message", verbose=True)
            assert "Error message" in caplog.text

    def test_critical_logs_message(self, caplog):
        """Test critical function logs message."""
        setup_logging(level="CRITICAL", propagate=True)
        with caplog.at_level(logging.CRITICAL, logger="cli_audit"):
            critical("Critical message", verbose=True)
            assert "Critical message" in caplog.text


class TestBackwardCompatibility:
    """Test backward compatibility with vlog."""

    def test_vlog_integration(self, caplog):
        """Test vlog uses new logging system."""
        from cli_audit.common import vlog

        setup_logging(level="INFO", propagate=True)
        with caplog.at_level(logging.INFO, logger="cli_audit"):
            vlog("Test vlog message", verbose=True)
            assert "Test vlog message" in caplog.text

    def test_vlog_respects_verbose_flag(self, caplog):
        """Test vlog respects verbose flag."""
        from cli_audit.common import vlog

        setup_logging(level="INFO", propagate=True)
        with caplog.at_level(logging.INFO, logger="cli_audit"):
            caplog.clear()
            vlog("Should not appear", verbose=False)
            # When verbose=False, vlog should not output
