"""TeraBox API Gateway - Main Flask Application.

This module defines the Flask application and all API route handlers.
Business logic has been separated into dedicated modules:
- config.py: Configuration and constants
- utils.py: Utility functions
- terabox_client.py: TeraBox API client logic
"""

from flask import Flask, request, jsonify, Response
import asyncio
from datetime import datetime
import logging
import time
import aiohttp

# Import from our modules
from config import (
    load_cookies,
    PROXY_BASE_URL,
    PROXY_MODE_RESOLVE,
    PROXY_MODE_PAGE,
    PROXY_MODE_API,
    PROXY_MODE_STREAM,
    PROXY_MODE_SEGMENT,
)
from utils import is_valid_share_url
from terabox_client import (
    fetch_download_link,
    fetch_direct_links,
    _gather_format_file_info,
    _normalize_api2_items,
)


def format_response_time(seconds: float) -> str:
    """Format response time with appropriate unit (s or m).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted string with 's' or 'm' suffix
    """
    if seconds >= 60:
        minutes = round(seconds / 60, 2)
        return f"{minutes}m"
    else:
        return f"{round(seconds, 3)}s"


def create_app() -> Flask:
    """Create and configure the Flask application.

    This factory keeps a top-level `app` available for Vercel (module import)
    while allowing local development with `python api.py`.
    """

    app = Flask(__name__, static_folder="public", static_url_path="/public")

    # Basic CORS for browser clients (no extra dependency)
    @app.after_request
    def add_cors_headers(resp: Response) -> Response:
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return resp

    return app


# Create module-level `app` so Vercel/Gunicorn can import it: `from api import app`
app = create_app()


# Basic CORS for browser clients (no extra dependency)
@app.after_request
def add_cors_headers(resp: Response) -> Response:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return resp


# Optional blueprint registration: if endpoints.bp exists, register it.
try:
    from endpoints import bp as endpoints_bp  # type: ignore

    app.register_blueprint(endpoints_bp)
except Exception:
    # No blueprint found or failed to import; continue with routes defined below
    pass


# =============== API ROUTES ===============


@app.route("/")
def index():
    """API information endpoint"""
    return jsonify(
        {
            "name": "TeraBox API",
            "version": "2.0",
            "status": "operational",
            "endpoints": {
                "/": "API information",
                "/api": "Unified endpoint - file listing and proxy modes (resolve, page, api, stream, segment)",
                "/api2": "Fetch files with direct download links",
                "/help": "Detailed usage instructions",
                "/health": "Health check",
            },
            "contact": "@Saahiyo",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})


async def _proxy_request(url: str, params: dict, cookies: dict) -> dict:
    """Internal helper to make async proxy requests.
    
    Args:
        url: Proxy base URL
        params: Query parameters
        cookies: Cookie dictionary
        
    Returns:
        dict: Response data with content, status, headers, and content_type
    """
    try:
        async with aiohttp.ClientSession(cookies=cookies, headers=headers) as session:
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
                    except:
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




