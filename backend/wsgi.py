"""Entry point for gunicorn (production) and `python wsgi.py` (local development)."""

import os

from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":
    # Development server only; production runs gunicorn with a gevent worker (see Procfile).
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=True,
        allow_unsafe_werkzeug=True,
    )
