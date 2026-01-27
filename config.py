"""Configuration module for TeraBox API Gateway.

This module contains all configuration settings, constants, headers,
and cookie loading logic used throughout the application.
"""

import logging
import os
from typing import Dict


# Logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# Allowed TeraBox domains
ALLOWED_HOSTS: set[str] = {
    "terabox.app",
    "www.terabox.app",
    "teraboxshare.com",
    "www.teraboxshare.com",
    "terabox.com",
    "www.terabox.com",
    "1024terabox.com",
    "www.1024terabox.com",
}


# Unified Cloudflare Worker proxy configuration
PROXY_BASE_URL: str = "https://tbx-proxy.shakir-ansarii075.workers.dev/"
PROXY_MODE_RESOLVE: str = "resolve"  # Recommended: automatic resolution with jsToken extraction
PROXY_MODE_PAGE: str = "page"        # For debugging: returns raw HTML
PROXY_MODE_API: str = "api"          # Manual API access when jsToken is known
PROXY_MODE_STREAM: str = "stream"    # HLS playlist proxy with segment URL rewriting
PROXY_MODE_SEGMENT: str = "segment"  # Media segment (.ts, .m4s) proxy


# Default HTTP headers for requests
headers: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


def load_cookies() -> dict[str, str]:
    """Load cookies from environment variables or a local file.
    
    Supports multiple formats for COOKIE_JSON:
    1. Full JSON object: {"ndus": "token_value", "other": "value"}
    2. Simple string: just the ndus token value (will be auto-wrapped)
    
    Priority order:
    1. COOKIE_JSON environment variable
    2. TERABOX_COOKIES_JSON environment variable
    3. TERABOX_COOKIES_FILE environment variable
    
    Returns:
        dict[str, str]: Dictionary of cookie key-value pairs
    """
    data = None
    
    # First try COOKIE_JSON from .env file
    cookie_json = os.getenv("COOKIE_JSON")
    if cookie_json:
        try:
            import json
            # Try parsing as JSON first
            data = json.loads(cookie_json)
            logging.info("Loaded cookies from COOKIE_JSON environment variable (JSON format)")
        except json.JSONDecodeError:
            # If it's not valid JSON, treat it as a simple ndus token value
            cookie_json = cookie_json.strip()
            if cookie_json:
                data = {"ndus": cookie_json}
        except Exception as e:
            logging.warning(f"Failed to parse COOKIE_JSON: {e}")
    
    # Fall back to TERABOX_COOKIES_JSON environment variable
    if not data:
        raw = os.getenv("TERABOX_COOKIES_JSON")
        if raw:
            try:
                import json
                data = json.loads(raw)
                logging.info("Loaded cookies from TERABOX_COOKIES_JSON environment variable")
            except Exception as e:
                logging.warning(f"Failed to parse TERABOX_COOKIES_JSON: {e}")
    
    # Fall back to TERABOX_COOKIES_FILE environment variable
    if not data:
        file_path = os.getenv("TERABOX_COOKIES_FILE")
        if file_path:
            try:
                import json
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logging.info(f"Loaded cookies from '{file_path}' file")
            except FileNotFoundError:
                # This is not an error if cookies are provided via other means
                pass
            except Exception as e:
                logging.warning(f"Failed to read '{file_path}': {e}")

    if isinstance(data, dict):
        return {k: str(v) for k, v in data.items()}

    logging.warning("Cookies not loaded. API requests will likely fail.")
    return {}
