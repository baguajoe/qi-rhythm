from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


def register_blueprints(app: Flask) -> None:
    from .auth import bp as auth_bp
    from .rhythms import bp as rhythms_bp
    from .teams import bp as teams_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(teams_bp, url_prefix="/api/teams")
    app.register_blueprint(rhythms_bp, url_prefix="/api")

    @app.errorhandler(HTTPException)
    def _http_error(err: HTTPException):
        return jsonify(error=err.description or err.name), err.code
