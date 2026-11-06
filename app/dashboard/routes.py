"""Example dashboard route backed by sample data until the models exist."""
from flask import render_template

from ..auth.services import login_required
from ..sample_data import SAMPLE_TRANSACTIONS, summarize
from . import bp


@bp.route("/")
@login_required
def index():
    """Show the income, expense and balance summary."""
    return render_template("dashboard/index.html", summary=summarize(SAMPLE_TRANSACTIONS))
