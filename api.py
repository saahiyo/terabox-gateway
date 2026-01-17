from flask import Flask, request, jsonify, Response
import aiohttp
import asyncio
import logging
import os
from urllib.parse import parse_qs, urlparse
from datetime import datetime
from typing import Any, Dict, List, Optional, Union


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


def is_valid_share_url(u: str) -> bool:
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


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
# Optional blueprint registration: if endpoints.bp exists, register it.
try:
    from endpoints import bp as endpoints_bp  # type: ignore

    app.register_blueprint(endpoints_bp)
except Exception:
    # No blueprint found or failed to import; continue with routes defined below
    pass


# You can override cookies via environment variables or a `cookies.json` file.
# - COOKIE_JSON: A JSON string containing cookie key-value pairs (from .env file).
# - TERABOX_COOKIES_JSON: A JSON string containing cookie key-value pairs.
# - TERABOX_COOKIES_FILE: The path to a JSON file with cookies.
#   If not set, the application defaults to loading `cookies.json`.


def load_cookies() -> dict[str, str]:
    """Load cookies from environment variables or a local file.
    
    Supports multiple formats for COOKIE_JSON:
    1. Full JSON object: {"ndus": "token_value", "other": "value"}
    2. Simple string: just the ndus token value (will be auto-wrapped)
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
                logging.info("Loaded cookies from COOKIE_JSON environment variable (simple string format)")
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


headers: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


def find_between(string: str, start: str, end: str) -> Optional[str]:
    """Extract substring between two markers"""
    start_index = string.find(start)
    if start_index == -1:
        return None
    start_index += len(start)
    end_index = string.find(end, start_index)
    if end_index == -1:
        return None
    return string[start_index:end_index]


def extract_thumbnail_dimensions(url: str) -> str:
    """Extract dimensions from thumbnail URL's size parameter"""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    size_param = params.get("size", [""])[0]

    if size_param:
        parts = size_param.replace("c", "").split("_u")
        if len(parts) == 2:
            return f"{parts[0]}x{parts[1]}"
    return "original"


async def get_formatted_size(size_bytes: Union[int, str]) -> str:
    """Convert bytes to human-readable format"""
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


