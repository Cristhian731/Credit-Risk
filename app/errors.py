"""Error pages for 400 (invalid CSRF token), 404 and 500."""
from flask import current_app, render_template, request
from flask_wtf.csrf import CSRFError

from .extensions import db

_FALLBACK_500 = (
    "<!doctype html><title>Server error</title>"
    "<h1>Something went wrong</h1><p>Please try again in a few minutes.</p>"
)


def _render(template, status):
    return render_template(template), status


def register_error_handlers(app):
    """Attach the error handlers to the application."""

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        current_app.logger.warning("CSRF check failed on %s %s: %s", request.method, request.path, error.description)
        return _render("errors/400.html", 400)

    @app.errorhandler(404)
    def not_found(error):
        current_app.logger.info("404 on %s %s", request.method, request.path)
        return _render("errors/404.html", 404)

    @app.errorhandler(500)
    def server_error(error):
        # A failed request can leave the session in a broken state.
        db.session.rollback()
        current_app.logger.error(
            "500 on %s %s", request.method, request.path, exc_info=getattr(error, "original_exception", None)
        )
        try:
            return _render("errors/500.html", 500)
        except Exception:  # the page itself needs the database; never fail while reporting a failure
            current_app.logger.exception("Could not render the 500 page")
            return _FALLBACK_500, 500
