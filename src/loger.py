"""Centralized structured logging configuration."""
import logging
import sys
import structlog


def configure_logger(level: str = "INFO") -> None:
    """
    Configure structlog for JSON-formatted output to stdout.

    Call once at application start. After that, anywhere in the codebase:
        log = structlog.get_logger()
        log.info("rates_fetched", currency="USD", count=10)
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),  # human-readable for dev
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