@app.route("/api", methods=["GET"])
def api():
    """Unified API endpoint - handles file information and proxy modes.
    
    Supports two usage patterns:
    1. Legacy mode: /api?url=... (backward compatible file listing)
    2. Proxy modes: /api?mode=... (resolve, page, api, stream, segment)
    
    This is a synchronous wrapper around the async helpers so the app
    can run under standard WSGI servers (and Vercel). Internally we
    call asyncio.run to execute the async logic.
    """
    try:
        start_time = time.time()
        mode = request.args.get("mode")
        url = request.args.get("url")
        
        # ===== PROXY MODE LOGIC =====
        if mode:
            # Validate mode parameter
            valid_modes = [PROXY_MODE_RESOLVE, PROXY_MODE_PAGE, PROXY_MODE_API, 
                          PROXY_MODE_STREAM, PROXY_MODE_SEGMENT]
            
            if mode not in valid_modes:
                return jsonify({
                    "error": "Invalid mode",
                    "allowed": valid_modes,
                    "provided": mode
                }), 400
            
            # Build proxy request parameters
            params = {"mode": mode}
            
            # Add all query parameters except 'mode' to the proxy request
            for key, value in request.args.items():
                if key != "mode":
                    params[key] = value
            
            # Validate required parameters based on mode
            if mode == PROXY_MODE_RESOLVE:
                if "surl" not in params:
                    return jsonify({"error": "Missing required parameter: surl"}), 400
            elif mode == PROXY_MODE_PAGE:
                if "surl" not in params:
                    return jsonify({"error": "Missing required parameter: surl"}), 400
            elif mode == PROXY_MODE_API:
                if "jsToken" not in params or "shorturl" not in params:
                    return jsonify({"error": "Missing required parameters: jsToken and shorturl"}), 400
            elif mode == PROXY_MODE_STREAM:
                if "surl" not in params:
                    return jsonify({"error": "Missing required parameter: surl"}), 400
            elif mode == PROXY_MODE_SEGMENT:
                if "url" not in params:
                    return jsonify({"error": "Missing required parameter: url"}), 400
            
            # Forward cookies from client request if present
            cookies = {}
            if "Cookie" in request.headers:
                # Parse cookie header
                cookie_header = request.headers.get("Cookie")
                for cookie in cookie_header.split(";"):
                    cookie = cookie.strip()
                    if "=" in cookie:
                        key, value = cookie.split("=", 1)
                        cookies[key.strip()] = value.strip()
            
            # If no cookies from client, try loading from config
            if not cookies:
                cookies = load_cookies()
            
            # Make proxy request
            result = asyncio.run(_proxy_request(PROXY_BASE_URL, params, cookies))
            
            if "error" in result:
                return jsonify(result), result.get("status_code", 500)
            
            # Return response with appropriate content type
            return Response(
                result["content"],
                status=result["status"],
                headers=result["headers"],
                content_type=result["content_type"]
            )
        
        # ===== LEGACY FILE LISTING MODE =====
        if not url:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Missing required parameter: url or mode",
                        "examples": {
                            "file_listing": "/api?url=https://teraboxshare.com/s/...",
                            "proxy_resolve": "/api?mode=resolve&surl=abc123",
                            "proxy_stream": "/api?mode=stream&surl=abc123"
                        }
                    }
                ),
                400,
            )
        
        if not is_valid_share_url(url):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Invalid TeraBox share URL",
                        "example": "/api?url=https://teraboxshare.com/s/XXXXXXXX",
                    }
                ),
                400,
            )

        password = request.args.get("pwd", "")
        logging.info(f"API request for URL: {url}")

        # Load cookies to include in response
        cookies = load_cookies()

        # Run async fetch in event loop
        link_data = asyncio.run(fetch_download_link(url, password))

        # Check if error occurred
        if isinstance(link_data, dict) and "error" in link_data:
            status_code = 400 if link_data.get("requires_password") else 500
            return (
                jsonify(
                    {
                        "status": "error",
                        "url": url,
                        "error": link_data["error"],
                        "errno": link_data.get("errno"),
                        "message": link_data.get("message", ""),
                        "requires_password": link_data.get("requires_password", False),
                    }
                ),
                status_code,
            )

        # Format file information
        if link_data:
            formatted_files = asyncio.run(_gather_format_file_info(link_data))
            response_time = format_response_time(time.time() - start_time)

            return jsonify(
                {
                    "status": "success",
                    # "used_cookie": cookies.get("ndus", ""), # Removed for privacy
                    "url": url,
                    "files": formatted_files,
                    "total_files": len(formatted_files),
                    "response_time": response_time,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        else:
            return (
                jsonify({"status": "error", "message": "No files found", "url": url}),
                404,
            )

    except Exception as e:
        logging.error(f"API error: {e}", exc_info=True)
        return (
            jsonify(
                {"status": "error", "message": str(e), "params": dict(request.args)} 
            ),
            500,
        )


@app.route("/api2", methods=["GET"])
def api2():
    """Alternative API endpoint - with direct download links (sync wrapper)."""
    try:
        start_time = time.time()
        url = request.args.get("url")

        if not url:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Missing required parameter: url",
                        "example": "/api2?url=https://teraboxshare.com/s/...",
                    }
                ),
                400,
            )
        if not is_valid_share_url(url):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Invalid TeraBox share URL",
                        "example": "/api2?url=https://teraboxshare.com/s/XXXXXXXX",
                    }
                ),
                400,
            )

        logging.info(f"API2 request for URL: {url}")

        password = request.args.get("pwd", "")

        link_data = asyncio.run(fetch_direct_links(url, password))

        # Check if error occurred
        if isinstance(link_data, dict) and "error" in link_data:
            return (
                jsonify(
                    {
                        "status": "error",
                        "url": url,
                        "error": link_data["error"],
                        "errno": link_data.get("errno"),
                    }
                ),
                500,
            )

        if link_data:
            # Normalize file objects to match /api shape and include direct_link when available
            formatted_files = asyncio.run(_normalize_api2_items(link_data))
            response_time = format_response_time(time.time() - start_time)
            return jsonify(
                {
                    "status": "success",
                    "url": url,
                    "files": formatted_files,
                    "total_files": len(formatted_files),
                    "response_time": response_time,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        else:
            return (
                jsonify({"status": "error", "message": "No files found", "url": url}),
                404,
            )

    except Exception as e:
        logging.error(f"API2 error: {e}", exc_info=True)
        return (
            jsonify({"status": "error", "message": str(e), "url": request.args.get("url", "")} ),
            500,
        )


@app.route("/help", methods=["GET"])
def help_page():
    """Help and documentation endpoint"""
    return jsonify(
        {
            "TeraBox API Documentation": {
                "version": "2.0",
                "description": "Extract file information from TeraBox share links",
                "Endpoints": {
                    "/api": {
                        "method": "GET",
                        "description": "Unified endpoint - file information and proxy modes",
                        "usage_patterns": {
                            "file_listing": {
                                "description": "Traditional file listing (backward compatible)",
                                "parameters": {
                                    "url": "Required - TeraBox share link",
                                    "pwd": "Optional - Password for protected links",
                                },
                                "example": "/api?url=https://teraboxshare.com/s/1ABC...",
                            },
                            "proxy_modes": {
                                "description": "Direct proxy access with multiple modes",
                                "modes": {
                                    "resolve": {
                                        "description": "Auto extract jsToken + fetch share API (recommended)",
                                        "parameters": {"surl": "Required - Short URL ID"},
                                        "example": "/api?mode=resolve&surl=abc123",
                                    },
                                    "page": {
                                        "description": "Proxy raw share HTML page",
                                        "parameters": {"surl": "Required - Short URL ID"},
                                        "example": "/api?mode=page&surl=abc123",
                                    },
                                    "api": {
                                        "description": "Manual share API proxy (when jsToken is known)",
                                        "parameters": {
                                            "jsToken": "Required - JavaScript token",
                                            "shorturl": "Required - Short URL ID",
                                            "root": "Optional - Default: 1",
                                            "dplogid": "Optional - Log ID",
                                        },
                                        "example": "/api?mode=api&jsToken=XYZ&shorturl=abc123",
                                    },
                                    "stream": {
                                        "description": "Fetch and rewrite M3U8 playlist for HLS streaming",
                                        "parameters": {
                                            "surl": "Required - Short URL ID",
                                            "type": "Optional - Stream quality (default: M3U8_AUTO_360)",
                                        },
                                        "example": "/api?mode=stream&surl=abc123&type=M3U8_AUTO_360",
                                    },
                                    "segment": {
                                        "description": "Proxy media segments (.ts, .m4s)",
                                        "parameters": {"url": "Required - Encoded segment URL"},
                                        "example": "/api?mode=segment&url=ENCODED_URL",
                                    },
                                },
                                "notes": [
                                    "Cookies are forwarded from client request if provided",
                                    "Use mode=resolve for most use cases",
                                    "Stream and segment modes enable HLS video playback",
                                ],
                            },
                        },
                    },
                    "/api2": {
                        "method": "GET",
                        "description": "Fetch files with direct download links",
                        "parameters": {
                            "url": "Required - TeraBox share link",
                            "pwd": "Optional - Password for protected links",
                        },
                        "example": "/api2?url=https://teraboxshare.com/s/1ABC...",
                    },
                },
                "Error Codes": {
                    "0": "Success",
                    "-1": "General error",
                    "400141": "Verification required (password/captcha)",
                },
                "Response Format": {
                    "success": {
                        "status": "success",
                        "url": "The requested URL",
                        "files": "Array of file objects",
                        "total_files": "Number of files",
                        "timestamp": "ISO timestamp",
                    },
                    "error": {
                        "status": "error",
                        "message": "Error description",
                        "errno": "Error code",
                    },
                },
                "Notes": [
                    "Cookies must be updated regularly (they expire)",
                    "Links requiring passwords need pwd parameter",
                    "Some links may require captcha verification",
                    "Rate limiting may apply",
                ],
                "Contact": "@Saahiyo",
            }
        }
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)