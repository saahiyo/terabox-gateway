import os
import sys
import argparse
from .api import app

def cli() -> None:
    parser = argparse.ArgumentParser(description="Run the TeraBox Gateway Flask server.")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"), help="Host to bind to")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")), help="Port to bind to")
    parser.add_argument("--debug", action="store_true", default=os.getenv("FLASK_DEBUG", "0") == "1", help="Enable debug mode")
    args = parser.parse_args()
    
    app.run(host=args.host, port=args.port, debug=args.debug)
