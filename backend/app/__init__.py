"""Qi Rhythm backend: Flask application factory."""

import os

from flask import Flask, jsonify
from flask_cors import CORS

from .config import config_by_name
from .extensions import db, jwt, migrate, socketio


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name or os.getenv("APP_CONFIG", "default")])

    from . import games, models, sockets  # noqa: F401  (models, game modes, socket handlers)
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

    _register_jwt_errors()
    register_cli(app)
    from .api import register_blueprints

    register_blueprints(app)

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="qi-rhythm-api")

    return app


def _register_jwt_errors() -> None:
    """Auth failures use the same {"error": ...} shape and plain language as the rest of the API,
    and always 401, so the dashboard can show "Please sign in again" instead of a generic error."""

    def signed_out(message: str):
        return jsonify(error=message), 401

    jwt.unauthorized_loader(lambda _reason: signed_out("Please sign in."))
    jwt.invalid_token_loader(lambda _reason: signed_out("Please sign in again."))
    jwt.expired_token_loader(
        lambda _header, _payload: signed_out("Your sign-in has expired. Please sign in again.")
    )
    jwt.revoked_token_loader(lambda _header, _payload: signed_out("Please sign in again."))
