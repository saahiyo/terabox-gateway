"""TeraBox API Gateway - Main Flask Application.

This module defines the Flask application and all API route handlers.
Flask 3.x is used for native async route support.
Business logic has been separated into dedicated modules:
- config.py: Configuration and constants
- utils.py: Utility functions
- terabox_client.py: TeraBox API client logic
"""

from flask import Flask, request, jsonify, Response, send_from_directory
from datetime import datetime, timezone
import logging
import time

# Import from our modules
from config import (
    headers,
    load_cookies,
    PROXY_BASE_URL,
    PROXY_MODE_RESOLVE,
    PROXY_MODE_PAGE,
    PROXY_MODE_API,
    PROXY_MODE_STREAM,
    PROXY_MODE_SEGMENT,
    PROXY_MODE_THUMBNAIL,
    PROXY_MODE_LOOKUP,
    PROXY_MODE_HEALTH,
)
from utils import is_valid_share_url, _proxy_request
from terabox_client import (
    fetch_download_link,
    fetch_direct_links,
    _normalize_api2_items,
)
from rate_limiter import rate_limit
import cache



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

    app = Flask(__name__, static_folder="swagger", static_url_path="/swagger")
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
except ImportError:
    # No blueprint found; continue with routes defined below
    pass


# =============== API ROUTES ===============





@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()})







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
                "/docs": "Interactive Swagger UI documentation (API playground)",
                "/swagger.json": "OpenAPI 3.0.0 specification (JSON)",
                "/api": "Unified endpoint - file listing with direct download links, and proxy modes",
                "/health": "Health check",
            },
            "contact": "@Saahiyo",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.route("/api", methods=["GET"])
@rate_limit
async def api():
    """Unified API endpoint - handles file information and proxy modes."""
    try:
        start_time = time.time()
        mode = request.args.get("mode")
        url = request.args.get("url")
        
        # ===== PROXY MODE LOGIC =====
        if mode:
            # Validate mode parameter
            valid_modes = [
                PROXY_MODE_RESOLVE,
                PROXY_MODE_PAGE,
                PROXY_MODE_API,
                PROXY_MODE_STREAM,
                PROXY_MODE_SEGMENT,
                PROXY_MODE_THUMBNAIL,
                PROXY_MODE_LOOKUP,
                PROXY_MODE_HEALTH,
            ]
            
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
            elif mode == PROXY_MODE_LOOKUP:
                if "surl" not in params and "fid" not in params:
                    return jsonify({"error": "Missing required parameter: surl or fid"}), 400
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
            elif mode == PROXY_MODE_THUMBNAIL:
                if "fid" not in params:
                    return jsonify({"error": "Missing required parameter: fid"}), 400
            elif mode == PROXY_MODE_HEALTH:
                pass
            
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
            
            # Extract client headers to forward
            req_headers = {}
            for k, v in request.headers.items():
                if k.lower() in ["x-admin-key", "authorization"]:
                    req_headers[k] = v
            
            # Make proxy request
            result = await _proxy_request(PROXY_BASE_URL, params, cookies, req_headers=req_headers)
            
            if "error" in result:
                return jsonify(result), result.get("status_code", 500)
            
            # Return response with appropriate content type, filtering out transport/encoding headers
            excluded_headers = {
                "transfer-encoding",
                "content-encoding",
                "content-length",
                "connection",
                "keep-alive",
                "host",
            }
            response_headers = {
                k: v for k, v in result["headers"].items()
                if k.lower() not in excluded_headers
            }
            return Response(
                result["content"],
                status=result["status"],
                headers=response_headers,
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

        resolve = request.args.get("resolve", "0") in ("1", "true", "True")

        # Check cache first
        cached = cache.get(url, password)
        if cached is not None:
            if resolve:
                resolved_data = await fetch_direct_links(url, password, files=cached)
                if isinstance(resolved_data, dict) and "error" in resolved_data:
                    status_code = 400 if resolved_data.get("requires_password") else 500
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "url": url,
                                "error": resolved_data["error"],
                                "errno": resolved_data.get("errno"),
                                "message": resolved_data.get("message", ""),
                                "requires_password": resolved_data.get("requires_password", False),
                            }
                        ),
                        status_code,
                    )
                formatted_files = await _normalize_api2_items(resolved_data)
            else:
                formatted_files = await _normalize_api2_items(cached)
            
            response_time = format_response_time(time.time() - start_time)
            resp_dict = {
                "status": "success",
                "url": url,
                "files": formatted_files,
                "total_files": len(formatted_files),
                "response_time": response_time,
                "cached": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "used_cookies": getattr(formatted_files, "used_cookies", False),
            }
            if getattr(formatted_files, "fallback_no_cookie", False):
                resp_dict["fallback_no_cookie"] = True
                resp_dict["warning"] = "Cookies were rate-limited or invalid. Resolved anonymously without cookies. Download links may be missing."
            return jsonify(resp_dict)

        link_data = await fetch_download_link(url, password)

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
            cache.put(url, link_data, password)
            if resolve:
                resolved_data = await fetch_direct_links(url, password, files=link_data)
                if isinstance(resolved_data, dict) and "error" in resolved_data:
                    status_code = 400 if resolved_data.get("requires_password") else 500
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "url": url,
                                "error": resolved_data["error"],
                                "errno": resolved_data.get("errno"),
                                "message": resolved_data.get("message", ""),
                                "requires_password": resolved_data.get("requires_password", False),
                            }
                        ),
                        status_code,
                    )
                formatted_files = await _normalize_api2_items(resolved_data)
            else:
                formatted_files = await _normalize_api2_items(link_data)
            response_time = format_response_time(time.time() - start_time)

            resp_dict = {
                "status": "success",
                "url": url,
                "files": formatted_files,
                "total_files": len(formatted_files),
                "response_time": response_time,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "used_cookies": getattr(formatted_files, "used_cookies", False),
            }
            if getattr(formatted_files, "fallback_no_cookie", False):
                resp_dict["fallback_no_cookie"] = True
                resp_dict["warning"] = "Cookies were rate-limited or invalid. Resolved anonymously without cookies. Download links may be missing."

            return jsonify(resp_dict)
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


