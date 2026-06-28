"""TeraBox API client module.

This module handles all interactions with the TeraBox API,
including fetching file information, download links, and formatting responses.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qs, urlparse

import aiohttp

from .config import headers, load_cookies
from .utils import find_between, extract_thumbnail_dimensions, get_formatted_size


class FileList(list):
    """Subclass of list to carry additional metadata like fallback_no_cookie."""
    fallback_no_cookie: bool = False
    used_cookies: bool = False


async def fetch_download_link(
    url: str, password: str = ""
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Fetch file information from TeraBox share link using unified proxy API.
    
    This function uses the unified Cloudflare Worker proxy with mode=resolve,
    which automatically handles jsToken extraction and API calls in a single request.
    
    Args:
        url: TeraBox share URL
        password: Optional password for protected links
        
    Returns:
        Union[List[Dict[str, Any]], Dict[str, Any]]: List of files or error dict
    """
    try:
        from .config import PROXY_BASE_URL, PROXY_MODE_RESOLVE
        
        # Extract surl from URL
        parsed_url = urlparse(url)
        if "surl=" in parsed_url.query:
            surl = parse_qs(parsed_url.query)["surl"][0]
        elif "/s/" in parsed_url.path:
            surl = parsed_url.path.split("/s/")[1].split("/")[0].split("?")[0]
        else:
            logging.error("Could not extract surl from URL")
            return {"error": "Invalid URL format", "errno": -1}
        
        # Remove leading "1" if present (TeraBox shortcode format)
        if surl.startswith("1"):
            surl = surl[1:]
        
        # We will attempt with loaded cookies first, and retry without cookies if blocked by verification
        initial_cookies = load_cookies()
        attempts = [initial_cookies]
        # Only add a retry without cookies if we actually have cookies to test with initially
        if initial_cookies:
            attempts.append({})
            
        for idx, cookies_to_send in enumerate(attempts):
            is_last_attempt = (idx == len(attempts) - 1)
            try:
                # Use unified proxy with mode=resolve for automatic token extraction and API call
                async with aiohttp.ClientSession(cookies=cookies_to_send, headers=headers) as session:
                    params = {
                        "mode": PROXY_MODE_RESOLVE,
                        "surl": surl,
                        "raw": "1",  # Get raw upstream response instead of simplified format
                    }
                    if password:
                        params["pwd"] = password
                    
                    logging.info(f"Fetching file list from unified proxy (mode=resolve, attempt={idx+1}): {PROXY_BASE_URL}")
                    
                    async with session.get(PROXY_BASE_URL, params=params) as response:
                        # Handle non-200 responses
                        if response.status != 200:
                            error_text = await response.text()
                            logging.error(f"Proxy returned {response.status}: {error_text}")
                            
                            should_retry = False
                            try:
                                import json
                                err_json = json.loads(error_text)
                                upstream_err = err_json.get("details", {})
                                if isinstance(upstream_err, dict):
                                    upstream_errno = upstream_err.get("errno")
                                    upstream_msg = upstream_err.get("errmsg", "")
                                    if upstream_errno == 4000020 or "need verify" in str(upstream_msg).lower():
                                        if not is_last_attempt:
                                            logging.warning("Upstream returned 'need verify' with cookies. Retrying without cookies.")
                                            should_retry = True
                                        else:
                                            return {
                                                "error": "Verification required",
                                                "errno": 4000020,
                                                "message": "This link requires password or captcha verification",
                                                "surl": surl,
                                                "requires_password": True,
                                            }
                            except Exception as e:
                                logging.debug(f"Failed to parse error response JSON: {e}")
                            
                            if should_retry:
                                continue
                            
                            return {
                                "error": f"Proxy error: {response.status}",
                                "errno": -1,
                                "details": error_text[:200]  # Truncate for logging
                            }
                        
                        response_data = await response.json()
                        
                        # Check for error response from proxy
                        if "error" in response_data:
                            error_msg = response_data.get("error", "Unknown error")
                            logging.error(f"Proxy error: {error_msg}")
                            
                            # Check if this is a token extraction failure (may need cookies)
                            if "jsToken" in error_msg or "cookie" in error_msg.lower():
                                return {
                                    "error": error_msg,
                                    "errno": -1,
                                    "message": "Failed to extract authentication tokens. Cookies may be required for this share.",
                                }
                            
                            return {
                                "error": error_msg,
                                "errno": -1,
                            }
                        
                        # With raw=1, the response format is: {"source": "live", "upstream": {...}}
                        # Extract the actual TeraBox API response from upstream
                        if "upstream" in response_data:
                            api_response = response_data["upstream"]
                            logging.info(f"Proxy response source: {response_data.get('source', 'unknown')}")
                        else:
                            # Fallback for other formats
                            api_response = response_data.get("data", response_data)
                        
                        # Handle TeraBox API errors
                        errno = api_response.get("errno", -1)
                        logging.info(f"Response errno: {errno}")
                        
                        # Handle verification required
                        if errno == 400141 or errno == 4000020:
                            if not is_last_attempt:
                                logging.warning(f"Upstream returned errno {errno} with cookies. Retrying without cookies.")
                                continue
                            
                            logging.warning("Link requires verification")
                            return {
                                "error": "Verification required",
                                "errno": errno,
                                "message": "This link requires password or captcha verification",
                                "surl": surl,
                                "requires_password": True,
                            }
                        
                        # Handle other errors
                        if errno != 0:
                            error_msg = api_response.get("errmsg", "Unknown error")
                            logging.error(f"API error {errno}: {error_msg}")
                            return {"error": error_msg, "errno": errno}
                        
                        # Check if we got the file list
                        if "list" not in api_response:
                            logging.error(f"No file list in response. Response keys: {list(api_response.keys())}")
                            return {"error": "No files found in response", "errno": -1}
                        
                        files = api_response["list"]
                        logging.info(f"Found {len(files)} items")
                        
                        # If it's a directory (only in full API format), fetch its contents
                        if files and files[0].get("isdir") == "1":
                            logging.info("Fetching directory contents")
                            
                            # For directory contents, we need to use the API mode with additional parameters
                            # Extract necessary tokens from the initial response if available
                            js_token = api_response.get("jsToken")
                            log_id = api_response.get("dplogid")
                            
                            if not js_token:
                                logging.warning("No jsToken in response for directory listing, returning folder info only")
                                result_files = FileList(files)
                                result_files.fallback_no_cookie = (idx > 0)
                                result_files.used_cookies = (idx == 0 and bool(cookies_to_send))
                                return result_files
                            
                            # Use mode=api for directory contents with the jsToken
                            from .config import PROXY_MODE_API
                            
                            dir_params = {
                                "mode": PROXY_MODE_API,
                                "jsToken": js_token,
                                "shorturl": surl,
                                "dir": files[0]["path"],
                                "order": "asc",
                                "by": "name",
                            }
                            if log_id:
                                dir_params["dplogid"] = log_id
                            if password:
                                dir_params["pwd"] = password
                            
                            async with session.get(PROXY_BASE_URL, params=dir_params) as dir_response:
                                if dir_response.status != 200:
                                    logging.warning("Failed to fetch directory contents, returning folder info")
                                    result_files = FileList(files)
                                    result_files.fallback_no_cookie = (idx > 0)
                                    result_files.used_cookies = (idx == 0 and bool(cookies_to_send))
                                    return result_files
                                
                                dir_data = await dir_response.json()
                                
                                # Handle wrapped response for directory listing too
                                if "data" in dir_data:
                                    dir_data = dir_data["data"]
                                
                                if "list" in dir_data and dir_data.get("errno") == 0:
                                    files = dir_data["list"]
                                    logging.info(f"Found {len(files)} files in directory")
                                else:
                                    logging.warning("Failed to parse directory contents, returning folder info")
                        
                        result_files = FileList(files)
                        result_files.fallback_no_cookie = (idx > 0)
                        result_files.used_cookies = (idx == 0 and bool(cookies_to_send))
                        return result_files
            except Exception as e:
                logging.error(f"Error on attempt {idx+1}: {e}", exc_info=True)
                if is_last_attempt:
                    return {"error": str(e), "errno": -1}
                    
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return {"error": str(e), "errno": -1}


