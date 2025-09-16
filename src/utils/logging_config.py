import logging
import os
import json
from datetime import datetime
from typing import Dict, Any


class ContextualFormatter(logging.Formatter):
    """Custom formatter that includes context information for structured logging"""

    def format(self, record):
        # Create base log entry
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'function': record.funcName,
            'module': record.module,
            'line': record.lineno
        }

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        # Add any custom attributes from the record
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id

        if hasattr(record, 'processing_time_ms'):
            log_entry['processing_time_ms'] = record.processing_time_ms

        if hasattr(record, 'file_size'):
            log_entry['file_size'] = record.file_size

        return json.dumps(log_entry)


def setup_logging() -> None:
    """Configure structured logging for the Azure Function"""

    # Get log level from environment
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Create console handler for Azure Functions
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))

    # Set up structured formatter
    formatter = ContextualFormatter()
    console_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Configure Azure libraries to reduce noise
    logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
    logging.getLogger('azure.storage.blob').setLevel(logging.WARNING)
    logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

    logging.info("Logging configuration initialized", extra={'log_level': log_level})


def get_contextual_logger(name: str, request_id: str = None) -> logging.LoggerAdapter:
    """Get a logger with contextual information"""
    logger = logging.getLogger(name)

    class ContextAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            # Add request_id to all log messages if available
            if self.extra.get('request_id'):
                kwargs['extra'] = kwargs.get('extra', {})
                kwargs['extra']['request_id'] = self.extra['request_id']
            return msg, kwargs

    extra_context = {}
    if request_id:
        extra_context['request_id'] = request_id

    return ContextAdapter(logger, extra_context)


def log_performance(logger: logging.Logger, operation: str,
                   processing_time_ms: int, request_id: str = None,
                   file_size: int = None) -> None:
    """Log performance metrics for operations"""
    extra = {
        'processing_time_ms': processing_time_ms,
        'operation': operation
    }

    if request_id:
        extra['request_id'] = request_id

    if file_size:
        extra['file_size'] = file_size

    logger.info(f"Performance: {operation} completed in {processing_time_ms}ms", extra=extra)


def log_error_with_context(logger: logging.Logger, error: Exception,
                          operation: str, request_id: str = None,
                          additional_context: Dict[str, Any] = None) -> None:
    """Log error with full context information"""
    extra = {
        'operation': operation,
        'error_type': type(error).__name__
    }

    if request_id:
        extra['request_id'] = request_id

    if additional_context:
        extra.update(additional_context)

    logger.error(f"Error in {operation}: {str(error)}", extra=extra, exc_info=True)