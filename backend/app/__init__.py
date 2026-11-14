"""Qi Rhythm backend: Flask application factory."""

import os

from flask import Flask, jsonify
from flask_cors import CORS

from .config import config_by_name
from .extensions import db, jwt, migrate, socketio


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name or os.getenv("APP_CONFIG", "default")])

    from . import models  # noqa: F401  (register models with SQLAlchemy/Alembic)
    from .cli import register_cli

    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    jwt.init_app(app)
    CORS(app, origins=app.config["CORS_ORIGINS"])
    socketio.init_app(
        app,
        cors_allowed_origins=app.config["CORS_ORIGINS"],
        async_mode=app.config["SOCKETIO_ASYNC_MODE"],
    )

    register_cli(app)

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="qi-rhythm-api")

    return app
