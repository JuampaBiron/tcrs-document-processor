import re
from typing import Optional
from pydantic import ValidationError


def validate_request_id(request_id: str) -> bool:
    """Validate TCRS request ID format (12 digits)"""
    pattern = r'^\d{12}$'
    return bool(re.match(pattern, request_id))


def validate_email(email: str) -> bool:
    """Validate email address format"""
    pattern = r'^[^@]+@[^@]+\.[^@]+$'
    return bool(re.match(pattern, email))


def validate_blob_url(url: str) -> bool:
    """Validate Azure Blob Storage URL format"""
    blob_pattern = r'^https://[^/]+\.blob\.core\.windows\.net/.*$'
    return bool(re.match(blob_pattern, url))


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')

    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_length = 255 - len(ext) - 1 if ext else 255
        filename = name[:max_name_length] + ('.' + ext if ext else '')

    return filename


def validate_file_size(file_data: bytes, max_size_mb: int = 50) -> bool:
    """Validate file size is within limits"""
    max_size_bytes = max_size_mb * 1024 * 1024
    return len(file_data) <= max_size_bytes


def sanitize_error_message(error_message: str) -> str:
    """Sanitize error message for API response (remove sensitive info)"""
    # Remove file paths
    error_message = re.sub(r'[A-Za-z]:\\[^\\s]+', '[FILE_PATH]', error_message)
    error_message = re.sub(r'/[^\s]+', '[FILE_PATH]', error_message)

    # Remove URLs (except blob storage)
    error_message = re.sub(r'https?://(?!.*blob\.core\.windows\.net)[^\s]+', '[URL]', error_message)

    # Remove connection strings
    error_message = re.sub(r'AccountKey=[^;]+', 'AccountKey=[REDACTED]', error_message)

    return error_message