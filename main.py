"""
Beyond Madeira CRM API v2.0
Flask + PostgreSQL + Airtable Sync
"""

import os
from app import create_app

app = create_app()


def create_app_gunicorn():
    """Factory for gunicorn."""
    return create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
