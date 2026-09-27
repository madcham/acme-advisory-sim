"""
Structured logging for Context Bank simulation.

Provides:
- Consistent log formatting across modules
- Structured data in log messages
- Log level configuration
- Optional file output
"""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union
from pathlib import Path
from dataclasses import dataclass, asdict


# =============================================================================
# LOG RECORD TYPES
# =============================================================================

@dataclass
class ContextBankLogRecord:
    """Structured log record for Context Bank operations."""
    operation: str  # deposit, retrieve, validate, synthesize
    object_id: Optional[str] = None
    success: bool = True
    duration_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class AgentLogRecord:
    """Structured log record for agent operations."""
    agent_id: str
    operation: str  # decision, retrieval, deposit
    scenario_type: Optional[str] = None
    outcome: Optional[str] = None
    context_used: Optional[list] = None
    confidence: Optional[float] = None


@dataclass
class ValidationLogRecord:
    """Structured log record for validation operations."""
    object_id: str
    validation_status: str
    checks_passed: int
    checks_failed: int
    checks_warning: int
    adjusted_confidence: Optional[float] = None


@dataclass
class ChaosLogRecord:
    """Structured log record for chaos events."""
    chaos_type: str
    week: int
    impact_description: str
    affected_objects: Optional[int] = None


# =============================================================================
# CUSTOM FORMATTER
# =============================================================================

class StructuredFormatter(logging.Formatter):
    """
    Formatter that outputs JSON-structured logs.

    Useful for log aggregation and analysis tools.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add structured data if present
        if hasattr(record, "structured_data"):
            log_data["data"] = record.structured_data

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add source location
        log_data["source"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        return json.dumps(log_data)


class ReadableFormatter(logging.Formatter):
    """
    Formatter for human-readable console output.
    """

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        # Format timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Format level with color
        level = record.levelname
        if self.use_colors and level in self.LEVEL_COLORS:
            level = f"{self.LEVEL_COLORS[level]}{level:8}{self.RESET}"
        else:
            level = f"{level:8}"

        # Format message
        message = record.getMessage()

        # Add structured data if present
        if hasattr(record, "structured_data") and record.structured_data:
            data_str = " | " + " ".join(
                f"{k}={v}" for k, v in record.structured_data.items()
            )
            message += data_str

        return f"{timestamp} {level} [{record.name}] {message}"


# =============================================================================
# LOGGER SETUP
# =============================================================================

def setup_logging(
    level: Union[int, str] = logging.INFO,
    log_file: Optional[Path] = None,
    json_format: bool = False,
    use_colors: bool = True,
) -> None:
    """
    Set up logging configuration.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        json_format: Use JSON format for file output
        use_colors: Use colors in console output
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler with readable format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ReadableFormatter(use_colors=use_colors))
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        if json_format:
            file_handler.setFormatter(StructuredFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
            ))
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger
    """
    return logging.getLogger(name)


# =============================================================================
# STRUCTURED LOGGING HELPERS
# =============================================================================

class StructuredLogger:
    """
    Logger wrapper that makes structured logging easy.

    Example:
        logger = StructuredLogger(__name__)
        logger.info("Deposited context", object_id="CTX-001", confidence=0.85)
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _log(
        self,
        level: int,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Log with structured data."""
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "(unknown file)",
            0,
            message,
            (),
            None,
        )
        if kwargs:
            record.structured_data = kwargs
        self._logger.handle(record)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, message, **kwargs)

    def log_context_bank_operation(self, record: ContextBankLogRecord) -> None:
        """Log a context bank operation."""
        level = logging.INFO if record.success else logging.WARNING
        self._log(level, f"ContextBank.{record.operation}", **asdict(record))

    def log_agent_operation(self, record: AgentLogRecord) -> None:
        """Log an agent operation."""
        self._log(logging.INFO, f"Agent.{record.operation}", **asdict(record))

    def log_validation(self, record: ValidationLogRecord) -> None:
        """Log a validation operation."""
        level = logging.INFO if record.checks_failed == 0 else logging.WARNING
        self._log(level, f"Validation", **asdict(record))

    def log_chaos_event(self, record: ChaosLogRecord) -> None:
        """Log a chaos event."""
        self._log(logging.WARNING, f"Chaos.{record.chaos_type}", **asdict(record))


# =============================================================================
# PERFORMANCE LOGGING
# =============================================================================

class OperationTimer:
    """
    Context manager for timing operations.

    Example:
        with OperationTimer("deposit", logger) as timer:
            bank.deposit(obj)
        # Automatically logs duration
    """

    def __init__(
        self,
        operation: str,
        logger: Union[logging.Logger, StructuredLogger],
        **extra_data: Any,
    ):
        self.operation = operation
        self.logger = logger
        self.extra_data = extra_data
        self.start_time: Optional[float] = None
        self.duration_ms: Optional[float] = None

    def __enter__(self) -> "OperationTimer":
        import time
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        import time
        if self.start_time:
            self.duration_ms = (time.perf_counter() - self.start_time) * 1000

        if isinstance(self.logger, StructuredLogger):
            self.logger.info(
                f"Operation completed: {self.operation}",
                duration_ms=self.duration_ms,
                success=exc_type is None,
                **self.extra_data,
            )
        else:
            self.logger.info(
                f"Operation {self.operation} completed in {self.duration_ms:.2f}ms"
            )
