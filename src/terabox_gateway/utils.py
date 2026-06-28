"""Utility functions for TeraBox API Gateway.

This module contains helper functions used across the application
for string manipulation, formatting, and validation.
"""

import logging
from typing import Optional, Union
from urllib.parse import parse_qs, urlparse
import aiohttp

from .config import ALLOWED_HOSTS


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


def get_formatted_size(size_bytes: Union[int, str]) -> str:
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


async def _proxy_request(url: str, params: dict, cookies: dict, req_headers: dict = None) -> dict:
    """Internal helper to make async proxy requests.
    
    Args:
        url: Proxy base URL
        params: Query parameters
        cookies: Cookie dictionary
        req_headers: Optional client headers to forward
        
    Returns:
        dict: Response data with content, status, headers, and content_type
    """
    try:
        from .config import headers as default_headers
        proxy_headers = default_headers.copy()
        if req_headers:
            for k, v in req_headers.items():
                if k.lower() in ["x-admin-key", "authorization"]:
                    proxy_headers[k] = v

        async with aiohttp.ClientSession(cookies=cookies, headers=proxy_headers) as session:
            async with session.get(url, params=params) as response:
                content = await response.read()
                
                # Determine content type
                content_type = response.headers.get("Content-Type", "application/json")
                
                # For non-200 responses, try to parse as JSON error
                if response.status != 200:
                    try:
                        error_data = await response.json()
                        return {
                            "error": error_data.get("error", "Proxy request failed"),
                            "status_code": response.status,
                            "details": error_data
                        }
                    except Exception:
                        return {
                            "error": f"Proxy returned status {response.status}",
                            "status_code": response.status,
                            "details": content.decode("utf-8", errors="ignore")[:500]
                        }
                
                # Return successful response
                return {
                    "content": content,
                    "status": response.status,
                    "headers": dict(response.headers),
                    "content_type": content_type
                }
    
    except Exception as e:
        logging.error(f"Proxy request error: {e}", exc_info=True)
        return {
            "error": str(e),
            "status_code": 500
        }

