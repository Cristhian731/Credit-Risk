"""Authentication views.

Only a placeholder login page exists so the navigation link works.
"""
from flask import render_template

from . import bp


# TODO(teammate B): replace with the real login view (GET shows the form, POST
# calls services.authenticate_user) and add register and logout views.
@bp.route("/login")
def login():
    """Placeholder login page."""
    return render_template("auth/login.html")
