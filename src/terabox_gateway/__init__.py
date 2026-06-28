from .api import app
from .terabox_client import fetch_download_link, fetch_direct_links

__all__ = ["app", "fetch_download_link", "fetch_direct_links"]
