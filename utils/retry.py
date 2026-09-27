"""
Retry logic with exponential backoff for API calls.

Provides robust retry handling for:
- Claude API calls (rate limits, transient failures)
- Classification API calls
- Any external service calls

Features:
- Exponential backoff with jitter
- Configurable retry counts and delays
- Specific exception handling
- Structured logging of retry attempts
"""

import time
import random
import logging
from dataclasses import dataclass, field
from typing import Callable, TypeVar, Optional, Type, Tuple, Any
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    # Maximum number of retry attempts
    max_retries: int = 3

    # Initial delay between retries (seconds)
    initial_delay: float = 1.0

    # Maximum delay between retries (seconds)
    max_delay: float = 60.0

    # Exponential backoff multiplier
    backoff_multiplier: float = 2.0

    # Jitter range (0.0-1.0) - randomizes delay to prevent thundering herd
    jitter: float = 0.1

    # Exceptions to retry on (empty = retry on all exceptions)
    retryable_exceptions: Tuple[Type[Exception], ...] = field(
        default_factory=lambda: (
            ConnectionError,
            TimeoutError,
            OSError,
        )
    )

    # Exceptions to never retry on
    non_retryable_exceptions: Tuple[Type[Exception], ...] = field(
        default_factory=lambda: (
            ValueError,
            TypeError,
            KeyError,
        )
    )


# Default configurations for different use cases
CLAUDE_API_CONFIG = RetryConfig(
    max_retries=3,
    initial_delay=1.0,
    max_delay=30.0,
    backoff_multiplier=2.0,
    jitter=0.2,
)

CLASSIFICATION_API_CONFIG = RetryConfig(
    max_retries=2,
    initial_delay=0.5,
    max_delay=10.0,
    backoff_multiplier=2.0,
    jitter=0.1,
)

QUICK_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    initial_delay=0.1,
    max_delay=1.0,
    backoff_multiplier=1.5,
    jitter=0.05,
)


class RetryExhausted(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_exception: Exception,
    ):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception


def calculate_delay(
    attempt: int,
    config: RetryConfig,
) -> float:
    """
    Calculate delay for a retry attempt.

    Uses exponential backoff with jitter.
    """
    # Base delay with exponential backoff
    delay = config.initial_delay * (config.backoff_multiplier ** attempt)

    # Cap at max delay
    delay = min(delay, config.max_delay)

    # Add jitter
    if config.jitter > 0:
        jitter_range = delay * config.jitter
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0, delay)


def should_retry(
    exception: Exception,
    config: RetryConfig,
) -> bool:
    """Determine if an exception should trigger a retry."""
    # Never retry on non-retryable exceptions
    if isinstance(exception, config.non_retryable_exceptions):
        return False

    # If retryable_exceptions is specified, only retry on those
    if config.retryable_exceptions:
        return isinstance(exception, config.retryable_exceptions)

    # Default: retry on all exceptions not in non_retryable
    return True


def retry_with_backoff(
    func: Optional[Callable[..., T]] = None,
    *,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> Callable[..., T]:
    """
    Decorator that retries a function with exponential backoff.

    Args:
        func: The function to wrap (auto-filled by decorator)
        config: Retry configuration (defaults to CLAUDE_API_CONFIG)
        on_retry: Callback called before each retry with (attempt, exception, delay)

    Returns:
        Wrapped function that retries on failure

    Example:
        @retry_with_backoff(config=CLAUDE_API_CONFIG)
        def call_claude_api(prompt: str) -> str:
            return client.messages.create(...)

        # Or with callback:
        @retry_with_backoff(on_retry=lambda a, e, d: logger.warning(f"Retry {a}"))
        def risky_operation():
            ...
    """
    if config is None:
        config = CLAUDE_API_CONFIG

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(config.max_retries + 1):
                try:
                    return fn(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Check if we should retry
                    if not should_retry(e, config):
                        logger.warning(
                            f"Non-retryable exception in {fn.__name__}: {type(e).__name__}: {e}"
                        )
                        raise

                    # Check if we have retries left
                    if attempt >= config.max_retries:
                        logger.error(
                            f"All {config.max_retries} retries exhausted for {fn.__name__}. "
                            f"Last error: {type(e).__name__}: {e}"
                        )
                        raise RetryExhausted(
                            f"Failed after {attempt + 1} attempts",
                            attempts=attempt + 1,
                            last_exception=e,
                        ) from e

                    # Calculate delay
                    delay = calculate_delay(attempt, config)

                    # Log retry
                    logger.info(
                        f"Retry {attempt + 1}/{config.max_retries} for {fn.__name__} "
                        f"after {type(e).__name__}. Waiting {delay:.2f}s..."
                    )

                    # Call retry callback if provided
                    if on_retry:
                        on_retry(attempt + 1, e, delay)

                    # Wait before retry
                    time.sleep(delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")

        return wrapper

    # Handle both @retry_with_backoff and @retry_with_backoff()
    if func is not None:
        return decorator(func)
    return decorator


def retry_operation(
    operation: Callable[..., T],
    *args: Any,
    config: Optional[RetryConfig] = None,
    **kwargs: Any,
) -> T:
    """
    Retry an operation with exponential backoff.

    Non-decorator version for one-off retries.

    Args:
        operation: Function to call
        *args: Positional arguments for operation
        config: Retry configuration
        **kwargs: Keyword arguments for operation

    Returns:
        Result of operation

    Example:
        result = retry_operation(
            api_client.fetch,
            "https://api.example.com/data",
            config=QUICK_RETRY_CONFIG,
        )
    """
    if config is None:
        config = CLAUDE_API_CONFIG

    @retry_with_backoff(config=config)
    def wrapped() -> T:
        return operation(*args, **kwargs)

    return wrapped()


# =============================================================================
# SPECIALIZED RETRY FUNCTIONS FOR COMMON OPERATIONS
# =============================================================================

def retry_claude_api(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator optimized for Claude API calls."""
    return retry_with_backoff(
        func,
        config=CLAUDE_API_CONFIG,
        on_retry=lambda a, e, d: logger.info(f"Claude API retry {a}: {e}"),
    )


def retry_classification(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator optimized for classification API calls."""
    return retry_with_backoff(
        func,
        config=CLASSIFICATION_API_CONFIG,
    )
