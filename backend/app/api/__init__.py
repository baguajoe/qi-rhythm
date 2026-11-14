from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


def register_blueprints(app: Flask) -> None:
    from .activities import bp as activities_bp
    from .auth import bp as auth_bp
    from .backing import bp as backing_bp
    from .calibration import bp as calibration_bp
    from .display import bp as display_bp
    from .rhythms import bp as rhythms_bp
    from .sessions import bp as sessions_bp
    from .teams import bp as teams_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(teams_bp, url_prefix="/api/teams")
    app.register_blueprint(rhythms_bp, url_prefix="/api")
    app.register_blueprint(calibration_bp, url_prefix="/api/calibration")
    app.register_blueprint(sessions_bp, url_prefix="/api")
    app.register_blueprint(display_bp, url_prefix="/api")
    app.register_blueprint(activities_bp, url_prefix="/api/activities")
    app.register_blueprint(backing_bp, url_prefix="/api")

    @app.errorhandler(413)
    def _too_large(err):
        mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return (
            jsonify(
                error=f"That file is too big (the limit is {mb} MB). Try a shorter loop or a "
                "16-bit WAV export."
            ),
            413,
        )

    @app.errorhandler(HTTPException)
    def _http_error(err: HTTPException):
        return jsonify(error=err.description or err.name), err.code
