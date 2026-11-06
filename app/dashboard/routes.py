"""Dashboard route: financial summary built from the repository."""
from decimal import Decimal

from flask import render_template

from ..auth.services import get_current_user, login_required
from ..services.repository import list_credit_applications, list_transactions
from . import bp


def summarize(transactions):
    """Return total income, total expense and balance for a list of transactions."""
    income = sum((t["amount"] for t in transactions if t["type"] == "income"), Decimal("0"))
    expense = sum((t["amount"] for t in transactions if t["type"] == "expense"), Decimal("0"))
    return {"income": income, "expense": expense, "balance": income - expense}


@bp.route("/")
@login_required
def index():
    """Show the income, expense and balance summary and the number of evaluations."""
    user = get_current_user()
    return render_template(
        "dashboard/index.html",
        summary=summarize(list_transactions(user.id)),
        evaluations=len(list_credit_applications(user.id)),
    )
