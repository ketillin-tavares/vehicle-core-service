import pytest
from loguru import logger as loguru_logger

from src.infrastructure.observability.logging import (
    StructuredLogger,
    configure_logging,
    get_logger,
)


class TestConfigureLogging:
    """Tests for configure_logging sink setup."""

    def test_configure_logging_replaces_sinks_without_raising(self) -> None:
        """Test that configure_logging removes existing sinks and adds a new stdout sink."""
        # Arrange
        loguru_logger.remove()

        # Act
        configure_logging("DEBUG")

        # Assert
        assert len(loguru_logger._core.handlers) == 1

    def test_configure_logging_defaults_to_info_level(self) -> None:
        """Test that configure_logging uses INFO as the default level when none is provided."""
        # Arrange / Act
        configure_logging()

        # Assert
        handler = next(iter(loguru_logger._core.handlers.values()))
        assert handler.levelno == loguru_logger.level("INFO").no


class TestGetLogger:
    """Tests for the get_logger factory and the StructuredLogger adapter."""

    def test_get_logger_returns_structured_logger_singleton(self) -> None:
        """Test that get_logger always returns the same StructuredLogger instance."""
        # Arrange / Act
        first_call = get_logger()
        second_call = get_logger()

        # Assert
        assert isinstance(first_call, StructuredLogger)
        assert first_call is second_call

    def test_info_logs_event_with_structured_fields(self, capsys: "pytest.CaptureFixture[str]") -> None:  # noqa: F821
        """Test that info() emits the event name and structured kwargs to the configured sink."""
        # Arrange
        configure_logging("INFO")
        logger = get_logger()

        # Act
        logger.info("vehicle_created", vehicle_id="abc-123", status="available")

        # Assert
        captured = capsys.readouterr()
        assert "vehicle_created" in captured.out

    def test_error_logs_event_at_error_level(self, capsys: "pytest.CaptureFixture[str]") -> None:  # noqa: F821
        """Test that error() emits the event name at ERROR level."""
        # Arrange
        configure_logging("DEBUG")
        logger = get_logger()

        # Act
        logger.error("vehicle_creation_failed", reason="invalid_price")

        # Assert
        captured = capsys.readouterr()
        assert "vehicle_creation_failed" in captured.out
        assert "ERROR" in captured.out

    def test_debug_and_warning_log_events(self, capsys: "pytest.CaptureFixture[str]") -> None:  # noqa: F821
        """Test that debug() and warning() emit their respective event names to the sink."""
        # Arrange
        configure_logging("DEBUG")
        logger = get_logger()

        # Act
        logger.debug("debug_event")
        logger.warning("warning_event")

        # Assert
        captured = capsys.readouterr()
        assert "debug_event" in captured.out
        assert "warning_event" in captured.out

    def test_exception_logs_event_with_traceback(self, capsys: "pytest.CaptureFixture[str]") -> None:  # noqa: F821
        """Test that exception() emits the event name including the active exception traceback."""
        # Arrange
        configure_logging("DEBUG")
        logger = get_logger()

        # Act
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception("vehicle_processing_error")

        # Assert
        captured = capsys.readouterr()
        assert "vehicle_processing_error" in captured.out
        assert "ValueError" in captured.out