async def fetch_download_link(
    url: str, password: str = ""
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Fetch file information from TeraBox share link"""
    try:
        cookies = load_cookies()
        async with aiohttp.ClientSession(cookies=cookies, headers=headers) as session:
            # Step 1: Get the share page and extract tokens
            logging.info(f"Fetching share page: {url}")
            async with session.get(url) as response1:
                response1.raise_for_status()
                response_data = await response1.text()

                # Extract required tokens
                js_token = find_between(response_data, "fn%28%22", "%22%29")
                log_id = find_between(response_data, "dp-logid=", "&")

                if not js_token or not log_id:
                    logging.error("Failed to extract required tokens")
                    return {
                        "error": "Failed to extract authentication tokens",
                        "errno": -1,
                    }

                request_url = str(response1.url)

                # Extract surl from URL
                if "surl=" in request_url:
                    surl = request_url.split("surl=")[1].split("&")[0]
                elif "/s/" in request_url:
                    surl = request_url.split("/s/")[1].split("?")[0]
                else:
                    logging.error("Could not extract surl from URL")
                    return {"error": "Invalid URL format", "errno": -1}

                logging.info(f"Extracted surl: {surl}, logid: {log_id}")

                # Update headers with the actual referer
                session_headers = headers.copy()
                session_headers["Referer"] = request_url

                params = {
                    "app_id": "250528",
                    "web": "1",
                    "channel": "dubox",
                    "clienttype": "0",
                    "jsToken": js_token,
                    "dplogid": log_id,
                    "page": "1",
                    "num": "20",
                    "order": "time",
                    "desc": "1",
                    "site_referer": request_url,
                    "shorturl": surl,
                    "root": "1",
                }
                if password:
                    params["pwd"] = password

                list_url = "https://www.terabox.app/share/list"
                logging.info(f"Fetching file list from: {list_url}")

                async with session.get(
                    list_url, params=params, headers=session_headers
                ) as response2:
                    response_data2 = await response2.json()

                    errno = response_data2.get("errno", -1)

                    # Handle verification required
                    if errno == 400141:
                        logging.warning("Link requires verification")
                        return {
                            "error": "Verification required",
                            "errno": 400141,
                            "message": "This link requires password or captcha verification",
                            "surl": surl,
                            "requires_password": True,
                        }

                    # Handle other errors
                    if errno != 0:
                        error_msg = response_data2.get("errmsg", "Unknown error")
                        logging.error(f"API error {errno}: {error_msg}")
                        return {"error": error_msg, "errno": errno}

                    # Check if we got the file list
                    if "list" not in response_data2:
                        logging.error("No file list in response")
                        return {"error": "No files found in response", "errno": -1}

                    files = response_data2["list"]
                    logging.info(f"Found {len(files)} items")

                    # Step 3: If it's a directory, fetch its contents
                    if files and files[0].get("isdir") == "1":
                        logging.info("Fetching directory contents")
                        params.update(
                            {
                                "dir": files[0]["path"],
                                "order": "asc",
                                "by": "name",
                                "dplogid": log_id,
                            }
                        )
                        params.pop("desc", None)
                        params.pop("root", None)

                        async with session.get(
                            list_url, params=params, headers=session_headers
                        ) as response3:
                            response_data3 = await response3.json()

                            if "list" not in response_data3:
                                return {
                                    "error": "Failed to fetch directory contents",
                                    "errno": -1,
                                }

                            files = response_data3["list"]
                            logging.info(f"Found {len(files)} files in directory")

                    return files

    except aiohttp.ClientResponseError as e:
        logging.error(f"HTTP error: {e.status} - {e.message}")
        return {"error": f"HTTP error: {e.status}", "errno": -1}
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return {"error": str(e), "errno": -1}


async def format_file_info(file_data: Dict[str, Any]) -> Dict[str, Any]:
    """Format file information for API response"""
    thumbnails = {}
    if "thumbs" in file_data:
        for key, url in file_data["thumbs"].items():
            if url:
                dimensions = extract_thumbnail_dimensions(url)
                thumbnails[dimensions] = url

    return {
        "filename": file_data.get("server_filename", "Unknown"),
        "size": await get_formatted_size(file_data.get("size", 0)),
        "size_bytes": file_data.get("size", 0),
        "download_link": file_data.get("dlink", ""),
        "is_directory": file_data.get("isdir") == "1",
        "thumbnails": thumbnails,
        "path": file_data.get("path", ""),
        "fs_id": file_data.get("fs_id", ""),
    }


async def fetch_direct_links(
    url: str, password: str = ""
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Fetch files with direct download links (alternative method)"""

    try:
        files = await fetch_download_link(url, password)

        if isinstance(files, dict) and "error" in files:
            return files

        # Load cookies for the session (previous code referenced undefined `cookies`)
        session_cookies = load_cookies()

        async with aiohttp.ClientSession(
            cookies=session_cookies,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30, connect=10),
        ) as session:
            results = []
            for item in files or []:
                # Ensure each item is a dict; skip otherwise

                if not isinstance(item, dict):
                    logging.warning(f"Skipping non-dict item in files: {type(item)}")

                    continue

                # Get direct link by following redirect

                dlink = item.get("dlink") or ""

                direct_link = None

                if dlink:
                    try:
                        async with session.head(
                            dlink, allow_redirects=False
                        ) as response:
                            direct_link = response.headers.get("Location")

                    except Exception as e:
                        logging.error(f"Error getting direct link: {e}")

                results.append(
                    {
                        "filename": item.get("server_filename", "Unknown"),
                        "size": await get_formatted_size(item.get("size", 0)),
                        "size_bytes": item.get("size", 0),
                        "link": dlink,
                        "direct_link": direct_link,
                        "thumbnail": (item.get("thumbs") or {}).get("url3", ""),
                    }
                )

            return results

    except Exception as e:
        logging.error(f"Error in fetch_direct_links: {e}")

        return {"error": str(e), "errno": -1}


async def _gather_format_file_info(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Helper to run format_file_info concurrently for a list of file dicts."""
    tasks = [format_file_info(item) for item in files if isinstance(item, dict)]
    if not tasks:
        return []
    results = await asyncio.gather(*tasks)
    return results


async def _normalize_api2_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize items returned by fetch_direct_links to the /api response shape."""
    out: List[Dict[str, Any]] = []
    for item in items or []:
        try:
            if not isinstance(item, dict):
                continue
            filenamestr = item.get("filename") or item.get("server_filename", "Unknown")
            size_h = (
                item.get("size")
                if isinstance(item.get("size"), str)
                else await get_formatted_size(item.get("size", 0))
            )
            size_b = item.get("size_bytes", item.get("size", 0))
            download = (
                item.get("direct_link")
                or item.get("download_link")
                or item.get("link")
                or item.get("dlink")
                or ""
            )
            thumbs: Dict[str, str] = {}
            thumb_single = item.get("thumbnail") or (item.get("thumbs") or {}).get("url3")
            if thumb_single:
                thumbs["original"] = thumb_single
            formatted = {
                "filename": filenamestr,
                "size": size_h,
                "size_bytes": size_b,
                "download_link": download,
                "is_directory": item.get("is_directory", False),
                "thumbnails": thumbs,
                "path": item.get("path", ""),
                "fs_id": item.get("fs_id", ""),
            }
            if item.get("direct_link"):
                formatted["direct_link"] = item["direct_link"]
            out.append(formatted)
        except Exception:
            continue
    return out


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
