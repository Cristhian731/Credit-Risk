"""Example transaction routes backed by sample data until the models exist."""
from flask import render_template

from ..auth.services import login_required
from ..sample_data import SAMPLE_TRANSACTIONS
from . import bp


@bp.route("/")
@login_required
def index():
    """List the user's transactions."""
    return render_template("transactions/index.html", transactions=SAMPLE_TRANSACTIONS)


@bp.route("/new")
@login_required
def new():
    """Show the form to register an income or expense."""
    return render_template("transactions/new.html")
