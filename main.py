import os

# Directly import the Flask application from `api.py`.
# Vercel will look for a module-level `app` or `handler`.
from api import app  # type: ignore


def main() -> None:
    """Run the Flask development server for local testing."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
