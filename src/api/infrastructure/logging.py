"""Structlog configuration for the application.

Configures structlog with colored console output for development
and JSON output for production.
"""

import os
import sys

import structlog


def configure_logging() -> None:
    """Configure structlog with appropriate processors.

    Uses colored console output for development (when FORCE_COLOR is set
    or running in a TTY), otherwise uses JSON output for production.
    """
    # Determine if we should use colored console output
    # FORCE_COLOR=1 enables colors even in non-TTY environments (like Docker)
    force_color = os.environ.get("FORCE_COLOR", "").lower() in ("1", "true", "yes")
    is_tty = sys.stdout.isatty()
    use_colors = force_color or is_tty

    # Common processors for all environments
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if use_colors:
        # Development: colored console output
        processors: list[structlog.types.Processor] = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON output
        processors = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