async def format_file_info(file_data: Dict[str, Any]) -> Dict[str, Any]:
    """Format file information for API response.
    
    Args:
        file_data: Raw file data from TeraBox API
        
    Returns:
        Dict[str, Any]: Formatted file information
    """
    thumbnails = {}
    if "thumbs" in file_data:
        for key, url in file_data["thumbs"].items():
            if url:
                dimensions = extract_thumbnail_dimensions(url)
                thumbnails[dimensions] = url

    return {
        "filename": file_data.get("server_filename", "Unknown"),
        "size": get_formatted_size(file_data.get("size", 0)),
        "size_bytes": file_data.get("size", 0),
        "download_link": file_data.get("dlink", ""),
        "is_directory": file_data.get("isdir") == "1",
        "thumbnails": thumbnails,
        "path": file_data.get("path", ""),
        "fs_id": file_data.get("fs_id", ""),
    }


async def fetch_direct_links(
    url: str, password: str = "", files: Optional[List[Dict[str, Any]]] = None
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Fetch files with direct download links (alternative method).
    
    Args:
        url: TeraBox share URL
        password: Optional password for protected links
        files: Optional list of files already fetched from cache or API
        
    Returns:
        Union[List[Dict[str, Any]], Dict[str, Any]]: List of files with direct links or error dict
    """

    try:
        if files is None:
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
            results = FileList()
            if hasattr(files, "fallback_no_cookie"):
                results.fallback_no_cookie = files.fallback_no_cookie
            if hasattr(files, "used_cookies"):
                results.used_cookies = files.used_cookies
            for item in files or []:
                # Ensure each item is a dict; skip otherwise

                if not isinstance(item, dict):
                    logging.warning(f"Skipping non-dict item in files: {type(item)}")

                    continue

                # Get direct link by following redirect

                dlink = item.get("dlink") or ""
                logging.info(f"Direct link: {dlink}")

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
                        "size": get_formatted_size(item.get("size", 0)),
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
    """Helper to run format_file_info concurrently for a list of file dicts.
    
    Args:
        files: List of file data dictionaries
        
    Returns:
        List[Dict[str, Any]]: List of formatted file information
    """
    tasks = [format_file_info(item) for item in files if isinstance(item, dict)]
    if not tasks:
        return []
    results = await asyncio.gather(*tasks)
    return results


async def _normalize_api2_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize items returned by fetch_direct_links to the /api response shape.
    
    Args:
        items: List of items from fetch_direct_links
        
    Returns:
        List[Dict[str, Any]]: Normalized list of file information
    """
    out = FileList()
    if hasattr(items, "fallback_no_cookie"):
        out.fallback_no_cookie = items.fallback_no_cookie
    if hasattr(items, "used_cookies"):
        out.used_cookies = items.used_cookies
    for item in items or []:
        try:
            if not isinstance(item, dict):
                continue
            filenamestr = item.get("filename") or item.get("server_filename", "Unknown")
            size_h = (
                item.get("size")
                if isinstance(item.get("size"), str)
                else get_formatted_size(item.get("size", 0))
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