@app.route("/admin/<path:subpath>", methods=["GET"])
@rate_limit
async def admin_proxy(subpath):
    """Proxy admin requests to the upstream worker."""
    try:
        base_url = PROXY_BASE_URL.rstrip("/")
        upstream_url = f"{base_url}/admin/{subpath}"
        
        # Forward query parameters
        params = dict(request.args)
        
        # Forward cookies
        cookies = {}
        if "Cookie" in request.headers:
            cookie_header = request.headers.get("Cookie")
            for cookie in cookie_header.split(";"):
                cookie = cookie.strip()
                if "=" in cookie:
                    key, value = cookie.split("=", 1)
                    cookies[key.strip()] = value.strip()
        if not cookies:
            cookies = load_cookies()
            
        # Extract forwardable headers
        req_headers = {}
        for k, v in request.headers.items():
            if k.lower() in ["x-admin-key", "authorization"]:
                req_headers[k] = v
                
        # Make proxy request
        result = await _proxy_request(upstream_url, params, cookies, req_headers=req_headers)
        
        if "error" in result:
            return jsonify(result), result.get("status_code", 500)
            
        excluded_headers = {
            "transfer-encoding",
            "content-encoding",
            "content-length",
            "connection",
            "keep-alive",
            "host",
        }
        response_headers = {
            k: v for k, v in result["headers"].items()
            if k.lower() not in excluded_headers
        }
        return Response(
            result["content"],
            status=result["status"],
            headers=response_headers,
            content_type=result["content_type"]
        )
    except Exception as e:
        logging.error(f"Admin proxy error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500



@app.route("/swagger.json", methods=["GET"])
def swagger_spec():
    """Serve the OpenAPI 3.0.0 JSON specification."""
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(os.path.join(base_dir, "swagger"), "swagger.json")



@app.route("/docs", methods=["GET"])
def swagger_ui():
    """Serve the Swagger UI documentation playground."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>TeraBox Gateway API - Swagger UI</title>
      <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
      <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5/favicon-32x32.png" sizes="32x32" />
      <style>
        html { box-sizing: border-box; overflow: -margin-y; }
        *, *:before, *:after { box-sizing: inherit; }
        body { margin: 0; background: #fafafa; }
        .swagger-ui .topbar { display: none; }
      </style>
    </head>
    <body>
      <div id="swagger-ui"></div>
      <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js" charset="UTF-8"></script>
      <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js" charset="UTF-8"></script>
      <script>
        window.onload = () => {
          window.ui = SwaggerUIBundle({
            url: '/swagger.json',
            dom_id: '#swagger-ui',
            presets: [
              SwaggerUIBundle.presets.apis,
              SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout",
            deepLinking: true,
            showExtensions: true,
            showCommonExtensions: true
          });
        };
      </script>
    </body>
    </html>
    """



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)