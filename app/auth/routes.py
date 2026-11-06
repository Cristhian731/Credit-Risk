"""Authentication views.

The login form lives on the home page (templates/auth/_login_form.html) and
posts to auth.login. These views are placeholders until the real login exists.
"""
from flask import flash, redirect, url_for

from . import bp

NOT_AVAILABLE_MESSAGE = "Login is not available yet."


def _not_available():
    flash(NOT_AVAILABLE_MESSAGE, "info")
    return redirect(url_for("main.index"))


# TODO(teammate B): implement authentication
@bp.route("/login", methods=["GET", "POST"])
def login():
    """POST: log in with the fields email, password and remember."""
    return _not_available()


# TODO(teammate B): implement authentication
@bp.route("/register", methods=["GET", "POST"])
def register():
    """GET: show the registration form. POST: create the account."""
    return _not_available()


# TODO(teammate B): implement authentication
@bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Log the current user out and go back to the home page."""
    return _not_available()
