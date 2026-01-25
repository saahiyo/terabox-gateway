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

# Import from our modules
from config import load_cookies
from utils import is_valid_share_url
from terabox_client import (
    fetch_download_link,
    fetch_direct_links,
    _gather_format_file_info,
    _normalize_api2_items,
)


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
                "/api": "Fetch file information from TeraBox link",
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


@app.route("/api", methods=["GET"])
def api():
    """Main API endpoint - fetch file information.

    This is a synchronous wrapper around the async helpers so the app
    can run under standard WSGI servers (and Vercel). Internally we
    call asyncio.run to execute the async logic.
    """
    try:
        url = request.args.get("url")

        if not url:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Missing required parameter: url",
                        "example": "/api?url=https://teraboxshare.com/s/...",
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

            return jsonify(
                {
                    "status": "success",
                    # "used_cookie": cookies.get("ndus", ""), # Removed for privacy
                    "url": url,
                    "files": formatted_files,
                    "total_files": len(formatted_files),
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
                {"status": "error", "message": str(e), "url": request.args.get("url", "")} 
            ),
            500,
        )


@app.route("/api2", methods=["GET"])
def api2():
    """Alternative API endpoint - with direct download links (sync wrapper)."""
    try:
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
            return jsonify(
                {
                    "status": "success",
                    "url": url,
                    "files": formatted_files,
                    "total_files": len(formatted_files),
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
                        "description": "Fetch file information",
                        "parameters": {
                            "url": "Required - TeraBox share link",
                            "pwd": "Optional - Password for protected links",
                        },
                        "example": "/api?url=https://teraboxshare.com/s/1ABC...",
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