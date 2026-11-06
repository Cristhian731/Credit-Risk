"""Income and expense routes. Data is read and written through the repository."""
from flask import flash, redirect, render_template, request, url_for

from ..auth.services import get_current_user, login_required
from ..services.repository import list_transactions, save_transaction
from . import bp
from .forms import validate_transaction


@bp.route("/")
@login_required
def index():
    """List the current user's transactions."""
    user = get_current_user()
    return render_template("transactions/index.html", transactions=list_transactions(user.id))


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    """GET: show the form. POST: validate and save an income or expense."""
    if request.method == "GET":
        return render_template("transactions/new.html", form={})

    values, errors = validate_transaction(request.form)
    if errors:
        for message in errors:
            flash(message, "danger")
        return render_template("transactions/new.html", form=request.form), 400

    # INTEGRATION: user_id comes from authenticated user
    values["user_id"] = get_current_user().id
    save_transaction(values)
    flash("Transaction saved.", "success")
    return redirect(url_for("transactions.index"))
