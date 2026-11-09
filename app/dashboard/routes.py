"""Dashboard route: financial summary calculated by the database on every read."""
from flask import render_template

from ..auth.services import get_current_user, login_required
from ..services.repository import count_credit_applications, transaction_totals
from . import bp


@bp.route("/")
@login_required
def index():
    """Show the income, expense and balance summary and the number of evaluations."""
    user = get_current_user()
    return render_template(
        "dashboard/index.html",
        summary=transaction_totals(user.id),
        evaluations=count_credit_applications(user.id),
    )
