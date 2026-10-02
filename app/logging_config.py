import logging
import sys

import structlog

from app.config import get_settings

settings = get_settings()

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "authorization",
    "secret",
    "jwt_secret_key",
    "webhook_secret",
}


def filter_sensitive_data(_, __, event_dict):
    """Recursively scrub sensitive keys from log dictionaries."""
    for key in list(event_dict.keys()):
        if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
            event_dict[key] = "[REDACTED]"
        elif isinstance(event_dict[key], dict):
            event_dict[key] = filter_sensitive_data(None, None, event_dict[key])
    return event_dict


def setup_logging():
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        filter_sensitive_data,
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.ENVIRONMENT == "production":
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger("diagpay")
