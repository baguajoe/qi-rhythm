"""Production server config (Railway).

Socket.IO needs a single worker with an async (gevent) event loop; live display state is kept in
that worker's memory. Audio analysis is CPU-bound but short (~0.1-0.5 s per take).
"""

import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"
workers = 1
timeout = 60
graceful_timeout = 20
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")


def post_worker_init(worker):  # noqa: ARG001 - gunicorn hook signature
    """Compile librosa/numba code paths before the first real recording arrives."""
    if os.getenv("AUDIO_WARMUP", "1") == "1":
        from app.audio.scoring import warmup

        warmup()
