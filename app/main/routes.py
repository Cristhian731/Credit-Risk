"""Routes for the public home page."""
from flask import render_template

from . import bp


@bp.route("/")
def index():
    """Landing page."""
    return render_template("main/index.html")
