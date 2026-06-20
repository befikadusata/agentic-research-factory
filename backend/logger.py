import structlog
import logging
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

def add_request_id(_, __, event_dict):
    event_dict["request_id"] = request_id_var.get()
    return event_dict

def setup_logger():
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        add_request_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if sys.stderr.isatty():
        # Pretty print for development
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # JSON for production
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

setup_logger()
logger = structlog.get_logger()
