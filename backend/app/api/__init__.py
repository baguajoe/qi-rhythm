from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


def register_blueprints(app: Flask) -> None:
    from .auth import bp as auth_bp
    from .teams import bp as teams_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(teams_bp, url_prefix="/api/teams")

    @app.errorhandler(HTTPException)
    def _http_error(err: HTTPException):
        return jsonify(error=err.description or err.name), err.code
