"""Routes for the public home page."""
from flask import redirect, render_template, url_for

from ..auth.services import auth_enabled, get_current_user
from . import bp


@bp.route("/")
def index():
    """Landing page; users who are already logged in go to the dashboard."""
    if auth_enabled() and get_current_user() is not None:
        return redirect(url_for("dashboard.index"))
    return render_template("main/index.html")
