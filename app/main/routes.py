"""Routes for the public pages: home and resources."""
from flask import render_template

from . import bp


@bp.route("/")
def index():
    """Public landing page. After logging in, each role goes to its own home (see auth.login)."""
    return render_template("main/index.html")


@bp.route("/resources")
def resources():
    """Public list of the project resources (report, repository, Colab, manuals and video)."""
    return render_template("main/resources.html")
