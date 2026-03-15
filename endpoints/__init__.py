"""
Blueprint package for auxiliary API endpoints.

This module exposes a Flask Blueprint named `bp`. It is optional and can be
registered by the main application if present:

    from endpoints import bp as endpoints_bp
    app.register_blueprint(endpoints_bp)

Routes are namespaced under the url_prefix "/v1" to avoid conflicts with
the core routes defined in the main application.
"""

from __future__ import annotations

from datetime import datetime, timezone
from flask import Blueprint, jsonify, request

# Public blueprint object imported by the app
bp = Blueprint("endpoints", __name__, url_prefix="/v1")

__all__ = ["bp"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@bp.get("/")
def v1_index():
    """Basic metadata for the v1 namespace."""
    return jsonify(
        {
            "name": "TeraBox API",
            "namespace": "/v1",
            "version": "1.0",
            "status": "operational",
            "endpoints": {
                "/v1": "This metadata",
                "/v1/health": "Health check for v1",
                "/v1/echo": "Echo query parameters and selected headers",
            },
            "timestamp": _now_iso(),
        }
    )


@bp.get("/health")
def v1_health():
    """Lightweight health check endpoint for the v1 blueprint."""
    return jsonify({"status": "healthy", "timestamp": _now_iso()})


@bp.get("/echo")
def v1_echo():
    """Echo back query parameters and selected headers for debugging."""
    headers_whitelist = {
        "User-Agent",
        "X-Forwarded-For",
        "X-Real-IP",
        "CF-Connecting-IP",
        "X-Request-ID",
    }
    echoed_headers = {
        k: v for k, v in request.headers.items() if k in headers_whitelist
    }
    return jsonify(
        {
            "args": request.args.to_dict(flat=True),
            "headers": echoed_headers,
            "timestamp": _now_iso(),
        }
    )
