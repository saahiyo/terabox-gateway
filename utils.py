"""Utility functions for TeraBox API Gateway.

This module contains helper functions used across the application
for string manipulation, formatting, and validation.
"""

import logging
from typing import Optional, Union
from urllib.parse import parse_qs, urlparse

from config import ALLOWED_HOSTS


def is_valid_share_url(u: str) -> bool:
    """Validate if a URL is a valid TeraBox share link.
    
    Args:
        u: URL string to validate
        
    Returns:
        bool: True if valid TeraBox share URL, False otherwise
    """
    try:
        parsed = urlparse(u)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.netloc.lower()
        if host not in ALLOWED_HOSTS:
            return False
        return ("/s/" in parsed.path) or ("surl=" in (parsed.query or ""))
    except Exception:
        return False


def find_between(string: str, start: str, end: str) -> Optional[str]:
    """Extract substring between two markers.
    
    Args:
        string: Source string to search in
        start: Starting marker string
        end: Ending marker string
        
    Returns:
        Optional[str]: Extracted substring or None if not found
    """
    start_index = string.find(start)
    if start_index == -1:
        return None
    start_index += len(start)
    end_index = string.find(end, start_index)
    if end_index == -1:
        return None
    return string[start_index:end_index]


def extract_thumbnail_dimensions(url: str) -> str:
    """Extract dimensions from thumbnail URL's size parameter.
    
    Args:
        url: Thumbnail URL containing size parameter
        
    Returns:
        str: Dimensions in format "WIDTHxHEIGHT" or "original"
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    size_param = params.get("size", [""])[0]

    if size_param:
        parts = size_param.replace("c", "").split("_u")
        if len(parts) == 2:
            return f"{parts[0]}x{parts[1]}"
    return "original"


async def get_formatted_size(size_bytes: Union[int, str]) -> str:
    """Convert bytes to human-readable format.
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        str: Formatted size string (e.g., "1.23 GB", "456.78 MB")
    """
    try:
        size_bytes = int(size_bytes)
        if size_bytes >= 1024 * 1024 * 1024:  # GB
            size = size_bytes / (1024 * 1024 * 1024)
            unit = "GB"
        elif size_bytes >= 1024 * 1024:  # MB
            size = size_bytes / (1024 * 1024)
            unit = "MB"
        elif size_bytes >= 1024:  # KB
            size = size_bytes / 1024
            unit = "KB"
        else:
            size = size_bytes
            unit = "bytes"

        return f"{size:.2f} {unit}"
    except Exception as e:
        logging.error(f"Error formatting size: {e}")
        return "Unknown"
